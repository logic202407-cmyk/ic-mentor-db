"""Beijing University of Science and Technology faculty platform (discipline index).

The platform publishes one listing per first-level discipline. Each teacher is a
``li > a > div.namebox`` card carrying ``span``（职称）, ``h1``（姓名） and the first
``p``（所在单位）; the two ``i`` counters underneath are platform view/praise
counts and are deliberately ignored.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# Offices that appear in the index but are not teaching units.
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|办公室|工会|离退休|人事处|财务处|"
                                 r"研究生院|教务处|机关")

SPECS = ({
    "key": "ustb_metallurgy",
    "code": "0806",
    "institution": "北京科技大学",
    "department": "冶金工程（学科索引）",
    "discipline": "冶金工程",
    "listing": ("https://faculty.ustb.edu.cn/xkjslb.jsp?totalpage=13&PAGENUM={page}"
                "&id=5634&lang=zh_CN&st=0"
                "&urltype=tsites.DisciplineTeacherList&wbtreeid=1014"),
    "max_pages": 14,
},)


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for anchor in soup.select("a[href]"):
        href = anchor["href"]
        if not re.search(r"faculty\.ustb\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm$", href):
            continue
        box = anchor.select_one("div.namebox")
        if box is None:
            continue
        title_el = box.select_one("span")
        name_el = box.select_one("h1")
        dept_el = box.select_one("p")
        if name_el is None:
            continue
        name = re.sub(r"[\s\u3000]+", "", name_el.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name):
            continue
        title = re.sub(r"[\s\u3000]+", "", title_el.get_text(" ", strip=True)) if title_el else ""
        dept = re.sub(r"[\s\u3000]+", "", dept_el.get_text(" ", strip=True)) if dept_el else ""
        if ADMINISTRATIVE_UNIT.search(dept):
            continue
        note = (f"学校教师主页按学科索引列出（所在单位：{dept or '未标注'}"
                f"{'，职称：' + title if title else ''}）；索引不含个人研究方向。"
                f"导师资格与招生专业以当年招生公告为准。")
        # Fall back to the discipline name exactly as the original collector did;
        # a different fallback string would key the same person under two
        # departments and create a duplicate row on a later run.
        rows.append(roster_row(
            name, spec["institution"], dept or spec["discipline"], spec["code"],
            NO_DIRECTION, href, url, "学校教师主页学科索引", note,
        ))
    return rows
