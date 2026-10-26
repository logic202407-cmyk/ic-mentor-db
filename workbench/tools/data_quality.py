"""数据质量报告：把「记录 ≠ 自然人」这件事量化成可复现的审计产物。

只读、不联网、不修改数据。输出：
- ``reports/data-quality.md``（人读）
- ``workbench/evaluation/data_quality.json``（机读，供 CI 与界面引用）

用法::

    python -m workbench.tools.data_quality            # 生成两份报告
    python -m workbench.tools.data_quality --check    # 只算不写，校验关键字段
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from workbench import catalog, public_research  # noqa: E402

OUT_MD = ROOT / "reports" / "data-quality.md"
OUT_JSON = ROOT / "workbench" / "evaluation" / "data_quality.json"

#: 缺失字段的展示名。论文/招生必须把「没取到」与「已读正文页但没有」分开列，
#: 因为二者对读者的含义完全不同：前者是采集缺口，后者才是这条记录的事实。
MISSING_LABELS = {
    "department": "缺院系",
    "homepage": "缺主页",
    "direction_pending": "研究方向待补",
    "papers_not_searched": "论文：只读到名录页、未检索到（没取到）",
    "papers_none_extracted": "论文：已读正文页但未提取到（没有）",
    "recruitment_not_searched": "招生：只读到名录页、未检索到（没取到）",
    "recruitment_none_extracted": "招生：已读正文页但未提取到（没有）",
}


def collect() -> dict:
    entries = catalog.static_catalog()[0]
    public = [p for p in entries
              if p.get("catalog_source") or (p.get("id") or "").startswith("pilot-")]
    names = Counter((p.get("name") or "").strip() for p in public if p.get("name"))
    duplicate_groups = {name: count for name, count in names.items() if count > 1}
    # 同名组有两个分母：本报告用「公开来源」范围，消歧模块用全库。
    # 两个数字都报出来，否则读者会以为其中一个是错的。
    all_names = Counter((p.get("name") or "").strip() for p in entries if p.get("name"))
    duplicate_groups_all = {name: count for name, count in all_names.items() if count > 1}

    # 主页类型复用 disambiguate_names.PageIndex 的四条判据，而不是只看「来源声明的名录页」。
    # 只按后者统计会把「被不同姓名共用的列表页」当成「本人专属页」——全库实测 458 条，
    # 恰好是 homepage_kind 模块文档里说要避免的那种误导。
    from workbench.disambiguate_names import PageIndex
    pages = PageIndex(public)
    kinds = Counter(pages.kind((p.get("homepage") or "").strip()) for p in public)

    # 每条记录的档案只读一次：先前同一份档案被读了 3 次（reports / papers / recruitment）。
    dossiers = {p["id"]: (public_research.load(p["id"]) or {}) for p in public}
    reports = [data for data in dossiers.values()
               if data.get("status") in {"ready", "catalog"}]

    def count_rows(key: str) -> int:
        total = 0
        for data in reports:
            value = data.get(key)
            if isinstance(value, list):
                total += len(value)
        return total

    years = Counter()
    for profile in public:
        for assignment in profile.get("discipline_assignments") or []:
            year = assignment.get("year")
            if year:
                years[int(year)] += 1

    collected = Counter((p.get("collected_at") or "")[:7] for p in public
                        if p.get("collected_at"))

    # 工学条目必须与界面默认范围同口径（catalog.in_scope：看全部分学科归属）。
    # 只看 first_level_discipline 会漏掉「主学科是数学、但同时在 0804 下挂靠」这类记录，
    # 全库实测漏 104 条，于是本报告与 /api/catalog/summary 各说一套数字。
    engineering_scope = sum(1 for p in public if catalog.in_scope(p))
    engineering_primary = sum(
        1 for p in public if (p.get("first_level_discipline") or "")[:2] == "08")

    def missing_state(key: str) -> tuple[int, int]:
        """返回 ``(只读到名录页、未检索, 已读正文页但未提取到)``。"""
        not_searched = not_extracted = 0
        for profile in public:
            data = dossiers[profile["id"]]
            if data.get(key):
                continue
            if data.get("status") == "ready":
                not_extracted += 1
            else:
                # status 为 catalog：只读过名录/目录页，正文页的论文/招生根本没检索过。
                not_searched += 1
        return not_searched, not_extracted

    papers_not_searched, papers_none = missing_state("papers")
    recruit_not_searched, recruit_none = missing_state("recruitment")
    missing = {
        "department": sum(1 for p in public if not (p.get("department") or "").strip()),
        "homepage": sum(1 for p in public if not (p.get("homepage") or "").strip()),
        "direction_pending": sum(
            1 for p in public
            if (p.get("direction_group") or "").strip() in ("", "方向待补")),
        "papers_not_searched": papers_not_searched,
        "papers_none_extracted": papers_none,
        "recruitment_not_searched": recruit_not_searched,
        "recruitment_none_extracted": recruit_none,
    }
    # 论文作者归属：只有「已选 OpenAlex 作者并读过作品」的才算做过归属核对
    attributed = sum(1 for data in reports if data.get("openalex_snapshot"))

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "records": {
            "total": len(entries),
            "public_source": len(public),
            "engineering": engineering_scope,
            "engineering_primary_discipline": engineering_primary,
            "distinct_names": len(names),
            "duplicate_name_groups": len(duplicate_groups),
            "duplicate_name_records": sum(duplicate_groups.values()),
            "duplicate_name_groups_all_scope": len(duplicate_groups_all),
            "max_same_name": max(duplicate_groups.values()) if duplicate_groups else 0,
        },
        "homepage_kind": dict(kinds),
        "coverage": {
            "with_any_source": sum(1 for p in public if p.get("sources")),
            "with_statements": len(reports),
            "with_papers": sum(1 for data in reports if data.get("papers")),
            "with_relations": sum(1 for data in reports if data.get("relations")),
            "with_recruitment": sum(1 for data in reports if data.get("recruitment")),
            "with_admission_notices": sum(
                1 for data in reports if data.get("admission_notices")),
            "papers_total": count_rows("papers"),
            "relations_total": count_rows("relations"),
            "admission_notices_total": count_rows("admission_notices"),
            "author_attribution_checked": attributed,
        },
        "recruitment_years": dict(sorted(years.items())),
        "collected_months": dict(sorted(collected.items())),
        "missing_fields": missing,
        "notes": {
            "records_are_not_people": ("记录条数是「学科—导师」条目：同一自然人在多个学科/"
                                       "来源下会重复计数；全库自然人数量没有独立去重统计。"),
            "homepage": ("personal=本人专属页，roster=名录/被多人共用的列表页，none=未收录主页。"
                         "判据与 workbench.disambiguate_names.PageIndex 一致：来源声明的名录页、"
                         "同一 URL 被不同姓名共用、来源标题含名录/列表/目录/索引、"
                         "通用列表文件名；只看第一条会把 458 条列表页误报成本人专属页。"),
            "engineering": ("工学条目与界面默认范围（catalog.in_scope）同口径：只要任一分学科"
                            "归属落在 08 开头就算工学。仅按一级学科字段统计会少 104 条。"),
            "duplicate_names": ("同名组列出两个分母：public_source 为本报告口径（公开来源记录），"
                                "all_scope 与 workbench.disambiguate_names 同口径（全库）。"),
            "missing_fields": ("论文/招生的缺失分两行：「没取到」= 档案状态 catalog（只读到名录页，"
                               "正文页未检索）；「没有」= 档案状态 ready（正文页已读但没提取到）。"),
            "author_attribution": "只统计「已选 OpenAlex 作者并读过作品」的记录，不代表全库。",
        },
    }


def render(payload: dict) -> str:
    r = payload["records"]
    c = payload["coverage"]
    lines = [
        "# 数据质量报告（只读生成）",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 命令：`python -m workbench.tools.data_quality`",
        "",
        "## 一、记录数 ≠ 自然人数",
        "",
        "| 指标 | 数值 |",
        "|:--|--:|",
        f"| 记录条数（学科—导师条目） | {r['total']:,} |",
        f"| 其中公开来源 | {r['public_source']:,} |",
        f"| 其中工学条目（与界面默认范围同口径） | {r['engineering']:,} |",
        f"| 其中工学条目（仅按一级学科字段，会少算） "
        f"| {r['engineering_primary_discipline']:,} |",
        f"| 不同姓名数 | {r['distinct_names']:,} |",
        f"| 同名组（公开来源口径） | {r['duplicate_name_groups']:,} |",
        f"| 同名组（全库口径，与消歧模块一致） "
        f"| {r['duplicate_name_groups_all_scope']:,} |",
        f"| 同名涉及记录 | {r['duplicate_name_records']:,} |",
        "",
        f"> {payload['notes']['records_are_not_people']}",
        "",
        f"> 工学条目口径：{payload['notes']['engineering']}",
        "",
        f"> 同名组口径：{payload['notes']['duplicate_names']}",
        "",
        "## 二、主页与来源覆盖",
        "",
        "| 主页类型 | 记录数 |",
        "|:--|--:|",
    ]
    for kind, count in sorted(payload["homepage_kind"].items(),
                              key=lambda item: -item[1]):
        lines.append(f"| {kind} | {count:,} |")
    lines += [
        "",
        f"> 主页类型口径：{payload['notes']['homepage']}",
        "",
        f"- 有来源条目：{c['with_any_source']:,}",
        f"- 有论文记录：{c['with_papers']:,}（共 {c['papers_total']:,} 条论文线索）",
        f"- 有师承表述：{c['with_relations']:,}（共 {c['relations_total']:,} 条）",
        f"- 有招生说明：{c['with_recruitment']:,}；院系公告：{c['with_admission_notices']:,}",
        f"- 已做作者归属核对：{c['author_attribution_checked']:,}"
        f"（{payload['notes']['author_attribution']}）",
        "",
        "## 三、缺失字段（明确区分「没有」与「没取到」）",
        "",
        "| 字段 | 缺失条数 |",
        "|:--|--:|",
    ]
    for key in ("department", "homepage", "direction_pending",
                "papers_not_searched", "papers_none_extracted",
                "recruitment_not_searched", "recruitment_none_extracted"):
        if key not in payload["missing_fields"]:
            continue
        lines.append(f"| {MISSING_LABELS[key]} | {payload['missing_fields'][key]:,} |")
    lines += [
        "",
        f"> {payload['notes']['missing_fields']}",
        "",
        "## 四、招生年份与采集时间",
        "",
        f"- 招生年份分布：{json.dumps(payload['recruitment_years'], ensure_ascii=False)}",
        f"- 采集月份分布：{json.dumps(payload['collected_months'], ensure_ascii=False)}",
        "",
        "## 五、口径与边界",
        "",
        "- 不联网检查来源存活；「来源已失效」需人工核对后标注，不在此处推断。",
        "- 缺失一律保留为缺失，不填 0、不用同类均值替代。",
        "- 同名、主页错配等风险由 `workbench.disambiguate_names` 与人标注流程另行评估。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="数据质量报告（只读）")
    ap.add_argument("--check", action="store_true", help="只计算并校验关键字段，不写文件")
    args = ap.parse_args(argv)
    payload = collect()
    if args.check:
        problems = []
        if payload["records"]["total"] < 1000:
            problems.append("记录数异常偏小")
        if payload["records"]["public_source"] <= 0:
            problems.append("公开来源记录为 0")
        if not payload["homepage_kind"]:
            problems.append("主页类型统计为空")
        if problems:
            print("数据质量检查失败：" + "；".join(problems))
            return 1
        print(f"数据质量检查通过：{payload['records']['total']:,} 条记录，"
              f"{payload['records']['duplicate_name_groups']:,} 组同名，"
              f"主页类型 {payload['homepage_kind']}")
        return 0
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(render(payload), encoding="utf-8", newline="\n")
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"写出 {OUT_MD.relative_to(ROOT)} 与 {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())