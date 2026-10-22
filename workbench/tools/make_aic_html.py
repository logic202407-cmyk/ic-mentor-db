"""Render an AIC submission Markdown file to a print-ready HTML file.

Uses the system Python's `markdown` package plus an embedded print stylesheet
sized for A4 with CJK-capable font stacks. The HTML is then printed to PDF by
the bundled `tools/make_aic_pdf.ps1` helper (Microsoft Edge headless).

Usage:
    py -3.12 workbench/tools/make_aic_html.py <input.md> [output.html]
"""

from __future__ import annotations

import hashlib
import html
import pathlib
import sys

import markdown

CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Source Han Sans SC", "Noto Sans CJK SC", sans-serif;
  font-size: 10.2pt; line-height: 1.62; color: #1a1a1a; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 17pt; margin: 0 0 4mm; padding-bottom: 2mm; border-bottom: 2.2px solid #1f4e79; color: #14304a; }
h1 + blockquote { margin-top: 0; }
h2 { font-size: 13.2pt; margin: 7mm 0 2.5mm; padding: 1.6mm 0 1.6mm 3mm; border-left: 4px solid #1f4e79; background: #f2f6fa; color: #14304a; page-break-after: avoid; }
h3 { font-size: 11.2pt; margin: 5mm 0 2mm; color: #1f4e79; page-break-after: avoid; }
h4 { font-size: 10.4pt; margin: 4mm 0 1.5mm; color: #333; page-break-after: avoid; }
p { margin: 0 0 2.2mm; text-align: justify; }
ul, ol { margin: 0 0 2.4mm; padding-left: 6.5mm; }
li { margin-bottom: 1.1mm; }
table { border-collapse: collapse; width: 100%; margin: 2.5mm 0 4mm; font-size: 9.1pt; page-break-inside: auto; }
th, td { border: 0.7px solid #b8c4d0; padding: 1.5mm 2mm; text-align: left; vertical-align: top; }
th { background: #e8eef5; font-weight: 600; color: #14304a; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
blockquote { margin: 2.5mm 0; padding: 2.2mm 3.5mm; border-left: 3.5px solid #9fb3c8; background: #f7f9fb; color: #33475b; }
blockquote p { margin: 0 0 1.4mm; }
blockquote p:last-child { margin-bottom: 0; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.9pt; background: #f0f2f5; padding: 0.3mm 1mm; border-radius: 2px; }
pre { background: #f7f8fa; border: 0.7px solid #d5dbe2; border-radius: 3px; padding: 2.5mm 3mm; overflow-wrap: break-word; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.5pt; line-height: 1.42; }
hr { border: none; border-top: 0.7px solid #ccd4dc; margin: 5mm 0; }
strong { color: #10314d; }
a { color: #1f4e79; text-decoration: none; word-break: break-all; }
h2, h3 { break-after: avoid-page; }
/* Print header/footer is suppressed (--no-pdf-header-footer); show the document
   title on the first page only, keeping the rest clean for the page budget. */
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rendered = TEMPLATE.format(
        title=html.escape(src.stem),
        css=CSS,
        body=body,
    )
    # 把源 Markdown 的哈希嵌进 HTML 头部：主交付物是 PDF，而 PDF 由 HTML 渲染而来，
    # 一旦改了 md 却忘了重新生成，PDF 就会静默落后（本项目真实发生过一次：md 已写
    # 38/38，PDF 还停留在 35/3）。有了这个标记，`check_report_sync.py` 能直接判出来。
    marker = f"<!-- source-sha256: {digest} -->\n"
    rendered = rendered.replace("<head>", "<head>\n" + marker, 1)
    dst.write_text(rendered, encoding="utf-8")
    print(f"wrote {dst}  ({len(rendered):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
