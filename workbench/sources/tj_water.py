"""同济大学 土木工程学院 水利工程系 师资名录（0815 水利工程）.

学院水利工程系的「师资队伍」按职称分三张静态页：

* 教授/研究员/正高工   ``/szdw/js_yjy_zgg.htm``
* 副教授/副研究员/高工 ``/szdw/fjs_fyjy_gg.htm``
* 讲师                 ``/szdw/js1.htm``

三页共用一种卡片 ``a.academic-card``，**卡片文字把姓名与职称拼在一起**::

    <a class="academic-card" href="../info/1295/2169.htm"> 周德平研究员 </a>

因此姓名必须**剥掉职称后缀**再校验长度——否则「周德平研究员」会被当成姓名入库，
这违反项目红线（职称不得进入姓名或方向字段）。:data:`TITLE_SUFFIX` 枚举了本校
三张页面上出现的职称写法，测试里逐条断言姓名不含这些词。

口径说明：

* ``department`` 记为「水利工程系」——这是页面自身给出的最细一级。
* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://geohyd.tongji.edu.cn"

SPECS = (
    {
        "key": "tj_water_professor",
        "code": "0815",
        "institution": "同济大学",
        "department": "水利工程系（教授/研究员/正高工）",
        "discipline": "水利工程",
        "listing": f"{_BASE}/szdw/js_yjy_zgg.htm",
        "max_pages": 1,
    },
    {
        "key": "tj_water_associate",
        "code": "0815",
        "institution": "同济大学",
        "department": "水利工程系（副教授/副研究员/高工）",
        "discipline": "水利工程",
        "listing": f"{_BASE}/szdw/fjs_fyjy_gg.htm",
        "max_pages": 1,
    },
    {
        "key": "tj_water_lecturer",
        "code": "0815",
        "institution": "同济大学",
        "department": "水利工程系（讲师）",
        "discipline": "水利工程",
        "listing": f"{_BASE}/szdw/js1.htm",
        "max_pages": 1,
    },
)

ROOT_SELECTOR = "a.academic-card"
PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
# 卡片文字里拼着的职称后缀，长的放前面，避免「副研究员」被「研究员」半截匹配。
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|正高工|副高工|研究员|教授|"
    r"副教授|讲师|高工|院士)+$"
)
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def clean_name(text: str) -> str:
    """从卡片文字里取姓名：压掉空白、剥掉结尾职称，再交给 NAME_RE 校验。"""
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
    for anchor in soup.select(ROOT_SELECTOR):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = clean_name(anchor.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        note = (f"土木工程学院水利工程系「师资队伍 → {spec['department']}」名单；"
                f"卡片文字形如「姓名+职称」，入库前已剥掉职称后缀；"
                f"名录未列研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, urljoin(url, href), url, "学院师资队伍（按职称）", note,
        ))
    return rows
