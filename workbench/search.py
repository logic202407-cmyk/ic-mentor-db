"""Source-aware mentor discovery using a small open embedding model.

Similarity is relevance to the user's query, never a measure of mentor quality.

两条工程纪律写在这里，改代码前先读：

1. **与查询无关的工作只做一次。** ``search()`` 是每个 Web 请求调用一次的，文档
   格式化、切词建 BM25 索引、解压向量文件都与查询无关，按文档内容指纹缓存
   （``_Corpus``）。全量目录实测：缓存前 BM25 请求 0.48–1.70 s、语义请求
   0.24–1.25 s，而真正的打分只要 0.07 ms / 4.5 ms。
2. **弱相关不硬推。** ``guarded_empty_decision`` 把评测层验证过的空判规则接进
   检索路径：最高余弦低于 ``SEMANTIC_EMPTY_TAU`` **且**全库没有任何字面命中时返回
   空结果。只加余弦阈值会误杀正常查询（评测：10.1% 的 test 查询被判空），加上
   「无字面命中」这个前置条件后误杀为 0——两组数字都来自 ``retrieval_eval`` 实跑。
3. **没有研究条件就不出名单。** ``query_quality`` 先判查询里有没有研究条件；
   「推荐几个导师」「随便推荐一些」这类只有请求语气的查询直接返回空，而不是让
   BM25 顺着「导师」二字把全库当成结果端上来。拒绝原因与「无关查询」分开记录。
4. **索引文件按内容寻址。** 文件名取文档内容指纹，不取 project id：同一份语料
   换个项目 id 也复用同一份索引（旧实现按 project id 命名，全量目录的 30 MB
   索引换个 id 就白建一次）。索引未压缩落盘（32 MB 级实测：压缩写 1.34 s /
   未压缩 0.016 s，读 0.17 s / 0.036 s，文件只大 8%）。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from .core import DATA_DIR

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
_model = None
# "模型不可用"的判定只做一次：失败后把原因记下来，后续请求直接回落 BM25。
_model_error: str | None = None

# 离线开关：设成 1/true/yes/on 就不再尝试下载；已设 HF_HUB_OFFLINE 也算离线。
OFFLINE_ENV = "IC_MENTOR_OFFLINE"
MODEL_DOWNLOAD_TIMEOUT_ENV = "IC_MENTOR_MODEL_DOWNLOAD_TIMEOUT"
DEFAULT_DOWNLOAD_TIMEOUT_S = 15.0


class VectorModelUnavailable(RuntimeError):
    """向量模型不可用（本地缓存缺失/损坏且不允许或无法下载）。

    ``search()`` 会捕获它并回落到 BM25，把 ``fallback`` 文案带回给调用方——
    不抛 500，静默返回空。
    """


def _offline_requested() -> bool:
    truthy = {"1", "true", "yes", "on"}
    if os.environ.get(OFFLINE_ENV, "").strip().lower() in truthy:
        return True
    return os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in truthy


def _download_timeout() -> float:
    raw = os.environ.get(MODEL_DOWNLOAD_TIMEOUT_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_DOWNLOAD_TIMEOUT_S
    return value if value > 0 else DEFAULT_DOWNLOAD_TIMEOUT_S


def _bound_download_timeouts() -> None:
    """把 huggingface_hub 的网络超时压到可控范围（环境里已显式设过就不覆盖）。"""
    seconds = _download_timeout()
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", str(int(min(10, seconds))))
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", str(int(max(1, seconds))))


def _model_cached(cache: Path) -> bool:
    try:
        return any(cache.rglob("*.onnx"))
    except OSError:
        return False


def _new_embedder(cache: Path, local_only: bool):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache),
                         local_files_only=local_only)


_CACHE_LOCK = threading.Lock()
# 上限取 2 而不是更大：这是本地桌面工具，一份全量目录的缓存条目实测约 100 MB
# （文档文本 + 归一化文本 + BM25 数组 + 向量矩阵 30 MB），4 份就是 400 MB 常驻内存，
# 对单机工具不合理。缓存的用途是「语料内容没变就别重建」，2 份足够覆盖
# 「刷新前后各一份」的常见场景；超出就按 LRU 淘汰，下次用到时重建（代价见 _Corpus）。
# 注意：淘汰只影响速度，不影响正确性——缓存键是**文档内容指纹**，内容一改就失配重建。
_CACHE_MAX_CORPORA = 2
_CORPUS_CACHE: "OrderedDict[tuple[str, str], _Corpus]" = OrderedDict()


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


def _normalize_text(text: str) -> str:
    """``keyword_score`` 内部的归一化：去空白 + 小写。"""
    return re.sub(r"\s+", "", text.lower())


# ── 查询质量：这条查询到底有没有研究条件？────────────────────────────────
# 只有「请求语气 + 泛化对象词」的查询（「推荐几个导师」「帮我找老师」
# 「随便推荐一些」）不含任何研究条件。以前它们被判成字面查询、走 BM25，
# 于是顺着「导师」二字把一堆记录当成"推荐结果"端出来——那不是检索，是随机名单。
QUERY_QUALITY_OK = "ok"
QUERY_QUALITY_NO_RESEARCH_CONDITION = "no_research_condition"

# 请求/动作词：表达"帮我找"，不表达"找什么"。
_REQUEST_WORDS = (
    "求推荐", "推荐一下", "推荐", "介绍", "帮我", "帮忙", "请", "求", "随便",
    "看看", "看下", "看一下", "列举", "列出", "列", "给我", "给", "搜一下", "搜索",
    "搜", "查一下", "查询", "查", "找一下", "找找", "找", "想找", "想做", "想",
    "有没有", "有无", "哪些", "哪个", "哪位", "什么", "怎么", "怎么样", "如何",
    "多少", "是否", "一下", "几个", "几位", "一些", "一点", "几个",
)
# 泛化对象词：说的是"哪类东西"，不是"研究什么"。
_GENERIC_OBJECT_WORDS = (
    "博士生导师", "硕士生导师", "博士生招生", "硕士生招生", "研究生招生",
    "导师", "老师", "教授", "教师", "博导", "硕导", "研究员", "副研究员", "讲师",
    "助理教授", "课题组", "团队", "学院", "学校", "大学", "研究院", "研究所",
    "招生", "研究生", "博士生", "硕士生", "博士", "硕士", "本科生", "招生简章",
    "专业", "方向", "领域", "学科", "资料", "信息", "名单", "列表", "排行",
    "排名", "实力", "水平", "口碑", "评价", "好不好", "值得", "情况",
)
# 功能词/语气词：剥离后剩下的才是"查什么"。
_FUNCTION_WORDS = (
    "我们", "你们", "大家", "我", "你", "您", "他", "她", "它", "们",
    "的是", "了", "吗", "呢", "吧", "啊", "的", "和", "与", "及", "或",
    "是在", "在", "有", "没", "个", "位", "名", "条", "点", "下", "里", "中",
    "就", "也", "还", "很", "太", "最", "更", "比较", "都", "并", "把", "被",
    "对", "向", "把", "关于", "相关", "做", "搞", "从事", "研究", "了解",
)
_NO_RESEARCH_WORDS = tuple(sorted(
    set(_REQUEST_WORDS) | set(_GENERIC_OBJECT_WORDS) | set(_FUNCTION_WORDS),
    key=len, reverse=True))
# 英文里不承载主题的停用词；"for"/"of" 这类不应让查询变成"有内容"。
_ENGLISH_STOPWORDS = frozenset((
    "for", "of", "the", "and", "to", "in", "on", "with", "about", "please",
    "find", "me", "some", "any", "a", "an", "is", "are", "who", "what",
))
_CJK_CHAR = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_TOKEN = re.compile(r"[a-z0-9]+(?:[._+#-][a-z0-9]+)*")


def query_quality(query: str) -> str:
    """判定查询是否带有研究条件（``ok`` / ``no_research_condition``）。

    规则：把请求语气词、泛化对象词、功能词整词剥离后，看还剩什么——

    - 剩 ≥2 个汉字（如「硅光」「清华大学」「红烧肉」）→ ``ok``；
    - 剩一个有意义的拉丁/数字词（``MEMS``、``RISC-V``、``6G``；纯数字不算）→ ``ok``；
    - 什么都不剩（「推荐几个导师」「导师」「随便推荐一些」）→ ``no_research_condition``。

    判定只看**查询文本**，不看检索结果，也不看任何评分——这是一个"能不能问"的
    门槛，不是"谁更好"的排序。它刻意不处理"无害但无关"的查询（如「红烧肉的做法」）：
    那类查询有主题，交给 `guarded_empty_decision` 按相关性判空，两类拒绝原因分开。
    """
    text = str(query or "").strip().lower()
    if not text:
        return QUERY_QUALITY_NO_RESEARCH_CONDITION
    rest = text
    for word in _NO_RESEARCH_WORDS:
        if word in rest:
            rest = rest.replace(word, " ")
    if len(_CJK_CHAR.findall(rest)) >= 2:
        return QUERY_QUALITY_OK
    for token in _LATIN_TOKEN.findall(rest):
        if token in _ENGLISH_STOPWORDS or token.isdigit():
            continue
        return QUERY_QUALITY_OK
    return QUERY_QUALITY_NO_RESEARCH_CONDITION


def is_informative_query(query: str) -> bool:
    return query_quality(query) == QUERY_QUALITY_OK


def _gram_score(query: str, text: str) -> float:
    """二元组覆盖率，输入必须**已归一化**。

    ``keyword_score`` / ``keyword_scores`` / ``keyword_scores_for_texts`` 共用这一份
    公式，避免三处各写一遍再漂移（历史上逐标签与批量版就因此需要专门的对齐测试）。
    """
    if not query or not text:
        return 0.0
    if query in text:
        return 1.0
    grams = {query[i:i + 2] for i in range(max(1, len(query) - 1))}
    if not grams:
        return float(query in text)
    return sum(gram in text for gram in grams) / len(grams)


def keyword_score(query: str, text: str) -> float:
    return _gram_score(_normalize_text(query), _normalize_text(text))


def keyword_scores(labels, text: str) -> dict[str, float]:
    """``keyword_score`` 的批量版：文本只规范化一次。

    逐标签调用时，每个标签都会对**整段文本**重跑一次 ``re.sub``；方向推断一次要算
    「5,478 条 × 256 个标签」，实测把全库推断拖到 40 分钟以上。这里把文本规范化提到
    循环外，打分公式与 ``keyword_score`` 逐项一致（两者共用 ``_gram_score``，测试对齐）。
    """
    t = _normalize_text(text)
    result: dict[str, float] = {}
    if not t:
        return {label: 0.0 for label in labels}
    for label in labels:
        result[label] = _gram_score(_normalize_text(label), t)
    return result


def keyword_scores_for_texts(query: str, normalized_texts: list[str]) -> np.ndarray:
    """一条查询对**多段已归一化文本**打分，语义与逐条 ``keyword_score`` 完全一致。

    检索路径用它：旧实现每次检索都重新调 ``keyword_score``，等于把一万五千多段文本
    各自重新归一化一遍（实测全库 250 ms，这里约 15 ms，差在把规范化提出循环）。
    """
    q = _normalize_text(query)
    out = np.zeros(len(normalized_texts), dtype=np.float32)
    if not q:
        return out
    for index, text in enumerate(normalized_texts):
        if text:
            out[index] = _gram_score(q, text)
    return out


def _document_digest(profiles: list[dict], texts: list[str]) -> str:
    """文档内容指纹：与 ``_vectors`` 落盘 npz 里存的完全同一口径（可直接对账）。"""
    return hashlib.sha256(json.dumps(
        [(profile["id"], text) for profile, text in zip(profiles, texts)],
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


class _Corpus:
    """一份文档集合 + 它的派生索引（归一化文本、BM25、向量），按内容指纹复用。

    为什么需要：``search()`` 每个请求都会被调用一次，而旧实现**每次都**重新格式化
    全部文档、重新切词建 BM25 索引、重新解压 32 MB 向量文件。这些工作与查询无关。
    全量目录（15,719 条）实测单项成本：文档格式化 11 ms、切词 237 ms、BM25 索引
    0.5–1.6 s、解压向量 npz 278 ms；建好之后的打分只要 0.07 ms（BM25）/
    4.5 ms（全库余弦）。缓存之后热查询省掉上面全部重复工作。

    指纹覆盖 ``id`` 与文档正文，任何一条记录被编辑指纹就变，不会返回陈旧结果；
    缓存条目数有上限（``_CACHE_MAX_CORPORA``），条目里也只在真正用到时才构建派生对象。
    """

    def __init__(self, project_id: str, digest: str, texts: list[str]):
        self.project_id = project_id
        self.digest = digest
        self.texts = texts
        self._normalized: list[str] | None = None
        self._bm25: "BM25Index | None" = None
        self.vectors: np.ndarray | None = None

    @property
    def normalized(self) -> list[str]:
        if self._normalized is None:
            self._normalized = [_normalize_text(text) for text in self.texts]
        return self._normalized

    def bm25(self) -> "BM25Index":
        if self._bm25 is None:
            self._bm25 = BM25Index(self.texts)
        return self._bm25


def clear_cache() -> None:
    """清空进程内文档/索引缓存，并允许下一次请求重新尝试加载模型。

    生产无需调用；测试与"用户装好模型后重试"用它清掉"模型不可用"的记忆。
    """
    global _model_error
    with _CACHE_LOCK:
        _CORPUS_CACHE.clear()
    _model_error = None


def _corpus(project_id: str, profiles: list[dict]) -> _Corpus:
    """取（或登记）该内容指纹对应的 ``_Corpus``。"""
    texts = [document(profile) for profile in profiles]
    digest = _document_digest(profiles, texts)
    key = (project_id, digest)
    with _CACHE_LOCK:
        cached = _CORPUS_CACHE.get(key)
        if cached is not None:
            _CORPUS_CACHE.move_to_end(key)
            return cached
    corpus = _Corpus(project_id, digest, texts)
    with _CACHE_LOCK:
        _CORPUS_CACHE[key] = corpus
        while len(_CORPUS_CACHE) > _CACHE_MAX_CORPORA:
            _CORPUS_CACHE.popitem(last=False)
    return corpus


def _embedder():
    """取嵌入模型；本地缓存优先、离线不联网、失败只付一次代价。

    三条纪律（都对应实测到的"假死"）：
    1. **本地有权重就只读本地**（``local_files_only=True``）：不联网做版本检查，
       实测初始化从 1.707 s 降到 0.179 s，而且断网环境照常可用。
    2. **不在缺模型时长时间阻塞**：``IC_MENTOR_OFFLINE=1``（或已设 ``HF_HUB_OFFLINE``）
       时完全不尝试下载，直接抛 ``VectorModelUnavailable``；否则允许一次下载，但把
       huggingface_hub 的 ETag/下载超时压到 ``DEFAULT_DOWNLOAD_TIMEOUT_S`` 量级
       （实测无网环境原来会卡 71 s 才回落）。
    3. **把"模型不可用"的判定记住**：第二次请求直接抛，不再重试、不再阻塞。
       ``clear_cache()`` 会清掉这个判定（测试与显式重试用）。
    """
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error is not None:
        raise VectorModelUnavailable(_model_error)
    cache = DATA_DIR / "models"
    cache.mkdir(parents=True, exist_ok=True)
    offline = _offline_requested()
    if _model_cached(cache):
        try:
            _model = _new_embedder(cache, local_only=True)
            return _model
        except Exception as error:  # noqa: BLE001 - 缓存不完整时可能是下载不完整
            if offline:
                _model_error = (f"离线模式（{OFFLINE_ENV}）下本地缓存无法加载："
                                f"{type(error).__name__}: {error}")
                raise VectorModelUnavailable(_model_error) from error
    elif offline:
        _model_error = (f"离线模式（{OFFLINE_ENV}）且本地缓存 {cache} 里没有模型权重；"
                        "未尝试下载，已跳过语义检索")
        raise VectorModelUnavailable(_model_error)
    _bound_download_timeouts()
    try:
        _model = _new_embedder(cache, local_only=offline)
    except Exception as error:
        _model_error = f"{type(error).__name__}: {error}"
        raise
    return _model


def _index_path(digest: str) -> Path:
    """索引文件按**文档内容指纹**寻址（不是 project id）。

    旧实现用 ``{project_id}.npz``：同一份 15,719 条语料换个项目 id 就白建一次
    116 s 的向量索引，磁盘上那份 30 MB 索引完全用不上。内容寻址后，谁先建谁建，
    其余项目直接命中。
    """
    directory = DATA_DIR / "indexes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest[:32]}.npz"


# 内容寻址后每次内容变化都会产生新文件（全量目录一份约 30 MB），所以按最后写入
# 时间只保留最近的若干个；删除失败的（别的进程正打开着）留到下次。
_INDEX_KEEP_FILES = 6


def _prune_indexes(directory: Path, keep: Path) -> None:
    try:
        candidates = sorted(directory.glob("*.npz"),
                            key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        return
    for stale in candidates[_INDEX_KEEP_FILES:]:
        if stale == keep:
            continue
        try:
            stale.unlink()
        except OSError:
            pass


def _load_vectors(path: Path, corpus: "_Corpus") -> np.ndarray | None:
    """读索引并校验；不存在/损坏/半写入/模型不符一律当**未命中**（返回 None）。

    旧实现对损坏的 npz 直接抛异常，结果整条语义检索回落到 BM25 而且永远不再重建——
    坏文件不删，每次请求都踩一遍。这里把它当缓存未命中处理，顺手删掉坏文件。
    """
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as saved:
            vectors = saved["vectors"]
            if (str(saved["fingerprint"]) != corpus.digest
                    or str(saved["model"]) != MODEL_NAME):
                return None
            if vectors.ndim != 2 or len(vectors) != len(corpus.texts):
                raise ValueError("索引形状与语料不一致")
            return vectors
    except Exception:  # noqa: BLE001 - 损坏/截断/格式变化都按未命中处理
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _save_vectors(path: Path, corpus: "_Corpus", vectors: np.ndarray) -> None:
    """**未压缩**落盘 + 唯一临时文件原子替换。

    实测（15,719 × 512 float32）：``savez_compressed`` 写 1.342 s / 读 0.171 s，
    未压缩写 0.016 s / 读 0.036 s，文件只从 29.8 MB 涨到 32.2 MB（+8%）。
    冷启动在意的是读写耗时，不是这 2 MB。临时文件 + ``os.replace`` 保证不会留下
    半写入的索引被后续进程当成有效缓存。
    """
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    with open(temporary, "wb") as handle:
        np.savez(handle, vectors=vectors, fingerprint=corpus.digest, model=MODEL_NAME)
    os.replace(temporary, path)
    _prune_indexes(path.parent, keep=path)


def _vectors(project: dict, profiles: list[dict]) -> np.ndarray:
    """语料向量：进程内缓存 → 磁盘索引 → 真算，三级复用。返回已归一化矩阵。"""
    return _vectors_of(_corpus(project["id"], profiles), project)


def _legacy_index_path(project_id: str) -> Path | None:
    """旧命名（``{project_id}.npz``）的索引路径，用于一次性接管已有产物。"""
    if not project_id:
        return None
    return DATA_DIR / "indexes" / f"{project_id}.npz"


def _vectors_of(corpus: _Corpus, project: dict) -> np.ndarray:
    """``_vectors`` 的正文：接受已建好的 corpus，避免同一次请求里重复格式化文档。"""
    if corpus.vectors is not None:
        return corpus.vectors
    path = _index_path(corpus.digest)
    vectors = _load_vectors(path, corpus)
    if vectors is None:
        # 兼容迁移：旧版本按 project id 命名索引。内容指纹校验通过就接管并改成
        # 内容寻址名，避免升级后白白重建一次（全量目录一次就是两分钟级）。
        legacy = _legacy_index_path(corpus.project_id)
        if legacy is not None and legacy != path and legacy.exists():
            vectors = _load_vectors(legacy, corpus)
            if vectors is not None:
                _save_vectors(path, corpus, vectors)
    if vectors is not None:
        corpus.vectors = vectors
        return corpus.vectors
    vectors = np.asarray(list(_embedder().embed(corpus.texts)), dtype=np.float32)
    if len(vectors) != len(corpus.texts):
        raise RuntimeError("模型返回的向量数量与导师数量不一致")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    _save_vectors(path, corpus, vectors)
    corpus.vectors = vectors
    return vectors


def warm_index(project: dict) -> dict:
    """预先构建并落盘向量索引（离线预热用；不改变任何检索行为）。

    模型不可用时会抛异常——这是"预热"本身的前提。索引落在本地缓存目录
    （``.workbench-data/indexes``，已 gitignore），不会进仓库。
    """
    started = time.perf_counter()
    corpus = _corpus(str(project.get("id") or ""), project["profiles"])
    path = _index_path(corpus.digest)
    existed = path.exists()
    vectors = _vectors_of(corpus, project)
    return {
        "path": str(path),
        "documents": len(corpus.texts),
        "digest": corpus.digest[:16],
        "reused_existing_file": existed,
        "bytes": path.stat().st_size if path.exists() else 0,
        "bytes_in_memory": int(vectors.nbytes),
        "seconds": round(time.perf_counter() - started, 3),
    }


SEARCH_MODES = {"semantic", "keyword", "bm25", "hybrid", "auto"}
HYBRID_BM25_WEIGHT = 0.5   # 混合模式：BM25 与向量的权重（用户可用 API 覆盖默认值）
HYBRID_EMPTY_TAU = 0.25    # 混合分低于此值视为"没有相关结果"，返回空而不是硬推


def _looks_lexical(query: str) -> bool:
    """查询是否更像"术语/缩写"而不是一句自然语言。

    `VLSI`、`MEMS`、`EDA` 这类英文缩写在中文嵌入模型里会坍缩成同一个向量
    （评测实测 30 个缩写只有 2 个不同向量），所以 `auto` 模式对它们优先走 BM25；
    其余情况走混合检索。

    没有研究条件的查询不算"术语查询"：它们会被 ``search()`` 的质量门槛直接拒掉，
    这里把这条约束也写进分流函数，避免"推荐几个导师"被判成术语 query。
    """
    if not is_informative_query(query):
        return False
    latin = re.findall(r"[A-Za-z][A-Za-z0-9.+#_-]*", query)
    if any(re.search(r"[A-Z]{2,}", token) for token in latin):
        return True
    compact = re.sub(r"\s+", "", query)
    return len(compact) <= 6 and not re.search(r"[我你想找做的怎么如何哪些什么]", query)


def _bm25_scores(corpus: "_Corpus", query: str) -> np.ndarray:
    """在该文档集合的 BM25 索引上打分；索引按内容指纹缓存，不会每次重建。"""
    return corpus.bm25().scores(query)


def search(project: dict, query: str, mode: str = "semantic", limit: int = 20,
           discipline: str = "", institution: str = "") -> list[dict]:
    """检索导师。

    兼容既有 `semantic` / `keyword`，并新增三种**在评测里验证过**的方式：

    - ``bm25``：纯词法（缩写、术语、精确词优先）；
    - ``hybrid``：BM25 与向量归一化后各半；
    - ``auto``：像术语/缩写的查询走 BM25，其余走 hybrid。

    向量模型不可用时自动回落到 BM25，并在结果里写明 ``fallback``，
    而不是抛错或静默返回空。

    向量路径上还会做一次**低相关空判**（``guarded_empty_decision``）：查询与全库
    既没有字面命中、最高余弦又低于 ``SEMANTIC_EMPTY_TAU`` 时返回空列表而不是硬塞
    20 条无关记录。带学科/学校筛选时不做空判——评测口径只覆盖无筛选场景。

    查询本身没有研究条件时（``query_quality``）直接返回空列表：不按任何规则
    "随机给几个导师"，也不按优劣评分推荐。返回的每条结果都带 ``query_quality``
    字段（向后兼容的新增字段，值为 ``ok``）。
    """
    query = query.strip()[:300]
    if not query:
        raise ValueError("请输入研究兴趣或检索问题")
    if mode not in SEARCH_MODES:
        raise ValueError("未知的检索方式")
    quality = query_quality(query)
    if quality != QUERY_QUALITY_OK:
        return []          # 没有研究条件就不出名单：这是"能不能问"的门槛
    all_profiles = project["profiles"]
    profiles = [p for p in all_profiles
                if (not discipline or discipline.lower() in p["discipline"].lower())
                and (not institution or institution.lower() in p["institution"].lower())]
    if not profiles:
        return []

    project_id = str(project.get("id") or "")
    corpus = _corpus(project_id, profiles)
    filtered = bool(discipline or institution)
    # 向量始终按「全量文档」建；无筛选时与 ``corpus`` 是同一个缓存对象，
    # 有筛选时是另一个条目——这里显式取一次，避免同一次请求里重复格式化文档。
    full_corpus = _corpus(project_id, all_profiles) if filtered else corpus
    fallback = ""

    def semantic_scores():
        nonlocal fallback
        try:
            vectors = _vectors_of(full_corpus, project)
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
    vector = None
    lexical = None
    if mode == "keyword":
        scores = keyword_scores_for_texts(query, corpus.normalized)
    elif mode == "bm25":
        scores = _bm25_scores(corpus, query)
    elif mode == "semantic":
        vector = semantic_scores()
        if vector is None:
            scores, used = _bm25_scores(corpus, query), "bm25"
        else:
            scores = vector
    else:
        chosen = mode
        if mode == "auto":
            chosen = "bm25" if _looks_lexical(query) else "hybrid"
        if chosen == "bm25":
            scores, used = _bm25_scores(corpus, query), "bm25"
        else:
            vector = semantic_scores()
            if vector is None:
                scores, used = _bm25_scores(corpus, query), "bm25"
            else:
                lexical = normalize_scores(_bm25_scores(corpus, query))
                scores = (HYBRID_BM25_WEIGHT * lexical
                          + (1 - HYBRID_BM25_WEIGHT) * np.clip(vector, 0.0, 1.0))
                used = "hybrid"

    values = [float(score) for score in scores]
    if used == "hybrid" and values and max(values) < HYBRID_EMPTY_TAU:
        return []          # 弱相关不硬推：宁可返回空，也不给无关结果
    if vector is not None and not filtered:
        # 空判只看「查询对全库」的信号，所以用未筛选文档集合的 BM25 最高分。
        lexical_max = (float(np.max(lexical)) if lexical is not None
                       else float(np.max(_bm25_scores(corpus, query))))
        if guarded_empty_decision(vector, lexical_max):
            return []
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
            "query_quality": quality,
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
# 下面三个阈值只用于「低相关空判」，默认行为由 ``search()`` 决定（见函数说明）。
# 出处是 workbench.retrieval_eval 的实跑产物，不是估的：
#   - 无关探针的 10 条查询最高余弦最大 0.489，取网格里高于它的最小值 → empty_tau=0.50
#     （``workbench/reference/eval/retrieval.json`` 的 config.chosen.empty_tau）；
#   - 绝对阈值 tau 在 dev 上选出的 0.35 实际一行都没裁掉（trim_ratio=0），所以这里
#     的 0.40 只是更保守的尾巴下限，不作为空判依据；
#   - top1−top3 相对边际在 dev 上中位仅 0.0125，任何有实际作用的 delta 都会误杀，
#     因此 delta 默认 0（用 ``filter_low_relevance`` 时可显式传值）。
SEMANTIC_TAU = 0.40          # 语义余弦的绝对下限（尾部裁剪用，不参与空判）
SEMANTIC_MARGIN = 0.02       # top1 与 top3 的最小差距（相对边际）
SEMANTIC_EMPTY_TAU = 0.50    # 最高余弦低于此值且无字面命中 → 返回空结果

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


def guarded_empty_decision(vector_scores, lexical_max: float,
                           tau: float = SEMANTIC_EMPTY_TAU) -> bool:
    """「是否该返回空结果」的最终判定：低余弦 **且** 全库没有任何字面命中。

    这条规则与 ``workbench.retrieval_eval`` 里 ``guarded_empty`` 配置逐项一致，
    那两个数都是从评测产物里读出来的，不是调的：

    - 只加余弦阈值（``combined_with_empty``）：无关探针 10/10 全部判空，但 test 上
      **10.1%** 的正常查询被误判为空，NDCG@10 从 0.6769 掉到 0.6564；
    - 加上「全库没有任何字面命中」这个前置条件（``guarded_empty``）：无关探针仍有
      6/10 判空，而 test 上误判率为 **0**、NDCG@10 维持 0.6769 不变。

    ``tau`` 的语义因此是：语义分低**同时**又完全查不到字面证据，才认定“这条查询与
    本库无关”。只要还有任何字面命中就交回排序层，不替用户删结果。
    """
    values = np.asarray(vector_scores, dtype=np.float32)
    if values.size == 0:
        return False
    if float(values.max()) >= float(tau):
        return False
    return float(lexical_max) <= 0.0
