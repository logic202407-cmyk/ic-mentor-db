"""对外材料的事实一致性检查：把「写死在文档里的数字」钉到实际数据上。

为什么需要这个
--------------
仓库里已有两道数字检查，但都覆盖不到真正会出事的地方：

- `tools/check_doc_numbers.mjs` 校验的是**旧集成电路专题**（3,179 人 / 22 校）；
- `workbench/tools/check_readme_badges` 只校验 README 顶部徽章与体积表。

于是技术报告里长期写着「15,177 条 / 工学 10,540 / 公开来源 12,004 / 61 所」，
而事实表早已是「15,719 / 11,082 / 12,546 / 67」——**读者按报告核对接口，立刻就矛盾**。
这类过期不是粗心，是缺少机制：数字散落在 6 个文件里，没人会每次扩数据都手改一遍。

做法
----
不搞"全文正则扫数字"（历史段落里的旧数字会被误杀）。这里维护一张**显式声明表**：
每条 claim 指定"文件 + 必须同现的上下文 + 抓数字的正则 + 对应事实键"。
只有真正对外承诺当前口径的句子才会被检查；历史叙述（CHANGELOG 的旧版本数字、
业绩批次里的 `10,181→10,299`）不在此列——那是历史事实，改了反而是篡改。

`CHANGELOG.md` 里的 `321 / 715` 经 `git show v1.0.0:…`、`v1.1.0:…` 实测分别为
两个 tag 当时的真实测试方法数，因此**不纳入**本检查。

用法::

    python -m workbench.tools.check_facts_consistency
    python -m workbench.tools.check_facts_consistency --json out.json

退出码：全部一致 0，否则 1。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from workbench.tools.check_readme_badges import count_tests  # noqa: E402
from workbench.tools.report_facts import build_facts  # noqa: E402


def _extra_facts() -> dict:
    """事实表之外还需要校验的量。"""
    facts: dict = {}
    try:
        from workbench.tools.pack_research_bundle import MANIFEST
        if MANIFEST.is_file():
            facts["dossiers"] = json.loads(MANIFEST.read_text(encoding="utf-8")).get("count")
    except Exception:  # noqa: BLE001 - 校验工具不该因为读不到清单就崩
        pass
    facts["tests"] = count_tests()

    # AI 两处产物的计数：从**仓库副本**读（而不是 `.workbench-data/`），
    # 这样干净 clone 上也能校验报告里引用的 AI 数字。
    ai_dir = ROOT / "workbench/reference/ai"
    try:
        sug = json.loads((ai_dir / "direction_suggestions.json").read_text(encoding="utf-8"))
        facts["ai_pending"] = sug.get("pending")
        facts["ai_with_text"] = sug.get("with_text")
        facts["ai_would_apply"] = sug.get("would_apply")
    except (OSError, ValueError):
        pass
    try:
        review = json.loads((ai_dir / "name_review.json").read_text(encoding="utf-8"))
        facts["name_review_pairs"] = len(review) if isinstance(review, list) else None
    except (OSError, ValueError):
        pass
    return facts


# 每条：文件、名称、上下文正则（必须与数字同现）、抓数字、事实键、可选的分组序号。
# 用"上下文 + 正则"而不是裸数字，是为了改一个数字时不会连累无关句子。
CLAIMS: list[dict] = [
    # ── 技术报告：第五章规模数据（P0-1 的原发地）────────────────────────
    # 注意：这里不用裸的「全库…条」，因为同一章里还有「全库有 4,936 条记录的研究方向待补」
    # 这种**不同量纲**的句子。误杀一次，维护者就会把整条检查关掉——所以宁可把上下文
    # 写窄，也不要写宽。
    {"file": "workbench/aic-submission/技术报告.md", "name": "全库记录",
     "context": r"工作台目录含", "pattern": r"工作台目录含\s*[*]{0,2}([\d,]{3,})", "fact": "records_total"},
    {"file": "workbench/aic-submission/技术报告.md", "name": "工学条目",
     "context": r"工学", "pattern": r"工学\s*38\s*个一级学科\s*[*]{0,2}([\d,]{3,})", "fact": "engineering_records"},
    {"file": "workbench/aic-submission/技术报告.md", "name": "公开来源记录",
     "context": r"公开来源", "pattern": r"公开来源\s*[*]{0,2}([\d,]{3,})", "fact": "records_public"},
    {"file": "workbench/aic-submission/技术报告.md", "name": "公开来源机构",
     "context": r"涉及", "pattern": r"涉及\s*[*]{0,2}(\d+)\s*[*]{0,2}\s*所", "fact": "institutions_public"},
    {"file": "workbench/aic-submission/技术报告.md", "name": "方向待补条数",
     "context": r"方向待补", "pattern": r"全库有\s*[*]{0,2}([\d,]{3,})", "fact": "dir_pending"},
    # 测试数**故意不在这里校验**。它会随着"新增一个测试"就变，而正文写死一个数字
    # 会让每次加测试都要改文档。权威载体是 README 顶部徽章（由 check_readme_badges
    # 用 AST 统计并支持 --fix）。正文只说"全部通过"，不承诺具体项数。

    # ── 提交材料 README：复现性核验表（P0-4 的原发地）──────────────────
    {"file": "workbench/aic-submission/README.md", "name": "全库记录 / 公开来源 / 机构",
     "context": r"全库记录", "pattern": r"全库记录\s*/\s*公开来源\s*/\s*机构[^\n]*?([\d,]+)\s*/\s*([\d,]+)\s*/\s*(\d+)",
     "fact": ["records_total", "records_public", "institutions_public"]},
    {"file": "workbench/aic-submission/README.md", "name": "可读档案 / 论文 / 师承 / 招生",
     "context": r"可读档案",
     "pattern": r"可读档案\s*/\s*论文\s*/\s*师承\s*/\s*招生[^\n]*?([\d,]+)\s*/\s*([\d,]+)\s*/\s*(\d+)\s*/\s*([\d,]+)",
     "fact": ["readable_profiles", "papers", "relations", "recruitment"]},
    {"file": "workbench/aic-submission/README.md", "name": "逐人档案份数",
     "context": r"档案", "pattern": r"([\d,]{3,})\s*份档案", "fact": "dossiers"},
    {"file": "workbench/aic-submission/README.md", "name": "方向建议可写入条数",
     "context": r"可写入", "pattern": r"可写入\s*([\d,]{3,})", "fact": "ai_would_apply"},

    # ── 根 README：当前进度那一段 ─────────────────────────────────────
    {"file": "README.md", "name": "当前进度-全库记录",
     "context": r"当前进度", "pattern": r"全库\s*[*]{0,2}([\d,]+)\s*条[*]{0,2}记录", "fact": "records_total"},
    {"file": "README.md", "name": "当前进度-工学条目",
     "context": r"当前进度", "pattern": r"工学\s*38\s*个一级学科\s*[*]{0,2}([\d,]+)\s*条", "fact": "engineering_records"},
    {"file": "README.md", "name": "当前进度-公开来源",
     "context": r"当前进度", "pattern": r"公开来源\s*[*]{0,2}([\d,]+)\s*条", "fact": "records_public"},
    {"file": "README.md", "name": "当前进度-机构数",
     "context": r"当前进度", "pattern": r"涉及\s*[*]{0,2}(\d+)\s*所", "fact": "institutions_public"},
    {"file": "README.md", "name": "当前进度-来源模块",
     "context": r"当前进度", "pattern": r"来源模块\s*[*]{0,2}(\d+)\s*个", "fact": "source_modules"},
    {"file": "README.md", "name": "当前进度-离线快照",
     "context": r"当前进度", "pattern": r"离线快照\s*[*]{0,2}(\d+)\s*份", "fact": "fixtures"},
]


def _fact_values(facts: dict, spec) -> list[int | None]:
    keys = spec if isinstance(spec, list) else [spec]
    values: list[int | None] = []
    for key in keys:
        value = facts.get(key)
        values.append(None if value is None else int(value))
    return values


def check_file(path: Path, claims: list[dict], facts: dict) -> list[dict]:
    problems: list[dict] = []
    if not path.is_file():
        return [{"文件": str(path.relative_to(ROOT)), "名称": "文件缺失",
                 "行号": 0, "问题": "声明表引用的文件不存在"}]

    lines = path.read_text(encoding="utf-8").splitlines()
    for claim in claims:
        expected = _fact_values(facts, claim["fact"])
        pattern = re.compile(claim["pattern"])
        hits = 0
        for number, line in enumerate(lines, start=1):
            if not re.search(claim["context"], line):
                continue
            match = pattern.search(line)
            if not match:
                continue
            hits += 1
            for index, want in enumerate(expected):
                if want is None:
                    continue
                raw = match.group(index + 1) if match.lastindex and match.lastindex >= index + 1 else None
                if raw is None:
                    continue
                got = int(raw.replace(",", ""))
                if got != want:
                    problems.append({
                        "文件": claim["file"], "名称": claim["name"], "行号": number,
                        "问题": f"文中写 {got:,}，实际 {want:,}",
                        "原文": line.strip()[:160],
                    })
        if hits == 0:
            problems.append({
                "文件": claim["file"], "名称": claim["name"], "行号": 0,
                "问题": "声明表中登记的句子未在文件里找到（可能已被改写，需同步更新声明表）",
            })
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="对外材料事实一致性检查")
    ap.add_argument("--json", default="", help="把结果写入该 JSON")
    args = ap.parse_args()

    facts = build_facts()
    facts.update(_extra_facts())
    # 研究覆盖度字段来自 catalog.coverage()，report_facts 只取了一部分，这里补齐。
    try:
        from workbench import catalog
        cov = catalog.coverage(bundle_only=True)   # 对外数字以仓库档案包为准
        for key, value in (cov.get("research") or {}).items():
            facts.setdefault(key, value)
    except Exception:  # noqa: BLE001
        pass

    by_file: dict[str, list[dict]] = {}
    for claim in CLAIMS:
        by_file.setdefault(claim["file"], []).append(claim)

    problems: list[dict] = []
    checked = 0
    for file, claims in by_file.items():
        between = check_file(ROOT / file, claims, facts)
        checked += len(claims)
        problems.extend(between)

    lines = ["对外材料事实一致性", ""]
    lines.append(f"  检查 {checked} 条声明，涉及 {len(by_file)} 个文件")
    for key in ("records_total", "records_public", "institutions_public",
                "engineering_records", "disciplines_engineering", "tests", "dossiers"):
        if key in facts:
            lines.append(f"  事实 {key} = {facts[key]}")
    if problems:
        lines.append("")
        lines.append(f"  ✗ {len(problems)} 处不一致")
        for item in problems:
            where = f"{item['文件']}:{item['行号']}" if item["行号"] else item["文件"]
            lines.append(f"    - [{item['名称']}] {where}：{item['问题']}")
            if item.get("原文"):
                lines.append(f"      原文：{item['原文']}")
        lines.append("")
        lines.append("结论: 不一致（请按事实表改正；改动后重跑本命令）")
    else:
        lines.append("")
        lines.append("结论: 一致")

    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))

    if args.json:
        Path(args.json).write_text(
            json.dumps({"problems": problems, "checked": checked},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())