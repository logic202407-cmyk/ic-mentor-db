"""用开放嵌入模型给「方向待补」的记录推断研究方向，并给出可复现的验证结果。

为什么需要这个模块
------------------
全库 14,271 条记录里有 **4,030 条方向仍为「方向待补」**，但其中 **4,007 条已经读到
个人主页的履历文本**（中位 424 字），1,595 条还有论文目录。也就是说：**缺的不是数据，
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
    python -m workbench.infer_directions --validate 500
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
from .search import MODEL_NAME, _embedder, keyword_score  # noqa: E402

OUT_DIR = Path(".workbench-data/direction-inference")

# 这些标签不是"研究方向"，参与匹配只会把结果拉向退化答案。
DEGENERATE = {
    "", "方向待补", "不分研究方向", "不区分研究方向", "集成电路相关",
    "其他", "无", "待定", "未公开", "不公开", "暂无",
}
MIN_LABEL_COUNT = 5      # 出现太少的标签不进入词表
MAX_TEXT_CHARS = 1200    # 控制编码开销
PENDING = "方向待补"


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
    """推断用的文本：履历为主，必要时补摘要/院系/学科/论文题目。"""
    dossier = research.load(profile["id"]) or {}
    parts = [
        _as_text(dossier.get("biography"))[:600],
        _as_text(profile.get("summary"))[:200],
        f"院系 {profile.get('department', '')}",
        f"学科 {profile.get('discipline', '')}",
    ]
    papers = dossier.get("papers") or []
    if papers:
        titles = [_as_text(p) for p in papers[:10]]
        parts.append("论文 " + "；".join(t for t in titles if t)[:300])
    text = "；".join(p for p in parts if p.strip("； "))
    return re.sub(r"\s+", " ", text).strip()[:MAX_TEXT_CHARS]


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


# ── 验证 ────────────────────────────────────────────────────────────────
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

    sims = text_vectors @ label_vectors.T          # (n_text, n_label)
    top3 = np.argsort(-sims, axis=1)[:, :3]

    emb_hit1 = emb_hit3 = 0
    kw_hit1 = kw_hit3 = 0
    hy_hit1 = hy_hit3 = 0
    # 分层：真值标签是否在文本里被"字面写出"（履历里常有「研究方向：XXX」）
    strata = {"verbatim": {"n": 0, "emb1": 0, "kw1": 0},
              "non_verbatim": {"n": 0, "emb1": 0, "kw1": 0}}
    VERBATIM_MIN = 0.8

    for row, profile in enumerate(pool):
        truth = label_of(profile)
        ranked = [vocab[i] for i in top3[row]]
        emb_hit1 += ranked[0] == truth
        emb_hit3 += truth in ranked

        kw_scores = {lab: keyword_score(lab, texts[row]) for lab in vocab}
        kw = sorted(vocab, key=lambda lab: kw_scores[lab], reverse=True)
        kw_hit1 += kw[0] == truth
        kw_hit3 += truth in kw[:3]

        # 混合：关键词足够强就用它，否则回落到嵌入
        best_kw = kw_scores[kw[0]]
        hybrid_top1 = kw[0] if best_kw >= VERBATIM_MIN else ranked[0]
        hy_hit1 += hybrid_top1 == truth
        hy_hit3 += truth in ([kw[0]] if best_kw >= VERBATIM_MIN else ranked)

        bucket = "verbatim" if best_kw >= VERBATIM_MIN else "non_verbatim"
        strata[bucket]["n"] += 1
        strata[bucket]["emb1"] += ranked[0] == truth
        strata[bucket]["kw1"] += kw[0] == truth

    n = len(pool)
    return {
        "sampled": n,
        "vocab_size": len(vocab),
        "seconds": round(time.time() - started, 1),
        "embedding": {"top1": emb_hit1 / n if n else 0.0, "top3": emb_hit3 / n if n else 0.0},
        "keyword": {"top1": kw_hit1 / n if n else 0.0, "top3": kw_hit3 / n if n else 0.0},
        "hybrid": {"top1": hy_hit1 / n if n else 0.0, "top3": hy_hit3 / n if n else 0.0},
        "strata": {k: {"n": v["n"],
                       "embedding_top1": (v["emb1"] / v["n"]) if v["n"] else None,
                       "keyword_top1": (v["kw1"] / v["n"]) if v["n"] else None}
                   for k, v in strata.items()},
    }


# ── 推断 ────────────────────────────────────────────────────────────────
def infer(profiles: list[dict], vocab: list[str], min_score: float) -> dict:
    import numpy as np

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
    best = np.argmax(sims, axis=1)
    best_score = sims[np.arange(len(targets)), best]

    # 与验证阶段保持同一策略：关键词字面命中优先，否则回落嵌入。
    VERBATIM_MIN = 0.8
    suggestions = []
    for i, p in enumerate(targets):
        top3_idx = np.argsort(-sims[i])[:3]
        kw_scores = {lab: keyword_score(lab, texts[i]) for lab in vocab}
        kw_best = max(kw_scores, key=kw_scores.get)
        if kw_scores[kw_best] >= VERBATIM_MIN:
            chosen, score, method = kw_best, kw_scores[kw_best], "keyword"
        else:
            chosen = vocab[int(best[i])]
            score, method = float(best_score[i]), "embedding"
        suggestions.append({
            "id": p["id"],
            "name": p["name"],
            "institution": p["institution"],
            "discipline": p.get("first_level_discipline", ""),
            "suggested": chosen,
            "score": round(float(score), 4),
            "method": method,
            "top3": [{"label": vocab[int(j)], "score": round(float(sims[i][j]), 4)}
                     for j in top3_idx],
            "apply": bool(score >= min_score),
        })

    return {
        "pending": len(pending),
        "with_text": len(targets),
        "min_score": min_score,
        "would_apply": sum(1 for s in suggestions if s["apply"]),
        "by_method": {
            "keyword": sum(1 for s in suggestions if s["method"] == "keyword"),
            "embedding": sum(1 for s in suggestions if s["method"] == "embedding"),
        },
        "suggestions": suggestions,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="用嵌入模型推断研究方向并给出验证结果")
    ap.add_argument("--validate", type=int, default=0, metavar="N",
                    help="留出验证：抽样 N 条有方向的记录，报告 Top-1/Top-3")
    ap.add_argument("--apply", action="store_true", help="对「方向待补」产出建议")
    ap.add_argument("--min-score", type=float, default=0.55,
                    help="相似度阈值，低于此值不填（默认 0.55）")
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
        lines += [
            "## 留出验证",
            "",
            f"抽样 **{result['sampled']}** 条已有方向的记录，藏起方向、只用履历等文本预测：",
            "",
            "| 方法 | Top-1 | Top-3 |",
            "|:--|--:|--:|",
            f"| 关键词基线 | **{result['keyword']['top1']:.1%}** | {result['keyword']['top3']:.1%} |",
            f"| 嵌入模型（bge-small-zh-v1.5） | {result['embedding']['top1']:.1%} "
            f"| {result['embedding']['top3']:.1%} |",
            f"| 混合（关键词优先，弱则回落嵌入） | **{result['hybrid']['top1']:.1%}** "
            f"| {result['hybrid']['top3']:.1%} |",
            "",
            "### 消融：为什么关键词会赢",
            "",
            "把样本按「真值标签是否被字面写进文本」分层：",
            "",
            "| 分层 | 条数 | 关键词 Top-1 | 嵌入 Top-1 |",
            "|:--|--:|--:|--:|",
            f"| 字面命中（履历里直接写了方向） | {verb['n']} | "
            f"{(verb['keyword_top1'] or 0):.1%} | {(verb['embedding_top1'] or 0):.1%} |",
            f"| 未字面命中（需要语义推断） | {nonverb['n']} | "
            f"{(nonverb['keyword_top1'] or 0):.1%} | {(nonverb['embedding_top1'] or 0):.1%} |",
            "",
            "**这个分层的意义**：高校个人页常直接写「研究方向：XXX」，这类记录用关键词就能"
            "命中，嵌入模型反而因为把整段履历（职称、任职时间、行政职务）一起编码而被稀释。"
            "嵌入的价值只在「没有字面线索」的那一部分——所以本模块采用**混合策略**，"
            "而不是宣称嵌入一定更好。",
            "",
            f"耗时 {result['seconds']} 秒。",
            "",
        ]
        print(f"验证：关键词 Top-1 {result['keyword']['top1']:.1%} / "
              f"Top-3 {result['keyword']['top3']:.1%}；"
              f"嵌入 Top-1 {result['embedding']['top1']:.1%} / "
              f"Top-3 {result['embedding']['top3']:.1%}；混合 Top-1 {result['hybrid']['top1']:.1%}")
        (OUT_DIR / "validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")

    if args.apply:
        result = infer(pairs, vocab, args.min_score)
        lines += [
            "## 覆盖",
            "",
            f"- 方向待补：**{result['pending']}** 条",
            f"- 其中有可用文本：**{result['with_text']}** 条",
            f"- 相似度 ≥ {args.min_score} 因而会写入：**{result['would_apply']}** 条",
            f"- 低于阈值留空：**{result['with_text'] - result['would_apply']}** 条（宁可不填，不猜）",
            "",
        ]
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
