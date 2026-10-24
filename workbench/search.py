"""Source-aware mentor discovery using a small open embedding model.

Similarity is relevance to the user's query, never a measure of mentor quality.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from .core import DATA_DIR

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
_model = None


def document(profile: dict) -> str:
    parts = [
        f"学科：{profile.get('discipline', '')}",
        f"研究方向：{profile.get('interests', '')}",
        f"简介：{profile.get('summary', '')}",
        f"院系：{profile.get('department', '')}",
    ]
    for source in profile.get("sources", [])[:3]:
        if source.get("claim"):
            parts.append(f"来源线索：{source['claim'][:300]}")
    return "；".join(parts)[:1500]


def keyword_score(query: str, text: str) -> float:
    q = re.sub(r"\s+", "", query.lower())
    t = re.sub(r"\s+", "", text.lower())
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    grams = {q[i:i + 2] for i in range(max(1, len(q) - 1))}
    if not grams:
        return float(q in t)
    return sum(g in t for g in grams) / len(grams)


def keyword_scores(labels, text: str) -> dict[str, float]:
    """``keyword_score`` 的批量版：文本只规范化一次。

    逐标签调用时，每个标签都会对**整段文本**重跑一次 ``re.sub``；方向推断一次要算
    「5,478 条 × 256 个标签」，实测把全库推断拖到 40 分钟以上。这里把文本规范化提到
    循环外，打分公式与 ``keyword_score`` 逐项一致（测试里对齐两者）。
    """
    t = re.sub(r"\s+", "", text.lower())
    result: dict[str, float] = {}
    if not t:
        return {label: 0.0 for label in labels}
    for label in labels:
        q = re.sub(r"\s+", "", label.lower())
        if not q:
            result[label] = 0.0
        elif q in t:
            result[label] = 1.0
        else:
            grams = {q[i:i + 2] for i in range(max(1, len(q) - 1))}
            result[label] = (sum(g in t for g in grams) / len(grams)
                             if grams else float(q in t))
    return result


def _embedder():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        cache = DATA_DIR / "models"
        cache.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache))
    return _model


def _index_path(project_id: str) -> Path:
    directory = DATA_DIR / "indexes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{project_id}.npz"


def _vectors(project: dict, profiles: list[dict]) -> np.ndarray:
    texts = [document(p) for p in profiles]
    fingerprint = hashlib.sha256(json.dumps(
        [(p["id"], t) for p, t in zip(profiles, texts)], ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    path = _index_path(project["id"])
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            if str(saved["fingerprint"]) == fingerprint and str(saved["model"]) == MODEL_NAME:
                return saved["vectors"]
    vectors = np.asarray(list(_embedder().embed(texts)), dtype=np.float32)
    if len(vectors) != len(profiles):
        raise RuntimeError("模型返回的向量数量与导师数量不一致")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    np.savez_compressed(path, vectors=vectors, fingerprint=fingerprint, model=MODEL_NAME)
    return vectors


SEARCH_MODES = {"semantic", "keyword", "bm25", "hybrid", "auto"}
HYBRID_BM25_WEIGHT = 0.5   # 混合模式：BM25 与向量的权重（用户可用 API 覆盖默认值）
HYBRID_EMPTY_TAU = 0.25    # 混合分低于此值视为"没有相关结果"，返回空而不是硬推


def _looks_lexical(query: str) -> bool:
    """查询是否更像"术语/缩写"而不是一句自然语言。

    `VLSI`、`MEMS`、`EDA` 这类英文缩写在中文嵌入模型里会坍缩成同一个向量
    （评测实测 30 个缩写只有 2 个不同向量），所以 `auto` 模式对它们优先走 BM25；
    其余情况走混合检索。
    """
    latin = re.findall(r"[A-Za-z][A-Za-z0-9.+#_-]*", query)
    if any(re.search(r"[A-Z]{2,}", token) for token in latin):
        return True
    compact = re.sub(r"\s+", "", query)
    return len(compact) <= 6 and not re.search(r"[我你想找做的怎么如何哪些什么]", query)


def _bm25_scores(profiles: list[dict], query: str):
    index = BM25Index([document(profile) for profile in profiles])
    return index.scores(query)


def search(project: dict, query: str, mode: str = "semantic", limit: int = 20,
           discipline: str = "", institution: str = "") -> list[dict]:
    """检索导师。

    兼容既有 `semantic` / `keyword`，并新增三种**在评测里验证过**的方式：

    - ``bm25``：纯词法（缩写、术语、精确词优先）；
    - ``hybrid``：BM25 与向量归一化后各半；
    - ``auto``：像术语/缩写的查询走 BM25，其余走 hybrid。

    向量模型不可用时自动回落到 BM25，并在结果里写明 ``fallback``，
    而不是抛错或静默返回空。
    """
    query = query.strip()[:300]
    if not query:
        raise ValueError("请输入研究兴趣或检索问题")
    if mode not in SEARCH_MODES:
        raise ValueError("未知的检索方式")
    profiles = [p for p in project["profiles"]
                if (not discipline or discipline.lower() in p["discipline"].lower())
                and (not institution or institution.lower() in p["institution"].lower())]
    if not profiles:
        return []

    fallback = ""

    def semantic_scores():
        nonlocal fallback
        try:
            all_profiles = project["profiles"]
            vectors = _vectors(project, all_profiles)
            qvec = np.asarray(next(iter(_embedder().query_embed(query))), dtype=np.float32)
            qvec /= max(float(np.linalg.norm(qvec)), 1e-12)
            all_scores = vectors @ qvec
            id_to_score = {p["id"]: float(score)
                           for p, score in zip(all_profiles, all_scores)}
            return np.array([id_to_score[p["id"]] for p in profiles], dtype=np.float32)
        except Exception as error:  # noqa: BLE001 - 模型缺失/下载失败都要能回退
            fallback = f"向量模型不可用，已回落到 BM25（{type(error).__name__}）"
            return None

    used = mode
    if mode == "keyword":
        scores = np.array([keyword_score(query, document(p)) for p in profiles],
                          dtype=np.float32)
    elif mode == "bm25":
        scores = _bm25_scores(profiles, query)
    elif mode == "semantic":
        scores = semantic_scores()
        if scores is None:
            scores, used = _bm25_scores(profiles, query), "bm25"
    else:
        chosen = mode
        if mode == "auto":
            chosen = "bm25" if _looks_lexical(query) else "hybrid"
        if chosen == "bm25":
            scores, used = _bm25_scores(profiles, query), "bm25"
        else:
            vector = semantic_scores()
            if vector is None:
                scores, used = _bm25_scores(profiles, query), "bm25"
            else:
                lexical = normalize_scores(_bm25_scores(profiles, query))
                scores = (HYBRID_BM25_WEIGHT * lexical
                          + (1 - HYBRID_BM25_WEIGHT) * np.clip(vector, 0.0, 1.0))
                used = "hybrid"

    values = [float(score) for score in scores]
    if used == "hybrid" and values and max(values) < HYBRID_EMPTY_TAU:
        return []          # 弱相关不硬推：宁可返回空，也不给无关结果
    order = sorted(range(len(profiles)), key=lambda i: (-values[i], profiles[i]["name"]))
    results = []
    for i in order[:max(1, min(int(limit), 100))]:
        if values[i] <= 0:
            continue
        results.append({
            "profile": profiles[i],
            "similarity": round(values[i], 4),
            "mode": used,
            "requested_mode": mode,
            "fallback": fallback,
            "evidence_count": len(profiles[i].get("sources", [])),
        })
    return results


# ---------------------------------------------------------------------------
# 以下为检索评测新增的组件（增量，不改动 keyword_score / search 的既有语义）
#
# keyword_score() 是二元组覆盖率基线，语义与返回值保持不变——别的模块依赖它。
# 这里补上：中文切分、BM25 倒排索引、分数归一化、加权融合、RRF 融合、低相关过滤。
# 全部只依赖 numpy 与标准库，不引入新依赖。
# ---------------------------------------------------------------------------

BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
# 由 workbench.retrieval_eval 在 dev 划分上选出、并在 test 划分上复核过的取值。
# 这里只作为默认常量，search() 的既有行为不受影响（不会自动启用过滤）。
SEMANTIC_TAU = 0.40          # 语义余弦的绝对下限
SEMANTIC_MARGIN = 0.02       # top1 与 top3 的最小差距（相对边际）
SEMANTIC_EMPTY_TAU = 0.52    # 最高分低于此值视为低置信，建议返回空结果

_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_LATIN_RUN = re.compile(r"[a-z0-9]+(?:[._+#-][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """中文按字符 bigram、拉丁字母与数字按整词切分的轻量分词。

    不依赖 jieba 等第三方分词器（本项目无该依赖）：中文连续片段拆成相邻
    二字组合，ASCII 片段整体作为一词。这样 ``硅光`` 能命中 ``硅光子集成``，
    ``VLSI`` 也能作为独立词项命中。
    """
    if not text:
        return []
    lowered = str(text).lower()
    tokens: list[str] = []
    for match in _CJK_RUN.finditer(lowered):
        run = match.group()
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    for match in _LATIN_RUN.finditer(lowered):
        tokens.append(match.group())
    return tokens


class BM25Index:
    """纯 Python 倒排索引 + Okapi BM25 打分（k1=1.5, b=0.75）。

    只依赖 numpy。构造时把每个词项的文档下标与已算好的 BM25 权重存成
    两个定长数组，查询时按词项累加，避免逐文档循环。
    """

    def __init__(self, documents: list[str], k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = float(k1)
        self.b = float(b)
        self.size = len(documents)
        lengths = np.zeros(self.size, dtype=np.float32)
        postings: dict[str, dict[int, int]] = {}
        for index, text in enumerate(documents):
            tokens = tokenize(text)
            lengths[index] = len(tokens)
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token, frequency in counts.items():
                postings.setdefault(token, {})[index] = frequency
        self.avg_length = float(lengths.mean()) if self.size else 0.0
        # 分母里的文档长度归一化项：与词项无关，先整表算好。
        norm = self.k1 * (1.0 - self.b + self.b * lengths / max(self.avg_length, 1e-9))
        self._postings: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for token, frequencies in postings.items():
            indices = np.fromiter(frequencies.keys(), dtype=np.int32, count=len(frequencies))
            tf = np.fromiter(frequencies.values(), dtype=np.float32, count=len(frequencies))
            weight = tf * (self.k1 + 1.0) / (tf + norm[indices])
            df = len(frequencies)
            idf = math.log(1.0 + (self.size - df + 0.5) / (df + 0.5))
            self._postings[token] = (indices, weight * np.float32(idf))
        self.vocabulary_size = len(self._postings)

    def scores(self, query: str) -> np.ndarray:
        result = np.zeros(self.size, dtype=np.float32)
        for token in set(tokenize(query)):
            entry = self._postings.get(token)
            if entry is None:
                continue
            indices, weights = entry
            # 同一词项内文档下标唯一，可直接花式索引累加。
            result[indices] += weights
        return result

    def statistics(self) -> dict:
        """索引规模的自述数据（用于评测报告，不参与打分）。"""
        postings_entries = sum(len(indices) for indices, _ in self._postings.values())
        array_bytes = sum(indices.nbytes + weights.nbytes
                          for indices, weights in self._postings.values())
        return {
            "documents": self.size,
            "vocabulary": self.vocabulary_size,
            "postings": postings_entries,
            "array_bytes": array_bytes,
            "avg_document_tokens": round(self.avg_length, 2),
            "k1": self.k1,
            "b": self.b,
        }


def normalize_scores(scores) -> np.ndarray:
    """把一列分数线性压到 [0, 1]，便于不同量纲的方法相加。

    全零或常量输入直接返回全零：不放大没有信号的分数。
    """
    values = np.asarray(scores, dtype=np.float32)
    if values.size == 0:
        return values
    low = float(values.min())
    high = float(values.max())
    if not math.isfinite(high) or high - low < 1e-12:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def weighted_fuse(score_lists, weights) -> np.ndarray:
    """按权重相加已归一化的多路分数。

    空输入返回空数组；任一路长度不一致时抛 ValueError（避免静默错位）。
    """
    if not len(score_lists):
        return np.zeros(0, dtype=np.float32)
    lengths = {len(np.asarray(scores)) for scores in score_lists}
    if len(lengths) != 1:
        raise ValueError("参与融合的分数向量长度必须一致")
    total = np.zeros(lengths.pop(), dtype=np.float32)
    for scores, weight in zip(score_lists, weights):
        total += np.float32(weight) * normalize_scores(scores)
    return total


def _ranks(scores) -> np.ndarray:
    """把分数换成 1 起的排名（同分按下标先后，保证可复现）。"""
    values = np.asarray(scores, dtype=np.float32)
    order = np.argsort(-values, kind="stable")
    ranks = np.empty(values.size, dtype=np.float32)
    ranks[order] = np.arange(1, values.size + 1, dtype=np.float32)
    return ranks


def rrf_fuse(score_lists, k: int = RRF_K, weights=None) -> np.ndarray:
    """Reciprocal Rank Fusion：只用名次，不用原始分数量纲。

    ``score = Σ w_i / (k + rank_i)``，k 默认 60（与文献默认值一致）。
    """
    if not len(score_lists):
        return np.zeros(0, dtype=np.float32)
    lengths = {len(np.asarray(scores)) for scores in score_lists}
    if len(lengths) != 1:
        raise ValueError("参与融合的分数向量长度必须一致")
    if weights is None:
        weights = [1.0] * len(score_lists)
    total = np.zeros(lengths.pop(), dtype=np.float32)
    for scores, weight in zip(score_lists, weights):
        total += np.float32(weight) / (np.float32(k) + _ranks(scores))
    return total


def relevance_decision(scores, tau: float, delta: float = 0.0) -> tuple[list[bool], str]:
    """低相关过滤的判定核心：给出保留掩码与原因。

    规则（按顺序短路）：
    1. 空列表 → ``empty``。
    2. 最高分 < ``tau`` → 整体判为低相关，返回空结果（``below_threshold``）。
    3. 若给了 ``delta`` 且至少 3 条，则要求 top1 与 top3 的差距 ≥ ``delta``；
       否则判为“排序过于平坦、无法区分”（``flat_margin``）。
    4. 其余情况逐条保留分数 ≥ ``tau`` 的项（``kept``）。

    ``delta`` 为 0 表示不启用相对边际检查。列表不足 3 条时无法计算边际，
    视为通过（不因为条数少而判为低置信）。
    """
    values = [float(score) for score in scores]
    if not values:
        return [], "empty"
    if values[0] < float(tau):
        return [False] * len(values), "below_threshold"
    if delta > 0 and len(values) >= 3 and (values[0] - values[2]) < float(delta):
        return [False] * len(values), "flat_margin"
    return [value >= float(tau) for value in values], "kept"


def filter_low_relevance(scores, tau: float, delta: float = 0.0) -> tuple[list[float], str]:
    """对**已按分数降序**的列表做低相关过滤，返回 (保留的分数, 原因)。

    返回值直接就是界面上该展示的结果；原因为 ``below_threshold`` 或
    ``flat_margin`` 时列表为空，调用方可据此显示“未找到足够相关的导师”。
    """
    ordered = [float(score) for score in scores]
    keep, reason = relevance_decision(ordered, tau, delta)
    if not any(keep):
        return [], reason
    return [score for score, flag in zip(ordered, keep) if flag], reason
