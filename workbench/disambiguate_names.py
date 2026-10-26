"""同名导师消歧：证据分级的真值协议、评测与待核清单。

为什么必须重写真值协议（旧协议错在哪）
--------------------------------------
旧实现把 **「两两不同个人主页 URL ⇒ 必为不同人」** 当成绝对真值。这条假设不成立，
至少有三类反例：

1. **一人多页**：一位导师可能同时有院系页、课题组页、旧版页；两两不同 URL 完全可能
   是同一个人。
2. **改版/跳转/复用**：学校会改版、页面会跳转、URL 会被复用，同 URL 也可能不是同一人。
3. **名录页兜底**：只有学院名录、没有逐人详情页的导师，``homepage`` 只能回落到名录页。
   两条记录指向同一名录页，**不代表同一个人**——恰恰相反，同校同名的两个人最容易
   共用一张名录页。

旧协议的直接后果（本机实测，产物见 ``workbench/evaluation/`` 与
``.workbench-data/name-disambiguation/``）：

- 用真值的 690 对里，负例 610 对中有 **566 对是跨校**的。不同学校几乎必然是不同人，
  这类「简单负例」把 AUC 抬到 0.964（仅机构）/ 0.858（仅嵌入），但它衡量的是
  「能不能把两所学校分开」，不是本项目真正要回答的问题。
- 真正有决策难度的只有**同校同名**那一小撮：690 对里只有 124 对同校。
- 正例 80 对全部是同 URL + 同校，但 79/80 的两条记录一级学科不同，其中 64 对来自
  中南大学的「一人在多个学科列表下重复出现」——正例类别被单一学校的录入模式主导。

新协议：证据分级（三类判定）
----------------------------
判定只使用**仓库内已存字段**，且每条都写明依据，可人工复核：

- ``same_person``：**直接公开证据**。两条记录指向**同一个本人专属主页**（不是名录页、
  不是被多人共用的页面），且同机构。
- ``different_person``：**直接冲突证据**。两条记录各有**专属主页且互不相同**，并且
  院系或一级学科冲突；或者（更强的）分属不同机构。
- ``unknown``：证据不足。名录页/共用页、缺主页、同院系且同学科、主页站点归属与院系
  不符等，一律进 ``unknown``，**不进入任何指标计算**，单独报告数量。

「专属主页 vs 名录页」复用 :mod:`workbench.homepage_kind`（来源模块声明的 ``listing``），
再叠加三条同样可复现的判据：

1. 该 URL 被**不同姓名**的记录共用（说明它是列表页）；
2. 该 URL 的来源条目 ``title`` 含「名录/列表/目录/索引」（来源自己承认它是名录）；
3. 该 URL 末段是通用列表文件名（``list.htm`` 等）。

复核集还会用一条**与 URL 判等无关**的独立证据交叉检验「同一个 URL」这个结论：
**站点归属**——若某主页站点 ≥60% 的记录来自另一个院系，而当前记录自称在别的院系，
则这条主页很可能是按姓名匹配接错的，不能当作身份证据（详见 :meth:`PageIndex.unit_mismatch`）。

保守合并
--------
即使判定为 ``same_person``，本模块也**只给出合并建议，不自动合并**（保持项目现状）。
``different_person`` 不会被合并；``unknown`` 一律进人工核验队列。

命令
----
    python -m workbench.disambiguate_names --evaluate      # 新协议指标 + 旧协议对照
    python -m workbench.disambiguate_names --review        # 同校同名待核队列
    python -m workbench.disambiguate_names --gold          # 写程序辅助核验集 gold_pairs.json

产物
----
- ``.workbench-data/name-disambiguation/evaluation.json``           新协议指标
- ``.workbench-data/name-disambiguation/legacy_evaluation.json``    旧协议对照（URL 真值）
- ``.workbench-data/name-disambiguation/comparison.json``           新旧逐项对照
- ``.workbench-data/name-disambiguation/high_risk.json``            高危误合并候选
- ``.workbench-data/name-disambiguation/review.json``               同校同名队列（界面消费）
- ``workbench/evaluation/gold_pairs.json``                          独立复核集（入库）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
import pathlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import catalog, homepage_kind, public_research as research  # noqa: E402
from .search import MODEL_NAME, _embedder, keyword_score  # noqa: E402

OUT_DIR = Path(".workbench-data/name-disambiguation")
EVAL_DIR = Path("workbench/evaluation")
MAX_TEXT_CHARS = 900

# ── 证据分级 ────────────────────────────────────────────────────────────
SAME = "same_person"
DIFFERENT = "different_person"
UNKNOWN = "unknown"
LABELS = (SAME, DIFFERENT, UNKNOWN)

PAGE_PERSONAL = "personal"
PAGE_ROSTER = "roster"
PAGE_NONE = "none"

#: 来源 ``title`` 里出现这些词，说明来源自己声明这是名录/列表页。
LISTING_TITLE_MARKERS = ("名录", "列表", "目录", "索引")
#: 末段是这些通用文件名时，URL 不可能是某个人的专属页。
GENERIC_LIST_FILES = frozenset({
    "list.htm", "list.html", "list.shtml", "more.htm", "default.htm",
})
#: 履历里的「学科归属」套话，与「这个人是谁」无关，编码时要去掉。
PLACEHOLDER_MARKERS = (
    "学科归属按公开研究关键词",
    "学科归属由公开研究关键词推断",
    "不代替所在机构当年的招生专业认定",
    "招生专业以所在机构当年目录为准",
)
#: 站点归属判据：某站点 ≥ 该比例的记录来自同一个院系，则认为该站点属于那个院系。
HOST_OWNER_MIN_SHARE = 0.60
HOST_OWNER_MIN_RECORDS = 5

UNKNOWN_NEEDS = {
    "missing_url": "至少一条记录没有 homepage，无法定位到具体的人",
    "listing_page": "homepage 是名录/列表页，不能作为身份证据",
    "missing_url+listing_page": "缺主页，且另一条也只是名录页",
    "same_unit_no_conflict": "两页不同但院系与一级学科都相同，缺少区分两人的直接证据",
    "same_url_cross_institution": "同一 URL 出现在不同机构，需确认是否为页面复用",
}


def _as_text(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "title", "claim", "summary"):
            if value.get(key):
                return str(value[key])
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(v) for v in value)
    return str(value)


def canonical_home(url: str) -> str:
    """把主页 URL 归一化：去协议、去 www、去末尾斜杠与锚点，用于判等。"""
    u = (url or "").strip().lower()
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")


def identity_home(url: str) -> str:
    """判「是不是**同一个页面**」用的归一化：保留查询串。

    为什么必须和 :func:`canonical_home` 分开
    ----------------------------------------
    ``canonical_home`` 会丢掉整个查询串。这用于「按标题/文件名识别名录页」没问题，
    但当查询串本身就是页面标识时——``jiaoshi.php?aid=100``、
    ``teacherBasic/preview?teacherId=31448``、``_redirect?articleId=464818`` 这类
    CMS——把两条不同的个人页压成同一个 URL，就会让 :func:`pair_label` 得出
    「同一个专属主页 ⇒ 同一个人」，也就是**仅凭姓名相同 + 同一站点模板就把两个
    不同的人合并**。

    这不是理论风险：全库实测 **473 条记录、471 个互不相同的个人页**，只因查询串不同
    就被 ``canonical_home`` 压成 **11 个 URL**（中国林科院 111 页、南大电子 101 页、
    中科大 dslx 72 页、同济 62 页、上海交大化学化工学院 58 页、华东师大 48 页 …）。
    当前同名组里恰好没有落在这些 URL 上的两人组合，所以本次改动不改变任何标签；
    但判等口径本身不成立，一旦出现同名就会直接合并两个人。

    所以身份判等保留查询串，只抹掉协议、www、锚点与末尾斜杠这些装饰性差异。
    """
    u = (url or "").strip().lower()
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].replace("/?", "?")
    return u.rstrip("/")


def host_of(url: str) -> str:
    """取 URL 的主机名。"""
    u = (url or "").strip().lower()
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u)
    return u.split("/")[0].split("?")[0]


def _unit_core(name: str) -> str:
    """院系名归一化：去掉括号补充说明，取第一个层级。

    ``物理与天文学院（含李政道研究所）`` → ``物理与天文学院``；
    ``集成电路学院（信息与电子工程学院）· 芯片设计与EDA研究所`` → ``集成电路学院``。
    """
    text = (name or "").strip()
    if not text:
        return ""
    text = re.sub(r"[（(].*?[)）]", "", text)
    for sep in ("·", "／", "/", "、", "，", ","):
        if sep in text:
            text = text.split(sep)[0]
    return text.strip()


def _clean_bio(text: str) -> str:
    """去掉履历里的「学科归属」套话。

    这些句子是采集管线自己合成的口径说明，不含个人身份信息，却会让**任意两条同校
    记录**在嵌入空间里靠得很近——这是旧协议下假阳性的来源之一。
    """
    if not text:
        return ""
    parts = re.split(r"(?<=[。；])", text)
    kept = [p for p in parts if not any(m in p for m in PLACEHOLDER_MARKERS)]
    return "".join(kept).strip()


class PageIndex:
    """判断 ``homepage`` 是本人专属页还是名录/列表页，并给出站点归属统计。

    所有判据都来自目录记录本身（来源声明、来源标题、跨姓名共用、站点归属），
    不联网、不依赖人工清单，因此可复现。
    """

    def __init__(self, profiles: list[dict]):
        self.roster_declared = homepage_kind.roster_urls()
        names_by_url: dict[str, set[str]] = defaultdict(set)
        self.titles: dict[str, set[str]] = defaultdict(set)
        self.host_units: dict[str, Counter] = defaultdict(Counter)
        for p in profiles:
            url = (p.get("homepage") or "").strip()
            name = (p.get("name") or "").strip()
            if url and name:
                names_by_url[url].add(name)
            for source in (p.get("sources") or []):
                su = (source.get("url") or "").strip()
                if su:
                    self.titles[canonical_home(su)].add(
                        (source.get("title") or "").strip())
            host = host_of(url)
            if host:
                self.host_units[host][_unit_core(p.get("department") or "")] += 1
        self.shared_names = {u for u, n in names_by_url.items() if len(n) > 1}

    # ── 判据 1..3：是不是专属页 ─────────────────────────────────────────
    def kind(self, url: str) -> str:
        if not (url or "").strip():
            return PAGE_NONE
        if homepage_kind.is_roster_url(url):
            return PAGE_ROSTER
        if url in self.shared_names:
            return PAGE_ROSTER
        titles = self.titles.get(canonical_home(url)) or set()
        if any(any(m in t for m in LISTING_TITLE_MARKERS) for t in titles):
            return PAGE_ROSTER
        path = re.sub(r"^https?://", "", url.strip().lower()).split("?")[0]
        if path.rstrip("/").rsplit("/", 1)[-1] in GENERIC_LIST_FILES:
            return PAGE_ROSTER
        return PAGE_PERSONAL

    def kind_reason(self, url: str) -> str:
        """给 :meth:`kind` 配一条可复核的理由。"""
        if not (url or "").strip():
            return "missing_url"
        if homepage_kind.is_roster_url(url):
            return "declared_listing"
        if url in self.shared_names:
            return "shared_by_different_names"
        titles = self.titles.get(canonical_home(url)) or set()
        if any(any(m in t for m in LISTING_TITLE_MARKERS) for t in titles):
            return "source_title_says_listing"
        path = re.sub(r"^https?://", "", url.strip().lower()).split("?")[0]
        if path.rstrip("/").rsplit("/", 1)[-1] in GENERIC_LIST_FILES:
            return "generic_listing_file"
        return "dedicated_page"

    # ── 判据 4：站点归属是否与记录自己的院系相符 ────────────────────────
    def owner(self, url: str) -> tuple[str, float, int]:
        """该主页站点的主院系、占比与样本量。"""
        counter = self.host_units.get(host_of(url))
        if not counter:
            return "", 0.0, 0
        total = sum(counter.values())
        unit, count = counter.most_common(1)[0]
        return unit, count / total, total

    def unit_mismatch(self, url: str, profile: dict) -> bool:
        """主页站点主要服务于别的院系，而记录自称在另一个院系。

        典型：``life.sjtu.edu.cn`` 有 98.6% 的记录来自生命科学技术学院，却被一条
        「数学科学学院」的记录当作主页——这通常是按姓名匹配接错了页，不能当作
        「同一个人」的证据。
        """
        unit, share, total = self.owner(url)
        if not unit or total < HOST_OWNER_MIN_RECORDS or share < HOST_OWNER_MIN_SHARE:
            return False
        mine = _unit_core(profile.get("department") or "")
        if not mine:
            return False
        return unit not in mine and mine not in unit


def pair_label(a: dict, b: dict, pages: PageIndex) -> dict:
    """给一对同名记录定标签，并写明理由与证据强度。"""
    home_a = (a.get("homepage") or "").strip()
    home_b = (b.get("homepage") or "").strip()
    kind_a = pages.kind(home_a)
    kind_b = pages.kind(home_b)
    ident_a, ident_b = identity_home(home_a), identity_home(home_b)

    same_inst = a.get("institution") == b.get("institution")
    same_dept = a.get("department") == b.get("department")
    same_disc = (a.get("first_level_discipline") == b.get("first_level_discipline"))

    row = {
        "page_a": kind_a,
        "page_b": kind_b,
        "page_a_reason": pages.kind_reason(home_a),
        "page_b_reason": pages.kind_reason(home_b),
        "same_inst": same_inst,
        "same_dept": same_dept,
        "same_disc": same_disc,
    }

    # 1) 任一页不是专属页 → 无法定位到具体的人
    if kind_a != PAGE_PERSONAL or kind_b != PAGE_PERSONAL:
        reasons = []
        if kind_a == PAGE_NONE or kind_b == PAGE_NONE:
            reasons.append("missing_url")
        if kind_a == PAGE_ROSTER or kind_b == PAGE_ROSTER:
            reasons.append("listing_page")
        row.update(label=UNKNOWN, strength="none", reason="+".join(reasons))
        return row

    # 2) 同一个专属页 + 同机构 → 直接公开证据
    # 判等用 identity_home（保留查询串）：查询串常常就是页面 id，抹掉它会把
    # 「同一站点模板下的两个不同个人页」误判成同一页，从而把两个人合并。
    if ident_a and ident_a == ident_b:
        if not same_inst:
            row.update(label=UNKNOWN, strength="none",
                       reason="same_url_cross_institution")
            return row
        strength = "strong" if same_disc else "medium"
        row.update(label=SAME, strength=strength, reason="shared_dedicated_page")
        return row

    # 3) 两个互不相同的专属页 → 看单位是否冲突
    if not same_inst:
        row.update(label=DIFFERENT, strength="strong",
                   reason="distinct_pages_cross_institution")
        return row
    if not same_dept or not same_disc:
        row.update(label=DIFFERENT, strength="medium",
                   reason="distinct_pages_unit_conflict")
        return row
    row.update(label=UNKNOWN, strength="none", reason="same_unit_no_conflict")
    return row


def build_evidence_pairs(profiles: list[dict],
                         pages: PageIndex | None = None
                         ) -> tuple[list[dict], dict]:
    """按新协议给所有同名组合定标签（不跳过任何组，缺主页的组也要记账）。"""
    pages = pages or PageIndex(profiles)
    by_name: dict[str, list[dict]] = defaultdict(list)
    for p in profiles:
        name = (p.get("name") or "").strip()
        if name:
            by_name[name].append(p)

    rows: list[dict] = []
    stats = {
        "groups": 0,
        "groups_with_missing_home": 0,
        "pairs_total": 0,
        "labels": Counter(),
        "unknown_reasons": Counter(),
        "same_institution": Counter(),
        "cross_institution": Counter(),
    }
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        stats["groups"] += 1
        if any(not (p.get("homepage") or "").strip() for p in group):
            stats["groups_with_missing_home"] += 1
        for i, j in combinations(range(len(group)), 2):
            a, b = group[i], group[j]
            row = pair_label(a, b, pages)
            row.update(name=name, i=a, j=b)
            rows.append(row)
            stats["pairs_total"] += 1
            stats["labels"][row["label"]] += 1
            if row["label"] == UNKNOWN:
                stats["unknown_reasons"][row["reason"]] += 1
            bucket = "same_institution" if row["same_inst"] else "cross_institution"
            stats[bucket][row["label"]] += 1
    return rows, stats


# ── 旧协议（保留为对照，勿删）────────────────────────────────────────────
def build_pairs(pairs: list[dict]) -> tuple[list[dict], dict]:
    """**旧协议**：用 homepage 判等构造带标签的样本对。

    仅保留作对照与回归测试；新评测不要再使用它。它对「不同 URL」一律判异人，
    这正是本次整改要修掉的缺陷。
    """
    by_name = defaultdict(list)
    for p in pairs:
        n = (p.get("name") or "").strip()
        if n:
            by_name[n].append(p)

    labelled: list[dict] = []
    stats = {"groups": 0, "same_home_groups": 0, "diff_home_groups": 0,
             "skipped_missing_home": 0, "positives": 0, "negatives": 0}

    for name, group in by_name.items():
        if len(group) < 2:
            continue
        stats["groups"] += 1
        homes = [canonical_home(p.get("homepage") or "") for p in group]
        if any(not h for h in homes):
            stats["skipped_missing_home"] += 1
            continue
        uniq = set(homes)
        if len(uniq) == 1:
            stats["same_home_groups"] += 1
        else:
            stats["diff_home_groups"] += 1
        for i, j in combinations(range(len(group)), 2):
            same = homes[i] == homes[j]
            labelled.append({"name": name, "i": group[i], "j": group[j],
                             "same": same})
            stats["positives" if same else "negatives"] += 1
    return labelled, stats


# ── 特征 ────────────────────────────────────────────────────────────────
def profile_text(profile: dict, clean: bool = False) -> str:
    """成对特征用的文本。``clean=True`` 去掉采集管线合成的学科归属套话。"""
    dossier = research.load(profile["id"]) or {}
    biography = _as_text(dossier.get("biography"))
    if clean:
        biography = _clean_bio(biography)
    parts = [
        biography[:500],
        _as_text(profile.get("summary"))[:200],
        f"院系 {profile.get('department', '')}",
        f"学科 {profile.get('discipline', '')}",
    ]
    text = re.sub(r"\s+", " ", "；".join(p for p in parts if p.strip("； ")))
    return text.strip()[:MAX_TEXT_CHARS]


def normalize(matrix):
    import numpy as np
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def feature_rows(rows: list[dict], want_clean: bool = True) -> list[dict]:
    """给每一对补上成对特征（homepage 本身不参与特征）。"""
    import numpy as np

    records: dict[str, dict] = {}
    for row in rows:
        for side in ("i", "j"):
            records.setdefault(row[side]["id"], row[side])

    ids = list(records)
    if not ids:
        return []
    vectors = normalize(np.asarray(
        list(_embedder().embed([profile_text(records[i]) for i in ids])),
        dtype="float32"))
    pos = {pid: k for k, pid in enumerate(ids)}

    clean_vectors = None
    if want_clean:
        clean_vectors = normalize(np.asarray(
            list(_embedder().embed(
                [profile_text(records[i], clean=True) for i in ids])),
            dtype="float32"))

    out = []
    for row in rows:
        a, b = row["i"], row["j"]
        va, vb = vectors[pos[a["id"]]], vectors[pos[b["id"]]]
        enriched = dict(row)
        enriched.update({
            "same": row["label"] == SAME,
            "emb": float(np.dot(va, vb)),
            "kw": float(keyword_score(row["name"], profile_text(records[b["id"]]))),
        })
        if clean_vectors is not None:
            ca, cb = clean_vectors[pos[a["id"]]], clean_vectors[pos[b["id"]]]
            enriched["emb_clean"] = float(np.dot(ca, cb))
        out.append(enriched)
    return out


# ── 指标 ────────────────────────────────────────────────────────────────
def auc(rows: list[dict], key: str) -> float:
    """用秩和法算 AUC（不依赖 sklearn）。"""
    pos = [r[key] for r in rows if r["same"]]
    neg = [r[key] for r in rows if not r["same"]]
    if not pos or not neg:
        return 0.0
    win = 0.0
    for p in pos:
        for n in neg:
            win += 1.0 if p > n else (0.5 if p == n else 0.0)
    return win / (len(pos) * len(neg))


def prf(rows: list[dict], predict) -> dict:
    tp = fp = fn = tn = 0
    for r in rows:
        pred = predict(r)
        if pred and r["same"]:
            tp += 1
        elif pred and not r["same"]:
            fp += 1
        elif r["same"]:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "support": {"positives": tp + fn, "negatives": tn + fp}}


def evaluate(rows: list[dict]) -> dict:
    """**旧协议口径**的评测（保留作对照）。"""
    result = {
        "pairs": len(rows),
        "positives": sum(1 for r in rows if r["same"]),
        "negatives": sum(1 for r in rows if not r["same"]),
        "auc": {
            "institution_only": auc(rows, "same_inst"),
            "embedding_only": auc(rows, "emb"),
        },
        "baseline_institution": prf(rows, lambda r: r["same_inst"]),
        "thresholds": [],
    }
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        result["thresholds"].append({
            "emb>=": t,
            "same_inst_and_emb": prf(rows, lambda r, t=t: r["same_inst"] and r["emb"] >= t),
            "emb_only": prf(rows, lambda r, t=t: r["emb"] >= t),
        })
    return result


def confusion(rows: list[dict], predict) -> dict:
    """混淆矩阵 + P/R/F1。"""
    m = prf(rows, predict)
    return {
        "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "tn": m["tn"],
        "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
        "support": m["support"],
    }


def relabel(rows: list[dict], key: str = "reviewed_label") -> list[dict]:
    """按复核判定重建标签行（``same`` 随之重算），供评测使用。"""
    out = []
    for r in rows:
        label = r.get(key) or r["label"]
        item = dict(r)
        item["label"] = label
        item["same"] = label == SAME
        out.append(item)
    return out


def evaluate_protocol(rows: list[dict], scope: str) -> dict:
    """**新协议口径**：只在 ``same_person`` / ``different_person`` 上算指标。"""
    labelled = [r for r in rows if r["label"] in (SAME, DIFFERENT)]
    positives = sum(1 for r in labelled if r["same"])
    negatives = len(labelled) - positives
    # 缺一类时 AUC 无定义——必须显示为不可计算，而不是 0.000
    defined = bool(positives) and bool(negatives)
    result = {
        "scope": scope,
        "labelled_pairs": len(labelled),
        "positives": positives,
        "negatives": negatives,
        "excluded_unknown": len(rows) - len(labelled),
        "auc_defined": defined,
        "auc": {
            "institution_only": auc(labelled, "same_inst") if defined else None,
            "embedding_only": auc(labelled, "emb") if defined else None,
            "embedding_clean_only": (
                auc(labelled, "emb_clean") if defined else None),
        },
        "baseline_institution": confusion(labelled, lambda r: r["same_inst"]),
        "baseline_embedding": {
            "confusion": confusion(labelled, lambda r: r["emb"] >= 0.85),
            "threshold": 0.85,
        },
        "thresholds": [],
    }
    for t in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        result["thresholds"].append({
            "emb>=": t,
            "same_inst_and_emb": confusion(
                labelled, lambda r, t=t: r["same_inst"] and r["emb"] >= t),
            "emb_only": confusion(labelled, lambda r, t=t: r["emb"] >= t),
            "emb_clean_only": confusion(
                labelled, lambda r, t=t: r.get("emb_clean", 0.0) >= t),
        })
    return result


# ── 独立复核集 ──────────────────────────────────────────────────────────
def adjudicate(row: dict, pages: PageIndex) -> dict:
    """独立于「URL 判等」的复核判定：再用**站点归属**交叉检验。

    与 :func:`pair_label` 唯一的差别：同一个专属页被一条**院系不符**的记录引用时，
    不再当作「同一个人」的直接证据，而记为 ``unknown``——因为「按姓名接错主页」与
    「真实交叉挂靠」在字段层面无法区分。
    """
    a, b = row["i"], row["j"]
    auto = row["label"]
    verdict, strength, note = auto, row["strength"], ""
    extra: dict = {}

    if auto == SAME:
        mism_a = pages.unit_mismatch(a.get("homepage") or "", a)
        mism_b = pages.unit_mismatch(b.get("homepage") or "", b)
        if mism_a or mism_b:
            owner_rec = a if mism_a else b
            unit, share, total = pages.owner(owner_rec.get("homepage") or "")
            verdict, strength = UNKNOWN, "none"
            note = ("共享主页的站点归属与其中一条记录的院系不符"
                    f"（该站点 {share:.1%} 的记录来自「{unit}」，样本 {total} 条），"
                    "无法排除「按姓名匹配接错主页」")
            extra["unit_owner"] = {"unit": unit,
                                   "share": round(share, 4), "records": total}
        else:
            note = "两条记录指向同一个本人专属主页，且站点归属与院系一致"
    elif auto == DIFFERENT:
        if row["same_inst"]:
            note = ("两个互不相同的本人专属主页，且院系/一级学科冲突"
                    f"（院系相同={row['same_dept']}，一级学科相同={row['same_disc']}）")
        else:
            note = "两个互不相同的本人专属主页，且分属不同机构"
    else:
        note = "证据不足以判定同人/异人"

    return {"verdict": verdict, "evidence_strength": strength,
            "note": note, **extra}


def _quote(row_a: dict, row_b: dict) -> list[dict]:
    """把判定所依据的字段原名原值摘出来，人工可逐条复核。"""
    fields = []
    for field, label in (
        ("institution", "机构"),
        ("department", "院系"),
        ("first_level_discipline", "一级学科"),
        ("discipline", "学科"),
        ("homepage", "主页"),
        ("interests", "研究方向"),
    ):
        va = row_a.get(field) or ""
        vb = row_b.get(field) or ""
        if not va and not vb:
            continue
        fields.append({
            "field": field,
            "label": label,
            "a": str(va)[:120],
            "b": str(vb)[:120],
            "equal": str(va) == str(vb),
        })
    return fields


def gold_set(rows: list[dict], pages: PageIndex, seed: int = 42,
             unknown_sample: int = 25) -> list[dict]:
    """构造**程序辅助核验**样本集。

    重要：这里的 ``verdict`` 由 :func:`adjudicate` 的规则给出，而 ``auto_label`` 由
    :func:`pair_label` 的规则给出——**两者都是程序，不是人工标注**。因此本集合只用于
    「自动协议与规则复核是否一致」，不能当作 Precision/Recall 的人工金标准。

    真正的独立标注走 :mod:`workbench.human_labels`：导出盲标表 → 人工填写
    ``human_verdict``/``reviewer``/``reviewed_at`` → 导入后才计算指标；标注不足时
    只记录状态，不报告指标。

    组成为：同校同名的全部 ``same_person`` 与 ``different_person`` 候选（真正有决策
    难度的全域，不做抽样），再从 ``unknown`` 里按固定种子抽样，保证三类都有代表。
    """
    same_inst = [r for r in rows if r["same_inst"]]

    def order(r):
        return (r["name"], r["i"]["id"], r["j"]["id"])

    selected = [r for r in same_inst if r["label"] in (SAME, DIFFERENT)]
    unknowns = [r for r in same_inst if r["label"] == UNKNOWN]
    if len(unknowns) > unknown_sample:
        import random
        unknowns = random.Random(seed).sample(unknowns, unknown_sample)

    out = []
    for idx, row in enumerate(sorted(selected + unknowns, key=order), start=1):
        a, b = row["i"], row["j"]
        adj = adjudicate(row, pages)
        item = {
            "pair_id": f"G{idx:04d}",
            "name": row["name"],
            "institution": a.get("institution") if row["same_inst"] else None,
            "a": {
                "id": a["id"],
                "department": a.get("department"),
                "first_level_discipline": a.get("first_level_discipline"),
                "homepage": (a.get("homepage") or ""),
                "page_kind": row["page_a"],
            },
            "b": {
                "id": b["id"],
                "department": b.get("department"),
                "first_level_discipline": b.get("first_level_discipline"),
                "homepage": (b.get("homepage") or ""),
                "page_kind": row["page_b"],
            },
            "auto_label": row["label"],
            "verdict": adj["verdict"],
            "evidence_strength": adj["evidence_strength"],
            "evidence": {
                "rule": row["reason"],
                "note": adj["note"],
                "quoted_fields": _quote(a, b),
            },
            "same_institution": row["same_inst"],
        }
        if "unit_owner" in adj:
            item["evidence"]["unit_owner"] = adj["unit_owner"]
        if adj["verdict"] == UNKNOWN:
            item["missing_evidence"] = UNKNOWN_NEEDS.get(
                row["reason"],
                "主页站点归属与院系不符，需人工确认该主页是否接错")
        out.append(item)
    return out


def gold_agreement(gold: list[dict]) -> dict:
    """自动协议与**规则复核**的一致率（按类别）。

    两者同源（都读主页类型/站点归属/院系字段），所以这是一致性检查，
    不是"人工验证自动协议"的准确率。
    """
    clean = [g for g in gold if g["auto_label"] in (SAME, DIFFERENT)]
    agree = sum(1 for g in clean if g["verdict"] == g["auto_label"])
    per = {}
    for label in (SAME, DIFFERENT):
        sub = [g for g in gold if g["auto_label"] == label]
        hit = sum(1 for g in sub if g["verdict"] == label)
        per[label] = {"auto": len(sub), "agreed": hit,
                      "agreement": (hit / len(sub)) if sub else None}
    return {
        "protocol_status": "program-assisted",
        "protocol_note": ("auto_label 与 verdict 都由程序规则生成，二者同源；"
                          "该一致率不代表人工核验准确率。人工金标准见 human_labels。"),
        "reviewed_pairs": len(gold),
        "labelled_candidates": len(clean),
        "agreed": agree,
        "agreement": (agree / len(clean)) if clean else None,
        "by_auto_label": per,
        "verdict_distribution": dict(Counter(g["verdict"] for g in gold)),
    }


# ── 高危误合并 ──────────────────────────────────────────────────────────
def high_risk(rows: list[dict], pages: PageIndex,
              threshold: float = 0.85) -> list[dict]:
    """嵌入相似度很高、但证据判定**不是同人**的组合——最容易误合并的那些。"""
    out = []
    for row in rows:
        if row["label"] == SAME:
            continue
        emb = row.get("emb")
        if emb is None or emb < threshold:
            continue
        a, b = row["i"], row["j"]
        adj = adjudicate(row, pages)
        out.append({
            "name": row["name"],
            "institution": a.get("institution"),
            "emb": round(float(emb), 4),
            "emb_clean": round(float(row.get("emb_clean", 0.0)), 4),
            "label": row["label"],
            "strength": row["strength"],
            "reason": row["reason"],
            "same_institution": row["same_inst"],
            "a": {"id": a["id"], "dept": a.get("department"),
                  "discipline": a.get("first_level_discipline"),
                  "home": (a.get("homepage") or "")[:90],
                  "page": row["page_a"]},
            "b": {"id": b["id"], "dept": b.get("department"),
                  "discipline": b.get("first_level_discipline"),
                  "home": (b.get("homepage") or "")[:90],
                  "page": row["page_b"]},
            "note": adj["note"],
        })
    # 同校的排前面：跨校同名本来就几乎必然是两个人，不是真正的风险点
    out.sort(key=lambda x: (not x["same_institution"], -x["emb"]))
    return out


# ── 待核队列（界面消费）──────────────────────────────────────────────────
def review(rows: list[dict], pages: PageIndex | None = None) -> list[dict]:
    """同校同名的**全部**组合，逐对带（复核后的）标签、分数与判定依据。

    ``verdict`` 文案保持旧口径（疑似同人/待核/疑似异人）以便前端无需改动。
    标签取 :func:`adjudicate` 的复核结论而不是 :func:`pair_label` 的初判——两者只在
    「同一 URL 但站点归属与院系不符」这一种情形下不同，而那种情形**不够**称为
    「直接公开证据」，必须降级为待核。这体现保守合并原则。
    """
    items = []
    for row in rows:
        if not row["same_inst"]:
            continue
        a, b = row["i"], row["j"]
        emb = row.get("emb")
        if emb is None:
            continue
        adj = adjudicate(row, pages) if pages is not None else {
            "verdict": row["label"], "evidence_strength": row["strength"],
            "note": ""}
        label = adj["verdict"]
        if label == SAME:
            verdict = "疑似同人"
        elif label == DIFFERENT:
            verdict = "疑似异人"
        else:
            verdict = "待核"
        items.append({
            # ── 旧字段（前端与 ai_hints 依赖，保留）────────────────────
            "name": row["name"],
            "institution": a.get("institution"),
            "a": {"id": a["id"], "dept": a.get("department"),
                  "home": (a.get("homepage") or "")[:80]},
            "b": {"id": b["id"], "dept": b.get("department"),
                  "home": (b.get("homepage") or "")[:80]},
            "same_dept": row["same_dept"],
            "emb": round(float(emb), 4),
            "verdict": verdict,
            # ── 新字段：证据分级 ───────────────────────────────────────
            "label": label,
            "auto_label": row["label"],
            "strength": adj["evidence_strength"],
            "reason": row["reason"],
            "note": adj["note"],
            "page_a": row["page_a"],
            "page_b": row["page_b"],
            "needs_human_review": label != SAME,
            "auto_merge": False,
        })
    items.sort(key=lambda r: (-r["emb"], r["name"]))
    return items


# ── 报告 ────────────────────────────────────────────────────────────────
def _pct(x) -> str:
    return "—" if x is None else f"{x:.1%}"


def _f(x) -> str:
    """AUC 缺失时显示「不可计算」，绝不写成 0.000。"""
    return "不可计算" if x is None else f"{x:.3f}"


def _build_report(stats: dict, primary: dict | None = None,
                  supplementary: dict | None = None,
                  legacy: dict | None = None,
                  comparison: dict | None = None,
                  risky: list[dict] | None = None,
                  queue: list[dict] | None = None,
                  profiles_total: int = 0,
                  reviewed: dict | None = None,
                  agreement: dict | None = None,
                  human_status: dict | None = None) -> list[str]:
    lines = [
        "# 同名导师消歧：证据分级评测与待核清单",
        "",
        f"- 模型：`{MODEL_NAME}`（本地推理）",
        f"- 全库 {profiles_total} 条；同名组 **{stats['groups']}** 组，"
        f"其中 {stats['groups_with_missing_home']} 组存在缺主页的记录",
        f"- 同名组合共 **{stats['pairs_total']}** 对",
        "",
        "## 真值协议（证据分级）",
        "",
        "| 判定 | 含义 | 对数 |",
        "|:--|:--|--:|",
        f"| `same_person` | 同一**专属**个人主页 + 同机构 | {stats['labels'][SAME]} |",
        f"| `different_person` | 两页互不相同且院系/一级学科冲突，或分属不同机构 "
        f"| {stats['labels'][DIFFERENT]} |",
        f"| `unknown` | 证据不足，**不进入指标** | {stats['labels'][UNKNOWN]} |",
        "",
        "`unknown` 的成因分布：",
        "",
        "| 原因 | 对数 |",
        "|:--|--:|",
    ]
    for reason, count in stats["unknown_reasons"].most_common():
        lines.append(f"| `{reason}` | {count} |")

    if primary is not None:
        lines += [
            "",
            "## 主指标：同校同名（只含 `same_person` / `different_person`）",
            "",
            f"样本 **{primary['labelled_pairs']}** 对"
            f"（同人 {primary['positives']} / 异人 {primary['negatives']}），"
            f"另有 {primary['excluded_unknown']} 对 `unknown` 已剔除。",
            "",
            "| 指标 | 值 |",
            "|:--|--:|",
            f"| AUC（仅机构是否相同） | {_f(primary['auc']['institution_only'])} |",
            f"| AUC（仅履历嵌入） | {_f(primary['auc']['embedding_only'])} |",
            f"| AUC（嵌入，去掉学科归属套话） "
            f"| {_f(primary['auc']['embedding_clean_only'])} |",
            "",
            "混淆矩阵（朴素基线：机构相同即判同人）：",
            "",
            "| | 预测同人 | 预测异人 |",
            "|:--|--:|--:|",
            f"| **实际同人** | {primary['baseline_institution']['tp']} | "
            f"{primary['baseline_institution']['fn']} |",
            f"| **实际异人** | {primary['baseline_institution']['fp']} | "
            f"{primary['baseline_institution']['tn']} |",
            "",
            f"P {_pct(primary['baseline_institution']['precision'])} / "
            f"R {_pct(primary['baseline_institution']['recall'])} / "
            f"F1 {_pct(primary['baseline_institution']['f1'])}",
            "",
            "阈值消融（机构相同 **且** 嵌入 ≥ 阈值）：",
            "",
            "| 阈值 | TP | FP | FN | 精确率 | 召回率 | F1 |",
            "|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for t in primary["thresholds"]:
            m = t["same_inst_and_emb"]
            lines.append(f"| {t['emb>=']:.2f} | {m['tp']} | {m['fp']} | {m['fn']} | "
                         f"{_pct(m['precision'])} | {_pct(m['recall'])} | "
                         f"{_pct(m['f1'])} |")
        lines += [
            "",
            "注：本层内所有组合都是同校同名，`机构是否相同` 恒为 True，"
            "因此「机构相同 且 嵌入 ≥ 阈值」与「仅嵌入 ≥ 阈值」在这批样本上**是同一个"
            "判定式**，不再单列一张表。这本身就是旧协议的关键问题：机构特征在这个层"
            "里没有区分力。",
        ]

    if reviewed is not None:
        downgraded = 0
        if primary is not None:
            downgraded = reviewed["excluded_unknown"] - primary["excluded_unknown"]
        lines += [
            "",
            "## 规则复核后指标（程序判定，非人工金标准）",
            "",
            "复核规则对「同一 URL 但站点归属与院系不符」的组合降级为 `unknown`——这类"
            "主页很可能是按姓名匹配接错的，不能算直接证据。**注意：这一节仍是程序复核，"
            "不是人工标注**；人工金标准尚未完成，见文末「人工标注状态」。",
            "",
            f"样本 **{reviewed['labelled_pairs']}** 对"
            f"（同人 {reviewed['positives']} / 异人 {reviewed['negatives']}）；"
            f"剔除 `unknown` {reviewed['excluded_unknown']} 对，"
            f"其中 **{downgraded}** 对是复核后由「同人」降级而来。",
            "",
            "| 指标 | 值 |",
            "|:--|--:|",
            f"| AUC（仅机构是否相同） | {_f(reviewed['auc']['institution_only'])} |",
            f"| AUC（仅履历嵌入） | {_f(reviewed['auc']['embedding_only'])} |",
            f"| AUC（嵌入，去掉学科归属套话） "
            f"| {_f(reviewed['auc']['embedding_clean_only'])} |",
            f"| 朴素基线 P / R / F1 | "
            f"{_pct(reviewed['baseline_institution']['precision'])} / "
            f"{_pct(reviewed['baseline_institution']['recall'])} / "
            f"{_pct(reviewed['baseline_institution']['f1'])} |",
            "",
            "| 阈值 | TP | FP | FN | 精确率 | 召回率 | F1 |",
            "|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for t in reviewed["thresholds"]:
            m = t["emb_only"]
            lines.append(f"| {t['emb>=']:.2f} | {m['tp']} | {m['fp']} | {m['fn']} | "
                         f"{_pct(m['precision'])} | {_pct(m['recall'])} | "
                         f"{_pct(m['f1'])} |")

    if reviewed is not None:
        # 一致率必须来自本次运行，不能把某次跑出来的数字写死在文案里——
        # 数据一变，报告就会继续复述一个不再成立的「实测值」。
        if agreement and agreement.get("agreement") is not None:
            agreement_line = (
                "上面所有指标都来自**程序规则**：`pair_label`（自动判定）与 `adjudicate`"
                "（规则复核）同源，因此本次实测的一致率 "
                f"**{_pct(agreement['agreement'])}**"
                f"（{agreement['agreed']}/{agreement['labelled_candidates']} 对，"
                "与 `--gold` 写出的 `workbench/evaluation/gold_pairs.json` 同一批样本）"
                "只是「两套规则是否一致」，不是人工验证的准确率。")
        else:
            agreement_line = (
                "上面所有指标都来自**程序规则**：`pair_label`（自动判定）与`adjudicate`"
                "（规则复核）同源，两者的一致率只能说明规则之间是否自洽，"
                "不是人工验证的准确率。")
        # 状态必须按磁盘上是否真的有人工判断来渲染，不能写死成「待完成」：
        # 一旦跑过 --import-human，写死的「待完成」就成了假话。
        collected = bool(human_status
                         and human_status.get("protocol_status") == "human-collected")
        if collected:
            heading = "## 人工标注状态：**已收集人工判断**（人工金标准）"
            status_line = (
                f"本次同时读到 `human_labels.json`：人工独立判断 "
                f"**{human_status.get('distinct_pairs')}** 对"
                f"（同人 {human_status.get(SAME, 0)} / 异人 {human_status.get(DIFFERENT, 0)}"
                f" / 未知 {human_status.get(UNKNOWN, 0)}；争议 "
                f"{human_status.get('conflicts', 0)} 对）。"
                "**上表仍是程序指标，不是人工准确率**；人工指标见 `human_metrics.json`。")
        else:
            heading = "## 人工标注状态：**待完成**"
            status_line = ""
        lines += ["", heading, "", agreement_line, ""]
        if status_line:
            lines += [status_line, ""]
        lines += [
            "仓库已提供人工盲标协议与工具：",
            "",
            "```bat",
            ".venv\\Scripts\\python.exe -m workbench.disambiguate_names --export-human "
            "workbench/evaluation/human_annotation/annotation-template.csv",
            ".venv\\Scripts\\python.exe -m workbench.disambiguate_names --import-human "
            "<标注完成的CSV> --min-human 30",
            "```",
            "",
            "- 盲标表不含模型分数与自动判定；评分用键单独保存，标注者不可见；",
            "- 导入校验要求每行都有 verdict / reviewer / reviewed_at，缺一项整批拒绝；",
            "- 标注 ≥30 对且正负例各 ≥5 后，才计算人工金标准指标；在此之前"
            "**不得**把本节数字写成人工验证结果。",
            "",
            "协议与字段说明：`workbench/evaluation/human_annotation/protocol.md`。",
            "",
        ]

    if supplementary is not None:
        lines += [
            "",
            "## 补充：跨校同名（简单负例，**不作为主指标**）",
            "",
            f"{supplementary['labelled_pairs']} 对"
            f"（同人 {supplementary['positives']} / "
            f"异人 {supplementary['negatives']}）。"
            f"AUC 机构 {_f(supplementary['auc']['institution_only'])} / "
            f"嵌入 {_f(supplementary['auc']['embedding_only'])}。"
            "这部分几乎不需要模型：跨校基本就是异人，正例为 0 时 AUC 本身就无定义"
            "（所以显示不可计算）。把它算进主指标，就是旧协议高估的来源。",
        ]

    if legacy is not None and primary is not None and comparison is not None:
        lines += [
            "",
            "## 新旧协议对照",
            "",
            "| 项目 | 旧协议（URL 真值） | 新协议（证据分级） |",
            "|:--|--:|--:|",
            f"| 参与指标的对数 | {legacy['pairs']} | {primary['labelled_pairs']} |",
            f"| 正例 | {legacy['positives']} | {primary['positives']} |",
            f"| 负例 | {legacy['negatives']} | {primary['negatives']} |",
            f"| 其中同校 | {comparison['legacy']['same_institution_pairs']} | "
            f"{primary['labelled_pairs']} |",
            f"| 其中跨校 | {comparison['legacy']['cross_institution_pairs']} | 0 |",
            f"| AUC（仅机构） | {legacy['auc']['institution_only']:.3f} | "
            f"{_f(primary['auc']['institution_only'])} |",
            f"| AUC（仅嵌入） | {legacy['auc']['embedding_only']:.3f} | "
            f"{_f(primary['auc']['embedding_only'])} |",
            f"| 朴素基线 F1 | {_pct(legacy['baseline_institution']['f1'])} | "
            f"{_pct(primary['baseline_institution']['f1'])} |",
            "",
            "**旧协议为什么高估**：",
            "",
            f"1. 负例里 "
            f"**{comparison['verdict']['legacy_negative_share_cross_institution']:.1%}** "
            "是跨校组合，这类组合不需要任何模型就能判对；",
            "2. 同校层内「机构是否相同」恒为 True，AUC 直接塌到 "
            f"{_f(primary['auc']['institution_only'])}，旧报告里那个 0.9x 的机构 AUC "
            "全部来自跨校对比；",
            "3. 旧协议没有 `unknown` 档，被迫把「不同 URL」一律当异人，把一人多页、"
            "名录页回落这类情况错标成负例。",
        ]

    if risky:
        lines += [
            "",
            "## 高危误合并案例（嵌入 ≥ 0.85 但证据判**不是同人**）",
            "",
            f"共 **{len(risky)}** 对（同校的排在前面）。这类组合最容易被「文本很像」"
            "误导；跨校的虽然也列出，但它们本来就几乎必然是两个人，风险低得多。",
            "",
            "| 姓名 | 学校 | 同校 | 嵌入 | 一级学科 A | 一级学科 B | 院系 A | 院系 B | 判定 |",
            "|:--|:--|:--|--:|:--|:--|:--|:--|:--|",
        ]
        for item in risky[:20]:
            lines.append(
                f"| {item['name']} | {item['institution']} | "
                f"{'是' if item['same_institution'] else '否'} | "
                f"{item['emb']:.3f} | "
                f"{item['a']['discipline']} | {item['b']['discipline']} | "
                f"{(item['a']['dept'] or '-')[:24]} | "
                f"{(item['b']['dept'] or '-')[:24]} | {item['label']} |")
        if len(risky) > 20:
            lines.append(f"| … | 其余 {len(risky) - 20} 对见 `high_risk.json` "
                         "| | | | | | |")
        lines.append("")

    if queue:
        counts = Counter(i["label"] for i in queue)
        lines += [
            "## 同校同名：待核队列",
            "",
            f"共 **{len(queue)}** 对同校同名组合："
            f"`same_person` {counts[SAME]} / `different_person` {counts[DIFFERENT]} / "
            f"`unknown` {counts[UNKNOWN]}。",
            "",
            "**系统不自动合并**：即使判定为 `same_person` 也只给建议；``unknown`` 全部进"
            "人工核验。",
            "",
            "| 姓名 | 学校 | 嵌入 | 判定 | 依据 | 院系 A | 院系 B |",
            "|:--|:--|--:|:--|:--|:--|:--|",
        ]
        for it in queue[:60]:
            lines.append(
                f"| {it['name']} | {it['institution']} | {it['emb']:.3f} | "
                f"{it['verdict']} | {it['reason']} | "
                f"{(it['a']['dept'] or '-')[:22]} | {(it['b']['dept'] or '-')[:22]} |")
        if len(queue) > 60:
            lines.append(f"| … | 其余 {len(queue) - 60} 对见 `review.json` "
                         "| | | | | |")
        lines.append("")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="同名导师消歧：证据分级评测与待核清单")
    ap.add_argument("--evaluate", action="store_true",
                    help="跑新协议评测，并给出旧 URL 协议对照")
    ap.add_argument("--review", action="store_true", help="产出同校同名待核队列")
    ap.add_argument("--gold", action="store_true",
                    help="写出程序辅助核验集 workbench/evaluation/gold_pairs.json（非人工金标准）")
    ap.add_argument("--export-human", metavar="CSV", default="",
                    help="导出人工盲标表（不含模型分数）")
    ap.add_argument("--import-human", metavar="CSV", default="",
                    help="导入人工判断并（在样本足够时）重算指标")
    ap.add_argument("--human-status", action="store_true", help="查看人工金标准状态")
    ap.add_argument("--min-human", type=int, default=30,
                    help="报告人工指标所需的最小标注对数（默认 30）")
    ap.add_argument("--limit", type=int, default=0,
                    help="旧协议对照评测最多取多少对（0=全部）")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from . import human_labels
    if args.export_human or args.import_human or args.human_status:
        if args.export_human:
            result = human_labels.export(pathlib.Path(args.export_human))
            print(f"盲标表 {result['template']}（{result['pairs']} 对；"
                  f"{result['categories']}）；评分用键 {result['key']}")
        if args.import_human:
            summary = human_labels.import_labels(
                pathlib.Path(args.import_human), out_dir=EVAL_DIR,
                min_labels=args.min_human)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.human_status:
            print(json.dumps(human_labels.status(EVAL_DIR), ensure_ascii=False, indent=2))
        if not (args.evaluate or args.review or args.gold):
            return 0
    if not (args.evaluate or args.review or args.gold):
        args.evaluate = args.review = args.gold = True

    profiles, _by_id, _raw, _net = catalog.static_catalog()
    pages = PageIndex(profiles)
    print(f"模型 {MODEL_NAME}；全库 {len(profiles)} 条")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    rows, stats = build_evidence_pairs(profiles, pages)
    print(f"同名组 {stats['groups']}；组合 {stats['pairs_total']} 对："
          f"同人 {stats['labels'][SAME]} / 异人 {stats['labels'][DIFFERENT]} / "
          f"待核 {stats['labels'][UNKNOWN]}")

    primary = supplementary = legacy = comparison = reviewed = None
    report_agreement = None
    risky: list[dict] = []
    queue: list[dict] = []
    with_feat: list[dict] = []

    if args.evaluate or args.review:
        with_feat = feature_rows(rows)

    if args.evaluate:
        same_inst = [r for r in with_feat if r["same_inst"]]
        cross_inst = [r for r in with_feat if not r["same_inst"]]
        primary = evaluate_protocol(same_inst, "同校同名（主指标）")
        supplementary = evaluate_protocol(cross_inst, "跨校同名（简单负例，仅补充）")
        combined = evaluate_protocol(with_feat, "全部同名组合（含跨校）")

        # 复核后口径：用独立复核（站点归属交叉检验）改写标签
        for r in same_inst:
            r["reviewed_label"] = adjudicate(r, pages)["verdict"]
        reviewed = evaluate_protocol(
            relabel(same_inst, "reviewed_label"), "同校同名（复核后）")

        legacy_pairs, legacy_stats = build_pairs(profiles)
        sample = legacy_pairs
        if args.limit and len(sample) > args.limit:
            import random
            sample = random.Random(args.seed).sample(sample, args.limit)
        legacy_rows = []
        for p in sample:
            a, b = p["i"], p["j"]
            legacy_rows.append({
                "name": p["name"],
                "label": SAME if p["same"] else DIFFERENT,
                "i": a, "j": b,
                "same_inst": a.get("institution") == b.get("institution"),
                "same_dept": a.get("department") == b.get("department"),
                "same_disc": (a.get("first_level_discipline")
                              == b.get("first_level_discipline")),
            })
        legacy_feat = feature_rows(legacy_rows, want_clean=False)
        legacy = evaluate(legacy_feat)
        legacy["skipped_missing_home_groups"] = legacy_stats["skipped_missing_home"]

        comparison = {
            "legacy": {
                "protocol": "两两不同 URL ⇒ 异人（无 unknown 档）",
                "pairs": legacy["pairs"],
                "positives": legacy["positives"],
                "negatives": legacy["negatives"],
                "same_institution_pairs": sum(
                    1 for r in legacy_feat if r["same_inst"]),
                "cross_institution_pairs": sum(
                    1 for r in legacy_feat if not r["same_inst"]),
                "auc_institution": legacy["auc"]["institution_only"],
                "auc_embedding": legacy["auc"]["embedding_only"],
                "baseline_institution": legacy["baseline_institution"],
            },
            "evidence": {
                "protocol": "专属页/名录页分级 + unknown 剔除",
                "pairs_total": stats["pairs_total"],
                "labelled_same_institution": primary["labelled_pairs"],
                "labelled_cross_institution": supplementary["labelled_pairs"],
                "excluded_unknown": primary["excluded_unknown"],
                "auc_institution": primary["auc"]["institution_only"],
                "auc_embedding": primary["auc"]["embedding_only"],
                "baseline_institution": primary["baseline_institution"],
            },
            "verdict": {
                "legacy_negative_share_cross_institution": (
                    sum(1 for r in legacy_feat if not r["same_inst"] and not r["same"])
                    / max(1, legacy["negatives"])),
                "why_overestimated": (
                    "旧协议的负例绝大多数是跨校同名组合——不同学校几乎必然不是同一个人。"
                    "这类简单负例让 AUC 看起来很高，但它衡量的是「能不能把两所学校"
                    "分开」，不是本项目真正要回答的「同校同名是不是同一人」。"
                    "在同校层内，机构特征恒为 True，AUC 直接塌到 0.5。"),
            },
        }

        risky = high_risk(with_feat, pages, threshold=0.85)

        (OUT_DIR / "evaluation.json").write_text(
            json.dumps({
                "primary": primary,
                "reviewed": reviewed,
                "supplementary": supplementary,
                "combined": combined,
                "stats": {
                    "groups": stats["groups"],
                    "pairs_total": stats["pairs_total"],
                    "labels": dict(stats["labels"]),
                    "unknown_reasons": dict(stats["unknown_reasons"]),
                    "groups_with_missing_home": stats["groups_with_missing_home"],
                    "same_institution": dict(stats["same_institution"]),
                    "cross_institution": dict(stats["cross_institution"]),
                },
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        (OUT_DIR / "legacy_evaluation.json").write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        (OUT_DIR / "comparison.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        (OUT_DIR / "high_risk.json").write_text(
            json.dumps(risky, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")

        print(f"主指标（同校同名）：{primary['labelled_pairs']} 对"
              f"（同人 {primary['positives']} / 异人 {primary['negatives']}）；"
              f"AUC 机构 {_f(primary['auc']['institution_only'])} / "
              f"嵌入 {_f(primary['auc']['embedding_only'])}")
        print(f"复核后：{reviewed['labelled_pairs']} 对"
              f"（同人 {reviewed['positives']} / 异人 {reviewed['negatives']}；"
              f"另有 {reviewed['excluded_unknown'] - primary['excluded_unknown']} 对"
              f"由同人降级为待核）；"
              f"AUC 嵌入 {_f(reviewed['auc']['embedding_only'])}")
        print(f"旧协议对照：{legacy['pairs']} 对"
              f"（正例 {legacy['positives']} / 负例 {legacy['negatives']}）；"
              f"AUC 机构 {legacy['auc']['institution_only']:.3f} / "
              f"嵌入 {legacy['auc']['embedding_only']:.3f}")
        print(f"高危误合并 {len(risky)} 对 -> {OUT_DIR / 'high_risk.json'}")

    if args.review:
        queue = review(with_feat, pages)
        (OUT_DIR / "review.json").write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        counts = Counter(i["label"] for i in queue)
        print(f"待核队列 {len(queue)} 对（同人 {counts[SAME]} / "
              f"异人 {counts[DIFFERENT]} / 待核 {counts[UNKNOWN]}）"
              f" -> {OUT_DIR / 'review.json'}")

    if args.gold:
        gold = gold_set(rows, pages, seed=args.seed)
        agreement = gold_agreement(gold)
        report_agreement = agreement
        payload = {
            "schema": "mentor-workbench/gold-pairs/v1",
            "protocol_status": "program-assisted",
            "human_gold_status": "pending",
            "description": (
                "程序辅助核验集：判定字段可由 a/b 内的原始字段直接复现；"
                "verdict 由 adjudicate() 规则给出、auto_label 由 pair_label() 规则给出，"
                "两者都是程序，并非人工标注。人工金标准见 workbench/evaluation/human_annotation/。"),
            "seed": args.seed,
            "protocol": {
                "same_person": "同一专属个人主页 + 同机构 + 站点归属与院系一致",
                "different_person": "两个互不相同的专属主页且院系/一级学科冲突（或跨机构）",
                "unknown": "名录页/缺主页/同院系同学科/站点归属不符 —— 不进入指标",
            },
            "agreement": agreement,
            "pairs": gold,
        }
        (EVAL_DIR / "gold_pairs.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        pd = agreement["verdict_distribution"]
        print(f"复核集 {len(gold)} 对（同人 {pd.get(SAME, 0)} / "
              f"异人 {pd.get(DIFFERENT, 0)} / 待核 {pd.get(UNKNOWN, 0)}）；"
              f"与自动协议一致率 {agreement['agreement']:.3f}"
              f" -> {EVAL_DIR / 'gold_pairs.json'}")

    # 报告要引用「两套规则的一致率」时，必须现场算一遍；样本只依赖规则，不需要嵌入。
    if reviewed is not None and report_agreement is None:
        report_agreement = gold_agreement(gold_set(rows, pages, seed=args.seed))

    lines = _build_report(stats, primary, supplementary, legacy, comparison,
                          risky, queue, len(profiles), reviewed,
                          report_agreement,
                          human_labels.status(EVAL_DIR))
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"报告 -> {OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())