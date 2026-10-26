"""校验技术报告 PDF 的硬限制：页数 ≤15、大小 ≤10 MB。

为什么单独做
------------
赛题要求「技术报告 PDF，正文 ≤15 页，≤10 MB」。这是**硬限制**，超了可能直接不合格。
而页数会随着往报告里加内容**悄悄超限**——本项目真实发生过：补齐两章 AI 实证后，
页数从 15 涨到 18，而当时所有文档都还写着"14 页"。**加内容时没人会去数页数。**

产物缺失时为什么跳过而不是报错
------------------------------
参赛交付物已停止跟踪（公开仓库只保留长期开源部分），干净 clone 上没有这个 PDF。
那不是「超限」，而是「本来就不该有这个文件」。但跳过必须**显式**：缺文件时静默返回 0
会被读成「页数与大小已校验通过」，比红更危险。所以这里打印
`状态: SKIP — …未随仓库发布，已跳过` 并以 0 退出；需要把缺失当失败时用 `--strict`。

用法::

    python -m workbench.tools.check_pdf_limits
    python -m workbench.tools.check_pdf_limits --pdf 其他.pdf --max-pages 15 --max-mb 10
    python -m workbench.tools.check_pdf_limits --strict   # 缺 PDF 即失败

退出码：满足返回 0，超限返回 1；PDF 缺失返回 0（显式 SKIP），加 ``--strict`` 时返回 1。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

DEFAULT_PDF = "workbench/evaluation/records/技术报告.pdf"
SKIP_REASON = "未随仓库发布，已跳过"


def count_pages(pdf: pathlib.Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 环境缺库
        raise SystemExit(f"需要 pypdf 才能数页数：{exc}") from exc
    return len(PdfReader(str(pdf)).pages)


def _emit(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))


def skip_text(pdf: pathlib.Path) -> str:
    """缺产物时的显式 SKIP 说明。措辞必须让人一眼看出「没校验」。"""
    return "\n".join([
        "报告 PDF 硬限制校验",
        "",
        f"  状态: SKIP — 报告 PDF {SKIP_REASON}（不是校验通过）",
        f"    ⊘ 缺少 {pdf.as_posix()}",
        "  说明: 参赛交付物已停止跟踪，原件只保留在所有者本机；",
        "        因此页数与大小均未校验。持有原件的机器上重跑本命令即可得到真实结论。",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="技术报告 PDF 硬限制校验")
    ap.add_argument("--pdf", default=DEFAULT_PDF)
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--max-mb", type=float, default=10.0)
    ap.add_argument("--strict", action="store_true",
                    help="缺 PDF 时判为失败（默认显式跳过并返回 0）")
    args = ap.parse_args()

    pdf = pathlib.Path(args.pdf)
    problems: list[str] = []
    if not pdf.is_file():
        if not args.strict:
            _emit(skip_text(pdf))
            return 0
        problems.append(f"找不到 {pdf}")
        lines: list[str] = ["报告 PDF 硬限制校验"]
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

    _emit("\n".join(lines + [("  ✗ " + p) for p in problems]))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())