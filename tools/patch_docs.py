# -*- coding: utf-8 -*-
"""patch_docs.py — 批量修正文档中的邮箱相关表述"""
import io
import os

ROOT = r"E:\ytm\mentor-db"

EDITS = [
    ("README.md", [
        ("| `data/processed/curated.csv` | 推荐集表（355 人，含招生信号、邮箱、课题组） |",
         "| `data/processed/curated.csv` | 推荐集表（355 人，含招生信号、课题组、主页链接） |"),
        ("| 师资名录 | 各高校院系官网公开的教师名录页与个人主页 | 姓名、职称、院系、研究方向、办公邮箱、荣誉 |",
         "| 师资名录 | 各高校院系官网公开的教师名录页与个人主页 | 姓名、职称、院系、研究方向、荣誉（**不含邮箱**） |"),
        ("- 可申请更正信息、删除邮箱、移除整条记录；",
         "- 可申请更正信息、移除整条记录、移除主页链接；"),
    ]),
    ("CONTRIBUTING.md", [
        ('- 删除邮箱、删除整条记录、只标注"不公开"——三种诉求都可以，请在 Issue 里写明；',
         '- 更正信息、移除整条记录、移除主页链接、标注"信息不公开"——都可以，请在 Issue 里写明；'),
        ('      "homepage": "URL 或 null", "email": "邮箱 或 null",',
         '      "homepage": "URL 或 null",'),
        ("- **不得编造或推测**任何字段——无法核实的填 `null`；",
         "- **不得编造或推测**任何字段——无法核实的填 `null`；\n- **不采集邮箱**：本项目不收录任何邮箱地址，请勿在名录中写入；"),
    ]),
    (r".github\ISSUE_TEMPLATE\correction.yml", [
        ("        - 删除邮箱（保留其他信息）", "        - 移除主页链接（保留其他信息）"),
    ]),
]

for rel, subs in EDITS:
    p = os.path.join(ROOT, rel)
    s = io.open(p, encoding="utf-8").read()
    for a, b in subs:
        if a in s:
            s = s.replace(a, b)
        else:
            print("  [未命中]", rel, "->", a[:45].replace("\n", " "))
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("updated", rel)
