"""报告事实表：把技术报告需要引用的每个数字一次性算准，避免手抄过期。

技术报告（`workbench/aic-submission/技术报告.md`）里嵌了很多数字，历史上出过
"报告写 10,441 条、实际已 14,000+" 这种过期，而读者只会照着报告核对。
这个工具把所有要引用的量算成一张表，改稿时直接对照，不要凭记忆写。

用法::

    python -m workbench.tools.report_facts
    python -m workbench.tools.report_facts --json facts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from workbench import catalog  # noqa: E402
from workbench.collect_engineering_scale import discover_sources  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def build_facts() -> dict:
    pairs, by_id, raw, net = catalog.static_catalog()
    disciplines = catalog.disciplines(None)
    engineering = [d for d in disciplines if d.get("engineering")]
    engineering_names = {d["name"] for d in engineering}

    # 口径直接复用 catalog.coverage()——报告与接口必须一致，不要各算一套。
    # 早先这里用 `origin == "public"` 判公开来源，取到 0 条（origin 是中文字符串），
    # 这种"自己另写一套口径"正是过期数字的来源。
    cov = catalog.coverage()

    # 机构分布只在工学学科内统计（报告引用的是工学规模）。
    per_disc: dict[str, Counter] = {}
    for p in pairs:
        disc = (p.get("first_level_discipline") or "").strip()
        if disc in engineering_names:
            per_disc.setdefault(disc, Counter())[p.get("institution") or "未标注"] += 1
    shares = []
    for disc, counts in per_disc.items():
        total = sum(counts.values())
        if not total:
            continue
        top = counts.most_common(1)[0][1]
        shares.append({"discipline": disc, "total": total,
                       "institutions": len(counts), "share": round(top / total, 4)})
    shares.sort(key=lambda r: -r["share"])

    sources = discover_sources()
    fixtures = [p for p in FIXTURES.glob("*.html")]

    return {
        "records_total": cov["total_records"],
        "records_public": cov["public_records"],
        "institutions_public": cov["public_institutions"],
        "records_official": cov["official_records"],
        "disciplines_total": len(disciplines),
        "disciplines_engineering": len(engineering),
        "engineering_records": sum(d.get("count", 0) for d in engineering),
        "source_modules": len({spec["module"] for spec in sources.values()}),
        "source_keys": len(sources),
        "fixtures": len(fixtures),
        "distribution": {
            "threshold": 0.60,
            "passing": sum(1 for s in shares if s["share"] < 0.60),
            "failing": sum(1 for s in shares if s["share"] >= 0.60),
            "worst": shares[:5],
            "best": shares[-3:],
        },
    }


def as_markdown(facts: dict) -> str:
    d = facts["distribution"]
    lines = [
        "| 指标 | 数值 | 取数方式 |",
        "|:--|--:|:--|",
        f"| 全库记录 | **{facts['records_total']:,}** | `catalog.static_catalog()` |",
        f"| 公开来源记录 | **{facts['records_public']:,}** | `catalog.coverage()` |",
        f"| 公开来源机构 | **{facts['institutions_public']}** | `coverage()["public_institutions"]` |",
        f"| 一级学科 | **{facts['disciplines_total']}** | `catalog.disciplines()` |",
        f"| 其中工学 | **{facts['disciplines_engineering']}** | 同上，`engineering` |",
        f"| 工学学科—导师条目 | **{facts['engineering_records']:,}** | 工学学科的 `count` 之和 |",
        f"| 来源模块 | **{facts['source_modules']}** | `discover_sources()` 的 `module` 去重 |",
        f"| 来源 key | **{facts['source_keys']}** | `discover_sources()` 条目数 |",
        f"| 离线快照 | **{facts['fixtures']}** | `tests/fixtures/*.html` |",
        f"| 分布达标学科 | **{d['passing']}** / 未达标 **{d['failing']}** | 最大单一机构占比 < {d['threshold']:.0%} |",
        "",
        "**分布最偏的 5 个学科**（对外引用时建议连同机构数一起说）：",
        "",
        "| 学科 | 条目 | 机构 | 最大占比 |",
        "|:--|--:|--:|--:|",
    ]
    for s in d["worst"]:
        lines.append(f"| {s['discipline']} | {s['total']} | {s['institutions']} | {s['share']:.1%} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="报告事实表")
    ap.add_argument("--json", default="", help="把明细写入该 JSON")
    args = ap.parse_args()

    facts = build_facts()
    text = as_markdown(facts)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))

    if args.json:
        Path(args.json).write_text(
            json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\n明细 -> {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
