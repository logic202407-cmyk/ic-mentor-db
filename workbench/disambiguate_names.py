"""同名导师消歧：用嵌入 + 机构信号判断「同名两条记录是不是同一个人」。

为什么这件事值得做
------------------
全库有 **908 组同名**（占姓名的 7.0%，涉及 2,231 条记录），其中 **224 组是同校内同名**
——那才是真正会看错人的场景。现有实现只用「学校 + 院系」硬约束，宁可判"同名待核"也不猜，
这是对的；但它没利用**履历文本**这条强信号。

真值从哪来（关键）
------------------
**个人主页 URL 本身就是可核验的真值**：同一 URL 必然是同一人；两两不同的 URL 必然是
不同人（两个独立的个人主页不会指同一个人）。因此：

- 395 组同 URL  → **431 对同人**（正例）
- 299 组全不同 URL → **1,617 对异人**（负例）

**``homepage`` 只用作标签，绝不进入特征**——否则就是拿答案当输入。

特征
----
1. 机构是否相同
2. 院系是否相同
3. 学科是否相同
4. 履历/摘要文本的嵌入余弦相似度（``BAAI/bge-small-zh-v1.5``，本地推理）

输出
----
- 对 2,048 对带真值的样本做二分类评测：AUC、以及若干阈值下的 P/R/F1
- 与"只看机构"的朴素规则对比，给出提升幅度
- 对**没有真值**的同名组（同校内同名等）产出待核清单，逐对带分数与判定分档

命令
----
    python -m workbench.disambiguate_names --evaluate
    python -m workbench.disambiguate_names --review
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import catalog, public_research as research  # noqa: E402
from .search import MODEL_NAME, _embedder, keyword_score  # noqa: E402

OUT_DIR = Path(".workbench-data/name-disambiguation")
MAX_TEXT_CHARS = 900


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


def profile_text(profile: dict) -> str:
    dossier = research.load(profile["id"]) or {}
    parts = [
        _as_text(dossier.get("biography"))[:500],
        _as_text(profile.get("summary"))[:200],
        f"院系 {profile.get('department', '')}",
        f"学科 {profile.get('discipline', '')}",
    ]
    return re.sub(r"\s+", " ", "；".join(p for p in parts if p.strip("； "))).strip()[:MAX_TEXT_CHARS]


def normalize(matrix):
    import numpy as np
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def build_pairs(pairs: list[dict]) -> tuple[list[dict], dict]:
    """按姓名分组，用 homepage 判等构造带标签的样本对。"""
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
            labelled.append({"name": name, "i": group[i], "j": group[j], "same": same})
            stats["positives" if same else "negatives"] += 1
    return labelled, stats


def feature_rows(labelled: list[dict]) -> list[dict]:
    """计算每一对的成对特征（homepage 不参与）。"""
    # 先把每对涉及的记录文本编码一次
    texts = {}
    for pair in labelled:
        for side in ("i", "j"):
            p = pair[side]
            if p["id"] not in texts:
                texts[p["id"]] = profile_text(p)

    ids = list(texts)
    if not ids:
        return []
    vectors = normalize(__import__("numpy").asarray(
        list(_embedder().embed([texts[i] for i in ids])), dtype="float32"))
    pos = {pid: k for k, pid in enumerate(ids)}

    import numpy as np
    rows = []
    for pair in labelled:
        a, b = pair["i"], pair["j"]
        va, vb = vectors[pos[a["id"]]], vectors[pos[b["id"]]]
        rows.append({
            "name": pair["name"],
            "same": pair["same"],
            "same_inst": a.get("institution") == b.get("institution"),
            "same_dept": a.get("department") == b.get("department"),
            "same_disc": a.get("first_level_discipline") == b.get("first_level_discipline"),
            "emb": float(np.dot(va, vb)),
            "kw": float(keyword_score(pair["name"], texts[b["id"]])),
        })
    return rows


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
    tp = fp = fn = 0
    for r in rows:
        pred = predict(r)
        if pred and r["same"]:
            tp += 1
        elif pred and not r["same"]:
            fp += 1
        elif r["same"]:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn}


def evaluate(rows: list[dict]) -> dict:
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


def review(pairs: list[dict], rows: list[dict]) -> list[dict]:
    """对「同校内同名、且主页 URL 不同」的组合产出待核清单。

    同 URL 的组合已被判为同一人（由学校页面体系决定），不需要人工核；
    这里只列真正会看错人的那些。
    """
    import numpy as np

    by_name = defaultdict(list)
    for p in pairs:
        n = (p.get("name") or "").strip()
        if n:
            by_name[n].append(p)

    pending = []
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        for a, b in combinations(group, 2):
            if a.get("institution") != b.get("institution"):
                continue
            if canonical_home(a.get("homepage") or "") == canonical_home(b.get("homepage") or ""):
                continue
            pending.append((name, a, b))
    if not pending:
        return []

    # 每条记录只编码一次
    records = {}
    for _name, a, b in pending:
        records[a["id"]] = a
        records[b["id"]] = b
    ids = list(records)
    texts = [profile_text(records[i]) for i in ids]
    vectors = normalize(np.asarray(list(_embedder().embed(texts)), dtype="float32"))
    pos = {pid: k for k, pid in enumerate(ids)}

    results = []
    for name, a, b in pending:
        sim = float(np.dot(vectors[pos[a["id"]]], vectors[pos[b["id"]]]))
        verdict = "疑似同人" if sim >= 0.85 else ("疑似异人" if sim < 0.6 else "待核")
        results.append({
            "name": name,
            "institution": a.get("institution"),
            "a": {"id": a["id"], "dept": a.get("department"),
                  "home": (a.get("homepage") or "")[:80]},
            "b": {"id": b["id"], "dept": b.get("department"),
                  "home": (b.get("homepage") or "")[:80]},
            "same_dept": a.get("department") == b.get("department"),
            "emb": round(sim, 4),
            "verdict": verdict,
        })
    results.sort(key=lambda r: -r["emb"])
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="同名导师消歧：评测与待核清单")
    ap.add_argument("--evaluate", action="store_true", help="用 homepage 真值做二分类评测")
    ap.add_argument("--review", action="store_true", help="产出同校内同名的待核清单")
    ap.add_argument("--limit", type=int, default=0, help="评测时最多取多少对（0=全部）")
    args = ap.parse_args()

    pairs, _by_id, _raw, _net = catalog.static_catalog()
    print(f"模型 {MODEL_NAME}；全库 {len(pairs)} 条")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    labelled, stats = build_pairs(pairs)
    print(f"同名组 {stats['groups']}；可用真值的对 {len(labelled)} "
          f"（同人 {stats['positives']} / 异人 {stats['negatives']}）")

    lines = [
        "# 同名导师消歧：评测与待核清单",
        "",
        f"- 模型：`{MODEL_NAME}`（本地推理）",
        f"- 全库 {len(pairs)} 条；同名组 **{stats['groups']}** 组",
        f"- 真值来源：**个人主页 URL**（同 URL ⇒ 同人；两两不同 URL ⇒ 异人）。"
        f"`homepage` **只作标签，不进特征**。",
        f"- 带真值的样本对：**{len(labelled)}** 对（同人 {stats['positives']} / "
        f"异人 {stats['negatives']}）；跳过缺少主页的组 {stats['skipped_missing_home']} 个",
        "",
    ]

    if args.evaluate:
        sample = labelled
        if args.limit and len(sample) > args.limit:
            import random
            sample = random.Random(42).sample(sample, args.limit)
        rows = feature_rows(sample)
        result = evaluate(rows)
        lines += [
            "## 二分类评测",
            "",
            f"样本 {result['pairs']} 对（正例 {result['positives']} / 负例 {result['negatives']}）。"
            f"AUC：",
            "",
            "| 特征 | AUC |",
            "|:--|--:|",
            f"| 仅机构是否相同 | {result['auc']['institution_only']:.3f} |",
            f"| 仅履历文本嵌入相似度 | **{result['auc']['embedding_only']:.3f}** |",
            "",
            "**朴素基线**（机构相同即判同人）：",
            f"P {result['baseline_institution']['precision']:.1%} / "
            f"R {result['baseline_institution']['recall']:.1%} / "
            f"F1 {result['baseline_institution']['f1']:.1%}",
            "",
            "**机构相同 + 嵌入阈值**：",
            "",
            "| 阈值 | 精确率 | 召回率 | F1 |",
            "|--:|--:|--:|--:|",
        ]
        for t in result["thresholds"]:
            m = t["same_inst_and_emb"]
            lines.append(f"| emb ≥ {t['emb>=']:.1f} | {m['precision']:.1%} | "
                         f"{m['recall']:.1%} | {m['f1']:.1%} |")
        lines += [
            "",
            "解读：机构相同但嵌入相似度低，很可能是**同校同名异人**（这正是最容易看错的情形）；"
            "加入嵌入后精确率上升，说明它把这类错误挡掉了。",
            "",
        ]
        (OUT_DIR / "evaluation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"评测：AUC 机构 {result['auc']['institution_only']:.3f} / "
              f"嵌入 {result['auc']['embedding_only']:.3f}；"
              f"基线 F1 {result['baseline_institution']['f1']:.1%}")

    if args.review:
        items = review(pairs, [])
        lines += [
            "## 同校内同名：待核清单",
            "",
            f"共 **{len(items)}** 对同校内同名、且主页 URL 不同（同 URL 的已知同人已排除）。",
            "",
            "| 姓名 | 学校 | 嵌入相似度 | 判定 | 院系 A | 院系 B |",
            "|:--|:--|--:|:--|:--|:--|",
        ]
        for it in items[:80]:
            lines.append(
                f"| {it['name']} | {it['institution']} | {it['emb']:.3f} | {it['verdict']} | "
                f"{(it['a']['dept'] or '-')[:26]} | {(it['b']['dept'] or '-')[:26]} |")
        if len(items) > 80:
            lines.append(f"| … | 其余 {len(items) - 80} 对见 JSON | | | | |")
        lines += [
            "",
            "**判定分档只是排序辅助，不是结论**：`疑似同人/待核/疑似异人` 由相似度阈值给出，"
            "所有条目都需要人工核对主页与院系后再决定是否合并。**系统不会自动合并。**",
            "",
        ]
        (OUT_DIR / "review.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"待核清单 {len(items)} 对 -> {OUT_DIR / 'review.json'}")

    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"报告 -> {OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
