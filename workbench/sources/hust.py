"""Huazhong University of Science and Technology, School of Artificial
Intelligence and Automation (人工智能与自动化学院) faculty directory.

The 学院师资 "按系列表" page publishes the whole teaching roster grouped first by
系/研究所 (``div.yjbt``, e.g. 自主智能与智能控制系) and then by 职称 band
(``h6``: 正高 / 副高 / 中级). Every band holds one ``div.js_bt`` with one ``ul``
of ``li > a``; the anchor text is the person's name and the href is either their
own page on ``faculty.hust.edu.cn`` or a college ``info/`` page.

The tabs switch client-side, but no name is rendered by script: the four 系 and
their 125 entries are all present in the served HTML, so one static pass reads
the complete roster without touching an API. The 博士后 / 实验工程人员 /
荣休教师 groups live on separate listing pages and are deliberately not part of
this source.

The college's four 系 cover the 控制科学与工程 二级学科 directions
(控制理论与控制工程 / 检测技术与自动化装置 / 系统工程 / 模式识别与智能系统),
which is why the roster is filed under 0811; the listing itself states no
research direction, so every row keeps 方向待补 and carries only its 系 as the
department and its 职称 band in the note.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# Non-teaching units that must never become a department (contract rule 5).
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|工会|离退休|办公室|机关|人事|财务|教务|"
                                 r"学生工作|行政|校友|后勤")
# Anchors that are chrome or a unit heading rather than a person's name.
NAV_NOISE = re.compile(r"^(首页|上页|下页|尾页|末页|返回|更多|学院师资|杰出学者|"
                       r"实验工程人员|博士后|荣休教师|按系列表|按姓名拼音首字母列表|"
                       r"办公室|实验室|研究中心|实验中心|教学中心|教研室|研究所|"
                       r"中心|学院|系|机关|党委|工会|离退休)$")

SPECS = ({
    "key": "hust_aia_control",
    "code": "0811",
    "institution": "华中科技大学",
    "department": "人工智能与自动化学院",
    "discipline": "控制科学与工程",
    "listing": "https://aia.hust.edu.cn/szdw/xysz/axlb.htm",
    "max_pages": 1,
},)


def _squash(text: str) -> str:
    """Drop every kind of space, including the full-width one used in names."""
    return re.sub(r"[\s\u3000]+", "", text or "")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    root = soup.select_one("div.js_menu") or soup

    rows: list[dict] = []
    unit = ""
    rank = ""
    for node in root.find_all(["div", "h6", "ul"]):
        classes = node.get("class") or []
        if node.name == "div" and "yjbt" in classes:
            unit = _squash(node.get_text(" ", strip=True))
            rank = ""
            continue
        if node.name == "h6":
            rank = _squash(node.get_text(" ", strip=True))
            continue
        # Only the roster lists inside div.munu_js hold people; the surrounding
        # navigation lists must not be walked.
        if node.name != "ul" or node.find_parent("div", class_="munu_js") is None:
            continue
        if ADMINISTRATIVE_UNIT.search(unit):
            continue
        for anchor in node.find_all("a"):
            name = _squash(anchor.get_text(" ", strip=True))
            if not NAME_RE.fullmatch(name) or NAV_NOISE.fullmatch(name):
                continue
            href = (anchor.get("href") or "").strip()
            homepage = url if href in ("", "#") or href.startswith("javascript") \
                else urljoin(url, href)
            unit_name = unit or spec["department"]
            note = (f"学院师资名录按系与职称分组列出（{unit or '未标注系'}，"
                    f"{rank or '职称未标注'}）；名录不含个人研究方向。"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit_name, spec["code"],
                NO_DIRECTION, homepage, url, "学院师资名录（按系列表）", note,
            ))
    return rows
