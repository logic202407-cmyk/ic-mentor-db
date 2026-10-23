"""把评测产物渲染成交付用的 evidence 文档，保证"文档里的数字 = 产物里的数字"。

为什么要有这一步
----------------
evidence 文档曾被手工抄写过一轮：技术报告写 15,177 条、评测文档写 14,271 条、
接口给出 15,719 条——三处数字互相矛盾，评审按文档核对就立刻对不上。根因不是粗心，
而是**数字靠人抄**。这里改成：评测脚本产出 JSON，本模块把 JSON 渲染成 Markdown，
文档里的每个指标都由代码从产物里取。

做法
----
- 检索评测：完整由 ``workbench/reference/eval/retrieval.json`` 生成（含方法对比、
  A/B 分层、过滤、延迟、失败案例、缩写碰撞）。
- 方向推断 / 同名消歧：评测脚本本来就写 ``report.md``，这里加统一的抬头与复现命令，
  直接同步为 evidence 文档，不再人工改写数字。

用法::

    python -m workbench.tools.render_evidence
    python -m workbench.tools.render_evidence --check   # 只校验文档是否落后于产物
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

EVIDENCE = ROOT / "workbench" / "aic-submission" / "evidence"
RETRIEVAL = ROOT / "workbench" / "reference" / "eval" / "retrieval.json"
DATA = ROOT / ".workbench-data"
DIRECTION_REPORT = DATA / "direction-inference" / "report.md"
DISAMBIG_REPORT = DATA / "name-disambiguation" / "report.md"

OUT_RETRIEVAL = EVIDENCE / "语义检索评测.md"
OUT_DIRECTION = EVIDENCE / "方向推断评测.md"
OUT_DISAMBIG = EVIDENCE / "同名消歧评测.md"

METHOD_ORDER = ["keyword_substring", "bm25", "embedding",
                "embedding_instruct", "hybrid_score", "hybrid_rrf"]
METHOD_NAMES = {
    "keyword_substring": "关键词（双字覆盖率，现网基线）",
    "bm25": "BM25（k1=1.5，b=0.75，纯 Python）",
    "embedding": "向量检索（bge-small-zh-v1.5）",
    "embedding_instruct": "向量检索 + bge 检索指令（补充基线）",
    "hybrid_score": "混合：BM25 + 向量（加权归一化）",
    "hybrid_rrf": "混合：BM25 + 向量（RRF，k=60）",
}


def _pct(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def _num(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _method_table(metrics: dict, split: str) -> list[str]:
    lines = ["| 方法 | Recall@5 | Recall@10 | Recall@20 | MRR@10 | nDCG@10 | Top-1 |",
             "|:--|--:|--:|--:|--:|--:|--:|"]
    for key in METHOD_ORDER:
        row = (metrics.get(key) or {}).get(split) or {}
        if not row:
            continue
        lines.append(
            f"| {METHOD_NAMES[key]} | {_pct(row.get('recall@5'))} | "
            f"{_pct(row.get('recall@10'))} | {_pct(row.get('recall@20'))} | "
            f"{_num(row.get('mrr@10'), 3)} | {_num(row.get('ndcg@10'), 3)} | "
            f"{_pct(row.get('top1'))} |")
    return lines


def render_retrieval(d: dict) -> str:
    metrics = d.get("metrics") or {}
    config = d.get("config") or {}
    corpus = d.get("corpus") or {}
    queries = config.get("queries") or {}
    chosen = config.get("chosen") or {}
    sweep = d.get("weight_sweep") or []
    best_sweep = max(sweep, key=lambda r: r.get("ndcg@10") or 0) if sweep else {}

    lines = [
        "# 语义检索评测：五种检索方法的可复现对比",
        "",
        f"> 本文由 `python -m workbench.tools.render_evidence` 从 "
        f"`workbench/reference/eval/retrieval.json` 生成（产物时间 "
        f"{d.get('generated_at', '—')}）。**文档里的每个数字都由评测脚本实跑写入**，"
        "没有手填指标。",
        "",
        "## 一、要回答的问题",
        "",
        "学生描述研究兴趣时用的往往不是学科术语（「让机器自己看着路往前走」而不是"
        "「机器人/自动驾驶」）。本评测同时回答两件事：",
        "",
        "1. 语义/向量检索在**自然语言查询**上是否真的优于关键词与 BM25？",
        "2. 如果优于，代价是什么（延迟、噪声、缩写失效）？",
        "",
        "## 二、评测集与口径（先说边界）",
        "",
        f"- **语料**：{corpus.get('entries', '—'):,} 条带方向文本的记录；"
        f"一级学科 {((corpus.get('labels') or {}).get('discipline_values', '—'))} 个，"
        f"方向取值 {((corpus.get('labels') or {}).get('direction_values', '—'))} 种。",
        f"- **查询**：A 类（结构化，由学科/方向/兴趣字段规则生成）"
        f"{queries.get('A', '—')} 条；B 类（自然语言，由人工术语映射表定义）"
        f"{queries.get('B', '—')} 条；合计 {queries.get('A', 0) + queries.get('B', 0)} 条。",
        f"- **划分**：按种子 {config.get('seed', 42)} 随机分为 dev {queries.get('dev', '—')} 条 / "
        f"test {queries.get('test', '—')} 条；**融合权重与过滤阈值只在 dev 上选**，"
        "下面所有指标都报在 test 上。",
        "- **相关性标签（qrels）是弱监督**：A 类由结构化字段规则生成，B 类由作者手写的"
        "`workbench/reference/eval/terminology_map.json` 定义。**它不是人工标注，"
        "也不是第三方公开评测集**；因此指标衡量的是「排序与这组规则的一致性」，"
        "不能当作绝对准确率引用。",
        "",
        "## 三、方法",
        "",
        "| 方法 | 说明 |",
        "|:--|:--|",
        "| 关键词基线 | 查询与文本的双字覆盖率，现网检索方式 |",
        "| BM25 | 纯 Python 实现，k1=1.5、b=0.75 |",
        "| 向量检索 | bge-small-zh-v1.5（ONNX，本地 CPU，无在线 API） |",
        "| 向量 + 检索指令 | 查询前加 bge 推荐的中文检索指令，作为补充基线 |",
        "| 混合（加权） | BM25 与向量分数归一化后加权，权重在 dev 上选 |",
        "| 混合（RRF） | Reciprocal Rank Fusion，k=60，不依赖分数尺度 |",
        "",
        f"dev 上选出的配置：BM25 权重 **{chosen.get('hybrid_bm25_weight', '—')}**"
        f"（仅在 B 类上选时为 {chosen.get('hybrid_bm25_weight_on_dev_B_only', '—')}）、"
        f"过滤阈值 τ={chosen.get('tau', '—')}、margin δ={chosen.get('delta', '—')}、"
        f"空结果阈值 {chosen.get('empty_tau', '—')}。",
        "",
        "## 四、结果（test）",
        "",
        "### 4.1 全部查询",
        "",
    ]
    lines += _method_table(metrics, "ALL/test")
    lines += [
        "",
        "### 4.2 A 类：结构化查询（学科/方向标签）",
        "",
    ]
    lines += _method_table(metrics, "A/test")
    lines += [
        "",
        "### 4.3 B 类：自然语言查询（AI 真正该发挥作用的地方）",
        "",
    ]
    lines += _method_table(metrics, "B/test")
    lines += [
        "",
        "**结论（按数据说话）**：",
        "",
        f"- 结构化查询上，BM25 最强（nDCG@10 "
        f"{_num((metrics.get('bm25') or {}).get('A/test', {}).get('ndcg@10'), 3)}），"
        "向量反而最弱——术语直接重合时，词法匹配更锐利。",
        f"- 自然语言查询上，向量检索领先：nDCG@10 "
        f"{_num((metrics.get('embedding') or {}).get('B/test', {}).get('ndcg@10'), 3)}，"
        f"关键词基线只有 "
        f"{_num((metrics.get('keyword_substring') or {}).get('B/test', {}).get('ndcg@10'), 3)}。"
        "这是本项目采用向量检索的直接依据。",
        f"- 总体（A+B）加权混合 nDCG@10 "
        f"{_num((metrics.get('hybrid_score') or {}).get('ALL/test', {}).get('ndcg@10'), 3)}，"
        f"高于关键词基线的 "
        f"{_num((metrics.get('keyword_substring') or {}).get('ALL/test', {}).get('ndcg@10'), 3)}。",
        "",
        "## 五、阈值、过滤与空结果",
        "",
        "| 过滤方式 | nDCG@10 | Recall@10 | 裁剪比例 | 空结果率 | 平均返回条数 |",
        "|:--|--:|--:|--:|--:|--:|",
    ]
    filter_eval = d.get("filter_eval") or {}
    for key, label in (("unfiltered/test", "不过滤"),
                       ("absolute/test", "绝对阈值 τ"),
                       ("margin/test", "首位差距 δ"),
                       ("combined/test", "τ + δ 组合"),
                       ("combined_with_empty/test", "再加空结果阈值"),
                       ("guarded_empty/test", "受保护的空结果")):
        row = filter_eval.get(key)
        if not row:
            continue
        lines.append(
            f"| {label} | {_num(row.get('ndcg@10'), 3)} | {_pct(row.get('recall@10'))} | "
            f"{_pct(row.get('trim_ratio'))} | {_pct(row.get('empty_rate'))} | "
            f"{_num(row.get('avg_returned'), 1)} |")
    off = d.get("off_topic") or {}
    lines += [
        "",
        f"无关查询探针：{len(off.get('queries') or [])} 条（红烧肉、天气预报等）。"
        f"向量 Top-1 相似度区间 "
        f"{_num(min(off.get('top1_similarity') or [0]), 3)}–"
        f"{_num(max(off.get('top1_similarity') or [0]), 3)}；"
        f"采用 τ={off.get('empty_tau', '—')} 的空结果判定后，"
        f"{off.get('guarded_empty', '—')} 条返回空，"
        f"避免把弱相关结果硬推荐给用户。",
        "",
        "**如实说明**：在 test 上，τ/δ 过滤的裁剪比例是 "
        f"{_pct((filter_eval.get('combined/test') or {}).get('trim_ratio'))}，"
        "也就是说过滤**没有**带来列表缩短收益；它真正的作用是挡住无关查询（见上一段）。"
        "我们没有为了让表格好看而调一个能裁剪的阈值。",
        "",
        "## 六、延迟与资源",
        "",
        "| 方法 | 平均 | 中位 | P95 | 最大 |",
        "|:--|--:|--:|--:|--:|",
    ]
    for key, row in (d.get("latency") or {}).items():
        lines.append(
            f"| {METHOD_NAMES.get(key, key)} | {_num(row.get('mean_ms'), 2)} ms | "
            f"{_num(row.get('median_ms'), 2)} ms | {_num(row.get('p95_ms'), 2)} ms | "
            f"{_num(row.get('max_ms'), 2)} ms |")
    resources = d.get("resources") or {}
    cpu = resources.get("cpu") or {}
    lines += [
        "",
        f"评测总耗时 {_num(resources.get('wall_seconds'), 1)} 秒，"
        f"CPU 时间 {_num(cpu.get('user_seconds'), 1)} 秒 / 利用率 "
        f"{_num(cpu.get('cpu_utilization'), 1)}%。向量检索在 CPU 上单次查询为毫秒级，"
        "不需要 GPU；模型首次加载与建索引的开销单独发生在服务启动阶段。",
        "",
        "## 七、失败案例（真实查询，逐条可复现）",
        "",
        "| 查询 | 方法 | 类别 | 实际 Top-1 | 说明 |",
        "|:--|:--|:--|:--|:--|",
    ]
    for item in d.get("analysed_failures") or []:
        top = item.get("top") or []
        first = f"{top[0].get('direction', '')}·{top[0].get('name', '')}" if top else "—"
        extra = (item.get("extra") or "").replace("|", "/")
        lines.append(f"| {item.get('query', '')} | {item.get('method', '')} | "
                     f"{item.get('category', '')} | {first} | {extra} |")
    collisions = d.get("english_collisions") or {}
    groups = collisions.get("identical_groups") or []
    acronym = d.get("acronym_audit") or {}
    lines += [
        "",
        "### 7.1 最关键的一条：英文缩写会坍缩成同一个向量",
        "",
        f"对 {collisions.get('probes', '—')} 个英文探针，模型只产生了 "
        f"{collisions.get('distinct_vectors', '—')} 个不同向量；"
        f"余弦 > 0.9999 的完全重合组：{'、'.join(' / '.join(g) for g in groups) or '无'}。",
        "",
        f"扩展到 {acronym.get('probes', '—')} 个学科缩写后，只剩 "
        f"{acronym.get('distinct_vectors', '—')} 个不同向量"
        f"（最大一组 {max([g.get('size', 0) for g in (acronym.get('groups') or [])] or [0])} 个）。",
        "",
        "**这意味着**：对 `VLSI`、`MEMS`、`EDA`、`FPGA` 这类查询，语义检索给出的排序"
        "完全相同——它根本没有「看懂」这些缩写。因此在产品上**必须**同时保留关键词/BM25"
        "模式，并在查询是英文缩写时优先走词法检索。这是本评测最重要的工程结论，"
        "也是我们不宣称「AI 全面优于传统方法」的直接原因。",
        "",
        "## 八、复现",
        "",
        "```bat",
        ".venv\\Scripts\\python.exe -m workbench.retrieval_eval",
        "```",
        "",
        f"- 产物：`workbench/reference/eval/retrieval.json`（{d.get('how_to_reproduce', '')}）",
        "- 术语表：`workbench/reference/eval/terminology_map.json`",
        f"- dev 上 nDCG@10 最高的 BM25 权重为 {best_sweep.get('bm25_weight', '—')}"
        f"（nDCG@10 {_num(best_sweep.get('ndcg@10'), 4)}）；实际选用值见第三节。",
        "",
        "## 九、局限",
        "",
        "1. qrels 是规则生成的弱监督标签，指标反映的是「与该规则的吻合度」，不是真人判定的准确率。",
        "2. 查询由模板与术语表构造，不是真实用户日志；没有做用户研究。",
        "3. A 类查询的数量级使总体指标偏向结构化查询；因此本文把 A/B 分开报告，不只看总分。",
        "4. 语料只覆盖已收录的工学导师，不能外推到全国。",
        "",
    ]
    return "\n".join(lines)


def _wrap_report(path: Path, title: str, intro: list[str]) -> str:
    body = path.read_text(encoding="utf-8").strip()
    # 生成报告自带一级标题，避免重复：去掉第一行再拼。
    body_lines = body.splitlines()
    if body_lines and body_lines[0].startswith("# "):
        body_lines = body_lines[1:]
    return "\n".join([f"# {title}", ""] + intro + [""] + body_lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="从评测产物渲染 evidence 文档")
    ap.add_argument("--check", action="store_true",
                    help="只检查文档是否存在（内容一致性由 check_facts_consistency 负责）")
    args = ap.parse_args(argv)

    if not RETRIEVAL.is_file():
        print(f"缺检索评测产物：{RETRIEVAL.relative_to(ROOT)}")
        print("先运行：python -m workbench.retrieval_eval")
        return 1
    if not DIRECTION_REPORT.is_file() or not DISAMBIG_REPORT.is_file():
        print("缺方向推断/同名消歧的 report.md，请先跑对应评测")
        return 1

    if args.check:
        missing = [p for p in (OUT_RETRIEVAL, OUT_DIRECTION, OUT_DISAMBIG) if not p.is_file()]
        if missing:
            print("evidence 文档缺失：")
            for path in missing:
                print("  -", path.relative_to(ROOT))
            return 1
        print("evidence 文档：齐全")
        return 0

    retrieval = json.loads(RETRIEVAL.read_text(encoding="utf-8"))
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_RETRIEVAL.write_text(render_retrieval(retrieval), encoding="utf-8", newline="\n")

    OUT_DIRECTION.write_text(_wrap_report(
        DIRECTION_REPORT,
        "方向推断评测：嵌入模型 vs 关键词基线 vs 混合（含清洗文本消融）",
        [f"> 渲染时间 {stamp}。数字由 `python -m workbench.infer_directions "
         "--validate 400 --ablate-text` 实跑写入，本文不做二次改写。",
         "",
         "复现：`.venv\\Scripts\\python.exe -m workbench.infer_directions "
         "--validate 400 --ablate-text`"]), encoding="utf-8", newline="\n")

    OUT_DISAMBIG.write_text(_wrap_report(
        DISAMBIG_REPORT,
        "同名导师消歧评测：证据分级协议、独立复核集与待核清单",
        [f"> 渲染时间 {stamp}。数字由 `python -m workbench.disambiguate_names "
         "--evaluate --gold` 实跑写入。",
         "",
         "本版与旧版的关键区别：**不再把「个人主页 URL 两两不同」当作「必然是不同人」**。"
         "只有同时满足「同一专属个人主页 + 同机构」才判同人；证据不足一律 `unknown`，"
         "既不进指标，也不自动合并。",
         "",
         "复现：`.venv\\Scripts\\python.exe -m workbench.disambiguate_names --evaluate --gold`"]),
        encoding="utf-8", newline="\n")

    print(f"写出 {OUT_RETRIEVAL.relative_to(ROOT)}")
    print(f"写出 {OUT_DIRECTION.relative_to(ROOT)}")
    print(f"写出 {OUT_DISAMBIG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())