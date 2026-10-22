"""校验技术报告 PDF 的硬限制：页数 ≤15、大小 ≤10 MB。

为什么单独做
------------
赛题要求「技术报告 PDF，正文 ≤15 页，≤10 MB」。这是**硬限制**，超了可能直接不合格。
而页数会随着往报告里加内容**悄悄超限**——本项目真实发生过：补齐两章 AI 实证后，
页数从 15 涨到 18，而当时所有文档都还写着"14 页"。**加内容时没人会去数页数。**

用法::

    python -m workbench.tools.check_pdf_limits
    python -m workbench.tools.check_pdf_limits --pdf 其他.pdf --max-pages 15 --max-mb 10

退出码：满足返回 0，超限返回 1。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

DEFAULT_PDF = "workbench/aic-submission/技术报告.pdf"


def count_pages(pdf: pathlib.Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 环境缺库
        raise SystemExit(f"需要 pypdf 才能数页数：{exc}") from exc
    return len(PdfReader(str(pdf)).pages)


def main() -> int:
    ap = argparse.ArgumentParser(description="技术报告 PDF 硬限制校验")
    ap.add_argument("--pdf", default=DEFAULT_PDF)
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--max-mb", type=float, default=10.0)
    args = ap.parse_args()

    pdf = pathlib.Path(args.pdf)
    problems: list[str] = []
    if not pdf.is_file():
        problems.append(f"找不到 {pdf}")
        lines = []
    else:
        pages = count_pages(pdf)
        size_mb = pdf.stat().st_size / 1024 / 1024
        lines = [
            f"报告 PDF：{pdf.name}",
            f"  页数 {pages}（上限 {args.max_pages}）"
            f"{'  ✓' if pages <= args.max_pages else '  ✗'}",
            f"  大小 {size_mb:.2f} MB（上限 {args.max_mb:g} MB）"
            f"{'  ✓' if size_mb <= args.max_mb else '  ✗'}",
        ]
        if pages > args.max_pages:
            problems.append(
                f"页数 {pages} 超过上限 {args.max_pages}——"
                "要么精简内容，要么收紧排版（make_aic_html.py 里的 @page/font-size/line-height）")
        if size_mb > args.max_mb:
            problems.append(f"大小 {size_mb:.2f} MB 超过上限 {args.max_mb:g} MB")

    text = "\n".join(lines + [("  ✗ " + p) for p in problems])
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
