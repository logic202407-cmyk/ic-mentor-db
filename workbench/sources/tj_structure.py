"""同济大学 土木工程学院 建筑工程系 师资名录（0814 土木工程）.

建筑工程系（结构工程方向）「师资队伍」按职称分三张静态页：

* 教授/研究员          ``/szdw/js.htm``
* 副教授/副研究员      ``/szdw/fjs.htm``
* 讲师                 ``/szdw/js1.htm``

每页把教师列成卡片，姓名与职称**分开放**（与本项目的 ``tj_water.py`` 不同，那边是拼
在一起的），因此姓名直接取锚文本即可；仍保留 :func:`clean_title` 作防御，避免个别
卡片把职称写进同一行。

口径说明：

* ``department`` 记为「建筑工程系」——页面自身给出的最细一级，对应 0814 土木工程下
  的结构工程方向。
* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://structure.tongji.edu.cn"

SPECS = (
    {
        "key": "tj_structure_professor",
        "code": "0814",
        "institution": "同济大学",
        "department": "建筑工程系（教授/研究员）",
        "discipline": "土木工程",
        "listing": f"{_BASE}/szdw/js.htm",
        "max_pages": 1,
    },
    {
        "key": "tj_structure_associate",
        "code": "0814",
        "institution": "同济大学",
        "department": "建筑工程系（副教授/副研究员）",
        "discipline": "土木工程",
        "listing": f"{_BASE}/szdw/fjs.htm",
        "max_pages": 1,
    },
    {
        "key": "tj_structure_lecturer",
        "code": "0814",
        "institution": "同济大学",
        "department": "建筑工程系（讲师）",
        "discipline": "土木工程",
        "listing": f"{_BASE}/szdw/js1.htm",
        "max_pages": 1,
    },
)

PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|正高工|副高工|研究员|教授|"
    r"副教授|讲师|高工|院士)+$"
)
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def clean_title(text: str) -> str:
    """剥掉可能粘在姓名后面的职称；剥完不是合法姓名则返回空串。"""
    raw = re.sub(r"[\s\u3000\xa0]+", "", text)
    stripped = TITLE_SUFFIX.sub("", raw)
    return stripped if NAME_RE.fullmatch(stripped) else ""


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = clean_title(anchor.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        note = (f"土木工程学院建筑工程系「师资队伍 → {spec['department']}」名单；"
                f"名录未列职称与个人研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, urljoin(url, href), url, "学院师资队伍（按职称）", note,
        ))
    return rows
