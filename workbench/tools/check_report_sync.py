"""校验报告三件产物是否同步：Markdown → HTML → PDF。

为什么需要
----------
主交付物是 **PDF**，而 PDF 由 HTML 渲染、HTML 由 Markdown 生成。只要改完 md 忘了重新
生成，PDF 就会**静默落后**——本项目真实发生过一次：md 已写「38 个工学学科全部达标」，
而 PDF 还停留在「35 个达标、3 个未达标」。评审读的是 PDF，这种错会直接要命。

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

退出码：一致返回 0，不一致返回 1（便于放进 CI）。
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

BASE = pathlib.Path("workbench/aic-submission")
MARKER = re.compile(r"<!--\s*source-sha256:\s*([0-9a-f]{64})\s*-->")


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="报告产物同步校验")
    ap.add_argument("--md", default="技术报告.md")
    args = ap.parse_args()

    md = BASE / args.md
    html = md.with_suffix(".html")
    pdf = md.with_suffix(".pdf")

    problems: list[str] = []
    lines: list[str] = [f"报告同步校验：{md.name} / {html.name} / {pdf.name}"]

    for f in (md, html, pdf):
        if not f.is_file():
            problems.append(f"缺少 {f.name}")
    if problems:
        for line in lines + ["  ✗ " + p for p in problems]:
            print(line)
        return 1

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

    for line in lines:
        try:
            print(line)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", "replace"))
    for p in problems:
        msg = "  ✗ " + p
        try:
            print(msg)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
