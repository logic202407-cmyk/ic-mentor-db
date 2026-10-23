"""算法评测的只读汇总：把**已入库的真实评测产物**整理成界面可消费的一份 JSON。

设计原则
--------
1. **不现算指标。** 这里只读 `workbench/reference/eval/retrieval.json` 与
   `workbench/evaluation/*.json`——它们是评测脚本在本机实跑后写出的产物。
   界面拿到的每个数字都能在对应产物里找到原始出处，避免"页面上的数字没人知道怎么来的"。
2. **缺产物就明说。** 没跑过评测的干净 clone 上，文件可能不存在；此时返回
   ``available: false`` 并给出复现命令，而不是编造 0 或用旧数字顶上。
3. **口径写在响应里。** 弱监督 qrels、dev/test 划分、阈值只在 dev 上选——这些边界
   跟着数据一起返回，界面必须展示，否则数字会被误读成"人工标注的准确率"。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_EVAL = ROOT / "workbench" / "reference" / "eval"
EVAL_DIR = ROOT / "workbench" / "evaluation"

RETRIEVAL = REFERENCE_EVAL / "retrieval.json"
DIRECTIONS = EVAL_DIR / "direction_validation.json"
DISAMBIGUATION = EVAL_DIR / "disambiguation_eval.json"
SIGNIFICANCE = EVAL_DIR / "significance.json"

METHOD_LABELS = {
    "keyword_substring": "关键词（双字覆盖率，现网基线）",
    "bm25": "BM25（纯 Python 实现）",
    "embedding": "向量检索（bge-small-zh-v1.5）",
    "hybrid_score": "混合（BM25 + 向量，加权）",
    "hybrid_rrf": "混合（BM25 + 向量，RRF 融合）",
    "embedding_instruct": "向量检索 + bge 检索指令（补充基线）",
}


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def summary() -> dict:
    retrieval = _load(RETRIEVAL)
    if not retrieval:
        return {
            "available": False,
            "reason": "还没有可用的检索评测产物",
            "how_to_reproduce": "python -m workbench.retrieval_eval",
            "expected": str(RETRIEVAL.relative_to(ROOT)),
        }

    metrics = retrieval.get("metrics") or {}
    methods = []
    for key, by_split in metrics.items():
        methods.append({
            "key": key,
            "label": METHOD_LABELS.get(key, key),
            "a_test": by_split.get("A/test") or {},
            "b_test": by_split.get("B/test") or {},
            "all_dev": by_split.get("ALL/dev") or {},
            "all_test": by_split.get("ALL/test") or {},
        })
    # 主表的排序固定为「基线 → 单模型 → 混合」，避免前端各自排序导致口径不一。
    order = ["keyword_substring", "bm25", "embedding",
             "embedding_instruct", "hybrid_score", "hybrid_rrf"]
    methods.sort(key=lambda m: order.index(m["key"]) if m["key"] in order else 99)

    filter_eval = retrieval.get("filter_eval") or {}
    payload = {
        "available": True,
        "generated_at": retrieval.get("generated_at"),
        "how_to_reproduce": retrieval.get("how_to_reproduce"),
        "honesty": retrieval.get("honesty"),
        "sources": {
            "retrieval": str(RETRIEVAL.relative_to(ROOT)).replace("\\", "/"),
            "directions": str(DIRECTIONS.relative_to(ROOT)).replace("\\", "/"),
            "disambiguation": str(DISAMBIGUATION.relative_to(ROOT)).replace("\\", "/"),
            "significance": str(SIGNIFICANCE.relative_to(ROOT)).replace("\\", "/"),
        },
        "corpus": retrieval.get("corpus") or {},
        "config": {
            "seed": (retrieval.get("config") or {}).get("seed"),
            "dev_ratio": (retrieval.get("config") or {}).get("dev_ratio"),
            "queries": (retrieval.get("config") or {}).get("queries") or {},
            "chosen": (retrieval.get("config") or {}).get("chosen") or {},
            "return_limit": (retrieval.get("config") or {}).get("return_limit"),
        },
        "retrieval": {
            "methods": methods,
            "filter": {
                "unfiltered_test": filter_eval.get("unfiltered/test") or {},
                "absolute_test": filter_eval.get("absolute/test") or {},
                "margin_test": filter_eval.get("margin/test") or {},
                "combined_test": filter_eval.get("combined/test") or {},
            },
            "latency": retrieval.get("latency") or {},
            "resources": retrieval.get("resources") or {},
            "weight_sweep": retrieval.get("weight_sweep") or [],
            "failures": retrieval.get("analysed_failures") or [],
            "acronyms": retrieval.get("acronym_audit") or {},
            "collisions": retrieval.get("english_collisions") or {},
            "off_topic": retrieval.get("off_topic") or {},
            "degenerate_bias": retrieval.get("degenerate_bias") or {},
        },
        "directions": _load(DIRECTIONS),
        "disambiguation": _load(DISAMBIGUATION),
        "significance": _load(SIGNIFICANCE),
    }
    return payload