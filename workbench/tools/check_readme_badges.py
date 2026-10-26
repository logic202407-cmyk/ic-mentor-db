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

工作流：**新增测试文件或改动数据后，先跑一次 --fix**——测试数统计的是 	est_ 方法数，
加一个方法徽章就过期一次。这条检查存在的意义就是让"忘了更新"变成必须处理的失败项，
而不是悄悄在首页显示一个错数字。

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
# 「纳入 git 的文件（N 个） | 约 X MB」
SIZE_ROW = re.compile(r"纳入 git 的文件（(\d+) 个）\s*\|\s*\*\*约 (\d+) MB\*\*")
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


def tracked_size() -> tuple[int, float]:
    """返回 (跟踪文件数, 跟踪内容总 MB)。

    口径要同时满足两个要求：

    **① 与平台无关。** 大小取 git **blob 字节数**（`cat-file -s`），不读工作区文件——
    工作区体积受行尾影响（Windows CRLF / Linux LF 差 2 MB 以上），blob 则处处一致。
    并且必须 `-c core.quotepath=false`：git 默认把非 ASCII 路径转义成八进制
    （`启动.cmd` → `"\\345\\220\\257..."`），在别人的环境里匹配不到文件。

    **② 与"即将提交的内容"一致。** 提交内容就是**索引**，所以这里直接以索引为准：

    - 新文件已 `git add` 未提交 → 在索引里，计入；
    - 文件已 `git rm --cached`（停止跟踪）→ 不在索引里，不计入。

    **为什么不再用「HEAD 树 ∪ 索引」。** 旧实现取两者并集，只能"补上新文件"，
    无法"减去已删除文件"：本轮把 7 份参赛交付物 `git rm --cached` 之后，
    `--fix` 写出的文件数是 **729**，真正提交完是 **722**，CI 立刻变红。
    并集遇到**已暂存的删除**时会把 HEAD 里还有、索引里已删的文件继续算进去。
    索引本身就是"将要提交的树"，用它当唯一口径既不需要并集，也没有这个盲区。
    """
    import subprocess

    def _run(*args: str, stdin: str | None = None) -> str:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", input=stdin)
        return proc.stdout

    oids: list[str] = []
    # `<mode> <oid> <stage>\t<path>`；合并冲突时同一路径会有多条 stage
    for record in _run("ls-files", "-s", "-z").split("\0"):
        if not record.strip():
            continue
        fields = record.split()
        if len(fields) >= 3:
            oids.append(fields[1])
    if not oids:
        return 0, 0.0

    total = 0
    out = _run("cat-file", "--batch-check", stdin="\n".join(oids) + "\n")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "blob":
            try:
                total += int(parts[2])
            except ValueError:
                continue  # size 为 "-" 的条目（如符号链接）
    return len(oids), total / 1024 / 1024


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

    # 体积表
    size_files = size_mb = None
    m_size = SIZE_ROW.search(text)
    act_files, act_mb = tracked_size()
    if m_size:
        size_files, size_mb = int(m_size.group(1)), int(m_size.group(2))
        if size_files != act_files:
            problems.append(f"体积表「文件 {size_files} 个」实际 {act_files} 个")
        if abs(size_mb - act_mb) > max(3.0, act_mb * 0.15):
            problems.append(f"体积表「约 {size_mb} MB」实际 {act_mb:.1f} MB")
    else:
        problems.append("体积表未找到「纳入 git 的文件（N 个）| 约 X MB」这一行")

    if problems and args.fix:
        fixed = text
        if m_size and size_files is not None:
            fixed = SIZE_ROW.sub(
                f"纳入 git 的文件（{act_files} 个） | **约 {round(act_mb)} MB**", fixed, count=1)
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
    lines.append(f"  体积表：徽章 {size_files} 个 / {size_mb} MB"
                 f"　实际 {act_files} 个 / {act_mb:.1f} MB")
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
