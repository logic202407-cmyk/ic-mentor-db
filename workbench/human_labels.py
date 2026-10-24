"""同名消歧的人工标注：导出盲标表、导入独立判断、按人工标签重算指标。

背景（为什么必须单独做这一层）
------------------------------
仓库里原先的「独立复核集」`gold_pairs.json` 其实是**程序规则**生成的：
`adjudicate()` 用主页类型、站点归属、院系冲突等规则给出 verdict，
`gold_set()` 只是把这些 verdict 整理成样本。它测的是「自动协议与规则复核是否一致」，
**不是**人工金标准，也不能当作 Precision/Recall 的真实来源。

本模块把两件事分开：

1. **导出**：只给证据（姓名/机构/院系/主页/主页类型/配对编号），
   **不含模型分数与自动标签**，保证标注者盲标；
   模型侧的 emb 与自动判定另存 `human_annotation_key.json`，只在评分时使用。
2. **导入**：要求每行都有 ``human_verdict``（same_person / different_person / unknown）、
   ``reviewer`` 与 ``reviewed_at``；缺一项即整批拒绝——
   这样才能挡住「用模型批量填一列然后冒充人工」的做法。
   标签不足（默认 <30 条或正负例任一侧 <5）时只记录状态，**不报告指标**。
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
COLUMNS = [
    "pair_id", "category", "name", "institution",
    "a_id", "a_dept", "a_discipline", "a_home", "a_page_kind",
    "b_id", "b_dept", "b_discipline", "b_home", "b_page_kind",
    "human_verdict", "human_confidence", "reviewer", "reviewed_at",
    "evidence_note",
]
MIN_LABELS = 30
MIN_PER_CLASS = 5


def pair_id(a_id: str, b_id: str) -> str:
    joined = "\0".join(sorted([a_id, b_id]))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


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
        item = {
            "pair_id": pair_id(row["i"]["id"], row["j"]["id"]),
            "category": _category(row, adj),
            "name": row["name"],
            "institution": row["i"].get("institution") or "",
            "a_id": row["i"]["id"], "a_dept": row["i"].get("department") or "",
            "a_discipline": row["i"].get("first_level_discipline") or "",
            "a_home": row["i"].get("homepage") or "",
            "a_page_kind": row["page_a"],
            "b_id": row["j"]["id"], "b_dept": row["j"].get("department") or "",
            "b_discipline": row["j"].get("first_level_discipline") or "",
            "b_home": row["j"].get("homepage") or "",
            "b_page_kind": row["page_b"],
            "human_verdict": "", "human_confidence": "", "reviewer": "",
            "reviewed_at": "", "evidence_note": "",
            "_program_label": row["label"],
            "_program_verdict": adj["verdict"],
            "_emb": row.get("emb"),
            "_reason": row.get("reason") or "",
        }
        buckets.setdefault(item["category"], []).append(item)
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
        "note": "盲标用：本文件含模型分数与自动判定，标注者不得查看。",
        "items": {item["pair_id"]: {
            "emb": item["_emb"], "program_label": item["_program_label"],
            "program_verdict": item["_program_verdict"], "reason": item["_reason"],
            "category": item["category"], "name": item["name"],
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


def import_labels(path: Path, *, out_dir: Path, min_labels: int = MIN_LABELS) -> dict:
    """导入人工判断。缺 reviewer/日期、未知判定或伪造空行都会被拒绝。"""
    rows = _read_rows(path)
    labels: list[dict] = []
    problems: list[str] = []
    for index, row in enumerate(rows, start=2):
        verdict = (row.get("human_verdict") or "").strip()
        if not verdict:
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
            "pair_id": row["pair_id"].strip(), "verdict": verdict,
            "reviewer": reviewer, "reviewed_at": reviewed_at,
            "confidence": confidence or None,
            "note": (row.get("evidence_note") or "").strip()[:500],
            "name": row.get("name", ""), "category": row.get("category", ""),
        })
    if problems:
        raise ValueError("；".join(problems[:5]) + ("…" if len(problems) > 5 else ""))
    if not labels:
        raise ValueError("没有可导入的人工判断（human_verdict 全为空）")

    key_path = Path(path).with_name(Path(path).stem + "-key.json")
    key = {}
    if key_path.is_file():
        key = (json.loads(key_path.read_text(encoding="utf-8")).get("items") or {})
    for item in labels:
        meta = key.get(item["pair_id"]) or {}
        item["emb"] = meta.get("emb")
        item["program_label"] = meta.get("program_label")
        item["program_verdict"] = meta.get("program_verdict")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mentor-workbench/human-labels/v1",
        "protocol_status": "human-collected",
        "labels": labels,
        "counts": dict(Counter(item["verdict"] for item in labels)),
        "reviewers": sorted({item["reviewer"] for item in labels}),
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
    usable = [item for item in labels if item["verdict"] in (SAME, DIFFERENT)]
    positives = sum(1 for item in usable if item["verdict"] == SAME)
    negatives = len(usable) - positives
    status = ("ready" if len(usable) >= min_labels
              and positives >= MIN_PER_CLASS and negatives >= MIN_PER_CLASS
              else "insufficient")
    out = {
        "protocol_status": payload.get("protocol_status", "human-collected"),
        "labelled_total": len(labels),
        "usable_pairs": len(usable),
        "unknown": len(labels) - len(usable),
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

    def prf(predicate) -> dict:
        tp = sum(1 for item in usable if item["verdict"] == SAME and predicate(item))
        fp = sum(1 for item in usable if item["verdict"] == DIFFERENT and predicate(item))
        fn = positives - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
                "recall": recall, "f1": f1}

    program = prf(lambda item: item.get("program_label") == SAME)
    thresholds = []
    for threshold in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
        row = prf(lambda item, t=threshold: (item.get("emb") or 0) >= t)
        row["emb>="] = threshold
        thresholds.append(row)
    out.update({"program_rule": program, "embedding_thresholds": thresholds})
    return out


def status(out_dir: Path) -> dict:
    path = Path(out_dir) / "human_labels.json"
    if not path.is_file():
        return {"protocol_status": "pending",
                "note": "尚未收集人工独立判断；先导出盲标表并请至少两位标注者完成。"}
    return json.loads(path.read_text(encoding="utf-8")).get("counts", {}) | {
        "protocol_status": "human-collected"}