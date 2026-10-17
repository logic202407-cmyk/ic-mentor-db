"""华南理工大学 化学与化工学院 师资队伍（0817 化学工程与技术）.

学院「师资队伍」按**职称**分成几张静态页，每页把该职称的教师列在
``ul.wp_article_list`` 里，每人的链接指向院内文章页
``/ce/<年>/<月日>/c<栏目>a<文章>/page.htm``::

    ul.wp_article_list
      <a href="/ce/2012/1221/c2421a54738/page.htm">曹桢</a>
      …

本模块为三个职称类别各建一个 ``SPECS`` 条目（共用同一个 ``parse``）：

* 教授（研究员）  ``/ce/2421/list.htm``
* 副教授（副研、高工） ``/ce/2422/list.htm``
* 讲师（助理研究员） ``/ce/2424/list.htm``

**刻意不收**「实验团队教师」（``/ce/2425/list.htm``，27 位）：那是实验技术系列，
与教学科研教师是不同岗位序列，混在一起会让"该学科教师"的口径失真；本模块的收录
范围在备注里逐条写明。

收录规则可核实：只收链接形如 ``c<栏目>a<文章>/page.htm`` 的锚点——这条规则同时
排除了「下载区」这类栏目标签（它们指向 ``list.htm``）。名录不列研究方向，故
``direction`` 一律 :data:`NO_DIRECTION`；页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://www2.scut.edu.cn/ce"

SPECS = (
    {
        "key": "scut_chem_professor",
        "code": "0817",
        "institution": "华南理工大学",
        "department": "化学与化工学院（教授/研究员）",
        "discipline": "化学工程与技术",
        "listing": f"{_BASE}/2421/list.htm",
        "max_pages": 1,
    },
    {
        "key": "scut_chem_associate",
        "code": "0817",
        "institution": "华南理工大学",
        "department": "化学与化工学院（副教授/副研/高工）",
        "discipline": "化学工程与技术",
        "listing": f"{_BASE}/2422/list.htm",
        "max_pages": 1,
    },
    {
        "key": "scut_chem_lecturer",
        "code": "0817",
        "institution": "华南理工大学",
        "department": "化学与化工学院（讲师/助理研究员）",
        "discipline": "化学工程与技术",
        "listing": f"{_BASE}/2424/list.htm",
        "max_pages": 1,
    },
)

# 名录容器：只有 ul.wp_article_list 里才是该职称的教师。
ROOT_SELECTORS = ("ul.wp_article_list", "div.news_list")
# 文章页链接：c<栏目>a<文章>/page.htm —— 这条规则同时排除指向 list.htm 的栏目标签。
PERSON_HREF = re.compile(r"c\d+a\d+/page\.htm")
# 行政/非教学单位（合同第 5 条）；本页不会命中，保留作防御。
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
# 职称词，兜底防止职称串进方向字段（合同红线 2）。
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = None
    for selector in ROOT_SELECTORS:
        root = soup.select_one(selector)
        if root is not None:
            break
    if root is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in root.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        homepage = urljoin(url, href)
        note = (f"化学与化工学院「师资队伍」按职称公布（{spec['department']}）；"
                f"名录只列姓名，未列个人研究方向。本来源收教授/研究员、副教授/副研/高工、"
                f"讲师/助理研究员三类教学科研教师，**不含**实验技术系列（实验团队教师）；"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, homepage, url, "学院师资队伍（按职称）", note,
        ))
    return rows
