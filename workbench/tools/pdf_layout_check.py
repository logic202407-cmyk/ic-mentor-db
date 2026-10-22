"""版式体检：统计每页内容的**竖向填充度**，自动发现半页空白这类排版问题。

为什么需要
----------
报告要求 ≤15 页，而**排版浪费**（某页只填了一半、下一章整块被推到新页）会白吃页数。
上一轮靠肉眼发现第 2 页空了半页——但肉眼看 15 页既慢又容易漏。

指标选择：**不要用"墨迹覆盖率"**
--------------------------------
第一版统计"非白像素占比"，结果每页都只有 12%–26%，全被误判成留白偏多。
原因是**文字页的墨迹覆盖率本来就很低**（一行字只占行高的三成），这个指标衡量的是
"字排得密不密"，不是"这页填满了没有"。

正确指标是**竖向填充度**：找到页面最下方那一行有墨迹的位置，除以页高。
正文页通常在 85%–97%；若是半页空白，这个值会掉到 60% 左右。

用法::

    python -m workbench.tools.pdf_layout_check
    python -m workbench.tools.pdf_layout_check --min-fill 0.80 --dpi 80

退出码：所有页都在阈值以上返回 0，否则 1（末页通常偏空，默认豁免）。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

DEFAULT_PDF = "workbench/aic-submission/技术报告.pdf"
# 灰度低于此值算"有墨迹"，滤掉纸张纹理与抗锯齿边缘
INK_THRESHOLD = 200


def page_bottom_fill(pdf_path: pathlib.Path, dpi: int) -> list[float]:
    """逐页返回"最下方墨迹所在行 / 页高"。"""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    fills: list[float] = []
    for index in range(len(doc)):
        page = doc[index]
        bitmap = page.render(scale=dpi / 72.0)
        image = bitmap.to_pil().convert("L")
        width, height = image.size
        pixels = image.load()
        last_ink_row = 0
        # 自上而下扫描；每行只要有一个暗像素就算有内容（页边距内应无墨迹）
        for y in range(height - 1, -1, -1):
            row_has_ink = False
            for x in range(0, width, 2):  # 隔点采样，够用且快
                if pixels[x, y] < INK_THRESHOLD:
                    row_has_ink = True
                    break
            if row_has_ink:
                last_ink_row = y
                break
        fills.append(last_ink_row / height if height else 0.0)
    return fills


def main() -> int:
    ap = argparse.ArgumentParser(description="PDF 版式体检（逐页竖向填充度）")
    ap.add_argument("--pdf", default=DEFAULT_PDF)
    ap.add_argument("--min-fill", type=float, default=0.60,
                    help="硬阈值：低于此值判为排版问题（默认 0.60）")
    ap.add_argument("--warn-fill", type=float, default=0.80,
                    help="软阈值：低于此值只提示（默认 0.80）")
    ap.add_argument("--dpi", type=int, default=80)
    args = ap.parse_args()

    pdf = pathlib.Path(args.pdf)
    if not pdf.is_file():
        print(f"找不到 {pdf}")
        return 1

    fills = page_bottom_fill(pdf, args.dpi)
    total_pages = len(fills)

    problems: list[str] = []
    warnings: list[str] = []
    lines = [
        f"版式体检：{pdf.name}（{total_pages} 页）",
        f"  硬阈值 {args.min_fill:.0%}（低于即判问题）／软阈值 {args.warn_fill:.0%}（低于仅提示）",
        "",
    ]
    for i, fill in enumerate(fills, start=1):
        is_last = i == total_pages
        flag = ""
        if not is_last and fill < args.min_fill:
            flag = "  <-- 留白过多，需处理"
            problems.append(f"第 {i} 页仅填充到 {fill:.0%}")
        elif not is_last and fill < args.warn_fill:
            flag = "  <-- 下方留白偏多（正常，仅提示）"
            warnings.append(f"第 {i} 页 {fill:.0%}")
        lines.append(f"  p{i:>2}  {fill:>6.1%}{flag}")

    body = fills[:-1] if total_pages > 1 else fills
    avg = sum(body) / len(body) if body else 0
    lines += ["", f"正文页平均填充度 {avg:.1%}；末页 {fills[-1]:.0%}（末页偏空属正常，不判失败）"]
    if warnings:
        lines.append("")
        lines.append("提示（不判失败）：" + "；".join(warnings))
    if problems:
        lines.append("")
        lines.append("需要检查的页：" + "；".join(problems))
    lines.append("")
    lines.append("结论: " + ("版式正常" if not problems else f"{len(problems)} 页下方留白偏多"))

    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
