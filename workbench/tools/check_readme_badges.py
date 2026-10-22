"""校验 README 顶部徽章里的数字是否与仓库实际一致。

为什么需要
----------
徽章是**评审打开仓库第一眼看到的东西**，却最容易过期：它们只是写死的字符串，
没有任何机制会去更新。实测发现两个都错得很远——写着「tests-321 passed」（实际 707）、
「记录-14,271 条」（实际 15,719）。

`tools/check_doc_numbers.mjs` 管的是旧 IC 专题的数据表，覆盖不到这里的徽章，
所以单独做一道检查。

实现要点：**测试数用 AST 静态统计，不真跑测试**——数 `test_` 开头的方法即可，
既快又不需要执行副作用。

用法::

    python -m workbench.tools.check_readme_badges
    python -m workbench.tools.check_readme_badges --fix   # 就地改正徽章

退出码：一致返回 0，不一致返回 1。
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"
TESTS_DIR = ROOT / "workbench/tests"

TESTS_BADGE = re.compile(r"tests-(\d+)%20passed")
RECORDS_BADGE = re.compile(r"记录-(\d+)%2C(\d+)%20条|记录-(\d+)%20条")


def count_tests() -> int:
    """静态统计测试方法数（不执行测试）。"""
    total = 0
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1
    return total


def actual_numbers() -> dict[str, int]:
    sys.path.insert(0, str(ROOT))
    from workbench import catalog

    cov = catalog.coverage()
    return {
        "tests": count_tests(),
        "records": cov["total_records"],
    }


def badge_numbers(text: str) -> dict[str, int | None]:
    out: dict[str, int | None] = {"tests": None, "records": None}
    m = TESTS_BADGE.search(text)
    if m:
        out["tests"] = int(m.group(1))
    m = RECORDS_BADGE.search(text)
    if m:
        raw = (m.group(1) or "") + (m.group(2) or "") if m.group(1) else (m.group(3) or "")
        out["records"] = int(raw.replace(",", ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 README 徽章数字")
    ap.add_argument("--fix", action="store_true", help="就地改正徽章数字")
    args = ap.parse_args()

    text = README.read_text(encoding="utf-8")
    claimed = badge_numbers(text)
    actual = actual_numbers()

    problems: list[str] = []
    for key, label in (("tests", "测试数"), ("records", "全库记录")):
        want = actual[key]
        have = claimed[key]
        if have is None:
            problems.append(f"徽章里没找到「{label}」")
        elif have != want:
            problems.append(f"徽章「{label}」写的是 {have:,}，实际 {want:,}")

    if problems and args.fix:
        fixed = text
        if claimed["tests"] is not None and claimed["tests"] != actual["tests"]:
            fixed = TESTS_BADGE.sub(f"tests-{actual['tests']}%20passed", fixed, count=1)
        if claimed["records"] is not None and claimed["records"] != actual["records"]:
            # 千分位要按整串分组（15,719），不是先把万位摘出来（那会得到 1,5719）。
            # 徽章 URL 里逗号要写成 %2C。
            shown = f"{actual['records']:,}".replace(",", "%2C")
            fixed = re.sub(r"记录-[\d%2C]+%20条", f"记录-{shown}%20条", fixed, count=1)
        README.write_text(fixed, encoding="utf-8", newline="\n")
        print("已改正徽章：")
        for p in problems:
            print("  -", p)
        problems = []

    lines = ["README 徽章校验", ""]
    lines.append(f"  测试数：徽章 {claimed['tests']} / 实际 {actual['tests']}")
    lines.append(f"  全库记录：徽章 {claimed['records']} / 实际 {actual['records']}")
    if problems:
        lines.append("")
        for p in problems:
            lines.append("  ✗ " + p)
        lines.append("")
        lines.append("结论: 不一致（可用 --fix 改正）")
    else:
        lines.append("")
        lines.append("结论: 一致")

    out = "\n".join(lines)
    try:
        print(out)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((out + "\n").encode("utf-8", "replace"))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
