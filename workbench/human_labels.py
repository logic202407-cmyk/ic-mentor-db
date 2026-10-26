"""同名消歧的人工标注：导出盲标表、导入独立判断、按人工标签重算指标。

背景（为什么必须单独做这一层）
------------------------------
仓库里原先的「独立复核集」`gold_pairs.json` 其实是**程序规则**生成的：
`adjudicate()` 用主页类型、站点归属、院系冲突等规则给出 verdict，
`gold_set()` 只是把这些 verdict 整理成样本。它测的是「自动协议与规则复核是否一致」，
**不是**人工金标准，也不能当作 Precision/Recall 的真实来源。

本模块把两件事分开：

1. **导出**：只给证据（配对编号、两侧姓名/机构/院系/学科/主页/主页类型/来源 URL），
   **不含模型分数、不含自动标签、也不含 ``category``**，保证标注者盲标。
   ``category`` 由 ``adjudicate()`` 的结论派生（形如 ``shared_homepage_unit_mismatch``、
   ``listing_page``），给了它等于把程序的身份结论写在标注者眼前，因此只写进评分键
   （内部分层抽样需要），不进盲标表。可见字段清单见 :data:`BLIND_FIELDS`。
2. **导入**：要求每行都有 ``human_verdict``（same_person / different_person / unknown）、
   ``reviewer`` 与 ``reviewed_at``；缺一项即整批拒绝——
   这样才能挡住「用模型批量填一列然后冒充人工」的做法。
   标签不足（默认 <30 条或正负例任一侧 <5）时只记录状态，**不报告指标**。

3. **合并**：同一个 ``pair_id`` 的多份标注（协议建议两位标注者）只算**一条**独立真值。
   不合并的话，15 对 × 2 人 = 30 行就能跨过 30 对门槛，样本量凭空翻倍。
   两位标注者判定相反时记为 ``conflict`` 并降为 ``unknown``，不进入指标。

4. **不编造指标**：评分用键（含程序判定与嵌入分数）缺失时，
   ``program_rule`` / ``embedding_thresholds`` 一律置 ``null``——
   「没测」不能显示成「测出来精确率 0.0」。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from . import catalog
from .disambiguate_names import (
    DIFFERENT, SAME, UNKNOWN, PageIndex, adjudicate, build_evidence_pairs,
)

VERDICTS = {SAME, DIFFERENT, UNKNOWN}
CONFIDENCES = {"low", "medium", "high", ""}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

#: 盲标者**可见**的全部字段：只有公开证据本身。
#:
#: 明确排除以下由程序判定派生的字段，否则「盲标」名不副实：
#:
#: - ``category``：由 :func:`_category` 依据 ``adjudicate()`` 的结论派生，
#:   取值形如 ``shared_homepage_unit_mismatch`` / ``listing_page``——
#:   等于把程序的身份结论写在标注者眼前；
#: - ``emb`` / ``program_label`` / ``program_verdict``：模型分数与自动判定，
#:   只存评分键文件，标注者不可见。
#:
#: ``a_page_kind`` / ``b_page_kind`` 保留：它是对「公开 URL 与来源标题」这条
#: **可复核证据**的确定性归类（名录页 / 专属页 / 未收录），不是身份判断；
#: 人工标注时正需要知道「这一页是不是本人专属页」。
BLIND_FIELDS = [
    "pair_id",
    "a_name", "a_institution", "a_dept", "a_discipline",
    "a_home", "a_page_kind", "a_source_urls",
    "b_name", "b_institution", "b_dept", "b_discipline",
    "b_home", "b_page_kind", "b_source_urls",
]
#: 标注者要填写的字段（缺任一必填项整批拒绝）。
ANNOTATION_FIELDS = [
    "human_verdict", "human_confidence", "reviewer", "reviewed_at",
    "evidence_note",
]
#: 盲标表的完整表头 = 可见证据 + 待填字段。**不含 category。**
COLUMNS = BLIND_FIELDS + ANNOTATION_FIELDS
MIN_LABELS = 30
MIN_PER_CLASS = 5


def pair_id(a_id: str, b_id: str) -> str:
    joined = "\0".join(sorted([a_id, b_id]))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _source_urls(profile: dict) -> str:
    """该记录登记过的来源 URL（分号分隔），供标注者自己打开核对。"""
    urls = []
    for source in profile.get("sources") or []:
        url = (source or {}).get("url") or ""
        if url and url not in urls:
            urls.append(url)
    return "；".join(urls[:5])


def _category(row: dict, adjudged: dict) -> str:
    """把困难样本分成可解释的几类，便于人工按类别复核。"""
    pages = {row["page_a"], row["page_b"]}
    home_a = (row["i"].get("homepage") or "").strip()
    home_b = (row["j"].get("homepage") or "").strip()
    if "roster" in pages:
        return "listing_page"
    if adjudged.get("unit_owner"):
        return "shared_homepage_unit_mismatch"
    if home_a and home_a == home_b:
        return ("shared_homepage_cross_dept" if not row["same_dept"]
                else "shared_homepage")
    if pages == {"personal"}:
        return "distinct_personal"
    if "none" in pages:
        return "missing_homepage"
    return "mixed_page"


def candidates(rows: list[dict], pages: PageIndex, per_category: int = 60) -> list[dict]:
    """从同名组合里挑「同校同名」的困难样本，按类别限流，避免某一类淹没标注表。"""
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        if not row["same_inst"]:
            continue
        adj = adjudicate(row, pages)
        category = _category(row, adj)
        item = {
            "pair_id": pair_id(row["i"]["id"], row["j"]["id"]),
            # category 只写进 key（内部分层抽样用），**不写进盲标表**。
            "category": category,
            "a_name": row["i"].get("name") or row["name"],
            "a_institution": row["i"].get("institution") or "",
            "a_dept": row["i"].get("department") or "",
            "a_discipline": row["i"].get("first_level_discipline") or "",
            "a_home": row["i"].get("homepage") or "",
            "a_page_kind": row["page_a"],
            "a_source_urls": _source_urls(row["i"]),
            "b_name": row["j"].get("name") or row["name"],
            "b_institution": row["j"].get("institution") or "",
            "b_dept": row["j"].get("department") or "",
            "b_discipline": row["j"].get("first_level_discipline") or "",
            "b_home": row["j"].get("homepage") or "",
            "b_page_kind": row["page_b"],
            "b_source_urls": _source_urls(row["j"]),
            "human_verdict": "", "human_confidence": "", "reviewer": "",
            "reviewed_at": "", "evidence_note": "",
            "_program_label": row["label"],
            "_program_verdict": adj["verdict"],
            "_emb": row.get("emb"),
            "_reason": row.get("reason") or "",
            # 记录 id 只留在 key 里，便于复核时回查原始记录；盲标表不出现 id。
            "_a_id": row["i"]["id"], "_b_id": row["j"]["id"],
        }
        buckets.setdefault(category, []).append(item)
    chosen: list[dict] = []
    for category in sorted(buckets):
        chosen.extend(buckets[category][:per_category])
    # 同一 pair 只出现一次（不同组可能重复），按 pair_id 去重
    seen: set[str] = set()
    unique = []
    for item in chosen:
        if item["pair_id"] in seen:
            continue
        seen.add(item["pair_id"])
        unique.append(item)
    return unique


def export(path: Path, *, data_dir: Path | None = None, per_category: int = 60) -> dict:
    profiles, _by_id, _raw, _net = catalog.static_catalog()
    pages = PageIndex(profiles)
    rows, stats = build_evidence_pairs(profiles, pages)
    items = candidates(rows, pages, per_category=per_category)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow(item)
    key = {
        "schema": "mentor-workbench/human-annotation-key/v1",
        "note": ("内部评分键：含模型分数、自动判定与分层类别，标注者**不得查看**。"
                 "盲标表（annotation-template.csv）不含其中任何一项。"),
        "blind_fields": list(BLIND_FIELDS),
        "held_back_fields": ["category", "emb", "program_label",
                             "program_verdict", "reason", "name", "a_id", "b_id"],
        "items": {item["pair_id"]: {
            "emb": item["_emb"], "program_label": item["_program_label"],
            "program_verdict": item["_program_verdict"], "reason": item["_reason"],
            # category 留在 key 里：内部分层抽样与统计需要，但不给标注者看。
            "category": item["category"],
            "name": item["a_name"],
            "a_id": item.get("_a_id", ""), "b_id": item.get("_b_id", ""),
        } for item in items},
    }
    key_path = path.with_name(path.stem + "-key.json")
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    return {"template": str(path), "key": str(key_path), "pairs": len(items),
            "categories": dict(Counter(item["category"] for item in items)),
            "groups": stats["groups"], "pairs_total": stats["pairs_total"]}


def _read_rows(path: Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"标注表缺少列：{missing}")
        return list(reader)


def _parse_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _merge_judgements(judged: list[dict]) -> tuple[list[dict], list[str]]:
    """把同一对的多份人工判断合并成**一条独立真值**，并标出争议。

    为什么必须合并
    --------------
    协议本身建议「至少两位标注者完成」，于是同一个 ``pair_id`` 会自然地出现多行。
    如果每一行都算一条独立真值，15 对 × 2 位标注者 = 30 行，就能直接跨过
    ``MIN_LABELS`` 门槛——这是**用重复计数冒充足够的标注量**，会让原本不足 30 对
    的人工金标准被报成「ready」。样本量也是假的：真正独立的判断只有 15 对。

    同一对被不同标注者判成相反结论时，两边都不算真值：记为 ``conflict``，
    判定降为 ``unknown``（不进入任何指标），由人工先行裁决。
    同一位标注者针对同一对留下互相矛盾的两行，同样按争议处理。
    """
    grouped: dict[str, list[dict]] = {}
    for item in judged:
        grouped.setdefault(item["pair_id"], []).append(item)

    merged: list[dict] = []
    conflicts: list[str] = []
    for pair in sorted(grouped):
        items = grouped[pair]
        by_reviewer: dict[str, set[str]] = {}
        for item in items:
            by_reviewer.setdefault(item["reviewer"], set()).add(item["verdict"])
        verdicts = sorted({verdict for votes in by_reviewer.values() for verdict in votes})
        inconsistent = any(len(votes) > 1 for votes in by_reviewer.values())
        conflict = len(verdicts) > 1 or inconsistent or not verdicts
        if conflict:
            conflicts.append(pair)
        notes = [item["note"] for item in items if item["note"]]
        confidences = [item["confidence"] for item in items if item["confidence"]]
        merged.append({
            "pair_id": pair,
            # 争议对不给任何一侧盖章：降为 unknown，等人工裁决
            "verdict": UNKNOWN if conflict else verdicts[0],
            "verdicts": verdicts,
            "conflict": conflict,
            "reviewers": sorted(by_reviewer),
            "reviewed_at": max(item["reviewed_at"] for item in items),
            "confidence": (max(confidences, key=lambda value: CONFIDENCE_ORDER[value])
                           if confidences else None),
            "note": " / ".join(notes)[:500],
            "name": items[0]["name"], "category": items[0]["category"],
        })
    return merged, conflicts


def import_labels(path: Path, *, out_dir: Path, min_labels: int = MIN_LABELS) -> dict:
    """导入人工判断。缺 reviewer/日期、未知判定或伪造空行都会被拒绝。"""
    rows = _read_rows(path)
    labels: list[dict] = []
    problems: list[str] = []
    for index, row in enumerate(rows, start=2):
        verdict = (row.get("human_verdict") or "").strip()
        if not verdict:
            continue
        pair = (row.get("pair_id") or "").strip()
        if not pair:
            problems.append(f"第 {index} 行：缺少 pair_id，无法与配对证据对应")
            continue
        if verdict not in VERDICTS:
            problems.append(f"第 {index} 行：未知判定 {verdict!r}")
            continue
        reviewer = (row.get("reviewer") or "").strip()
        reviewed_at = (row.get("reviewed_at") or "").strip()
        if not reviewer:
            problems.append(f"第 {index} 行：缺少 reviewer（人工判断必须可追溯）")
            continue
        if not _parse_date(reviewed_at):
            problems.append(f"第 {index} 行：reviewed_at 必须是 YYYY-MM-DD")
            continue
        confidence = (row.get("human_confidence") or "").strip()
        if confidence not in CONFIDENCES:
            problems.append(f"第 {index} 行：human_confidence 只能是 low/medium/high")
            continue
        labels.append({
            "pair_id": pair, "verdict": verdict,
            "reviewer": reviewer, "reviewed_at": reviewed_at,
            "confidence": confidence or None,
            "note": (row.get("evidence_note") or "").strip()[:500],
            # 盲标表已不含 name/category（category 属程序派生，不能给标注者看）；
            # 它们在内部分层与统计中仍需要，从评分键补齐。
            "name": row.get("name", ""), "category": row.get("category", ""),
        })
    if problems:
        raise ValueError("；".join(problems[:5]) + ("…" if len(problems) > 5 else ""))
    if not labels:
        raise ValueError("没有可导入的人工判断（human_verdict 全为空）")

    # 同一对的多份标注合并成一条独立真值，否则重复计数会虚增样本量。
    labels, conflicts = _merge_judgements(labels)

    key_path = Path(path).with_name(Path(path).stem + "-key.json")
    key = {}
    if key_path.is_file():
        key = (json.loads(key_path.read_text(encoding="utf-8")).get("items") or {})
    for item in labels:
        meta = key.get(item["pair_id"]) or {}
        item["emb"] = meta.get("emb")
        item["program_label"] = meta.get("program_label")
        item["program_verdict"] = meta.get("program_verdict")
        # 盲标表不含这两个字段；分层统计仍需要，从评分键补齐（缺失则留空）。
        item["name"] = item.get("name") or meta.get("name") or ""
        item["category"] = item.get("category") or meta.get("category") or ""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mentor-workbench/human-labels/v1",
        "protocol_status": "human-collected",
        "labels": labels,
        "counts": dict(Counter(item["verdict"] for item in labels)),
        "judgements": sum(len(item["reviewers"]) for item in labels),
        "distinct_pairs": len(labels),
        "conflicts": conflicts,
        "reviewers": sorted({name for item in labels for name in item["reviewers"]}),
    }
    (out_dir / "human_labels.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    summary = metrics(payload, min_labels=min_labels)
    (out_dir / "human_metrics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return summary


def metrics(payload: dict, *, min_labels: int = MIN_LABELS) -> dict:
    labels = payload.get("labels") or []
    # 一个 pair_id 只算一条真值：同一对的多位标注已在 _merge_judgements 合并。
    conflicted = [item for item in labels if item.get("conflict")]
    usable = [item for item in labels
              if item["verdict"] in (SAME, DIFFERENT) and not item.get("conflict")]
    positives = sum(1 for item in usable if item["verdict"] == SAME)
    negatives = len(usable) - positives
    status = ("ready" if len(usable) >= min_labels
              and positives >= MIN_PER_CLASS and negatives >= MIN_PER_CLASS
              else "insufficient")
    out = {
        "protocol_status": payload.get("protocol_status") or "unknown",
        "labelled_total": len(labels),
        "usable_pairs": len(usable),
        "unknown": len(labels) - len(usable) - len(conflicted),
        "conflicts": len(conflicted),
        "positives": positives, "negatives": negatives,
        "reviewers": payload.get("reviewers") or [],
        "status": status,
        "note": ("人工金标准尚未达到最小规模，不报告 Precision/Recall/F1。"
                 if status != "ready" else
                 "以下指标基于人工独立判断，不是程序规则复核。"),
    }
    if status != "ready":
        out["needed"] = {"min_labels": min_labels, "min_per_class": MIN_PER_CLASS}
        return out

    def prf(items: list[dict], predicate) -> dict:
        """只在**确实带着该列取值**的样本上算指标，分母也随之收敛。"""
        pos = [item for item in items if item["verdict"] == SAME]
        tp = sum(1 for item in pos if predicate(item))
        fp = sum(1 for item in items if item["verdict"] == DIFFERENT and predicate(item))
        fn = len(pos) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
                "recall": recall, "f1": f1}

    # 评分用键（含程序判定与嵌入分数）可能整份缺失：此时**不能**拿 0 当真值去算，
    # 否则会输出一整张「精确率 0.0」的假指标。缺什么就把什么标成 None。
    program_items = [item for item in usable
                     if item.get("program_label") in (SAME, DIFFERENT)]
    embedding_items = [item for item in usable if item.get("emb") is not None]

    out["program_rule"] = (
        prf(program_items, lambda item: item.get("program_label") == SAME)
        if program_items else None)
    out["program_rule_pairs"] = len(program_items)
    out["program_rule_missing"] = len(usable) - len(program_items)

    if embedding_items:
        thresholds = []
        for threshold in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
            row = prf(embedding_items,
                      lambda item, t=threshold: float(item["emb"]) >= t)
            row["emb>="] = threshold
            thresholds.append(row)
        out["embedding_thresholds"] = thresholds
    else:
        out["embedding_thresholds"] = None
    out["embedding_pairs"] = len(embedding_items)
    out["embedding_missing"] = len(usable) - len(embedding_items)

    if not program_items or not embedding_items:
        out["metrics_note"] = (
            "评分用键（<标注表>-key.json）缺失或不完整：无法测量的指标一律置为 null，"
            "不输出 0.0，避免把「没测」显示成「测出来很差」。")
    return out


def status(out_dir: Path) -> dict:
    path = Path(out_dir) / "human_labels.json"
    if not path.is_file():
        return {"protocol_status": "pending",
                "note": "尚未收集人工独立判断；先导出盲标表并请至少两位标注者完成。"}
    stored = json.loads(path.read_text(encoding="utf-8"))
    return stored.get("counts", {}) | {
        "protocol_status": "human-collected",
        "distinct_pairs": stored.get("distinct_pairs"),
        "conflicts": len(stored.get("conflicts") or []),
    }