# -*- coding: utf-8 -*-
"""make_docx.py — 导师库报告 → Word（先清洗 <details> 等 HTML 标签）"""
import re
import sys
import os

sys.path.insert(0, r"E:\ytm\academic-investigations")
from md2docx import convert

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    md = f.read()

md = re.sub(r"<details>\s*<summary>(.*?)</summary>", r"\n#### \1\n", md, flags=re.S)
md = md.replace("</details>", "")
md = re.sub(r"<br\s*/?>", " ", md)
md = md.replace("⚠️", "(!)")
tmp = dst + ".tmp.md"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(md)
convert(tmp, dst, title=None)
os.remove(tmp)
print("SAVED", dst)
