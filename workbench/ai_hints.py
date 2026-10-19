"""把 AI 的两处「待复核」结果暴露给界面。

设计原则（与本项目既有口径一致）：

* **建议不是事实**。这里只读已生成的建议产物，**绝不写回** ``direction`` 等原始字段。
* **来源可追溯**。每条建议带 ``score`` 与 ``method``（keyword / embedding），
  同名待核带两边的个人主页地址。
* **缺产物不报错**：产物在 ``.workbench-data/``（gitignore），未跑过推断时接口返回空，
  界面显示"尚未生成"而不是崩掉。

产物格式见 ``workbench/infer_directions.py`` 与 ``workbench/disambiguate_names.py``。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SUGGESTIONS_PATH = Path(".workbench-data/direction-inference/suggestions.json")
REVIEW_PATH = Path(".workbench-data/name-disambiguation/review.json")

DISCLAIMER = ("AI 推断结果，仅供人工复核时参考，不构成事实、不改变参考分、"
              "也不会被自动写入数据。")


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _suggestions_by_id() -> dict[str, dict]:
    payload = _read(SUGGESTIONS_PATH)
    index: dict[str, dict] = {}
    for item in payload.get("suggestions") or []:
        mid = item.get("id")
        if mid:
            index[mid] = item
    return index


@lru_cache(maxsize=1)
def _review_by_id() -> dict[str, list[dict]]:
    payload = _read(REVIEW_PATH)
    index: dict[str, list[dict]] = {}
    if isinstance(payload, list):
        for pair in payload:
            for side in ("a", "b"):
                mid = (pair.get(side) or {}).get("id")
                if mid:
                    index.setdefault(mid, []).append(pair)
    return index


def clear_cache() -> None:
    """产物重新生成后调用。"""
    _suggestions_by_id.cache_clear()
    _review_by_id.cache_clear()


def direction_suggestion(mentor_id: str) -> dict | None:
    item = _suggestions_by_id().get(mentor_id)
    if not item:
        return None
    return {
        "suggested": item.get("suggested"),
        "score": item.get("score"),
        "method": item.get("method"),
        "top3": item.get("top3") or [],
        "passes_threshold": bool(item.get("apply")),
        "disclaimer": DISCLAIMER,
    }


def name_review(mentor_id: str) -> list[dict]:
    """这位导师涉及的同名待核组合（只保留另一方的可核信息）。"""
    out = []
    for pair in _review_by_id().get(mentor_id, []):
        a, b = pair.get("a") or {}, pair.get("b") or {}
        other = b if a.get("id") == mentor_id else a
        out.append({
            "name": pair.get("name"),
            "institution": pair.get("institution"),
            "similarity": pair.get("emb"),
            "verdict": pair.get("verdict"),
            "other": {"dept": other.get("dept"), "home": other.get("home")},
            "disclaimer": DISCLAIMER,
        })
    return out


def summary() -> dict:
    """给界面用的一行概览；产物缺失时各项为 0/None。"""
    payload = _read(SUGGESTIONS_PATH)
    review = _read(REVIEW_PATH)
    return {
        "direction": {
            "available": bool(payload.get("suggestions")),
            "pending": payload.get("pending"),
            "with_text": payload.get("with_text"),
            "would_apply": payload.get("would_apply"),
            "min_score": payload.get("min_score"),
            "by_method": payload.get("by_method") or {},
        },
        "name_review": {
            "available": bool(review),
            "pairs": len(review) if isinstance(review, list) else 0,
        },
        "disclaimer": DISCLAIMER,
    }


def hints_for(mentor_id: str) -> dict:
    """一次取全某位导师的 AI 提示。"""
    return {
        "direction_suggestion": direction_suggestion(mentor_id),
        "name_review": name_review(mentor_id),
        "disclaimer": DISCLAIMER,
    }
