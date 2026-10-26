"""校验报告三件产物是否同步：Markdown → HTML → PDF。

为什么需要
----------
主交付物是 **PDF**，而 PDF 由 HTML 渲染、HTML 由 Markdown 生成。只要改完 md 忘了重新
生成，PDF 就会**静默落后**——本项目真实发生过一次：md 已写「38 个工学学科全部达标」，
而 PDF 还停留在「35 个达标、3 个未达标」。评审读的是 PDF，这种错会直接要命。

产物缺失时为什么跳过而不是报错
------------------------------
参赛交付物（技术报告 md/html/pdf）已**停止跟踪**：公开仓库只保留长期开源部分，这些
材料只留在所有者本机。于是干净 clone 上三个文件都不存在——那不是「同步出错」，而是
「本来就不该有这个文件」。

关键：**跳过必须显式说出来**。如果缺文件时静默返回 0，CI 会给出「三件产物已同步」的
假绿，比红更危险。所以这里打印 `状态: SKIP — …未随仓库发布，已跳过` 并以 0 退出，
措辞明确写「不是校验通过」。需要把缺失当失败时用 `--strict`。

判据
----
``make_aic_html.py`` 会把源 Markdown 的 sha256 以注释形式嵌进 HTML 头部
（``<!-- source-sha256: ... -->``）。本脚本重新算一次 md 的哈希去比对：

1. HTML 里没有标记 → HTML 早于该机制生成，判为需要重新生成；
2. 哈希不一致 → md 改过但 HTML 没重跑；
3. 哈希一致 → 再看 PDF 是否比 HTML 新（PDF 由 HTML 渲染，必须更晚）。

用法::

    python -m workbench.tools.check_report_sync
    python -m workbench.tools.check_report_sync --md 其他.md
    python -m workbench.tools.check_report_sync --base 临时目录   # 用临时副本验证
    python -m workbench.tools.check_report_sync --strict           # 缺产物即失败

退出码：一致返回 0，不一致返回 1；产物缺失返回 0（显式 SKIP），加 ``--strict`` 时返回 1。
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

BASE = pathlib.Path("workbench/aic-submission")
MARKER = re.compile(r"<!--\s*source-sha256:\s*([0-9a-f]{64})\s*-->")
SKIP_REASON = "未随仓库发布，已跳过"


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _emit(text: str) -> None:
    """中文输出在 GBK 控制台上会抛 UnicodeEncodeError，退回 UTF-8 字节流。"""
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))


def skip_lines(missing: list[pathlib.Path]) -> list[str]:
    """缺产物时的显式 SKIP 说明。措辞必须让人一眼看出「没校验」。"""
    lines = ["", f"  状态: SKIP — 报告产物{SKIP_REASON}（不是校验通过）"]
    lines += [f"    ⊘ 缺少 {p.as_posix()}" for p in missing]
    lines += [
        "  说明: 该材料属参赛专用交付物，仓库已停止跟踪，原件只保留在所有者本机。",
        "        因此这里不做实质校验；在持有原件的机器上重跑本命令即可得到真实结论。",
    ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="报告产物同步校验")
    ap.add_argument("--base", default=str(BASE),
                    help=f"报告产物所在目录（默认 {BASE.as_posix()}）")
    ap.add_argument("--md", default="技术报告.md")
    ap.add_argument("--strict", action="store_true",
                    help="缺产物时判为失败（默认显式跳过并返回 0）")
    args = ap.parse_args()

    base = pathlib.Path(args.base)
    md = base / args.md
    html = md.with_suffix(".html")
    pdf = md.with_suffix(".pdf")

    lines: list[str] = [f"报告同步校验：{md.name} / {html.name} / {pdf.name}"]
    missing = [f for f in (md, html, pdf) if not f.is_file()]

    if missing:
        if not args.strict:
            _emit("\n".join(lines + skip_lines(missing)))
            return 0
        problems = [f"缺少 {f.as_posix()}" for f in missing]
        _emit("\n".join(lines + [""] + ["  ✗ " + p for p in problems]))
        return 1

    problems = []
    want = sha256_of(md)
    html_text = html.read_text(encoding="utf-8")
    m = MARKER.search(html_text)
    if not m:
        problems.append("HTML 里没有 source-sha256 标记（生成器版本过旧），需重新生成")
    elif m.group(1) != want:
        problems.append(
            f"HTML 落后于 Markdown（md={want[:12]}… / html={m.group(1)[:12]}…），"
            "需重新生成 HTML 与 PDF"
        )
    else:
        lines.append(f"  ✓ HTML 与 Markdown 一致（sha256 {want[:12]}…）")

    if not problems:
        if pdf.stat().st_mtime < html.stat().st_mtime:
            problems.append("PDF 早于 HTML（PDF 由 HTML 渲染，必须更晚），需重新生成 PDF")
        else:
            lines.append(f"  ✓ PDF 不早于 HTML（{pdf.stat().st_size // 1024} KB）")

    _emit("\n".join(lines + ["  ✗ " + p for p in problems]))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())