"""课题组公开信息观察 — group public-information observations.

为什么改成「观察」而不是「参考分」
--------------------------------
本模块原名「读研体验参考分」，会输出一个 0–100 的**综合分**。这个做法有三个
无法回避的问题：

1. 四个维度全部是**公开信息的代理指标**（论文署名、论文数、主页是否有链接），
   它们没有一项能衡量「读研体验」——补助、氛围、指导频次、毕业去向、是否允许
   实习，这些真正决定体验的东西一条都不在公开数据里。
2. 一旦有综合分，读者（尤其是正在选导师的学生）就会**跨导师排序**。而不同人
   可核实论文数从 0 到 300 不等，样本差异被权重掩盖，排序结果不可比。
3. 把缺失当 0 分：没有论文记录时，原实现算出的「组内活跃度」是 0 分，与"缺失
   ≠ 0"的承诺直接矛盾。学生看到 0 会以为"这个组不活跃"。

现在的做法
----------
只输出**分维度的事实与证据**，不输出综合分、不排序、不给等级：

* 每个维度都带：维度名、是否有证据、事实描述、原始数值、样本量、取数依据、
  边界说明。
* 每个维度严格处于三种状态之一：

  ``present``  有公开证据，且数值为 X（X > 0）
  ``absent``   有公开证据，且数值确为 0
  ``unknown``  没有公开证据 —— **绝不显示为 0**

  判据只有一条：这个维度所测的量**是否被测量过**。没测到就是 ``unknown``，
  不是 0，也不是"差"。
* 兼容字段 ``score`` / ``confidence`` / ``weights`` 保留键名但恒为 ``None``，
  以免旧前端读空。它们不参与任何计算，也不得在界面上显示。

维度选择与理由
--------------
``authorship``（署名结构）、``group_size``（历史一作人数，累计）、
``recent_output``（近三年公开论文数）、``transparency``（信息公开度，三项事实
清单）。四者都是"学生自己就能在公开页面上核对"的事实，符合本工具的定位：
把可核实的公开信息摆出来，判断留给读者。

关于「组内学生规模」这个旧维度
------------------------------
改版前它叫「团队承载力」，用 ``log1p(学生数)/log1p(30)`` 把人数直接换算成分数，
等于人为规定「30 人 = 满分」。更麻烦的是名称：``n_students_est`` 是**跨年份累计**
的不同第一作者姓名数（黄如 305 篇论文对应 165 个不同一作姓名），写成「组内学生
规模」会让读者以为「这位老师现在带 165 个学生」。现在它只作为
「历史一作人数（累计）」的事实呈现，明确写出不是在读人数、不是课题组规模，
并注明不可用于横向比较。

刻意不测的
----------
学术水平、论文数量高低、期刊档次、引用影响力（这些是学者产出，不是学生体验）；
指导质量、组内氛围、补助待遇、毕业去向、是否允许实习；师德与个人品质。
本模块不构成任何报考建议。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .homepage_kind import kind_of

ROOT = Path(__file__).resolve().parent.parent
RANKED = ROOT / "data" / "processed" / "mentor_ranked.json"

#: 展示门槛：少于这么多篇可核实论文就不展示「学生一作占比」。
#: 3 篇以下的比例没有解释力（0/2 与 0/200 不是一回事）。
MIN_PAPERS_FOR_AUTHORSHIP = 3

DIMENSIONS = ("authorship", "group_size", "recent_output", "transparency")

LABELS = {
    "authorship": "署名结构",
    "group_size": "历史一作人数（累计）",
    "recent_output": "近三年公开论文",
    "transparency": "信息公开度",
}

#: 每个维度真正在数的东西。名称必须自己说清楚，不能让读者靠猜。
METRICS = {
    "authorship": "学生一作占比（按本库判定规则）",
    "group_size": "不同第一作者姓名数（跨年份累计）",
    "recent_output": "近三年可核实论文数",
    "transparency": "三项可核对事实",
}

BASIS = {
    "authorship": "判定规则（来自论文元数据，未逐篇核读全文）：一篇论文要同时满足三条"
                  "才计为「学生一作」——①该导师本人不是第一作者；②第一作者姓名不在"
                  "该院校教师名单中、也不是本人的其他拼写；③第一作者的署名单位能匹配"
                  "到本库内置的高校名单。分母是该导师「有署名信息」的可核实论文数，"
                  "含导师自己一作的那些。",
    "group_size": "把符合上述「学生一作」规则的论文，按第一作者姓名去重计数。"
                  "**跨年份累计**，不做时间窗截断。",
    "recent_output": "数近三年（含当年）在该导师可核实论文中出现的篇数，只作为"
                     "「可核实产出」的事实记录，不评价高低。",
    "transparency": "三项可自行核对的事实：是否有本人专属主页、是否公开研究方向、"
                    "名录是否标注博导身份。只列事实，不打分。",
}

BOUNDARIES = {
    "authorship": "这条规则实际测的是「一作不是本校教师、且单位能匹配到内置高校名单」，"
                  "并不能确认作者与这位导师的师生关系；名单没覆盖的学校（以及单位写法"
                  "异常、只有拼音缩写的记录）会被漏计，因此比例偏低而不是偏高。"
                  "样本不足 3 篇时不做展示。",
    "group_size": "该数字是公开论文中不同第一作者姓名的**累计去重数，跨年份累加**；"
                  "它既不是在读学生数，也不是课题组规模，且会随论文检索覆盖变化。"
                  "资深教师该值天然更大，**不可用于横向比较**；也不含没有发表论文的学生、"
                  "新入学学生与博士后。",
    "recent_output": "只统计已收录的公开论文记录。数字小可能是因为该组产出少，"
                     "也可能是因为我们的检索没覆盖到；本条不判断活跃与否。",
    "transparency": "「未收录」不等于「未公开」。某院校只公布名录页时，主页一项记为"
                    "「收录到名录页」；名录未写研究方向，只说明我们没取到，不说明导师没有方向。",
}

NOT_MEASURED = [
    "不衡量学术水平、论文数量高低、期刊档次或引用影响力（这些是学者产出，不是学生体验）",
    "不衡量指导质量、课题组氛围、补助待遇、毕业去向与是否允许实习",
    "不衡量师德与个人品质，也不构成任何报考建议",
    "无公开论文数据时，相关维度记为「无公开证据」，不记为 0，也不参与任何排序",
]

STATE_RULES = {
    "present": "有公开证据，且所测量的量大于 0",
    "absent": "有公开证据，且所测量的量确为 0",
    "unknown": "没有公开证据；界面必须显示为「无公开证据」，不得显示为 0",
}

STATE_LABELS = {"present": "有公开证据", "absent": "有证据，记为 0", "unknown": "无公开证据"}

#: 兼容旧前端而保留、但恒为 None 的字段。任何界面都不应展示它们。
DEPRECATED_FIELDS = ("score", "confidence", "weights")


def _load_ranked() -> dict[str, dict]:
    """Map network_key ("学校|姓名") -> ranked row."""
    if not RANKED.exists():
        return {}
    rows = json.loads(RANKED.read_text(encoding="utf-8"))
    return {f"{r['school']}|{r['name_cn']}": r for r in rows}


@lru_cache(maxsize=1)
def ranked_index() -> dict[str, dict]:
    return _load_ranked()


def _dimension(
    key: str,
    state: str,
    *,
    value: float | int | None = None,
    display: str = "",
    sample: int | None = None,
    sample_label: str = "",
    fact: str = "",
    basis: str = "",
    boundary: str = "",
    facts: list[dict] | None = None,
) -> dict:
    """One observation dimension: fact + raw value + sample + basis + boundary."""
    assert state in STATE_RULES, state
    item = {
        "key": key,
        "label": LABELS[key],
        "metric": METRICS[key],
        "state": state,
        "state_label": STATE_LABELS[state],
        # available 是给旧前端与调用方看的布尔量；unknown 时恒为 False。
        "available": state != "unknown",
        "value": value,
        "display": display,
        "sample": sample,
        "sample_label": sample_label,
        "fact": fact,
        "basis": basis or BASIS[key],
        "boundary": boundary or BOUNDARIES[key],
    }
    if facts is not None:
        item["facts"] = facts
    return item


def _unknown(key: str, fact: str, *, sample: int | None = None,
             sample_label: str = "", basis: str = "", boundary: str = "") -> dict:
    return _dimension(key, "unknown", value=None, display="无公开证据", fact=fact,
                      sample=sample, sample_label=sample_label,
                      basis=basis, boundary=boundary)


def _skeleton(reason: str | None = None) -> dict:
    """All four dimensions in the 'unknown' state — used when there is no row."""
    dims = {
        "authorship": _unknown("authorship", "没有可核实的公开论文署名记录，无法观察署名结构。"),
        "group_size": _unknown("group_size", "没有可核实的公开论文记录，无法统计历史一作人数。"),
        "recent_output": _unknown("recent_output", "没有可核实的公开论文记录，无法判断近三年产出。"),
        "transparency": _transparency({}, ""),
    }
    return _envelope(dims, reason=reason or
                     "该条目暂无公开的论文署名与名录字段，四项观察均无公开证据。")


def _transparency(row: dict, homepage: str) -> dict:
    """Three checkable public facts. Deliberately not scored."""
    facts: list[dict] = []

    link = (homepage or row.get("homepage") or "").strip()
    kind = kind_of(link)
    if kind == "personal":
        facts.append({"key": "homepage", "label": "本人专属主页", "state": "present",
                      "value": "收录到本人专属页面", "detail": link})
    elif kind == "roster":
        facts.append({"key": "homepage", "label": "本人专属主页", "state": "absent",
                      "value": "收录到名录页（非本人专属页）",
                      "detail": "该院校只公布名录，链接打开的是本人所在名录页。"})
    else:
        facts.append({"key": "homepage", "label": "本人专属主页", "state": "unknown",
                      "value": "未收录主页链接",
                      "detail": "未收录不等于没有主页；需要自行在院系网站核对。"})

    keywords = [str(item).strip() for item in (row.get("research_keywords") or [])
                if str(item).strip()]
    if keywords:
        facts.append({"key": "research_direction", "label": "研究方向公开",
                      "state": "present",
                      "value": f"名录列出 {len(keywords)} 个研究方向",
                      "detail": "；".join(keywords[:4]) + ("…" if len(keywords) > 4 else "")})
    else:
        facts.append({"key": "research_direction", "label": "研究方向公开",
                      "state": "unknown", "value": "名录未收录研究方向",
                      "detail": "我们没取到关键词，不代表导师没有公开研究方向。"})

    phd = row.get("is_phd_advisor")
    if phd is True:
        facts.append({"key": "phd_advisor", "label": "名录标注博导", "state": "present",
                      "value": "名录标注为博导", "detail": ""})
    elif phd is False:
        facts.append({"key": "phd_advisor", "label": "名录标注博导", "state": "absent",
                      "value": "名录未标注为博导",
                      "detail": "名录字段明确记为否（可能是硕导或名录未写）。"})
    else:
        facts.append({"key": "phd_advisor", "label": "名录标注博导", "state": "unknown",
                      "value": "名录未记录该字段", "detail": "字段缺失，不表示不是博导。"})

    states = [item["state"] for item in facts]
    if "present" in states:
        state = "present"
    elif "unknown" in states:
        state = "unknown"
    else:
        state = "absent"

    measured = [item for item in facts if item["state"] != "unknown"]
    fact = "；".join(f"{item['label']}：{item['value']}" for item in facts)
    return _dimension(
        "transparency", state, value=None,
        display=f"{len(measured)}/{len(facts)} 项已核实" if measured else "无公开证据",
        sample=len(measured), sample_label=f"3 项中 {len(measured)} 项可核实",
        fact=fact, facts=facts)


def _envelope(dims: dict[str, dict], *, reason: str | None) -> dict:
    """Wrap dimensions into the observation view. No composite score exists here."""
    counts = {state: 0 for state in STATE_RULES}
    for dimension in dims.values():
        counts[dimension["state"]] += 1
    available = counts["present"] + counts["absent"] > 0
    return {
        "view": "group_public_observations",
        "title": "课题组公开信息观察",
        "subtitle": "只列公开可核实的事实，不打分、不排名",
        "available": available,
        "reason": None if available else (reason or "四项观察均无公开证据。"),
        "evidence_counts": counts,
        "evidence_summary": _summary_text(counts),
        "order": list(DIMENSIONS),
        "dimensions": dims,
        "labels": LABELS,
        "basis": BASIS,
        "boundaries": BOUNDARIES,
        "state_rules": STATE_RULES,
        "state_labels": STATE_LABELS,
        "not_measured": NOT_MEASURED,
        # 兼容字段：键名保留，值恒为 None，不参与任何计算。
        "score": None,
        "confidence": None,
        "weights": None,
        "deprecated_fields": list(DEPRECATED_FIELDS),
        "deprecated_note": "score / confidence / weights 已废弃，恒为 null；"
                           "本视图不提供综合分与跨导师排序。",
    }


def _summary_text(counts: dict[str, int]) -> str:
    """Neutral count of evidence, never a judgement of the person."""
    total = sum(counts.values())
    present, absent, unknown = counts["present"], counts["absent"], counts["unknown"]
    parts = [f"{total} 项观察中", f"{present} 项有公开证据"]
    if absent:
        parts.append(f"{absent} 项有证据且为 0")
    if unknown:
        parts.append(f"{unknown} 项无公开证据")
    return "，".join(parts) + "。"


def compute(network_key: str | None, *, homepage: str = "") -> dict:
    """Return the public-information observation for one mentor.

    ``homepage`` lets the caller pass the *resolved* homepage the page actually
    links to, so the observation and the header link never disagree.
    """
    row = ranked_index().get(network_key or "")
    if not row:
        return _skeleton()

    papers = int(row.get("n_ic_papers") or 0)
    dims: dict[str, dict] = {}

    # 1. 署名结构 — student first-author ratio (needs a minimum sample).
    ratio = row.get("student_led_ratio")
    if papers < MIN_PAPERS_FOR_AUTHORSHIP:
        dims["authorship"] = _unknown(
            "authorship",
            f"可核实论文只有 {papers} 篇，少于展示门槛 {MIN_PAPERS_FOR_AUTHORSHIP} 篇，"
            "不足以观察署名结构。",
            sample=papers, sample_label=f"{papers} 篇可核实论文")
    elif not isinstance(ratio, (int, float)):
        dims["authorship"] = _unknown(
            "authorship", f"有 {papers} 篇可核实论文，但均无可用署名信息。",
            sample=papers, sample_label=f"{papers} 篇可核实论文")
    else:
        percent = round(float(ratio) * 100, 1)
        state = "present" if percent > 0 else "absent"
        dims["authorship"] = _dimension(
            "authorship", state, value=percent, display=f"{percent}%",
            sample=papers, sample_label=f"{papers} 篇可核实论文",
            fact=f"在 {papers} 篇可核实论文里，有署名信息的论文中 {percent}% 的第一作者"
                 "不是该校教师、且署名单位可匹配到本库内置的高校名单"
                 "（按本库规则计为「学生一作」）。这不是「导师把一作让给学生」的比例。")

    # 2. 历史一作人数（累计）— distinct student-first-author names across all years.
    #    注意：这是一个跨年份累计值，不是某一时点的组内人数，更不是培养资源。
    students = row.get("n_students_est")
    if papers <= 0:
        dims["group_size"] = _unknown(
            "group_size", "没有可核实的公开论文记录，无法统计历史一作人数。",
            sample=0, sample_label="0 篇可核实论文")
    elif not isinstance(students, (int, float)):
        dims["group_size"] = _unknown(
            "group_size", "论文记录缺少第一作者信息，无法统计历史一作人数。",
            sample=papers, sample_label=f"{papers} 篇可核实论文")
    else:
        count = int(students)
        state = "present" if count > 0 else "absent"
        dims["group_size"] = _dimension(
            "group_size", state, value=count,
            display=f"{count} 人（累计，非在读）" if count else "0 人（累计）",
            sample=papers, sample_label=f"{papers} 篇可核实论文",
            fact="该数字为公开论文中不同第一作者姓名的累计去重数，跨年份累加；"
                 "它既不是在读学生数，也不是课题组规模，且会随论文检索覆盖变化。")

    # 3. 近三年公开论文数 — fact only, never a quality judgement.
    recent = row.get("recent3")
    if papers <= 0 or recent is None:
        dims["recent_output"] = _unknown(
            "recent_output",
            "没有可核实的公开论文记录，无法统计近三年产出。" if papers <= 0
            else "该条目缺少发表年份信息，无法统计近三年产出。",
            sample=papers, sample_label=f"{papers} 篇可核实论文")
    else:
        count = int(recent)
        state = "present" if count > 0 else "absent"
        if count:
            fact = f"近三年可核实的公开论文 {count} 篇（仅记录可核实的产出数量，不评价高低）。"
        else:
            fact = (f"已有 {papers} 篇可核实论文记录，但其中没有近三年发表的论文；"
                    "这也可能是我们的检索未覆盖，不代表该组近年没有产出。")
        dims["recent_output"] = _dimension(
            "recent_output", state, value=count, display=f"{count} 篇",
            sample=papers, sample_label=f"{papers} 篇可核实论文", fact=fact)

    # 4. 信息公开度 — three facts, no score.
    dims["transparency"] = _transparency(row, homepage)

    result = _envelope(dims, reason=None)
    result["network_key"] = network_key or ""
    result["sample"] = {
        "papers": papers,
        "papers_with_authors": int(row.get("n_all_papers") or 0),
        "recent3": int(row.get("recent3") or 0) if row.get("recent3") is not None else None,
        "first_author_papers": row.get("first_author"),
        "authorship_threshold": MIN_PAPERS_FOR_AUTHORSHIP,
    }
    return result