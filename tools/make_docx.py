# -*- coding: utf-8 -*-
"""make_docx.py — Markdown 报告 → Word（自包含，无外部依赖）

用法:
    python tools/make_docx.py <input.md> <output.docx>

特性:
    · 支持标题（# ~ ####）、表格、无序/有序列表、引用块、加粗与行内代码
    · 自动清洗 <details>/<summary> 等 HTML 标签
    · 中文字体显式指定 eastAsia，避免渲染时回退
依赖:
    pip install python-docx
"""
import os
import re
import sys

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _set_font(run, name_cn="微软雅黑", size=10.5, bold=False, color=None):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name_cn)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def _add_rich(p, text):
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            _set_font(p.add_run(part[2:-2]), bold=True)
        elif part.startswith("`") and part.endswith("`"):
            _set_font(p.add_run(part[1:-1]), size=9, color=(0x1F, 0x49, 0x7D))
        else:
            _set_font(p.add_run(part))


def _add_table(doc, header, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(header):
        c = t.cell(0, j)
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(h), size=9.5, bold=True)
        shd = c._tc.get_or_add_tcPr()
        el = OxmlElement("w:shd")
        el.set(qn("w:val"), "clear")
        el.set(qn("w:fill"), "D9E2F3")
        shd.append(el)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i + 1, j)
            c.text = ""
            _set_font(c.paragraphs[0].add_run(str(v)), size=9)
    doc.add_paragraph()


def convert(md_path, docx_path, title=None):
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    doc = Document()
    for s in doc.sections:
        s.top_margin = Cm(2)
        s.bottom_margin = Cm(2)
        s.left_margin = Cm(2.2)
        s.right_margin = Cm(2.2)

    if title and (not lines or not lines[0].startswith("# ")):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(p.add_run(title), size=18, bold=True, color=(0x1F, 0x3B, 0x73))
        doc.add_paragraph()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # 表格：连续的 | 行，且第二行是分隔行
        if (line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|")
                and set(lines[i + 1].replace("|", "").replace(" ", "")) <= set("-:")):
            tl = []
            while i < len(lines) and lines[i].startswith("|"):
                tl.append(lines[i].strip())
                i += 1
            hdr = [c.strip() for c in tl[0].strip("|").split("|")]
            rows = []
            for t2 in tl[2:]:
                cells = [c.strip() for c in t2.strip("|").split("|")]
                if len(cells) == len(hdr):
                    rows.append(cells)
            if rows:
                _add_table(doc, hdr, rows)
            continue
        if line.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_font(p.add_run(line[2:].strip()), size=18, bold=True, color=(0x1F, 0x3B, 0x73))
        elif line.startswith("## "):
            p = doc.add_paragraph()
            _set_font(p.add_run(line[3:].strip()), size=14, bold=True, color=(0x1F, 0x3B, 0x73))
            p.paragraph_format.space_before = Pt(10)
        elif line.startswith("### "):
            p = doc.add_paragraph()
            _set_font(p.add_run(line[4:].strip()), size=12, bold=True, color=(0x2E, 0x5A, 0x9C))
            p.paragraph_format.space_before = Pt(8)
        elif line.startswith("#### "):
            p = doc.add_paragraph()
            _set_font(p.add_run(line[5:].strip()), size=11, bold=True)
        elif line.startswith("- ") or line.startswith("* "):
            _add_rich(doc.add_paragraph(style="List Bullet"), line[2:])
        elif re.match(r"^\d+\. ", line):
            _add_rich(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", line))
        elif line.strip() == "" or line.startswith("---"):
            pass
        elif line.startswith("> "):
            p = doc.add_paragraph()
            _add_rich(p, line[2:])
            for r in p.runs:
                r.font.italic = True
                r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)
        else:
            _add_rich(doc.add_paragraph(), line)
        i += 1

    doc.save(docx_path)
    print("SAVED:", docx_path)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        md = f.read()
    # 清洗 HTML 标签：<details><summary>X</summary> -> 四级标题
    md = re.sub(r"<details>\s*<summary>(.*?)</summary>", r"\n#### \1\n", md, flags=re.S)
    md = re.sub(r"</details>", "", md)
    md = re.sub(r"<br\s*/?>", " ", md)
    md = re.sub(r"<[^>]+>", "", md)
    tmp = src + ".cleaned.md"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(md)
    convert(tmp, dst)
    os.remove(tmp)


if __name__ == "__main__":
    main()
