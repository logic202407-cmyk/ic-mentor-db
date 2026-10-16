"""Wuhan University School of Geodesy and Geomatics faculty directory.

The page is an ordered document: ``p.title04`` names the 研究所, ``h3`` names the
职称, and each ``ul.teacher`` that follows lists the people in that group. A single
pass over the sibling nodes therefore carries the current institute and rank
forward. Names contain full-width spaces ("邓　非") and some entries link to a
placeholder ``#``, in which case the listing page is kept as the source.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "whu_surveying",
    "code": "0816",
    "institution": "武汉大学",
    "department": "测绘学院",
    "discipline": "测绘科学与技术",
    "listing": "https://www.sgg.whu.edu.cn/szdw/zyjs.htm",
    "max_pages": 1,
},)


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for nav in soup.select("ul.am-nav, div.nei_left"):
        nav.decompose()
    root = soup.select_one("div.techer_list") or soup

    rows: list[dict] = []
    institute = ""
    rank = ""
    for node in root.find_all(["p", "h3", "ul"]):
        classes = node.get("class") or []
        if node.name == "p" and "title04" in classes:
            institute = re.sub(r"[\s\u3000]+", "", node.get_text(" ", strip=True))
            continue
        if node.name == "h3":
            rank = re.sub(r"[\s\u3000]+", "", node.get_text(" ", strip=True))
            continue
        if node.name != "ul" or "teacher" not in classes:
            continue
        for li in node.find_all("li"):
            anchor = li.find("a")
            if anchor is None:
                continue
            name = re.sub(r"[\s\u3000]+", "", anchor.get_text(" ", strip=True))
            if not NAME_RE.fullmatch(name):
                continue
            href = (anchor.get("href") or "").strip()
            homepage = href if href.startswith("http") else url
            unit = "·".join(x for x in (institute, rank) if x) or spec["department"]
            note = (f"学院专业教师名录按研究所与职称分组列出（{institute or '未标注所'}，"
                    f"{rank or '职称未标注'}）；名录不含个人研究方向。"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, homepage, url, "学院专业教师名录", note,
            ))
    return rows
