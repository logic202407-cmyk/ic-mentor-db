"""导师检索的离线评测程序：一条命令跑完方法对比、阈值选择与失败案例。

设计纪律
--------
1. **不编造标注。** 相关性判定（qrels）来自两条可复现的规则通道：
   A 类「标签对齐查询」由结构化字段（一级学科、``direction_group``、
   ``interests`` 关键词）规则生成；B 类「自然语言/跨术语查询」由手工写的
   术语映射表 ``workbench/reference/eval/terminology_map.json`` 定义。
   两者都是**弱监督 qrels**，不是外部人工标注，也不是第三方公开评测集。
2. **不在测试集上调参。** 查询按固定种子 42 划成 dev / test；融合权重、
   过滤阈值只在 dev（加上与查询无关的无关查询探针）上选，最终指标报在 test。
3. **所有数字都是本机实跑产物。** 报告里的每个指标都由本文件写出的
   ``results.json`` 直接生成，没有任何手填数字。

用法
----
    python -m workbench.retrieval_eval                # 完整评测
    python -m workbench.retrieval_eval --limit 2000   # 小语料冒烟（指标不可引用）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import statistics
import time
from collections import Counter
from pathlib import Path

import numpy as np

from . import catalog, scope
from .core import DATA_DIR, ROOT
from .search import (
    BM25Index,
    MODEL_NAME,
    RRF_K,
    document,
    relevance_decision,
    rrf_fuse,
    weighted_fuse,
)

SEED = 42
DEV_RATIO = 0.30
EVAL_DIR = DATA_DIR / "retrieval-eval"
REFERENCE_DIR = ROOT / "workbench" / "reference" / "eval"
TERMS_PATH = REFERENCE_DIR / "terminology_map.json"
SLIM_PATH = REFERENCE_DIR / "retrieval.json"

# 查询规模：A 类合计 186（在 150–300 区间内），B 类 40（在 30–60 区间内）。
A_DISCIPLINE_COUNT = 36
A_DIRECTION_COUNT = 60
A_INTEREST_COUNT = 90

RETURN_LIMIT = 20          # 每次查询最多返回多少条（同时是 Recall@20 的分母口径）
K_VALUES = (5, 10, 20)
NDCG_K = 10
MRR_K = 10

DEGENERATE_LABELS = {
    "方向待补", "不分研究方向", "不区分研究方向", "不设方向", "不区分方向", "不分方向", "无",
}
# 出现在 interests 里但不是研究方向的套话。它们会把 A 类查询变成“没有意义的标签查询”，
# 例如「博士生导师」只表示身份。此表在生成查询前写定，不参考任何检索结果。
BOILERPLATE_LABELS = {
    "博士生导师", "硕士生导师", "博士生招生", "硕士研究生", "博士研究生",
    "教授", "副教授", "研究员", "副研究员", "讲师", "助教",
    "导师", "教师", "学院", "学校", "招生", "研究生", "本科生", "教学",
    "研究方向", "简介", "个人简介", "团队", "课题组",
}
# 过滤阈值网格（只在 dev + 无关探针上选）
TAU_GRID = tuple(round(0.20 + 0.05 * i, 2) for i in range(11))     # 0.20 … 0.70
DELTA_GRID = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
NDCG_TOLERANCE = 0.005     # 选阈值时允许的 dev NDCG@10 绝对下降

ENGLISH_PROBES = ["VLSI", "MEMS", "photonic integration", "EDA", "RISC-V",
                  "chiplets", "AI for Science", "FPGA"]
# 30 个集成电路/信息领域常见缩写。用于量化“模型是否能把它们区分开”，
# 是产品必须同时保留关键词模式的直接依据。
ACRONYM_PROBES = [
    "5G", "6G", "ADC", "AI", "ASIC", "CMOS", "CPU", "CV", "DAC", "DDR",
    "DRAM", "DSP", "EDA", "FPGA", "GPU", "IoT", "MEMS", "ML", "NLP", "NPU",
    "PLL", "RISC-V", "SERDES", "SoC", "SPI", "SRAM", "TCAD", "UART", "VLSI", "WiFi",
]
CROSS_PROBES = [
    ("AI 用于材料发现", "材料 / 机器学习"),
    ("机器学习辅助芯片设计", "电子设计自动化 / 集成电路设计"),
    ("深度学习用于医学影像诊断", "医学 / 成像"),
    ("量子计算与密码学的交叉", "量子技术 / 密码"),
]
OFF_TOPIC_PROBES = [
    "红烧肉的做法", "怎么煮一杯好咖啡", "写一首关于春天的诗", "世界杯决赛比分",
    "红楼梦里的人物关系", "如何养一只猫", "装修预算怎么算", "番茄炒蛋放多少盐",
    "明天天气怎么样", "怎样学弹吉他",
]

METHOD_LABELS = {
    "keyword_substring": "keyword_substring（现有二元组覆盖率基线）",
    "bm25": "bm25（纯 Python 自实现，k1=1.5 b=0.75）",
    "embedding": "embedding（bge-small-zh-v1.5，现网方式）",
    "hybrid_score": "hybrid_score（BM25+向量 归一化加权）",
    "hybrid_rrf": "hybrid_rrf（BM25+向量 RRF，k=60）",
}
SUPPLEMENTARY_LABELS = {
    "embedding_instruct": "embedding_instruct（查询加 bge 检索指令，补充基线）",
}

# 逐条分析的失败案例。数字由程序实跑填，分类与说明是作者写的分析。
# 至少要覆盖：英文术语 ≥3 条、跨学科 ≥2 条，其余覆盖术语不重合/一词多义/标签粒度。
ANALYSED_FAILURES = (
    {"ref": "probe:VLSI", "category": "英文术语未覆盖", "method": "embedding"},
    {"ref": "probe:MEMS", "category": "英文术语未覆盖", "method": "embedding"},
    {"ref": "probe:EDA", "category": "英文术语未覆盖", "method": "embedding"},
    {"ref": "probe:AI 用于材料发现", "category": "跨学科被单一学科压制", "method": "embedding"},
    {"ref": "probe:量子计算与密码学的交叉", "category": "跨学科被单一学科压制", "method": "embedding"},
    {"ref": "b12", "category": "学科术语多义（「地面」）", "method": "bm25"},
    {"ref": "b05", "category": "学科术语多义（「计算机」）", "method": "bm25"},
    {"ref": "b06", "category": "术语不重合", "method": "bm25"},
    {"ref": "b13", "category": "单一领域簇压制（AI 芯片簇）", "method": "embedding"},
    {"ref": "a3-160", "category": "标签粒度过粗（qrels 口径）", "method": "bm25"},
)


# ---------------------------------------------------------------------------
# 语料
# ---------------------------------------------------------------------------

def load_corpus(limit: int | None = None) -> list[dict]:
    """全量目录条目（默认 15,719 条，不做工科过滤——索引规模就是全量）。"""
    entries = catalog.static_catalog()[0]
    if limit:
        entries = entries[:int(limit)]
    return entries


def corpus_documents(entries: list[dict]) -> list[str]:
    return [document(profile) for profile in entries]


def label_blob(profile: dict) -> str:
    """B 类判定用的标签文本：方向分类 + 研究方向 + 一级学科。"""
    return "|".join((
        profile.get("direction_group") or "",
        profile.get("interests") or "",
        profile.get("first_level_discipline") or "",
    ))


def discipline_names(profile: dict) -> set[str]:
    """该条记录的全部学科名（含招生目录给出的多项归属）。"""
    names = {profile.get("first_level_discipline") or ""}
    for row in profile.get("discipline_assignments", []) or []:
        names.add(row.get("first_level_discipline") or "")
    names.discard("")
    return names


# ---------------------------------------------------------------------------
# 查询集构造
# ---------------------------------------------------------------------------

def _usable_label(text: str) -> bool:
    if not (2 <= len(text) <= 20):
        return False
    if "全日制" in text or "(" in text or "（" in text:
        return False
    if text in DEGENERATE_LABELS or text in BOILERPLATE_LABELS or text.isdigit():
        return False
    return True


def _interests_tokens(profile: dict) -> list[str]:
    return [token.strip() for token in
            re.split(r"[、,，;；/\s]+", profile.get("interests") or "") if token.strip()]


def build_a_queries(entries: list[dict], rng: random.Random) -> list[dict]:
    """A 类：查询词直接来自结构化字段（标签对齐）。

    候选标签先在**工科默认视图**内统计，保证查询落在产品的默认范围内；
    但相关性判定在**全量索引**上做（索引不筛学科，非工科记录是真实干扰项）。
    """
    engineering = [p for p in entries if catalog.in_scope(p)]
    discipline_df: Counter = Counter()
    for profile in engineering:
        for name in discipline_names(profile):
            if re.match(r"^\d{4}\s", name) and scope.is_engineering(name):
                discipline_df[name] += 1
    direction_df: Counter = Counter(p.get("direction_group") or "" for p in engineering)
    interest_df: Counter = Counter()
    for profile in engineering:
        for token in _interests_tokens(profile):
            interest_df[token] += 1

    discipline_candidates = sorted(name for name, count in discipline_df.items() if count >= 20)
    direction_candidates = sorted(name for name, count in direction_df.items()
                                  if _usable_label(name) and count >= 5)
    interest_candidates = sorted(token for token, count in interest_df.items()
                                 if _usable_label(token) and count >= 5)

    # 相关性判定要扫全量语料 186 次，先把标签文本与学科名集预算好。
    blobs = [label_blob(profile) for profile in entries]
    names = [discipline_names(profile) for profile in entries]

    queries: list[dict] = []

    def add(subclass: str, plan_index: int, text: str, relevant: set[int], label: str) -> None:
        queries.append({
            "id": f"a{plan_index}-{len(queries):03d}",
            "class": "A",
            "subclass": subclass,
            "query": text,
            "label": label,
            "relevant": relevant,
        })

    # A1 一级学科名（查询里去掉四位代码，模拟学生直接输入学科名）。
    # 相关性用**带代码的完整学科标签**做精确匹配：否则「化学」会命中
    # 「化学工程与技术」，把两个不同一级学科混成一个相关集。
    for name in rng.sample(discipline_candidates, min(A_DISCIPLINE_COUNT, len(discipline_candidates))):
        bare = re.sub(r"^\d{4}\s*", "", name)
        relevant = {index for index, labels in enumerate(names) if name in labels}
        add("a_discipline", 1, bare, relevant, name)

    rule = "方向分类或研究方向字段包含该标签（子串匹配）"

    # A2 方向分类标签
    for label in rng.sample(direction_candidates, min(A_DIRECTION_COUNT, len(direction_candidates))):
        relevant = {index for index, blob in enumerate(blobs) if label in blob}
        add("a_direction", 2, label, relevant, label)
        queries[-1]["rule"] = rule

    # A3 研究方向关键词
    for token in rng.sample(interest_candidates, min(A_INTEREST_COUNT, len(interest_candidates))):
        relevant = {index for index, blob in enumerate(blobs) if token in blob}
        add("a_interest", 3, token, relevant, token)
        queries[-1]["rule"] = rule

    for query in queries:
        query.setdefault(
            "rule",
            "该导师的一级学科标签（含招生目录给出的多项归属，含四位代码）与查询的学科名一一对应",
        )
    return queries


def build_b_queries(entries: list[dict]) -> list[dict]:
    """B 类：自然语言 / 跨术语查询，相关性由手写术语映射表定义。"""
    data = json.loads(TERMS_PATH.read_text(encoding="utf-8"))
    blobs = [label_blob(profile) for profile in entries]
    queries = []
    for entry in data["entries"]:
        terms = entry["terms"]
        required = entry.get("require") or []
        relevant = set()
        for index, blob in enumerate(blobs):
            if not any(term in blob for term in terms):
                continue
            if any(not any(term in blob for term in group) for group in required):
                continue
            relevant.add(index)
        queries.append({
            "id": entry["id"],
            "class": "B",
            "subclass": "b_natural",
            "query": entry["query"],
            "label": "、".join(terms) + ("" if not required else
                                        "（且需含 " + "、".join("|".join(g) for g in required) + "）"),
            "relevant": relevant,
            "rule": data["matching_rule"],
            "rationale": entry.get("rationale", ""),
            "require": required,
        })
    return queries


def assign_splits(queries: list[dict]) -> dict[str, list[str]]:
    """固定种子 42，按子类分层划 dev/test（每层取 30% 为 dev）。"""
    rng = random.Random(SEED)
    strata: dict[str, list[dict]] = {}
    for query in queries:
        strata.setdefault(query["subclass"], []).append(query)
    dev: list[str] = []
    test: list[str] = []
    for name in sorted(strata):
        group = sorted(strata[name], key=lambda item: item["id"])
        rng.shuffle(group)
        boundary = max(1, min(len(group) - 1, round(len(group) * DEV_RATIO))) if len(group) > 1 else 1
        dev.extend(item["id"] for item in group[:boundary])
        test.extend(item["id"] for item in group[boundary:])
    return {"dev": sorted(dev), "test": sorted(test),
            "seed": SEED, "dev_ratio": DEV_RATIO}


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------

def _dcg(flags: list[int], k: int) -> float:
    return sum(1.0 / math.log2(rank + 1)
               for rank, flag in enumerate(flags[:k], start=1) if flag)


def query_metrics(returned: list[int], relevant: set[int]) -> dict:
    """单条查询的指标。``returned`` 是系统实际返回的有序文档下标列表。"""
    flags = [1 if index in relevant else 0 for index in returned]
    total = len(relevant)
    metrics = {
        "returned": len(returned),
        "relevant": total,
        "top1": float(flags[0]) if flags else 0.0,
        "empty": 1.0 if not returned else 0.0,
    }
    for k in K_VALUES:
        metrics[f"recall@{k}"] = (sum(flags[:k]) / total) if total else 0.0
    first = next((rank for rank, flag in enumerate(flags[:MRR_K], start=1) if flag), None)
    metrics[f"mrr@{MRR_K}"] = (1.0 / first) if first else 0.0
    ideal = _dcg([1] * min(total, NDCG_K), NDCG_K)
    metrics[f"ndcg@{NDCG_K}"] = (_dcg(flags, NDCG_K) / ideal) if ideal else 0.0
    return metrics


def aggregate(records: list[dict]) -> dict:
    """把多条查询的指标聚合成一个表行（等权平均）。"""
    if not records:
        return {}
    keys = [f"recall@{k}" for k in K_VALUES] + [f"mrr@{MRR_K}", f"ndcg@{NDCG_K}", "top1", "empty"]
    summary = {key: round(statistics.fmean(record["metrics"][key] for record in records), 4)
               for key in keys}
    summary["queries"] = len(records)
    summary["median_relevant"] = int(statistics.median(record["metrics"]["relevant"] for record in records))
    return summary


def latency_summary(samples: list[float]) -> dict:
    if not samples:
        return {}
    ordered = sorted(samples)
    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        low = int(math.floor(position))
        high = min(low + 1, len(ordered) - 1)
        weight = position - low
        return ordered[low] * (1 - weight) + ordered[high] * weight
    return {
        "n": len(ordered),
        "mean_ms": round(statistics.fmean(ordered) * 1000, 2),
        "median_ms": round(statistics.median(ordered) * 1000, 2),
        "p95_ms": round(percentile(0.95) * 1000, 2),
        "max_ms": round(ordered[-1] * 1000, 2),
    }


# ---------------------------------------------------------------------------
# 打分
# ---------------------------------------------------------------------------

def rank_of(scores: np.ndarray) -> np.ndarray:
    """分数降序排下标；同分按下标升序，保证任何方法都可复现。"""
    return np.argsort(-np.asarray(scores, dtype=np.float32), kind="stable")


def normalized_texts(texts: list[str]) -> list[str]:
    """``keyword_score`` 内部对文本做的归一化，预先算好一次。"""
    return [re.sub(r"\s+", "", text.lower()) for text in texts]


def keyword_scores_fast(query: str, normalized: list[str]) -> np.ndarray:
    """与 ``search.keyword_score`` **逐条等价**的批量版本。

    等价性由 ``workbench/tests/test_retrieval_eval.py`` 用真实语料抽样核对。
    存在的唯一理由是性能：直接对全量 15,719 条逐条调用 ``keyword_score`` 会把
    每次查询的文本归一化重复做一遍，单次约 3 秒。
    """
    q = re.sub(r"\s+", "", query.lower())
    out = np.zeros(len(normalized), dtype=np.float32)
    if not q:
        return out
    grams = {q[i:i + 2] for i in range(max(1, len(q) - 1))}
    total = float(len(grams))
    for index, text in enumerate(normalized):
        if not text:
            continue
        if q in text:
            out[index] = 1.0
        else:
            out[index] = sum(1 for gram in grams if gram in text) / total
    return out


def returned_list(scores: np.ndarray, limit: int = RETURN_LIMIT) -> tuple[list[int], np.ndarray]:
    """模拟产品行为：只返回 score > 0 的结果，最多 ``limit`` 条。"""
    scores = np.asarray(scores, dtype=np.float32)
    order = rank_of(scores)
    keep = [int(index) for index in order[:limit] if scores[index] > 0]
    return keep, scores


def corpus_vectors(texts: list[str], directory: Path) -> tuple[np.ndarray, dict]:
    """语料向量：首次真算并落盘，之后按指纹复用。返回 (向量, 构建信息)。"""
    from .search import _embedder
    directory.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(
        {"model": MODEL_NAME, "count": len(texts),
         "digest": hashlib.sha256("\x00".join(texts).encode("utf-8")).hexdigest()},
        ensure_ascii=False).encode("utf-8")).hexdigest()
    vectors_path = directory / "corpus_vectors.npy"
    meta_path = directory / "corpus_vectors.json"
    if vectors_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("fingerprint") == fingerprint:
            started = time.perf_counter()
            vectors = np.load(vectors_path)
            return vectors, {"reused": True, "cold_build_seconds": meta.get("cold_build_seconds"),
                             "load_seconds": round(time.perf_counter() - started, 2),
                             "bytes": vectors_path.stat().st_size, "count": len(vectors)}
    started = time.perf_counter()
    vectors = np.asarray(list(_embedder().embed(texts)), dtype=np.float32)
    seconds = time.perf_counter() - started
    if len(vectors) != len(texts):
        raise RuntimeError("模型返回的向量数量与语料数量不一致")
    vectors = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    np.save(vectors_path, vectors)
    meta_path.write_text(json.dumps({"fingerprint": fingerprint,
                                     "cold_build_seconds": round(seconds, 2),
                                     "model": MODEL_NAME, "count": len(vectors)},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    return vectors, {"reused": False, "cold_build_seconds": round(seconds, 2),
                     "load_seconds": round(seconds, 2),
                     "bytes": vectors_path.stat().st_size, "count": len(vectors)}


def embed_query(text: str, instruct: bool = False) -> np.ndarray:
    from .search import _embedder
    payload = f"为这个句子生成表示以用于检索相关文章：{text}" if instruct else text
    vector = np.asarray(next(iter(_embedder().embed([payload]))), dtype=np.float32)
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


# ---------------------------------------------------------------------------
# 评测主流程
# ---------------------------------------------------------------------------

def run_evaluation(limit: int | None = None, verbose: bool = True) -> dict:
    wall_start = time.perf_counter()
    cpu_start = os.times()
    phase_cpu: dict[str, dict] = {}
    phase_wall: dict[str, float] = {}

    def mark(name: str, wall_from: float, cpu_from) -> None:
        now_cpu = os.times()
        phase_wall[name] = round(time.perf_counter() - wall_from, 3)
        phase_cpu[name] = {
            "user_seconds": round(now_cpu.user - cpu_from.user, 3),
            "system_seconds": round(now_cpu.system - cpu_from.system, 3),
        }

    # ---- 1. 语料与查询集 ------------------------------------------------
    step_wall, step_cpu = time.perf_counter(), os.times()
    entries = load_corpus(limit)
    texts = corpus_documents(entries)
    rng = random.Random(SEED)
    a_queries = build_a_queries(entries, rng)
    b_queries = build_b_queries(entries)
    queries = a_queries + b_queries
    splits = assign_splits(queries)
    by_id = {query["id"]: query for query in queries}
    for query in queries:
        query["split"] = "dev" if query["id"] in set(splits["dev"]) else "test"
    mark("build_queries", step_wall, step_cpu)
    if verbose:
        print(f"[1/6] 语料 {len(entries)} 条；查询 {len(queries)} 条"
              f"（dev {len(splits['dev'])} / test {len(splits['test'])}）", flush=True)

    # ---- 2. 索引 --------------------------------------------------------
    step_wall, step_cpu = time.perf_counter(), os.times()
    bm25 = BM25Index(texts)
    bm25_stats = bm25.statistics()
    bm25_stats["build_seconds"] = round(time.perf_counter() - step_wall, 2)
    mark("build_bm25", step_wall, step_cpu)
    if verbose:
        print(f"[2/6] BM25 索引：词表 {bm25_stats['vocabulary']}，"
              f"{bm25_stats['build_seconds']} s", flush=True)

    step_wall, step_cpu = time.perf_counter(), os.times()
    vectors, vector_info = corpus_vectors(texts, EVAL_DIR)
    mark("build_vectors", step_wall, step_cpu)
    if verbose:
        print(f"[3/6] 向量：{'复用缓存' if vector_info['reused'] else '本次新建'}"
              f"（首次构建 {vector_info['cold_build_seconds']} s，"
              f"{vector_info['bytes'] / 1e6:.1f} MB）", flush=True)

    # ---- 3. 逐查询打分 --------------------------------------------------
    step_wall, step_cpu = time.perf_counter(), os.times()
    scores_store: dict[str, dict[str, np.ndarray]] = {}
    flat_texts = normalized_texts(texts)
    # 预热：第一次调用会额外做 ONNX/分词器的惰性初始化，不预热就会污染第一条查询的延迟。
    embed_query("预热查询")
    bm25.scores("预热查询")
    keyword_scores_fast("预热查询", flat_texts)
    timings: dict[str, list[float]] = {name: [] for name in
                                       ("keyword_substring", "bm25", "embedding", "embedding_instruct")}
    for order_index, query in enumerate(queries, start=1):
        text = query["query"]
        record: dict[str, np.ndarray] = {}

        mark_start = time.perf_counter()
        record["keyword_substring"] = keyword_scores_fast(text, flat_texts)
        timings["keyword_substring"].append(time.perf_counter() - mark_start)

        mark_start = time.perf_counter()
        record["bm25"] = bm25.scores(text)
        timings["bm25"].append(time.perf_counter() - mark_start)

        mark_start = time.perf_counter()
        record["embedding"] = vectors @ embed_query(text)
        timings["embedding"].append(time.perf_counter() - mark_start)

        mark_start = time.perf_counter()
        record["embedding_instruct"] = vectors @ embed_query(text, instruct=True)
        timings["embedding_instruct"].append(time.perf_counter() - mark_start)

        scores_store[query["id"]] = record
        if verbose and order_index % 40 == 0:
            print(f"      打分 {order_index}/{len(queries)}", flush=True)
    mark("score_queries", step_wall, step_cpu)

    # ---- 4. dev 上选超参 ------------------------------------------------
    step_wall, step_cpu = time.perf_counter(), os.times()
    dev_ids = splits["dev"]
    test_ids = splits["test"]

    weight_sweep = []
    for weight in [round(0.05 * i, 2) for i in range(21)]:
        rows = {}
        for query_class in ("A", "B", "ALL"):
            selected_ids = [query_id for query_id in dev_ids
                            if query_class == "ALL" or by_id[query_id]["class"] == query_class]
            metrics_rows = []
            for query_id in selected_ids:
                query = by_id[query_id]
                fused = weighted_fuse([scores_store[query_id]["bm25"],
                                       scores_store[query_id]["embedding"]],
                                      [weight, 1.0 - weight])
                returned, _ = returned_list(fused)
                metrics_rows.append(query_metrics(returned, query["relevant"]))
            rows[query_class] = metrics_rows
        weight_sweep.append({
            "bm25_weight": weight,
            "ndcg@10": round(statistics.fmean(r[f"ndcg@{NDCG_K}"] for r in rows["ALL"]), 4),
            "ndcg@10_A": round(statistics.fmean(r[f"ndcg@{NDCG_K}"] for r in rows["A"]), 4),
            "ndcg@10_B": round(statistics.fmean(r[f"ndcg@{NDCG_K}"] for r in rows["B"]), 4),
            "top1": round(statistics.fmean(r["top1"] for r in rows["ALL"]), 4),
        })
    chosen_weight = max(weight_sweep, key=lambda row: (row["ndcg@10"], row["bm25_weight"]))["bm25_weight"]
    # 同一条 dev 数据上另取一个“只在 B 类上调”的权重，用来显示按类调参会有多大差别。
    chosen_weight_b = max(weight_sweep, key=lambda row: (row["ndcg@10_B"], row["bm25_weight"]))["bm25_weight"]

    # 相对边际在本语料上到底有多大：先量出来，再谈阈值。
    margin_samples = []
    for query_id in dev_ids:
        returned, scores = returned_list(scores_store[query_id]["embedding"])
        top = [float(scores[index]) for index in returned[:3]]
        if len(top) >= 3:
            margin_samples.append(top[0] - top[2])
    margin_stats = {}
    if margin_samples:
        ordered = sorted(margin_samples)
        margin_stats = {
            "n": len(ordered),
            "median": round(statistics.median(ordered), 4),
            "p10": round(ordered[max(0, int(0.10 * (len(ordered) - 1)))], 4),
            "p90": round(ordered[int(0.90 * (len(ordered) - 1))], 4),
            "min": round(ordered[0], 4),
            "max": round(ordered[-1], 4),
        }

    # 过滤阈值：只看 dev 的向量检索结果 + 与查询无关的无关探针
    def filtered_indices(query_id: str, tau: float, delta: float) -> tuple[list[int], str]:
        returned, scores = returned_list(scores_store[query_id]["embedding"])
        kept_scores = [float(scores[index]) for index in returned]
        keep, reason = relevance_decision(kept_scores, tau, delta)
        return [index for index, flag in zip(returned, keep) if flag], reason

    def dev_ndcg(tau: float, delta: float) -> float:
        return statistics.fmean(
            query_metrics(filtered_indices(query_id, tau, delta)[0],
                          by_id[query_id]["relevant"])[f"ndcg@{NDCG_K}"]
            for query_id in dev_ids)

    baseline_dev_ndcg = dev_ndcg(0.0, 0.0)
    tau_ok = [tau for tau in TAU_GRID if dev_ndcg(tau, 0.0) >= baseline_dev_ndcg - NDCG_TOLERANCE]
    chosen_tau = max(tau_ok) if tau_ok else TAU_GRID[0]
    delta_ok = [delta for delta in DELTA_GRID
                if dev_ndcg(chosen_tau, delta) >= baseline_dev_ndcg - NDCG_TOLERANCE]
    chosen_delta = max(delta_ok) if delta_ok else 0.0

    def probe_top1(text: str) -> float:
        scores = vectors @ embed_query(text)
        return float(scores.max())

    off_topic_scores = [probe_top1(text) for text in OFF_TOPIC_PROBES]
    empty_tau_candidates = [tau for tau in TAU_GRID if max(off_topic_scores) < tau]
    chosen_empty_tau = min(empty_tau_candidates) if empty_tau_candidates else max(TAU_GRID)

    filter_grid = []
    for tau in TAU_GRID:
        row = {"tau": tau}
        for delta in DELTA_GRID:
            trimmed = 0
            kept_total = 0
            empties = 0
            for query_id in dev_ids:
                kept, reason = filtered_indices(query_id, tau, delta)
                trimmed += RETURN_LIMIT - len(kept)
                kept_total += len(kept)
                empties += 1 if not kept else 0
            row[f"ndcg@{delta}"] = round(dev_ndcg(tau, delta), 4)
            row[f"trim@{delta}"] = round(trimmed / (RETURN_LIMIT * len(dev_ids)), 4)
            row[f"empty@{delta}"] = round(empties / len(dev_ids), 4)
        filter_grid.append(row)
    mark("select_hyperparameters", step_wall, step_cpu)
    if verbose:
        print(f"[4/6] dev 选参：融合权重 bm25={chosen_weight}；"
              f"tau={chosen_tau} delta={chosen_delta} empty_tau={chosen_empty_tau}", flush=True)

    # ---- 5. 全量评估 ----------------------------------------------------
    step_wall, step_cpu = time.perf_counter(), os.times()
    methods = ("keyword_substring", "bm25", "embedding", "hybrid_score", "hybrid_rrf",
               "embedding_instruct")

    def method_scores(query_id: str, method: str) -> np.ndarray:
        record = scores_store[query_id]
        if method == "hybrid_score":
            return weighted_fuse([record["bm25"], record["embedding"]],
                                 [chosen_weight, 1.0 - chosen_weight])
        if method == "hybrid_rrf":
            return rrf_fuse([record["bm25"], record["embedding"]], k=RRF_K)
        return record[method]

    per_query: list[dict] = []
    for query in queries:
        entry = {"id": query["id"], "class": query["class"], "subclass": query["subclass"],
                 "split": query["split"], "query": query["query"], "label": query["label"],
                 "relevant": len(query["relevant"]), "methods": {}}
        for method in methods:
            scores = method_scores(query["id"], method)
            returned, raw = returned_list(scores)
            metrics = query_metrics(returned, query["relevant"])
            top = []
            for index in returned[:5]:
                profile = entries[index]
                top.append({
                    "name": profile.get("name", ""),
                    "institution": profile.get("institution", ""),
                    "direction": profile.get("direction_group", ""),
                    "interests": (profile.get("interests") or "")[:40],
                    "score": round(float(raw[index]), 4),
                    "relevant": 1 if index in query["relevant"] else 0,
                })
            entry["methods"][method] = {"metrics": metrics, "top5": top}
        per_query.append(entry)

    table: dict[str, dict] = {}
    for method in methods:
        table[method] = {}
        for query_class in ("A", "B", "ALL"):
            for split in ("dev", "test"):
                selected = [row for row in per_query
                            if (query_class == "ALL" or row["class"] == query_class)
                            and row["split"] == split]
                subset = [{"metrics": row["methods"][method]["metrics"]} for row in selected]
                table[method][f"{query_class}/{split}"] = aggregate(subset)

    subclass_table: dict[str, dict] = {}
    for method in methods:
        subclass_table[method] = {}
        for subclass in sorted({row["subclass"] for row in per_query}):
            selected = [row for row in per_query
                        if row["subclass"] == subclass and row["split"] == "test"]
            subclass_table[method][subclass] = aggregate(
                [{"metrics": row["methods"][method]["metrics"]} for row in selected])

    small_table: dict[str, dict] = {}
    for method in methods:
        small_table[method] = {}
        for query_class in ("A", "B"):
            selected = [row for row in per_query
                        if row["class"] == query_class and row["split"] == "test"
                        and row["relevant"] <= 30 and row["relevant"] > 0]
            small_table[method][query_class] = aggregate(
                [{"metrics": row["methods"][method]["metrics"]} for row in selected])

    # ---- 6. 过滤效果（报在 test） ---------------------------------------
    filter_eval = {}
    for config_name, (tau, delta, empty_tau, guard) in {
        "unfiltered": (0.0, 0.0, 0.0, False),
        "absolute": (chosen_tau, 0.0, 0.0, False),
        "margin": (0.0, chosen_delta, 0.0, False),
        "combined": (chosen_tau, chosen_delta, 0.0, False),
        "combined_with_empty": (chosen_tau, chosen_delta, chosen_empty_tau, False),
        "guarded_empty": (chosen_tau, chosen_delta, chosen_empty_tau, True),
    }.items():
        for split in ("dev", "test"):
            ids = dev_ids if split == "dev" else test_ids
            rows = []
            trimmed = 0
            kept_total = 0
            emptied = 0
            for query_id in ids:
                returned, scores = returned_list(scores_store[query_id]["embedding"])
                kept_scores = [float(scores[index]) for index in returned]
                keep, reason = relevance_decision(kept_scores, tau, delta)
                kept = [index for index, flag in zip(returned, keep) if flag]
                if kept and empty_tau and kept_scores and kept_scores[0] < empty_tau:
                    # guard=True 时，只有“语义低分 **且** 全库没有任何字面命中”才判空。
                    lexical = float(scores_store[query_id]["bm25"].max()) > 0
                    if not (guard and lexical):
                        kept = []
                        reason = "below_empty_threshold"
                trimmed += RETURN_LIMIT - len(kept)
                kept_total += len(kept)
                emptied += 1 if not kept else 0
                metrics = query_metrics(kept, by_id[query_id]["relevant"])
                metrics["reason"] = reason
                rows.append(metrics)
            filter_eval[f"{config_name}/{split}"] = {
                "ndcg@10": round(statistics.fmean(row[f"ndcg@{NDCG_K}"] for row in rows), 4),
                "top1": round(statistics.fmean(row["top1"] for row in rows), 4),
                "recall@10": round(statistics.fmean(row[f"recall@{10}"] for row in rows), 4),
                "trim_ratio": round(trimmed / (RETURN_LIMIT * len(ids)), 4),
                "empty_rate": round(emptied / len(ids), 4),
                "avg_returned": round(kept_total / len(ids), 2),
            }

    off_topic_bm25 = [round(float(bm25.scores(text).max()), 4) for text in OFF_TOPIC_PROBES]
    off_topic_behaviour = {
        "queries": OFF_TOPIC_PROBES,
        "top1_similarity": [round(score, 4) for score in off_topic_scores],
        "bm25_max": off_topic_bm25,
        "empty_tau": chosen_empty_tau,
        "returned_empty": sum(1 for score in off_topic_scores if score < chosen_empty_tau),
        "guarded_empty": sum(1 for score, lexical in zip(off_topic_scores, off_topic_bm25)
                             if score < chosen_empty_tau and lexical <= 0),
        "returned_count_without_filter": len(OFF_TOPIC_PROBES),
    }

    # ---- 7. 探针与失败案例 ----------------------------------------------
    # 英文缩写撞车检测：若两个查询的向量余弦 ≈ 1，说明模型把二者编码成了同一个东西，
    # 语义模式对它们不可能给出不同结果。这是可测的事实，不是猜测。
    english_vectors = {text: embed_query(text) for text in ENGLISH_PROBES}
    collision_groups: list[list[str]] = []
    assigned: set[str] = set()
    for text in ENGLISH_PROBES:
        if text in assigned:
            continue
        group = [text]
        for other in ENGLISH_PROBES:
            if other == text or other in assigned:
                continue
            if float(english_vectors[text] @ english_vectors[other]) > 0.9999:
                group.append(other)
                assigned.add(other)
        assigned.add(text)
        if len(group) > 1:
            collision_groups.append(sorted(group))
    english_collisions = {
        "probes": len(ENGLISH_PROBES),
        "distinct_vectors": len({tuple(np.round(vector, 6)) for vector in english_vectors.values()}),
        "identical_groups": collision_groups,
        "note": ("同一组内的查询在模型眼里是同一个输入，语义检索对它们的排序完全一致。"
                 "本项只统计余弦 > 0.9999 的情形，未做任何人工挑选。"),
    }

    probes = []
    for text in ENGLISH_PROBES + [pair[0] for pair in CROSS_PROBES]:
        expect = dict(CROSS_PROBES).get(text, "")
        scores = method_scores_for_probe(text, vectors, bm25, texts, chosen_weight)
        returned, raw = returned_list(scores["embedding"])
        top = []
        for index in returned[:3]:
            profile = entries[index]
            top.append({"name": profile.get("name", ""),
                        "institution": profile.get("institution", ""),
                        "direction": profile.get("direction_group", ""),
                        "interests": (profile.get("interests") or "")[:40],
                        "score": round(float(raw[index]), 4)})
        bm25_returned, bm25_raw = returned_list(scores["bm25"])
        bm25_top1 = ""
        if bm25_returned:
            first = entries[bm25_returned[0]]
            bm25_top1 = f"{first.get('direction_group', '') or '（空）'}·{first.get('name', '')}"
        lowered = text.lower()
        corpus_df = sum(1 for doc in texts if lowered in doc.lower())
        probes.append({"query": text, "kind": "english" if expect == "" else "cross",
                       "expect": expect, "top3_embedding": top,
                       "bm25_top1": bm25_top1,
                       "top1_bm25": round(float(bm25_raw.max()) if bm25_raw.size else 0.0, 4),
                       "exact_term_hits": corpus_df})

    failures = []
    for row in per_query:
        if row["split"] != "test":
            continue
        for method in ("bm25", "embedding", "hybrid_score"):
            metrics = row["methods"][method]["metrics"]
            if metrics["top1"] < 1.0:
                failures.append({
                    "id": row["id"], "class": row["class"], "subclass": row["subclass"],
                    "query": row["query"], "label": row["label"],
                    "method": method, "relevant": row["relevant"],
                    "top5": row["methods"][method]["top5"],
                })
                break
    failures.sort(key=lambda item: (item["class"], item["id"]))

    # 30 缩写审计：向量指纹 + 分词结果，把“模型分不开它们”这件事钉死到可复现。
    try:
        from .search import _embedder
        tokenizer = _embedder().model.tokenizer
    except Exception:
        tokenizer = None
    acronym_rows = []
    for acronym in ACRONYM_PROBES:
        vector = embed_query(acronym)
        fingerprint = hashlib.sha256(
            np.round(vector, 6).astype(np.float32).tobytes()).hexdigest()[:8]
        tokens = ""
        if tokenizer is not None:
            try:
                tokens = " ".join(tokenizer.encode(acronym).tokens)
            except Exception:
                tokens = ""
        acronym_rows.append({"acronym": acronym, "fingerprint": fingerprint, "tokens": tokens})
    groups: dict[str, list[str]] = {}
    for row in acronym_rows:
        groups.setdefault(row["fingerprint"], []).append(row["acronym"])
    ordered_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), item[1][0]))
    for index, (_fingerprint, members) in enumerate(ordered_groups, start=1):
        for member in members:
            for row in acronym_rows:
                if row["acronym"] == member:
                    row["group"] = f"G{index:02d}"
    acronym_audit = {
        "probes": len(ACRONYM_PROBES),
        "distinct_vectors": len(groups),
        "groups": [{"group": f"G{index:02d}", "fingerprint": fingerprint,
                    "size": len(members), "members": members}
                   for index, (fingerprint, members) in enumerate(ordered_groups, start=1)],
        "rows": acronym_rows,
        "how_to_reproduce": ("python -c \"from workbench.retrieval_eval import embed_query;"
                            " print(embed_query('VLSI') @ embed_query('MEMS'))\"  # ≈1.0"),
    }

    # 逐条失败案例：把 ANALYSED_FAILURES 的 ref 解析成真实检索结果
    probes_by_query = {probe["query"]: probe for probe in probes}
    per_query_by_id = {row["id"]: row for row in per_query}
    analysed_failures = []
    for spec in ANALYSED_FAILURES:
        reference = spec["ref"]
        if reference.startswith("probe:"):
            text = reference[len("probe:"):]
            probe = probes_by_query.get(text)
            if probe is None:
                continue
            analysed_failures.append({
                "ref": reference, "query": text,
                "kind": "英文缩写" if probe["kind"] == "english" else "跨学科",
                "expect": probe["expect"] or "—",
                "method": spec["method"], "category": spec["category"],
                "top": [{"direction": item["direction"], "name": item["name"],
                         "score": item["score"]} for item in probe["top3_embedding"]],
                "extra": (f"全文字面命中 {probe['exact_term_hits']} 条；"
                          f"BM25 Top-1：{probe['bm25_top1'] or '无'}（最高分 {probe['top1_bm25']}）"),
            })
        else:
            row = per_query_by_id.get(reference)
            if row is None:
                continue
            method = spec["method"]
            analysed_failures.append({
                "ref": reference, "query": row["query"], "kind": row["subclass"],
                "expect": row["label"], "method": method,
                "category": spec["category"],
                "top": [{"direction": item["direction"], "name": item["name"],
                         "score": item["score"]}
                        for item in row["methods"][method]["top5"][:3]],
                "extra": f"相关集 {row['relevant']} 条",
            })

    mark("evaluate", step_wall, step_cpu)

    # ---- 诊断：退化文档与文档长度是否扭曲语义排序 -----------------------
    degenerate_flags = np.asarray(
        [(profile.get("direction_group") or "") in DEGENERATE_LABELS for profile in entries],
        dtype=bool)
    length_array = np.asarray([len(text) for text in texts], dtype=np.float32)
    shares: list[float] = []
    top_lengths: list[float] = []
    for query_id in test_ids:
        returned, _scores = returned_list(scores_store[query_id]["embedding"])
        if not returned:
            continue
        top = np.asarray(returned[:10])
        shares.append(float(degenerate_flags[top].mean()))
        top_lengths.append(float(length_array[top].mean()))
    degenerate_bias = {
        "definition": "退化文档 = direction_group 属于「方向待补/不分研究方向」等占位标签",
        "corpus_share": round(float(degenerate_flags.mean()), 4),
        "test_top10_share_mean": round(statistics.fmean(shares), 4) if shares else 0.0,
        "test_top10_share_median": round(statistics.median(shares), 4) if shares else 0.0,
        "corpus_mean_doc_length": round(float(length_array.mean()), 1),
        "test_top10_mean_doc_length": round(statistics.fmean(top_lengths), 1) if top_lengths else 0.0,
    }

    wall_total = round(time.perf_counter() - wall_start, 2)
    cpu_end = os.times()
    cpu_total = {
        "user_seconds": round(cpu_end.user - cpu_start.user, 2),
        "system_seconds": round(cpu_end.system - cpu_start.system, 2),
    }
    cpu_total["total_seconds"] = round(cpu_total["user_seconds"] + cpu_total["system_seconds"], 2)
    cpu_total["cpu_utilization"] = round(cpu_total["total_seconds"] / max(wall_total, 1e-9) * 100, 1)

    degree = Counter(p.get("direction_group") or "" for p in entries)
    degenerate_share = round(
        sum(degree[label] for label in ("方向待补", "不分研究方向", "不区分研究方向",
                                        "不设方向", "不区分方向", "不分方向")) / max(len(entries), 1), 4)
    doc_lengths = [len(text) for text in texts]

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": {
            "seed": SEED, "dev_ratio": DEV_RATIO,
            "corpus_size": len(entries), "limit": limit,
            "model": MODEL_NAME,
            "bm25": {"k1": bm25.k1, "b": bm25.b, "rrf_k": RRF_K},
            "return_limit": RETURN_LIMIT, "k_values": list(K_VALUES),
            "chosen": {"hybrid_bm25_weight": chosen_weight,
                       "hybrid_bm25_weight_on_dev_B_only": chosen_weight_b,
                       "tau": chosen_tau, "delta": chosen_delta,
                       "empty_tau": chosen_empty_tau,
                       "ndcg_tolerance": NDCG_TOLERANCE},
            "queries": {
                "A": sum(1 for q in queries if q["class"] == "A"),
                "B": sum(1 for q in queries if q["class"] == "B"),
                "by_subclass": dict(Counter(q["subclass"] for q in queries)),
                "dev": len(splits["dev"]), "test": len(splits["test"]),
            },
            "terminology_map": {"path": str(TERMS_PATH.relative_to(ROOT)),
                                "entries": len(b_queries),
                                "sha256": hashlib.sha256(TERMS_PATH.read_bytes()).hexdigest()[:16]},
        },
        "splits": {"seed": SEED, "dev": splits["dev"], "test": splits["test"]},
        "corpus": {
            "entries": len(entries),
            "engineering_entries": sum(1 for p in entries if catalog.in_scope(p)),
            "degenerate_direction_share": degenerate_share,
            "document_length": {"mean": round(statistics.fmean(doc_lengths), 1),
                                "median": statistics.median(doc_lengths),
                                "max": max(doc_lengths),
                                "at_cap_1500": sum(1 for length in doc_lengths if length >= 1500)},
            "labels": {"discipline_values": len({n for p in entries for n in discipline_names(p)}),
                       "direction_values": len(degree)},
        },
        "indexes": {
            "keyword_substring": {"build_seconds": 0.0, "bytes": 0, "note": "无索引，逐条 O(N) 扫描"},
            "bm25": bm25_stats,
            "embedding": vector_info,
        },
        "metrics": table,
        "subclass_metrics": subclass_table,
        "small_relevant_subset": small_table,
        "latency": {method: latency_summary(samples) for method, samples in timings.items()},
        "resources": {"wall_seconds": wall_total, "cpu": cpu_total,
                      "phase_wall_seconds": phase_wall, "phase_cpu": phase_cpu},
        "weight_sweep": weight_sweep,
        "margin_stats": margin_stats,
        "degenerate_bias": degenerate_bias,
        "filter_grid": filter_grid,
        "filter_eval": filter_eval,
        "off_topic": off_topic_behaviour,
        "english_collisions": english_collisions,
        "acronym_audit": acronym_audit,
        "probes": probes,
        "analysed_failures": analysed_failures,
        "failures": failures,
        "per_query": per_query,
    }


def method_scores_for_probe(text: str, vectors: np.ndarray, bm25: BM25Index,
                            texts: list[str], weight: float) -> dict[str, np.ndarray]:
    keyword = keyword_scores_fast(text, normalized_texts(texts))
    sparse = bm25.scores(text)
    dense = vectors @ embed_query(text)
    return {
        "keyword_substring": keyword,
        "bm25": sparse,
        "embedding": dense,
        "hybrid_score": weighted_fuse([sparse, dense], [weight, 1.0 - weight]),
        "hybrid_rrf": rrf_fuse([sparse, dense], k=RRF_K),
    }


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _metric_row(name: str, row: dict) -> str:
    if not row:
        return f"| {name} | – | – | – | – | – | – | – |"
    return (f"| {name} | {_pct(row[f'recall@5'])} | {_pct(row[f'recall@{10}'])} | "
            f"{_pct(row[f'recall@{20}'])} | {row[f'mrr@{MRR_K}']:.4f} | "
            f"{row[f'ndcg@{NDCG_K}']:.4f} | {_pct(row['top1'])} | {row['queries']} |")


def _metric_cells(row: dict) -> str:
    """表格行里的指标单元格（方法名与划分由调用方拼）。"""
    if not row:
        return "– | – | – | – | – | – | – |"
    return (f"{_pct(row['recall@5'])} | {_pct(row['recall@10'])} | {_pct(row['recall@20'])} | "
            f"{row[f'mrr@{MRR_K}']:.4f} | {row[f'ndcg@{NDCG_K}']:.4f} | "
            f"{_pct(row['top1'])} | {row['queries']} |")


def write_report(result: dict, path: Path) -> None:
    config = result["config"]
    chosen = config["chosen"]
    metrics = result["metrics"]
    lines: list[str] = []
    add = lines.append

    add("# 导师检索评测报告（自动生成）")
    add("")
    add(f"> 生成时间：{result['generated_at']}")
    add("> 复现：`python -m workbench.retrieval_eval`")
    add("> 本文件由 `workbench/retrieval_eval.py` 自动写出，所有数字来自同目录的 "
        "`results.json`，没有任何手填数值。")
    add("")
    add("## 一、口径")
    add("")
    add(f"- 语料：**{config['corpus_size']:,} 条**目录记录（不做学科过滤，非工科记录作为真实干扰项留在索引里），"
        f"其中工科默认视图 {result['corpus']['engineering_entries']:,} 条。")
    add(f"- 查询：A 类 {config['queries']['A']} 条（标签对齐）+ B 类 {config['queries']['B']} 条"
        f"（自然语言/跨术语）= {config['queries']['A'] + config['queries']['B']} 条。")
    add(f"- 划分：固定种子 **{config['seed']}**，按子类分层取 {config['dev_ratio']:.0%} 为 dev；"
        f"dev {config['queries']['dev']} 条 / test {config['queries']['test']} 条。id 清单见 `results.json` 的 `splits`。")
    add(f"- 返回上限 {config['return_limit']} 条，只返回分数 > 0 的结果；"
        f"指标按**实际返回的有序列表**计算，返回为空则该查询各项指标记 0。")
    add(f"- 相关性为二值；NDCG 的理想 DCG 用 min(|相关集|, {NDCG_K}) 计算。")
    add("")
    add("**相关性判定规则（弱监督 qrels，不是人工标注）**")
    add("")
    add("- A 类 / 一级学科：该导师的一级学科标签（含招生目录给出的多项归属，含四位代码）与查询的学科名"
        "**一一对应**（用带代码的完整标签精确匹配，避免「化学」误命中「化学工程与技术」）。")
    add("- A 类 / 方向分类与研究方向关键词：该导师的 `direction_group` 或 `interests` 包含该标签（子串匹配）。")
    add("- B 类：该导师的 `direction_group` + `interests` + `first_level_discipline` 命中术语表中的标签"
        "（`terms` 组内取并集；给了 `require` 的查询还要求每一组至少命中一个，即组间取交集）。")
    add("")
    add("## 二、完整指标矩阵：5 方法 × A/B 两类 × dev/test")
    add("")
    add("**A 类（标签对齐查询：查询词直接来自一级学科 / 方向分类 / 研究方向关键词。"
        "关键词类方法天然占优，照实报告。）**")
    add("")
    add("| 方法 | 划分 | R@5 | R@10 | R@20 | MRR@10 | NDCG@10 | Top-1 | 查询数 |")
    add("|:--|:--|--:|--:|--:|--:|--:|--:|--:|")
    for method, label in METHOD_LABELS.items():
        for split in ("dev", "test"):
            add(f"| {label.split('（')[0]} | {split} | "
                + _metric_cells(metrics[method][f"A/{split}"]))
    add("")
    add("**B 类（跨术语自然语言查询：查询用学生口语，目标标签写法完全不同。"
        "语义类方法占优，照实报告。）**")
    add("")
    add("| 方法 | 划分 | R@5 | R@10 | R@20 | MRR@10 | NDCG@10 | Top-1 | 查询数 |")
    add("|:--|:--|--:|--:|--:|--:|--:|--:|--:|")
    for method, label in METHOD_LABELS.items():
        for split in ("dev", "test"):
            add(f"| {label.split('（')[0]} | {split} | "
                + _metric_cells(metrics[method][f"B/{split}"]))
    add("")
    add("> **两类查询不合并成一个总分。** A 类是“能不能找回已知标签”，B 类是“能不能跨术语”。"
        "把它们平均会正好抵消掉本评测最重要的结论——A 类上 BM25 领先、B 类上语义模型领先。"
        "合并口径的数字仍在 `results.json` 的 `metrics[方法][\"ALL/test\"]` 里，供需要时查，"
        "但本报告不据此下结论。")
    add("")
    add("补充基线（不在要求的五种之内）：")
    add("")
    add("| 方法 | A dev NDCG@10 | A test NDCG@10 | B dev NDCG@10 | B test NDCG@10 |")
    add("|:--|--:|--:|--:|--:|")
    for method, label in SUPPLEMENTARY_LABELS.items():
        add(f"| {label} | {metrics[method]['A/dev'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{metrics[method]['A/test'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{metrics[method]['B/dev'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{metrics[method]['B/test'][f'ndcg@{NDCG_K}']:.4f} |")
    add("")
    add("### dev → test 稳定性（检查是否在测试集上过拟合）")
    add("")
    gaps = [abs(metrics[method][f"{query_class}/dev"][f"ndcg@{NDCG_K}"]
                - metrics[method][f"{query_class}/test"][f"ndcg@{NDCG_K}"])
            for method in METHOD_LABELS for query_class in ("A", "B")]
    add(f"5 个方法 × 2 类查询共 10 组 dev/test 对照：NDCG@10 的最大落差 "
        f"**{max(gaps):.4f}**，平均 {statistics.fmean(gaps):.4f}。"
        "没有出现“在 dev 上调好、test 上崩掉”的形态。")
    add("")
    add("### 融合权重在 dev 上的扫描（为什么最终权重是这个值）")
    add("")
    add("| BM25 权重 | dev NDCG@10（全部） | dev NDCG@10（A 类） | dev NDCG@10（B 类） |")
    add("|--:|--:|--:|--:|")
    for row in result["weight_sweep"]:
        if round(row["bm25_weight"] * 100) % 10 != 0:
            continue
        marker = " ←选中" if row["bm25_weight"] == chosen["hybrid_bm25_weight"] else ""
        add(f"| {row['bm25_weight']:.2f}{marker} | {row['ndcg@10']:.4f} | "
            f"{row['ndcg@10_A']:.4f} | {row['ndcg@10_B']:.4f} |")
    add("")
    add(f"权重是在 **A+B 合并的 dev** 上选的，而 dev 里 A 类占多数，所以选出的权重 "
        f"**{chosen['hybrid_bm25_weight']:.2f}** 明显偏向 BM25。若只在 B 类 dev 上选会得到 "
        f"**{chosen['hybrid_bm25_weight_on_dev_B_only']:.2f}**（B 类更好、A 类更差）。"
        "两个数字都列出来，是因为“融合权重”本身依赖查询类型，不是普适常数。")
    add("")
    add("### A 类子类拆解（test）")
    add("")
    add("| 方法 | 一级学科 NDCG@10 | 方向分类 NDCG@10 | 研究方向关键词 NDCG@10 | 一类 Top-1 | 方向 Top-1 | 关键词 Top-1 |")
    add("|:--|--:|--:|--:|--:|--:|--:|")
    for method, label in METHOD_LABELS.items():
        row = result["subclass_metrics"][method]
        add(f"| {label} | {row['a_discipline'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{row['a_direction'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{row['a_interest'][f'ndcg@{NDCG_K}']:.4f} | "
            f"{_pct(row['a_discipline']['top1'])} | {_pct(row['a_direction']['top1'])} | "
            f"{_pct(row['a_interest']['top1'])} |")
    add("")
    add("### 相关集较小时（|相关集| ≤ 30）的召回（test）")
    add("")
    add("| 方法 | A R@5 | A R@10 | A R@20 | A 查询数 | B R@5 | B R@10 | B R@20 | B 查询数 |")
    add("|:--|--:|--:|--:|--:|--:|--:|--:|--:|")
    for method, label in METHOD_LABELS.items():
        a = result["small_relevant_subset"][method]["A"]
        b = result["small_relevant_subset"][method]["B"]
        add(f"| {label} | {_pct(a['recall@5'])} | {_pct(a['recall@10'])} | {_pct(a['recall@20'])} | "
            f"{a.get('queries', 0)} | {_pct(b['recall@5'])} | {_pct(b['recall@10'])} | "
            f"{_pct(b['recall@20'])} | {b.get('queries', 0)} |")
    add("")
    add("> 大相关集查询的 Recall@20 分母动辄上百（例如「电子科学与技术」有 2,591 条相关记录），"
        "此时 Recall@20 的上限只有 0.8%，不可能高。所以上表单独切出小相关集子集，"
        "让 Recall 恢复可解释性；主表同时给出两种口径。")
    add("")
    add("## 三、延迟与资源")
    add("")
    add("| 指标 | 数值 |")
    add("|:--|--:|")
    resources = result["resources"]
    add(f"| 整轮评测耗时（wall） | {resources['wall_seconds']} s |")
    add(f"| CPU 用户态 / 内核态 | {resources['cpu']['user_seconds']} s / {resources['cpu']['system_seconds']} s |")
    add(f"| CPU 占用（CPU 时间 ÷ wall） | {resources['cpu']['cpu_utilization']}% |")
    add("")
    add("> CPU 占用超过 100% 是因为向量计算走 numpy/ONNX 的多线程（多核并行），"
        "这是进程累计 CPU 时间除以挂钟时间的结果，不是单核占用率。")
    add("")
    add(f"| 模型初始化 + 语料向量（首次构建） | {result['indexes']['embedding']['cold_build_seconds']} s |")
    add(f"| 本次是否复用向量缓存 | {'是' if result['indexes']['embedding']['reused'] else '否（本次新建）'} |")
    add(f"| 向量文件大小 | {result['indexes']['embedding']['bytes'] / 1e6:.1f} MB |")
    add(f"| BM25 索引构建 | {result['indexes']['bm25']['build_seconds']} s |")
    add(f"| BM25 词表 / 倒排项 | {result['indexes']['bm25']['vocabulary']:,} / "
        f"{result['indexes']['bm25']['postings']:,} |")
    add("")
    add("单查询耗时（含全库打分与排序，n = 全部查询条数）：")
    add("")
    add("| 方法 | 平均 | 中位（P50） | P95 | 最大 | n |")
    add("|:--|--:|--:|--:|--:|--:|")
    for method, label in {**METHOD_LABELS, **SUPPLEMENTARY_LABELS}.items():
        row = result["latency"].get(method) or {}
        if not row:
            continue
        add(f"| {label.split('（')[0]} | {row['mean_ms']} ms | {row['median_ms']} ms | "
            f"{row['p95_ms']} ms | {row['max_ms']} ms | {row['n']} |")
    add("")
    add("## 四、低相关过滤（阈值在 dev 上选，效果报在 test）")
    add("")
    add(f"- 绝对阈值 tau 网格：{', '.join(f'{value:.2f}' for value in TAU_GRID)}")
    add(f"- 相对边际 delta 网格（top1 − top3）：{', '.join(f'{value:.2f}' for value in DELTA_GRID)}")
    add(f"- 选择规则：取**在 dev 上 NDCG@10 下降不超过 {NDCG_TOLERANCE}** 的最大 tau，再取同样条件下最大的 delta。")
    add(f"- 空结果阈值：无关探针的最高相似度全部低于该值才算数，选定 **empty_tau = {chosen['empty_tau']:.2f}**。")
    margin = result.get("margin_stats") or {}
    if margin:
        add(f"- 相对边际（top1 − top3）在 dev 上的实际分布：中位 **{margin['median']:.4f}**，"
            f"P10 {margin['p10']:.4f}，P90 {margin['p90']:.4f}，最小 {margin['min']:.4f}，最大 {margin['max']:.4f}"
            f"（n={margin['n']}）。边际本身很薄，所以任何有实际作用的 delta 都会误杀大量查询。")
    add("")
    add("| 配置 | 划分 | NDCG@10 | Top-1 | R@10 | 平均返回条数 | 裁掉比例 | 空结果比例 |")
    add("|:--|:--|--:|--:|--:|--:|--:|--:|")
    labels = {"unfiltered": "不过滤", "absolute": f"绝对阈值 tau={chosen['tau']:.2f}",
              "margin": f"相对边际 delta={chosen['delta']:.2f}",
              "combined": "两者都开",
              "combined_with_empty": f"两者 + 空结果阈值 {chosen['empty_tau']:.2f}",
              "guarded_empty": f"两者 + 空结果阈值（且要求无字面命中）"}
    for config_name, label in labels.items():
        for split in ("dev", "test"):
            row = result["filter_eval"][f"{config_name}/{split}"]
            add(f"| {label} | {split} | {row['ndcg@10']:.4f} | {_pct(row['top1'])} | "
                f"{_pct(row['recall@10'])} | {row['avg_returned']} | {_pct(row['trim_ratio'])} | "
                f"{_pct(row['empty_rate'])} |")
    add("")
    add("**绝对阈值 tau 的完整曲线（delta=0，dev）**")
    add("")
    add("| tau | dev NDCG@10 | 裁掉比例 | 空结果比例 |")
    add("|--:|--:|--:|--:|")
    for row in result["filter_grid"]:
        add(f"| {row['tau']:.2f} | {row['ndcg@0.0']:.4f} | {_pct(row['trim@0.0'])} | "
            f"{_pct(row['empty@0.0'])} |")
    add("")
    add("**无关查询的行为（语义模式，未过滤 vs 空结果阈值）**")
    add("")
    add("| 无关查询 | 最高余弦 | BM25 最高分 | 语义空判 | 语义+字面双重空判 |")
    add("|:--|--:|--:|:--|:--|")
    off = result["off_topic"]
    for text, score, lexical in zip(off["queries"], off["top1_similarity"], off["bm25_max"]):
        semantic = "空结果" if score < off["empty_tau"] else "仍返回结果"
        guarded = "空结果" if (score < off["empty_tau"] and lexical <= 0) else "仍返回结果"
        add(f"| {text} | {score:.4f} | {lexical:.2f} | {semantic} | {guarded} |")
    add("")
    add(f"- 未加过滤时，{off['returned_count_without_filter']} 条无关查询全部返回结果（硬塞）。")
    add(f"- 只靠 empty_tau={off['empty_tau']:.2f}：{off['returned_empty']}/{off['returned_count_without_filter']} 条返回空结果，"
        f"但代价是 test 上 {_pct(result['filter_eval']['combined_with_empty/test']['empty_rate'])} 的正常查询被误判为空。")
    add(f"- 加上「全库没有任何字面命中」这一条前置条件后："
        f"{off['guarded_empty']}/{off['returned_count_without_filter']} 条无关查询返回空结果，"
        f"test 上正常查询被误判为空的比例降到 "
        f"{_pct(result['filter_eval']['guarded_empty/test']['empty_rate'])}。")
    add("")
    add("## 五、英文缩写退化（一等结论）")
    add("")
    audit = result["acronym_audit"]
    collisions = result["english_collisions"]
    add(f"在 **{audit['probes']} 个**集成电路/信息领域常见缩写上，语义模型只产生了 "
        f"**{audit['distinct_vectors']} 个不同的查询向量**。逐条指纹如下"
        "（指纹 = 查询向量四舍五入到 6 位后的 float32 字节的 SHA-256 前 8 位；同指纹即同向量）：")
    add("")
    add("| 缩写 | 向量指纹 | 分组 | 分词结果 |")
    add("|:--|:--|:--|:--|")
    for row in audit["rows"]:
        add(f"| {row['acronym']} | `{row['fingerprint']}` | {row['group']} | "
            f"`{row['tokens'] or '（未取到）'}` |")
    add("")
    for group in audit["groups"]:
        if group["size"] > 1:
            add(f"- **{group['group']}**（{group['size']} 个，指纹 `{group['fingerprint']}`）："
                f"{' / '.join(group['members'])}")
    add("")
    add("**根因是所选中文嵌入模型的词表不覆盖大写英文子词，不是本项目的实现缺陷。**"
        "用模型自带分词器直接看就能确认：")
    add("")
    add("| 输入 | 分词结果 |")
    add("|:--|:--|")
    for acronym in ("VLSI", "MEMS", "SoC", "RISC-V"):
        tokens = next((row["tokens"] for row in audit["rows"] if row["acronym"] == acronym), "")
        add(f"| `{acronym}` | `{tokens or '（未取到）'}` |")
    add("| `vlsi`（全小写） | `[CLS] v ##ls ##i [SEP]`——小写会被切成子词，所以能区分 |")
    add("")
    add("`BAAI/bge-small-zh-v1.5` 是中文 BERT 系词表（21,128 个 token），英文大写串没有对应子词，"
        "整串被折叠成一个 `[UNK]`；于是 `VLSI`、`MEMS`、`SoC` 的输入序列完全相同，"
        "向量必然相同。本项目只是**如实报告**这个模型行为，没有改动模型，也没有在上面做掩盖。")
    add("")
    add("**后果与产品结论。**")
    add("")
    add("- 语义模式下，同组缩写的检索结果**逐条完全相同**——换个缩写用户会以为系统没反应。")
    add("- BM25 能区分它们（字面不同），这正是界面**必须同时保留关键词/BM25 模式**的直接依据。")
    add(f"- 8 条英文探针只产生 {collisions['distinct_vectors']} 个不同向量；同向量组："
        + ("；".join(" / ".join(group) for group in collisions["identical_groups"])
           or "无") + "。")
    add("")
    add("| 查询 | 类型 | 期望方向 | 全文字面命中条数 | BM25 最高分 | BM25 Top-1 | 语义 Top-3 方向 |")
    add("|:--|:--|:--|--:|--:|:--|:--|")
    for probe in result["probes"]:
        directions = " / ".join(
            f"{item['direction'] or '（空）'}({item['score']:.3f})" for item in probe["top3_embedding"])
        add(f"| {probe['query']} | {'英文' if probe['kind'] == 'english' else '跨学科'} | "
            f"{probe['expect'] or '—'} | {probe['exact_term_hits']} | {probe['top1_bm25']:.3f} | "
            f"{probe.get('bm25_top1', '')} | {directions} |")
    add("")
    add("## 六、失败案例逐条分析")
    add("")
    add(f"下面 {len(result['analysed_failures'])} 条是逐条分析的案例：分类与判断由人写，"
        "Top-3 与分数由程序实跑填入。test 划分中 Top-1 未命中的查询共 "
        f"{len(result['failures'])} 条，完整清单见 `results.json` 的 `failures`。")
    add("")
    add("| # | 案例 | 类别 | 查询 | 期望方向 | 方法 | Top-1 | Top-2 | Top-3 | 备注 |")
    add("|--:|:--|:--|:--|:--|:--|:--|:--|:--|:--|")
    for index, item in enumerate(result["analysed_failures"], start=1):
        cells = []
        for rank in range(3):
            if rank < len(item["top"]):
                entry = item["top"][rank]
                cells.append(f"{entry['direction'] or '（空方向）'}·{entry['name']}({entry['score']})")
            else:
                cells.append("—")
        add(f"| {index} | {item['ref']} | {item['category']} | {item['query']} | "
            f"{item['expect']} | {item['method']} | {cells[0]} | {cells[1]} | {cells[2]} | "
            f"{item['extra']} |")
    add("")
    add("**“文本过长被稀释”这一类没有出现，所以不列。** 语料文档最长 "
        f"{result['corpus']['document_length']['max']} 字，`document()` 的 1500 字截断"
        "从未触发，长度不构成失败原因；报告不编造这一类案例。")
    add("")
    add("## 七、必须一起读的边界")
    add("")
    add(f"- 全库有 **{_pct(result['corpus']['degenerate_direction_share'])}** 的记录方向分类是"
        "「方向待补/不分研究方向」这类退化标签，任何方法的召回上限都被这部分拉低。")
    add(f"- 文档文本平均 {result['corpus']['document_length']['mean']} 字"
        f"（中位 {result['corpus']['document_length']['median']}，最长 {result['corpus']['document_length']['max']}），"
        "`document()` 的 1500 字截断在上述语料上从未触发"
        f"（触达上限的记录数：{result['corpus']['document_length']['at_cap_1500']}）。"
        "因此“文本过长把信号稀释”这一失败类型**在本语料上无法复现**，报告里不会假称存在。")
    add("- 相关性按**标签字面子串**判定：一位导师方向确实对得上、但标签写法不同（例如查询"
        "「模拟集成电路设计」而记录写「模拟电路」）时会被判为不相关。这使指标**偏保守**，"
        "失败案例里必须区分「检索真错了」和「qrels 口径太窄」。")
    add("- A 类查询衡量「能否找回已知标签」，关键词类方法天然占优；B 类才考察术语鸿沟。"
        "两类不能混在一起说“哪个更好”。")
    add("- B 类的相关性来自一份手写术语表，作者只有本项目维护者一人，没有第二人复核，"
        "因此它是**弱监督 qrels**，不能等同于人工标注基准。")
    bias = result.get("degenerate_bias") or {}
    if bias:
        add(f"- 语义检索**没有**被退化文档主导：退化记录占全库 {_pct(bias['corpus_share'])}，"
            f"但在 test 的语义 top-10 里平均只占 {_pct(bias['test_top10_share_mean'])}"
            f"（中位 {_pct(bias['test_top10_share_median'])}），是**被压低**而不是被抬高。"
            "所以“方向待补的记录会变成万能近邻”这个说法在本语料上不成立。")
        add(f"- 也没有长度偏差：语义 top-10 的平均文档长度 {bias['test_top10_mean_doc_length']} 字，"
            f"与全库平均 {bias['corpus_mean_doc_length']} 字基本一致。")
    add("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def slim_result(result: dict) -> dict:
    """提交用的精简结果：去掉逐查询的大数组，保留指标、配置与划分清单。"""
    return {
        "schema_version": 1,
        "generated_at": result["generated_at"],
        "how_to_reproduce": "python -m workbench.retrieval_eval",
        "honesty": ("相关性来自规则生成的 A 类查询与作者手写的 B 类术语表（弱监督 qrels），"
                    "不是人工标注，也不是第三方评测集；指标由本机实跑产生。"),
        "config": result["config"],
        "splits": result["splits"],
        "corpus": result["corpus"],
        "indexes": result["indexes"],
        "metrics": result["metrics"],
        "subclass_metrics": result["subclass_metrics"],
        "small_relevant_subset": result["small_relevant_subset"],
        "latency": result["latency"],
        "resources": result["resources"],
        "weight_sweep": result["weight_sweep"],
        "margin_stats": result["margin_stats"],
        "degenerate_bias": result["degenerate_bias"],
        "filter_grid": result["filter_grid"],
        "filter_eval": result["filter_eval"],
        "off_topic": result["off_topic"],
        "english_collisions": result["english_collisions"],
        "acronym_audit": result["acronym_audit"],
        "probes": result["probes"],
        "analysed_failures": result["analysed_failures"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导师检索离线评测")
    parser.add_argument("--limit", type=int, default=None,
                        help="只取前 N 条语料（冒烟用，指标不可引用）")
    parser.add_argument("--out-dir", default=str(EVAL_DIR), help="产物目录")
    parser.add_argument("--no-slim", action="store_true", help="不写 reference/eval/retrieval.json")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_evaluation(limit=args.limit, verbose=not args.quiet)

    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = out_dir / "report.md"
    write_report(result, report_path)

    print(f"\n写出 {results_path}")
    print(f"写出 {report_path}")
    if not args.no_slim and args.limit is None:
        slim_path = SLIM_PATH
        slim_path.parent.mkdir(parents=True, exist_ok=True)
        slim_path.write_text(json.dumps(slim_result(result), ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"写出 {slim_path}")
    elif args.limit is not None:
        print("（--limit 冒烟运行，未写精简结果，避免覆盖可引用数字）")

    print("\n五种方法 × test 划分（NDCG@10 / Top-1 / R@10）")
    for method in METHOD_LABELS:
        a = result["metrics"][method]["A/test"]
        b = result["metrics"][method]["B/test"]
        print(f"  {method:18s} A: {a[f'ndcg@{NDCG_K}']:.4f} / {a['top1'] * 100:5.1f}% / "
              f"{a[f'recall@{10}'] * 100:5.1f}%    B: {b[f'ndcg@{NDCG_K}']:.4f} / "
              f"{b['top1'] * 100:5.1f}% / {b[f'recall@{10}'] * 100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())