"""编码体检：检查那些「被外部程序读取」的文件是否用了正确的编码。

为什么需要
----------
本项目连续踩过三次同类错误，每次都是**写文件时假设对方按 UTF-8 读**：

| 文件 | 读取方 | 读取方用的编码 | 错误后果 |
|:--|:--|:--|:--|
| `*.cmd` | cmd.exe | OEM 代码页（中文是 cp936） | 中文提示被切成乱码，报 `'on.exe' 不是内部命令` |
| `requirements.txt` | pip | 系统区域编码（cp936） | `UnicodeDecodeError`，装依赖第一步就失败 |
| `.gitattributes` | git | 字节流解析 | BOM 让行首 `#` 失效，注释被当成规则，每次 clone 报警告 |

共同点：**这些文件不是给人看的，是给某个程序看的**；而这些程序都不按 UTF-8 读。
所以规则是：**被外部工具消费的文件必须纯 ASCII**；只有人能读的文档才用 UTF-8 中文。

用法::

    python -m workbench.tools.encoding_audit
    python -m workbench.tools.encoding_audit --verbose

退出码：全部合规返回 0，否则 1。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# 规则：路径模式 -> (要求, 说明)
# 要求取值：
#   "ascii"    —— 必须纯 ASCII（读取方用区域/OEM 编码）
#   "no-bom"   —— 不得带 UTF-8 BOM（读取方按字节解析，BOM 会让行首 # 失效）
#   "utf8"     —— 必须是合法 UTF-8
RULES: tuple[tuple[str, str, str], ...] = (
    ("*.cmd", "ascii", "cmd.exe 用 OEM 代码页解析批处理"),
    ("*.bat", "ascii", "cmd.exe 用 OEM 代码页解析批处理"),
    ("workbench/requirements.txt", "ascii", "pip 用系统区域编码读取"),
    # git 允许中文注释：它按字节读，`#` 开头一律当注释。真正会坏的是 BOM。
    (".gitattributes", "no-bom", "git 按字节解析；BOM 会让行首 # 失效"),
    (".gitignore", "no-bom", "git 按字节解析；BOM 会让行首 # 失效"),
    ("tools/*.mjs", "utf8", "node 按 UTF-8 读取，可用中文"),
)

BOM = b"\xef\xbb\xbf"


def iter_files(root: pathlib.Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "node_modules", ".workbench-data"} for part in path.parts):
            continue
        if path.suffix in {".pdf", ".png", ".jpg", ".gz"}:
            continue
        yield path


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    ap = argparse.ArgumentParser(description="编码体检")
    ap.add_argument("--verbose", action="store_true", help="列出每个被检查的文件")
    args = ap.parse_args()

    problems: list[str] = []
    checked = 0

    for path in iter_files(ROOT):
        name = rel(path)
        rule = None
        for pattern, kind, why in RULES:
            if pathlib.PurePosixPath(name).match(pattern):
                rule = (kind, why)
                break
        if rule is None:
            continue
        checked += 1
        kind, why = rule
        raw = path.read_bytes()

        if kind == "ascii":
            bad = [i for i, b in enumerate(raw) if b > 127]
            if bad:
                problems.append(
                    f"{name}：含 {len(bad)} 个非 ASCII 字节（首个偏移 {bad[0]}）"
                    f"——{why}，会读不了")
            if raw.startswith(BOM):
                problems.append(f"{name}：以 UTF-8 BOM 开头——{why}")
        elif kind == "no-bom":
            if raw.startswith(BOM):
                problems.append(f"{name}：带 UTF-8 BOM——{why}")
        else:  # utf8
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                problems.append(f"{name}：不是合法 UTF-8（{exc.reason}）——{why}")

        if args.verbose:
            label = {"ascii": "纯 ASCII", "no-bom": "无 BOM", "utf8": "UTF-8"}[kind]
            print(f"  检查 {name}（{label}）")

    # 额外：仓库内不得残留带 BOM 的、被工具读取的文本文件
    leftovers = [name for name in ("workbench/requirements.txt", ".gitattributes", ".gitignore")
                 if (ROOT / name).is_file() and (ROOT / name).read_bytes().startswith(BOM)]
    for name in leftovers:
        msg = f"{name}：带 UTF-8 BOM"
        if msg not in problems:
            problems.append(msg)

    lines = [f"编码体检：检查 {checked} 个「被外部程序读取」的文件"]
    if problems:
        lines.append("")
        for p in problems:
            lines.append(f"  ✗ {p}")
        lines.append("")
        lines.append(f"结论: {len(problems)} 处编码问题")
    else:
        lines.append("  ✓ 全部合规（批处理/依赖清单/git 配置均为纯 ASCII 且无 BOM）")
        lines.append("")
        lines.append("结论: 通过")

    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
