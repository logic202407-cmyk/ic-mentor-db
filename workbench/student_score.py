"""学生向「读研体验参考分」— a student-facing reference score, computed on the fly.

What this is
------------
Four dimensions that describe *what it is like to be a student in the group*, each
built only from publicly verifiable signals already stored in this repository.
Every dimension reports its own basis and sample size so a reader can check the
number rather than trust it.

What this deliberately is NOT
-----------------------------
It is **not** a judgement of a mentor's academic standing, teaching quality,
character, or suitability for any individual. Publication volume, citation counts,
venue tiers and honourific titles are kept **out of the score** precisely because
they measure a scholar's output, not a student's experience. Those figures are
still shown elsewhere in the dossier as context; they simply do not move this
number.

Missing evidence
----------------
A dimension with no public evidence is reported as ``unknown`` with weight 0 and
the remaining weights are renormalised, so the score never silently treats "no
data" as "bad". ``confidence`` states how much of the weight was supported.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RANKED = ROOT / "data" / "processed" / "mentor_ranked.json"

WEIGHTS = {
    "guidance_structure": 30,   # 学生一作占比：是否把第一作者位置让给学生
    "team_capacity": 25,        # 组内学生规模（下限估计）
    "group_activity": 25,       # 近三年产出：组里是否还在正常运转
    "transparency": 20,         # 公开信息是否足以让外部学生核对
}

LABELS = {
    "guidance_structure": "指导结构",
    "team_capacity": "团队承载力",
    "group_activity": "组内活跃度",
    "transparency": "信息公开度",
}

BASIS = {
    "guidance_structure": "按该导师论文中「学生担任第一作者」的比例估计；比例越高，"
                          "越倾向于把一作位置留给学生。数据来自公开论文署名，未逐篇核读全文。",
    "team_capacity": "按论文一作去重推算的组内学生数下限；不等于在读人数，也不含未发论文的学生。",
    "group_activity": "按近三年可核实论文数判断课题组是否仍在正常运转。",
    "transparency": "按个人主页是否公开、研究方向是否公开、是否标注为博导三项计数；"
                    "反映外部学生能否自行核对信息，不代表导师是否愿意沟通。",
}

NOT_MEASURED = [
    "不衡量学术水平、论文数量、期刊档次或引用影响力（这些是学者产出，不是学生体验）",
    "不衡量指导质量、课题组氛围、补助待遇、毕业去向与是否允许实习",
    "不衡量师德与个人品质，也不构成任何报考建议",
    "无公开论文数据者，相关维度记为「无公开证据」并按剩余权重归一，不视为低分",
]


def _load_ranked() -> dict[str, dict]:
    """Map network_key ("学校|姓名") -> ranked row."""
    if not RANKED.exists():
        return {}
    rows = json.loads(RANKED.read_text(encoding="utf-8"))
    return {f"{r['school']}|{r['name_cn']}": r for r in rows}


@lru_cache(maxsize=1)
def ranked_index() -> dict[str, dict]:
    return _load_ranked()


def _band(value: float) -> float:
    return max(0.0, min(1.0, value))


def _dimension(score: float | None, detail: str, sample: int | None = None) -> dict:
    return {
        "score": None if score is None else round(score, 1),
        "detail": detail,
        "sample": sample,
    }


def compute(network_key: str | None) -> dict:
    """Return the student reference score for one mentor, or an explicit 'no data'."""
    row = ranked_index().get(network_key or "")
    if not row:
        return {
            "available": False,
            "reason": "该条目暂无公开的论文署名数据，无法计算参考分。",
            "dimensions": {},
            "score": None,
            "confidence": 0.0,
            "labels": LABELS,
            "weights": WEIGHTS,
            "basis": BASIS,
            "not_measured": NOT_MEASURED,
        }

    papers = int(row.get("n_ic_papers") or 0)
    dims: dict[str, dict] = {}

    # 1. 指导结构 — student first-author ratio
    ratio = row.get("student_led_ratio")
    if papers >= 3 and isinstance(ratio, (int, float)):
        dims["guidance_structure"] = _dimension(
            _band(float(ratio)) * 100,
            f"学生一作占比 {float(ratio) * 100:.0f}%（共 {papers} 篇可核实论文）",
            papers,
        )
    else:
        dims["guidance_structure"] = _dimension(
            None, f"可核实论文不足 3 篇（当前 {papers} 篇），不足以估计署名结构", papers)

    # 2. 团队承载力 — estimated group size (log-saturating)
    students = row.get("n_students_est")
    if isinstance(students, (int, float)) and students > 0:
        import math
        dims["team_capacity"] = _dimension(
            _band(math.log1p(float(students)) / math.log1p(30)) * 100,
            f"按一作去重推算组内学生约 {int(students)} 人（下限估计）",
            int(students),
        )
    else:
        dims["team_capacity"] = _dimension(None, "无法从公开论文推断组内学生规模", 0)

    # 3. 组内活跃度 — recent output
    recent = int(row.get("recent3") or 0)
    dims["group_activity"] = _dimension(
        _band(recent / 6.0) * 100,
        f"近三年可核实论文 {recent} 篇",
        recent,
    )

    # 4. 信息公开度 — three checkable public facts
    signals = [
        ("个人主页公开", bool(row.get("homepage"))),
        ("研究方向公开", bool(row.get("research_keywords"))),
        ("标注为博导", bool(row.get("is_phd_advisor"))),
    ]
    dims["transparency"] = _dimension(
        sum(1 for _, ok in signals if ok) / len(signals) * 100,
        "；".join(f"{name}：{'已公开' if ok else '未公开'}" for name, ok in signals),
        len(signals),
    )

    # Weighted score with renormalisation over the dimensions that have evidence.
    supported = {k: v for k, v in dims.items() if v["score"] is not None}
    total_weight = sum(WEIGHTS[k] for k in supported)
    if not total_weight:
        return {
            "available": False,
            "reason": "该条目暂无可用于计算参考分的公开证据。",
            "dimensions": dims,
            "score": None,
            "confidence": 0.0,
            "labels": LABELS,
            "weights": WEIGHTS,
            "basis": BASIS,
            "not_measured": NOT_MEASURED,
        }
    score = sum(dims[k]["score"] * WEIGHTS[k] for k in supported) / total_weight
    coverage = total_weight / sum(WEIGHTS.values())
    return {
        "available": True,
        "score": round(score, 1),
        # Neutral description of *evidence coverage*, never of the person.
        "evidence_note": evidence_note(coverage),
        "confidence": round(coverage, 2),
        "covered_dimensions": sorted(supported),
        "unknown_dimensions": sorted(set(WEIGHTS) - set(supported)),
        "dimensions": dims,
        "labels": LABELS,
        "weights": WEIGHTS,
        "basis": BASIS,
        "not_measured": NOT_MEASURED,
    }


def evidence_note(coverage: float) -> str:
    """Describe how much of the score's weight had public evidence behind it.

    Phrased about the *data*, not the mentor, so the wording cannot be read as a
    verdict on the person.
    """
    if coverage >= 0.95:
        return "四项公开信号齐备"
    if coverage >= 0.7:
        return "三项公开信号齐备"
    if coverage >= 0.45:
        return "两项公开信号齐备"
    return "公开信号较少，分数仅供参考"
