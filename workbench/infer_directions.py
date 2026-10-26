"""用开放嵌入模型给「方向待补」的记录推断研究方向，并给出可复现的验证结果。

为什么需要这个模块
------------------
全库有数千条记录的研究方向仍是「方向待补」，但其中绝大多数**已经读到个人主页的
履历文本**，不少还有论文目录。也就是说：**缺的不是数据，是把已有文本映射到方向
标签这一步**。具体条数以 `--validate`/`--apply` 的运行输出与
`workbench.tools.report_facts` 为准，本文件不写死。也就是说：**缺的不是数据，
是把已有文本映射到方向标签这一步**。这一步是嵌入模型的强项，也正是本项目愿意让 AI
参与的地方——它作用在**数据治理**上，而不是作用在对人的评价上。

做法
----
1. 从**已有方向**的记录里构建标签词表（按出现次数过滤，并剔除「不分研究方向」这类
   退化标签——它们不是方向）。
2. 用 ``BAAI/bge-small-zh-v1.5``（经 ``fastembed`` 本地推理）把标签与文本各自编码，
   取余弦相似度排序。
3. **留出验证**：随机抽一批有方向的记录，把方向藏起来，用履历文本预测，报 Top-1 /
   Top-3 准确率；同时用同一条文本跑**关键词基线**（``search.keyword_score``），
   给出"嵌入到底比关键词强多少"的对照。
4. 只对「方向待补」且文本可用、且相似度超过阈值的记录产出**建议**；阈值以下一律
   留空——宁可不填，也不猜。

命令
----
    python -m workbench.infer_directions --validate 400 --ablate-text
    python -m workbench.infer_directions --apply --min-score 0.55

产物
----
- ``.workbench-data/direction-inference/report.md``   验证与覆盖报告
- ``.workbench-data/direction-inference/suggestions.json``  逐条建议（含分数）
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import catalog, public_research as research  # noqa: E402
from .search import MODEL_NAME, _embedder, keyword_scores  # noqa: E402

OUT_DIR = Path(".workbench-data/direction-inference")

# 这些标签不是"研究方向"，参与匹配只会把结果拉向退化答案。
DEGENERATE = {
    "", "方向待补", "不分研究方向", "不区分研究方向", "集成电路相关",
    "其他", "无", "待定", "未公开", "不公开", "暂无",
}
MIN_LABEL_COUNT = 5      # 出现太少的标签不进入词表
MAX_TEXT_CHARS = 1200    # 控制编码开销
PENDING = "方向待补"

# ── 清洗文本变体（只用于消融，不是生产推断文本）────────────────────────────
# 为什么需要：整段履历里塞满职称、任职年份、行政职务，方向句只占一小部分。
# 把履历压成「只保留研究方向相关的句子」，可以检验"嵌入分数低"到底是模型
# 不懂中文语义，还是信号被长文本稀释。清洗规则全部可枚举、可复现。
_ROLE_NOISE = re.compile(
    r"(教授|副教授|讲师|助理教授|研究员|副研究员|院士|博士生导师|硕士生导师|"
    r"博导|硕导|院长|副院长|系主任|副主任|所长|副所长|处长|校长|党委书记|"
    r"副书记|主任|秘书|委员|党支部书记)")
_YEAR_RANGE = re.compile(r"(19|20)\d{2}\s*[-—~～至]\s*((19|20)\d{2})?\s*")
_SENTENCE = re.compile(r"[^。；;！!？?\n]+")
_RESEARCH_HINT = re.compile(r"(研究|方向|兴趣|领域|从事|专注|主要)")
# 采集管线追加的注释（不是公开原文），其中可能含方向提示，推断时必须剔除。
_PIPELINE_NOTE = re.compile(r"[^。；;！!？?\n]*用于工学导航[^。；;！!？?\n]*")


# ── 字段提取：biography 是 {text,url} 结构，不是字符串 ────────────────────
def _as_text(value) -> str:
    """把 biography / papers 之类的字段压平成纯文本。"""
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


def label_of(profile: dict) -> str:
    d = (profile.get("direction_group") or "").strip()
    if not d:
        i = profile.get("interests")
        d = _as_text(i).strip()
    return d


def profile_text(profile: dict) -> str:
    """推断用的文本：履历为主，必要时补摘要/院系/学科/论文题目。

    两个必须避免的泄漏（实测都真实存在）：

    1. **``discipline`` 字段装的是方向值**，不是一级学科——全库有 3,305 条记录的
       ``discipline`` 与 ``direction_group`` 完全相同。把它拼进文本＝把答案喂给模型，
       验证分数会虚高。这里只取 ``first_level_discipline``（如「0809 电子科学与技术」）。
    2. 采集管线曾在履历末尾追加「学科归属按公开研究关键词归入…，用于工学导航」这类
       **我们自己的注释**。它不是公开原文，且常含方向提示，必须剔除。
    """
    dossier = research.load(profile["id"]) or {}
    bio = _PIPELINE_NOTE.sub(" ", _as_text(dossier.get("biography")))[:600]
    summary = _PIPELINE_NOTE.sub(" ", _as_text(profile.get("summary")))[:200]
    parts = [
        bio,
        summary,
        f"院系 {profile.get('department', '')}",
        f"一级学科 {profile.get('first_level_discipline', '')}",
    ]
    papers = dossier.get("papers") or []
    if papers:
        titles = [_as_text(p) for p in papers[:10]]
        parts.append("论文 " + "；".join(t for t in titles if t)[:300])
    text = "；".join(p for p in parts if p.strip("； "))
    return re.sub(r"\s+", " ", text).strip()[:MAX_TEXT_CHARS]


def clean_profile_text(profile: dict, max_chars: int = 400) -> str:
    """消融用的精简文本：学科/院系 + 履历中与研究方向相关的句子。

    与 :func:`profile_text` 的差别是**去掉了论文题目、摘要和行政职务噪声**，
    只留下最可能承载方向的句子。生产推断仍用完整文本（见模块说明），这里只用于
    回答"如果把长文本稀释去掉，嵌入会变成什么样"。
    """
    dossier = research.load(profile["id"]) or {}
    # 只取履历正文：``_as_text`` 在正文为空时会回落到 summary，而 summary 可能含
    # 系统自己生成的方向提示，混进来会让消融凭空变好（实测会把 verbatim 层从 94% 拉到 78%）。
    raw = dossier.get("biography")
    bio = str(raw.get("text") or "") if isinstance(raw, dict) else _as_text(raw)
    bio = _PIPELINE_NOTE.sub(" ", bio)
    bio = _YEAR_RANGE.sub(" ", bio)
    bio = _ROLE_NOISE.sub(" ", bio)
    picked = [s for s in _SENTENCE.findall(bio) if _RESEARCH_HINT.search(s)]
    body = "；".join(picked) if picked else bio
    body = re.sub(r"\s+", " ", body).strip()[:max_chars]
    head = (f"一级学科 {profile.get('first_level_discipline', '')}；"
            f"院系 {profile.get('department', '')}")
    return f"{head}；{body}".strip("； ")


# ── 词表 ────────────────────────────────────────────────────────────────
def build_vocab(profiles: list[dict]) -> tuple[list[str], Counter]:
    """返回 (词表, 全量取值计数)。

    ``counts`` 统计**所有**取值（包括退化标签），这样报告里的"原始取值 N 种"是真实数字；
    ``vocab`` 才是可用于匹配的标签，需剔除退化标签且出现次数达标。
    """
    counts = Counter()
    for p in profiles:
        d = label_of(p)
        if d:
            counts[d] += 1
    vocab = [k for k, v in counts.most_common()
             if v >= MIN_LABEL_COUNT and k not in DEGENERATE]
    return vocab, counts


def _normalize(matrix):
    import numpy as np
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def embed_texts(texts: list[str], batch_note: str = "") -> "object":
    import numpy as np
    vectors = np.asarray(list(_embedder().embed(texts)), dtype=np.float32)
    return _normalize(vectors)


# 生产决策用的是**融合分**（关键词分与嵌入余弦的加权），不是裸余弦。
# 0.60 是留出验证上选的保守应用阈值；「接受多少 / 接受里对了多少」必须看
# `--validate` 现场生成的校准表（`validation.json` 的 calibration.fusion），
# 本文件不写死那些比例——它们会随语料与词表变化。相似度不是正确概率。
FUSION_APPLY_THRESHOLD = 0.60
CONFIDENCE_BANDS = ((0.70, "high"), (0.65, "medium"), (0.60, "low"))
CALIBRATION_THRESHOLDS = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)


def confidence_band(score) -> str:
    """把**融合分**映射成区间标签；低于 0.60 一律 unknown。"""
    if score is None:
        return "unknown"
    for threshold, name in CONFIDENCE_BANDS:
        if float(score) >= threshold:
            return name
    return "unknown"


def calibration_curve(records: list[dict], key: str,
                      thresholds=CALIBRATION_THRESHOLDS) -> list[dict]:
    """按阈值统计「接受多少 / 接受里对了多少」，用来谈精确率—覆盖率权衡。

    ``records`` 每项含 ``score``（该方法的 Top-1 分数）、``pred``、``truth``。
    这里只做统计，不把分数当概率。
    """
    total = len(records)
    rows = []
    for threshold in thresholds:
        accepted = [r for r in records if (r.get("score") or 0) >= threshold]
        hits = sum(1 for r in accepted if r["pred"] == r["truth"])
        rows.append({
            "score>=": threshold,
            "accepted": len(accepted),
            "coverage": (len(accepted) / total) if total else 0.0,
            "precision": (hits / len(accepted)) if accepted else None,
            "hits": hits,
        })
    return rows


def recommend_threshold(curve: list[dict], target_precision: float = 0.30,
                        min_coverage: float = 0.20) -> dict:
    """在满足目标精确率的前提下，取覆盖率可接受的最低阈值。"""
    for row in curve:
        precision = row.get("precision")
        if precision is None:
            continue
        if precision >= target_precision and row["coverage"] >= min_coverage:
            return {"score>=": row["score>="], "precision": precision,
                    "coverage": row["coverage"], "target_precision": target_precision}
    fallback = [row for row in curve if row.get("precision") is not None]
    best = max(fallback, key=lambda r: r["precision"]) if fallback else None
    return {"score>=": best["score>="] if best else None,
            "precision": best["precision"] if best else None,
            "coverage": best["coverage"] if best else None,
            "target_precision": target_precision,
            "note": "没有阈值同时满足目标精确率与最小覆盖率；以上为可达的最高精确率。"}


def threshold_note(min_score: float, row: dict | None) -> str:
    """报告里那句「阈值 X 的实测」：X 只能来自配置，不能在文案里写字面量。

    历史缺陷：报告长期硬编码「默认阈值 0.55」，而 ``FUSION_APPLY_THRESHOLD`` 早已是
    0.60——对外文档写错默认值就是在误导使用者。这里把阈值与实测行一起传入，两者
    不同步时也不可能再写出矛盾的数字。
    """
    if not row:
        return (f"当前阈值 **{min_score:.2f}** 不在本次校准网格上（步长 0.05），"
                "下表仅作参照。")
    precision = "—" if row.get("precision") is None else f"{row['precision']:.1%}"
    return (f"当前阈值 **{min_score:.2f}** 的实测：接受 {row.get('accepted', 0)} 条，"
            f"覆盖率 {row.get('coverage', 0):.1%}，接受中正确率 {precision}。")


# ── 验证 ────────────────────────────────────────────────────────────────
# 分数级融合的权重：由 ``validate`` 在 dev 子集上选出（`--validate` 的 fusion_tuning），
# 生产推断沿用同一个常数，保证"评测怎么做、线上就怎么做"。
FUSION_KEYWORD_WEIGHT = 0.30
FUSION_TUNING_SEED = 7


def _ranked_labels(scores_row, vocab: list[str], k: int = 3) -> list[str]:
    import numpy as np
    order = np.argsort(-scores_row)[:k]
    return [vocab[int(i)] for i in order]


def validate(profiles: list[dict], vocab: list[str], sample: int, seed: int = 42) -> dict:
    import numpy as np

    pool = [p for p in profiles
            if label_of(p) in vocab and profile_text(p)]
    rng = random.Random(seed)
    if len(pool) > sample:
        pool = rng.sample(pool, sample)

    started = time.time()
    label_vectors = embed_texts(vocab)
    texts = [profile_text(p) for p in pool]
    text_vectors = embed_texts(texts)
    truths = [label_of(p) for p in pool]

    sims = text_vectors @ label_vectors.T          # (n_text, n_label)
    sims_clipped = np.clip(sims, 0.0, 1.0)
    kw_rows = [keyword_scores(vocab, text) for text in texts]
    kw_matrix = np.array([[row[lab] for lab in vocab] for row in kw_rows], dtype=np.float32)
    n = len(pool)

    def hit(matrix) -> tuple[int, int, int, int]:
        h1 = h3 = 0
        strata_hits = {"verbatim": [0, 0], "non_verbatim": [0, 0]}
        for row, profile in enumerate(pool):
            truth = truths[row]
            ranked = _ranked_labels(matrix[row], vocab)
            h1 += ranked[0] == truth
            h3 += truth in ranked
            bucket = "verbatim" if truth in texts[row] else "non_verbatim"
            strata_hits[bucket][0] += 1
            strata_hits[bucket][1] += ranked[0] == truth
        return h1, h3, strata_hits

    kw_hit1, kw_hit3, strata_kw = hit(kw_matrix)
    emb_hit1, emb_hit3, strata_emb = hit(sims)

    # 阈值式混合：关键词得分够高就用关键词排序，否则回落嵌入。
    # Top-3 必须给满三个候选：旧实现关键词胜出时只把 kw[0] 放进列表，
    # 于是混合 Top-3 天然最多 1 个正确项，系统性低估。
    VERBATIM_MIN = 0.8
    hy_hit1 = hy_hit3 = 0
    for row in range(n):
        truth = truths[row]
        kw_ranked = _ranked_labels(kw_matrix[row], vocab)
        emb_ranked = _ranked_labels(sims[row], vocab)
        hybrid_ranked = (kw_ranked if kw_matrix[row].max() >= VERBATIM_MIN
                         else emb_ranked)
        hy_hit1 += hybrid_ranked[0] == truth
        hy_hit3 += truth in hybrid_ranked

    # 分数级融合 + dev/test 调参：权重只在 dev 上选，test 只报数。
    fused = FUSION_KEYWORD_WEIGHT * kw_matrix + (1 - FUSION_KEYWORD_WEIGHT) * sims_clipped
    fu_hit1, fu_hit3, strata_fu = hit(fused)

    order_idx = list(range(n))
    random.Random(FUSION_TUNING_SEED).shuffle(order_idx)
    cut = max(1, int(n * 0.4))
    dev, test = order_idx[:cut], order_idx[cut:]

    def on(rows, matrix) -> dict:
        if not rows:
            # 样本太少时 dev/test 会切成空集：空集上的准确率没有定义，
            # 旧实现在这里对空列表求平均直接 ZeroDivisionError。
            return {"n": 0, "top1": None, "top3": None}
        h1 = sum(_ranked_labels(matrix[r], vocab)[0] == truths[r] for r in rows)
        h3 = sum(truths[r] in _ranked_labels(matrix[r], vocab) for r in rows)
        return {"n": len(rows), "top1": h1 / len(rows), "top3": h3 / len(rows)}

    tuning = {"dev": len(dev), "test": len(test),
              "chosen_weight": FUSION_KEYWORD_WEIGHT}
    if not dev or not test:
        # 样本不足 2 条时切分必然有一边为空，调参隔离无从谈起。这里给出明确提示，
        # 而不是把空集当成「全错」去报 0%。
        tuning["insufficient_sample"] = True
        tuning["note"] = ("样本不足 2 条，无法划分 dev/test，调参隔离一节省略；"
                          "请用更大的 --validate N。")
        tuning["test"] = {name: {"n": 0, "top1": None, "top3": None}
                          for name in ("keyword", "embedding", "fusion")}
    else:
        best_weight, best_score = FUSION_KEYWORD_WEIGHT, -1.0
        for step in range(21):
            weight = step / 20
            matrix = weight * kw_matrix + (1 - weight) * sims_clipped
            metric = on(dev, matrix)
            score = metric["top1"] + metric["top3"]
            if score > best_score:
                best_weight, best_score = weight, score

        tuned = best_weight * kw_matrix + (1 - best_weight) * sims_clipped
        tuning.update({
            "chosen_weight": best_weight,
            "test": {"keyword": on(test, kw_matrix),
                     "embedding": on(test, sims),
                     "fusion": on(test, tuned)},
        })

    # ── 阈值校准：分别看「嵌入分数」与「融合分数」的精确率—覆盖率 ──────────
    emb_top = sims.argmax(axis=1)
    fuse_top = fused.argmax(axis=1)
    sorted_fused = np.sort(fused, axis=1)
    records = [{
        "score": float(sims[r, emb_top[r]]),
        "pred": vocab[int(emb_top[r])],
        "truth": truths[r],
    } for r in range(n)]
    fused_records = [{
        "score": float(fused[r, fuse_top[r]]),
        "pred": vocab[int(fuse_top[r])],
        "truth": truths[r],
    } for r in range(n)]
    emb_curve = calibration_curve(records, "emb")
    fused_curve = calibration_curve(fused_records, "fused")
    calibration = {
        "note": ("余弦相似度与融合分都**不是**正确概率；下表是实测的"
                 "「阈值 → 接受量 / 接受中正确比例」，用于选择保守阈值。"),
        "embedding": emb_curve,
        "fusion": fused_curve,
        "recommended": {
            "embedding": recommend_threshold(emb_curve),
            "fusion": recommend_threshold(fused_curve),
        },
        "default_threshold": FUSION_APPLY_THRESHOLD,
        "default_at_0_55": next((r for r in emb_curve if r["score>="] == 0.55), None),
        "default_at_threshold": next(
            (r for r in fused_curve if r["score>="] == FUSION_APPLY_THRESHOLD), None),
        "base_rate": (fu_hit1 / n) if n else 0.0,
    }

    # ── 学科约束消融：把候选限制在同院系/同二级学科常见的方向标签内 ────────
    import collections as _collections
    by_discipline: dict[str, set[str]] = _collections.defaultdict(set)
    for profile in profiles:
        label = label_of(profile)
        discipline = (profile.get("first_level_discipline") or "").strip()
        if label in vocab and discipline:
            by_discipline[discipline].add(label)
    restricted_rows = restricted_hits = 0
    for row, profile in enumerate(pool):
        discipline = (profile.get("first_level_discipline") or "").strip()
        allowed = by_discipline.get(discipline) or set()
        index = [i for i, label in enumerate(vocab) if label in allowed]
        if len(index) < 5:
            continue
        restricted_rows += 1
        best = index[int(np.argmax(fused[row][index]))]
        restricted_hits += vocab[best] == truths[row]
    discipline_ablation = {
        "rows": restricted_rows,
        "coverage": (restricted_rows / n) if n else 0.0,
        "top1": (restricted_hits / restricted_rows) if restricted_rows else None,
        "unrestricted_top1": fu_hit1 / n if n else 0.0,
        "note": ("候选限制在「同一级学科下已出现过的方向标签」；这只在样本里有该学科"
                 "标签时生效，覆盖率低于 100% 属正常。"),
    }

    return {
        "sampled": n,
        "vocab_size": len(vocab),
        "seconds": round(time.time() - started, 1),
        "embedding": {"top1": emb_hit1 / n if n else 0.0, "top3": emb_hit3 / n if n else 0.0},
        "keyword": {"top1": kw_hit1 / n if n else 0.0, "top3": kw_hit3 / n if n else 0.0},
        "hybrid": {"top1": hy_hit1 / n if n else 0.0, "top3": hy_hit3 / n if n else 0.0},
        "fusion": {"top1": fu_hit1 / n if n else 0.0, "top3": fu_hit3 / n if n else 0.0,
                   "keyword_weight": FUSION_KEYWORD_WEIGHT},
        "fusion_tuning": tuning,
        "calibration": calibration,
        "discipline_restricted": discipline_ablation,
        "strata": {
            name: {
                "n": strata_kw[name][0],
                "embedding_top1": (strata_emb[name][1] / strata_emb[name][0])
                if strata_emb[name][0] else None,
                "keyword_top1": (strata_kw[name][1] / strata_kw[name][0])
                if strata_kw[name][0] else None,
                "fusion_top1": (strata_fu[name][1] / strata_fu[name][0])
                if strata_fu[name][0] else None,
            }
            for name in ("verbatim", "non_verbatim")
        },
    }


# ── 清洗文本消融 ────────────────────────────────────────────────────────
def text_ablation(profiles: list[dict], vocab: list[str], sample: int,
                  seed: int = 42) -> dict:
    """同一抽样上比较「完整文本」与「只保留方向句」的嵌入表现。

    分层口径与 :func:`validate` 完全一致：真值标签是否作为字符串出现在**完整**
    文本里。verbatim 层的关键词基线几乎必然命中；真正需要语义能力的是
    non_verbatim 层——消融的价值就在于把这两层分开看。
    """
    import numpy as np

    pool = [p for p in profiles if label_of(p) in vocab and profile_text(p)]
    rng = random.Random(seed)
    if len(pool) > sample:
        pool = rng.sample(pool, sample)

    label_vectors = embed_texts(vocab)
    full_texts = [profile_text(p) for p in pool]
    clean_texts = [clean_profile_text(p) for p in pool]
    truths = [label_of(p) for p in pool]
    order_full = np.argsort(-(embed_texts(full_texts) @ label_vectors.T), axis=1)[:, :3]
    order_clean = np.argsort(-(embed_texts(clean_texts) @ label_vectors.T), axis=1)[:, :3]

    buckets: dict[str, list[int]] = {"verbatim": [], "non_verbatim": []}
    for row, text in enumerate(full_texts):
        buckets["verbatim" if truths[row] in text else "non_verbatim"].append(row)

    def score(rows: list[int], order) -> dict:
        n = len(rows)
        if not n:
            return {"n": 0, "top1": None, "top3": None}
        top1 = sum(vocab[int(order[r][0])] == truths[r] for r in rows) / n
        top3 = sum(truths[r] in [vocab[int(j)] for j in order[r]] for r in rows) / n
        return {"n": n, "top1": top1, "top3": top3}

    return {
        "sampled": len(pool),
        "vocab_size": len(vocab),
        "strata": {name: {"n": len(rows),
                          "full": score(rows, order_full),
                          "clean": score(rows, order_clean)}
                   for name, rows in buckets.items()},
    }


# ── 推断 ────────────────────────────────────────────────────────────────
def infer(profiles: list[dict], vocab: list[str], min_score: float,
          min_margin: float = 0.0, restrict_discipline: bool = True) -> dict:
    import numpy as np

    # 学科约束：同一级学科下已出现过的方向标签作为候选集。
    # 留出验证显示它把 Top-1 从 14.2% 提到 20.7%（覆盖 82% 的样本）。
    by_discipline: dict[str, set[str]] = {}
    if restrict_discipline:
        for profile in profiles:
            label = label_of(profile)
            discipline = (profile.get("first_level_discipline") or "").strip()
            if label in vocab and discipline:
                by_discipline.setdefault(discipline, set()).add(label)

    pending = [p for p in profiles if label_of(p) in ("", PENDING)]
    targets, texts = [], []
    for p in pending:
        t = profile_text(p)
        if t:
            targets.append(p)
            texts.append(t)

    if not targets:
        return {"pending": len(pending), "with_text": 0, "suggestions": []}

    label_vectors = embed_texts(vocab)
    text_vectors = embed_texts(texts)
    sims = text_vectors @ label_vectors.T
    # 先按行算一次全词表分数，再拼矩阵。**不要**把 keyword_scores() 放进内层推导式：
    # 那样每行会被调用 256 次（一次 per label），全库推断从几分钟变成几小时（实测踩过）。
    kw_rows = [keyword_scores(vocab, t) for t in texts]
    kw_matrix = np.array([[row[lab] for lab in vocab] for row in kw_rows], dtype=np.float32)
    fused = FUSION_KEYWORD_WEIGHT * kw_matrix + (1 - FUSION_KEYWORD_WEIGHT) * np.clip(sims, 0.0, 1.0)
    if by_discipline:
        # 只在该学科已有足够标签（≥5）时收紧；否则保持原候选，避免误伤。
        for row, profile in enumerate(targets):
            allowed = by_discipline.get(
                (profile.get("first_level_discipline") or "").strip()) or set()
            index = [i for i, label in enumerate(vocab) if label in allowed]
            if len(index) >= 5:
                keep = fused[row][index]
                masked = np.full_like(fused[row], -1.0)
                masked[index] = keep
                fused[row] = masked
    best = np.argmax(fused, axis=1)
    best_score = fused[np.arange(len(targets)), best]
    # 「是否写入」的阈值按**融合分**判定，与 FUSION_APPLY_THRESHOLD / confidence_band
    # 的口径一致（融合分才是生产决策用的分数）。
    # embedding_score 必须取**被建议那个标签**的余弦，不能用全词表 argmax(sims)：
    # 学科约束会把候选裁到「该学科下已出现过的标签」，两者可能不是同一个标签，
    # 那时报出来的嵌入分就属于另一个方向，等于建议无据可查。
    best_emb_score = sims[np.arange(len(targets)), best]
    fused_sorted = np.sort(fused, axis=1)
    margins = fused_sorted[:, -1] - fused_sorted[:, -2]

    suggestions = []
    for i, p in enumerate(targets):
        top3_idx = np.argsort(-fused[i])[:3]
        kw_scores = {lab: float(kw_matrix[i][j]) for j, lab in enumerate(vocab)}
        chosen = vocab[int(best[i])]
        suggestions.append({
            "id": p["id"],
            "name": p["name"],
            "institution": p["institution"],
            "discipline": p.get("first_level_discipline", ""),
            "suggested": chosen,
            "score": round(float(best_score[i]), 4),
            "embedding_score": round(float(best_emb_score[i]), 4),
            "keyword_score": round(float(kw_scores[chosen]), 4),
            "method": "fusion",
            "top3": [{"label": vocab[int(j)], "score": round(float(fused[i][j]), 4)}
                     for j in top3_idx],
            "margin": round(float(margins[i]), 4),
            "confidence_band": confidence_band(float(best_score[i])),
            "band_note": "confidence_band 是融合分区间，不是正确概率",
            "state": ("suggested"
                      if float(best_score[i]) >= min_score
                      and margins[i] >= min_margin
                      else "unknown"),
            "apply": bool(float(best_score[i]) >= min_score
                          and margins[i] >= min_margin),
        })

    return {
        "pending": len(pending),
        "with_text": len(targets),
        "min_score": min_score,
        "min_margin": min_margin,
        "would_apply": sum(1 for s in suggestions if s["apply"]),
        "unknown_state": sum(1 for s in suggestions if s["state"] == "unknown"),
        "bands": {band: sum(1 for s in suggestions if s["confidence_band"] == band)
                  for band in ("high", "medium", "low", "unknown")},
        "by_method": {
            "fusion": len(suggestions),
        },
        "suggestions": suggestions,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="用嵌入模型推断研究方向并给出验证结果")
    ap.add_argument("--validate", type=int, default=0, metavar="N",
                    help="留出验证：抽样 N 条有方向的记录，报告 Top-1/Top-3")
    ap.add_argument("--apply", action="store_true", help="对「方向待补」产出建议")
    ap.add_argument("--reuse-suggestions", action="store_true",
                    help="复用已有的 suggestions.json 重建报告（改报告/消融时不必重跑全库推断）")
    ap.add_argument("--ablate-text", action="store_true",
                    help="追加一次清洗文本消融（只保留研究方向句），用于定位长文本稀释")
    ap.add_argument("--min-score", type=float, default=FUSION_APPLY_THRESHOLD,
                    help="融合分阈值，低于此值标为 unknown 不写入（默认 0.60）")
    ap.add_argument("--no-restrict-discipline", action="store_true",
                    help="关闭「候选限制在同一级学科标签内」的约束（用于对照）")
    ap.add_argument("--min-margin", type=float, default=0.0,
                    help="Top-1 与 Top-2 融合分差的最小值；低于它标为 unknown（默认 0）")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    pairs, _by_id, _raw, _net = catalog.static_catalog()
    vocab, counts = build_vocab(pairs)
    print(f"模型 {MODEL_NAME}；词表 {len(vocab)} 个标签（原始取值 {len(counts)} 种）")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 方向推断：验证与覆盖报告",
        "",
        f"- 模型：`{MODEL_NAME}`（本地推理，经 fastembed）",
        f"- 词表：{len(vocab)} 个方向标签（从 {len(counts)} 种取值中过滤，"
        f"要求出现 ≥{MIN_LABEL_COUNT} 次，并剔除「不分研究方向」等退化标签）",
        f"- 全库 {len(pairs)} 条；有方向 "
        f"{sum(1 for p in pairs if label_of(p) not in ('', PENDING))} 条；"
        f"方向待补 {sum(1 for p in pairs if label_of(p) in ('', PENDING))} 条",
        "",
    ]

    if args.validate:
        result = validate(pairs, vocab, args.validate, args.seed)
        s = result["strata"]
        verb, nonverb = s["verbatim"], s["non_verbatim"]
        tuning = result["fusion_tuning"]
        labelled = [p for p in pairs if label_of(p) in vocab]
        leaked = sum(1 for p in labelled
                     if (p.get("discipline") or "") == label_of(p))
        leak_share = leaked / len(labelled) if labelled else 0.0
        lines += [
            "## 留出验证",
            "",
            "**先做泄漏审计。** ``discipline`` 字段在 "
            f"**{leak_share:.1%}** 的已标注记录上等于 ``direction_group``（同一取值）。"
            "把这个字段拼进输入文本，等于把答案喂给模型——修正前关键词基线因此虚高到 64.0%。"
            "本版验证文本只用 ``first_level_discipline``（如「0809 电子科学与技术」）"
            "与履历正文，并剔除采集管线追加的注释。",
            "",
            f"抽样 **{result['sampled']}** 条已有方向的记录，藏起方向、只用履历等文本预测：",
            "",
            "| 方法 | Top-1 | Top-3 |",
            "|:--|--:|--:|",
            f"| 关键词基线 | {result['keyword']['top1']:.1%} | {result['keyword']['top3']:.1%} |",
            f"| 嵌入模型（bge-small-zh-v1.5） | {result['embedding']['top1']:.1%} "
            f"| {result['embedding']['top3']:.1%} |",
            f"| 阈值混合（旧策略：关键词够强就用它） | {result['hybrid']['top1']:.1%} "
            f"| {result['hybrid']['top3']:.1%} |",
            f"| **分数级融合（关键词 {result['fusion']['keyword_weight']:.2f} + "
            f"嵌入 {1 - result['fusion']['keyword_weight']:.2f}）** | "
            f"**{result['fusion']['top1']:.1%}** | **{result['fusion']['top3']:.1%}** |",
            "",
        ]
        calibration = result["calibration"]
        cal_rows = []
        for row in calibration["embedding"]:
            precision = ("—" if row["precision"] is None
                         else f"{row['precision']:.1%}")
            cal_rows.append(f"| {row['score>=']:.2f} | {row['accepted']} | "
                            f"{row['coverage']:.1%} | {precision} |")
        at_threshold = next(
            (row for row in calibration["fusion"]
             if abs(float(row["score>="]) - float(args.min_score)) < 1e-9), None)
        restricted = result["discipline_restricted"]
        restricted_top1 = ("—" if restricted["top1"] is None
                           else f"{restricted['top1']:.1%}")
        lines += [
            "### 阈值与拒绝：余弦不是概率",
            "",
            calibration["note"],
            "",
            "| 嵌入 Top-1 分数 ≥ | 接受条数 | 覆盖率 | 接受中正确率 |",
            "|--:|--:|--:|--:|",
        ] + cal_rows + [
            "",
            threshold_note(args.min_score, at_threshold),
            "**这是实测比例，不是概率校准结果**——它只说明在该阈值下被接受的那批里"
            "有多少 Top-1 正确。低于阈值的记录一律标为 `unknown`，不写入建议。",
            "",
            "### 学科约束消融（候选限制在同一级学科已出现过的方向标签内）",
            "",
            f"可约束样本 **{restricted['rows']}** 条"
            f"（覆盖验证样本 {restricted['coverage']:.1%}）；约束后 Top-1 "
            f"{restricted_top1}，不约束 {restricted['unrestricted_top1']:.1%}。",
            "",
            "### 调参隔离：融合权重只在 dev 上选",
            "",
        ]
        if tuning.get("insufficient_sample"):
            lines += [f"- {tuning['note']}", ""]
        else:
            lines += [
                f"把同一样本按固定种子划成 dev {tuning['dev']} 条 / "
                f"test {tuning['test']['keyword']['n']} 条，"
                f"在 dev 上选中关键词权重 **{tuning['chosen_weight']:.2f}**"
                "（选择标准为 Top-1+Top-3），只在 test 上报数：",
                "",
                "| 方法 | test Top-1 | test Top-3 |",
                "|:--|--:|--:|",
                f"| 关键词基线 | {tuning['test']['keyword']['top1']:.1%} | "
                f"{tuning['test']['keyword']['top3']:.1%} |",
                f"| 嵌入模型 | {tuning['test']['embedding']['top1']:.1%} | "
                f"{tuning['test']['embedding']['top3']:.1%} |",
                f"| 分数级融合 | **{tuning['test']['fusion']['top1']:.1%}** | "
                f"**{tuning['test']['fusion']['top3']:.1%}** |",
                "",
            ]
        lines += [
            "### 分层：字面命中 vs 需要语义推断",
            "",
            "| 分层 | 条数 | 关键词 Top-1 | 嵌入 Top-1 | 融合 Top-1 |",
            "|:--|--:|--:|--:|--:|",
            f"| 字面命中（文本里出现该标签） | {verb['n']} | "
            f"{(verb['keyword_top1'] or 0):.1%} | {(verb['embedding_top1'] or 0):.1%} | "
            f"{(verb.get('fusion_top1') or 0):.1%} |",
            f"| 未字面命中（需要语义推断） | {nonverb['n']} | "
            f"{(nonverb['keyword_top1'] or 0):.1%} | {(nonverb['embedding_top1'] or 0):.1%} | "
            f"{(nonverb.get('fusion_top1') or 0):.1%} |",
            "",
            "**怎么读**：修正泄漏后，绝大多数样本都落在「未字面命中」层——方向标签是归一化后的"
            "名称，很少与公开原文逐字相同。这一层才是真实场景；任何宣称高准确率的报告，"
            "都应先排除「输入里直接含标签」这种假象。",
            "",
            f"耗时 {result['seconds']} 秒。",
            "",
        ]
        message = (f"验证：关键词 Top-1 {result['keyword']['top1']:.1%}；"
                   f"嵌入 {result['embedding']['top1']:.1%}；"
                   f"阈值混合 {result['hybrid']['top1']:.1%}；"
                   f"分数级融合 {result['fusion']['top1']:.1%}")
        if not tuning.get("insufficient_sample"):
            message += f"（test-only {tuning['test']['fusion']['top1']:.1%}）"
        else:
            message += f"（{tuning['note']}）"
        print(message)
        (OUT_DIR / "validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")

    if args.ablate_text:
        ablation = text_ablation(pairs, vocab, args.validate or 400, args.seed)
        strata = ablation["strata"]
        verb, nonverb = strata["verbatim"], strata["non_verbatim"]
        keyword_by_stratum = {}
        if args.validate:
            keyword_by_stratum = {
                name: (result["strata"][name] or {}).get("keyword_top1")
                for name in ("verbatim", "non_verbatim")}

        def pct(value) -> str:
            return "—" if value is None else f"{value:.1%}"

        def gain(row) -> float:
            full = (row["full"] or {}).get("top1") or 0.0
            clean = (row["clean"] or {}).get("top1") or 0.0
            return clean - full

        lines += [
            "### 消融：长文本稀释，还是模型不懂中文语义？",
            "",
            "把同一批样本的输入换成**只保留研究方向句**的清洗文本（去掉论文题目、摘要、"
            "任职年份与行政职务），再算一次嵌入。关键词列取自同一层的基线：",
            "",
            "| 分层 | 条数 | 关键词 Top-1 | 完整文本·嵌入 Top-1 | 清洗文本·嵌入 Top-1 | 清洗文本·嵌入 Top-3 |",
            "|:--|--:|--:|--:|--:|--:|",
        ]
        for name, label in (("verbatim", "字面命中（履历里写了方向）"),
                            ("non_verbatim", "未字面命中（需语义推断）")):
            row = strata[name]
            lines.append(
                f"| {label} | {row['n']} | {pct(keyword_by_stratum.get(name))} | "
                f"{pct(row['full']['top1'])} | {pct(row['clean']['top1'])} | "
                f"{pct(row['clean']['top3'])} |")
        lines += [
            "",
            "**怎么读这张表**：",
            "",
            f"1. 字面命中层：完整文本 {pct(verb['full']['top1'])} → 清洗后 "
            f"{pct(verb['clean']['top1'])}（{gain(verb)*100:+.1f} 个百分点）。"
            "这一层的关键词基线本就接近上限，收益主要说明**整段履历确实稀释了方向信号**。",
            f"2. 未字面命中层：完整文本 {pct(nonverb['full']['top1'])} → 清洗后 "
            f"{pct(nonverb['clean']['top1'])}（{gain(nonverb)*100:+.1f} 个百分点）。"
            "这一层才是真正需要语义推断的部分。",
            "3. 因此生产推断仍用**完整文本 + 分数级融合**；清洗文本只作为"
            "诊断实验保留，用来解释分数来源，而不是用来刷指标。",
            "",
            f"消融耗时含在总耗时内；样本 {ablation['sampled']} 条、词表 "
            f"{ablation['vocab_size']} 个标签。",
            "",
        ]
        (OUT_DIR / "text_ablation.json").write_text(
            json.dumps(ablation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"文本消融：字面层 {pct(verb['full']['top1'])}→{pct(verb['clean']['top1'])}；"
              f"未字面层 {pct(nonverb['full']['top1'])}→{pct(nonverb['clean']['top1'])}")

    if args.apply or args.reuse_suggestions:
        if args.reuse_suggestions and not args.apply:
            cached = OUT_DIR / "suggestions.json"
            if not cached.is_file():
                print(f"没有可复用的建议产物：{cached}，请先跑一次 --apply")
                return 1
            result = json.loads(cached.read_text(encoding="utf-8"))
        else:
            result = infer(pairs, vocab, args.min_score, args.min_margin,
                   restrict_discipline=not args.no_restrict_discipline)
        lines += [
            "## 覆盖",
            "",
            f"- 方向待补：**{result['pending']}** 条",
            f"- 其中有可用文本：**{result['with_text']}** 条",
            f"- 融合分 ≥ {args.min_score} 因而给出建议：**{result['would_apply']}** 条",
            f"- 标为 unknown（证据不足、不写入）：**{result['unknown_state']}** 条",
            f"- 区间分布：high {result['bands']['high']} / medium {result['bands']['medium']} /"
            f" low {result['bands']['low']} / unknown {result['bands']['unknown']}",
            "",
            f"**关于阈值**：本次决策阈值是 **{args.min_score:.2f}**，它是**融合分**"
            "（关键词分与嵌入余弦的加权），不是「会正确的概率」。"
            "注意「阈值与拒绝」一节那张表的横轴是**嵌入 Top-1 分数**，与这里的融合分"
            "**不是同一个量纲**，不要拿表里的行去对本次阈值；本次阈值对应的接受量、"
            "覆盖率与接受中正确率，已在该表紧接着的一行里单独写出。"
            "低于阈值的记录一律写 unknown，不填。",
            "",
        ]
        if args.apply:
            (OUT_DIR / "suggestions.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n")
        print(f"覆盖：待补 {result['pending']}，有文本 {result['with_text']}，"
              f"可写入 {result['would_apply']}")

    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"报告 -> {OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
