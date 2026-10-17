"""大连理工大学 生物工程学院 教师列表（0836 生物工程）.

大连理工大学教师主页系统（``faculty.dlut.edu.cn``）与中南大学那套不同：它提供
**单位列表**（``xylb.jsp``，``CollegeTeacherList``）而不是学科列表
（``xklb.jsp`` 在本校 404）。生物工程学院对应 ``id=1229``，页面自报「共87条」，
每页 12 条，故 ``totalpage=8``。

每张卡片是一个 ``div.jsy``，锚文本把姓名、单位、职称、入口拼在一起::

    安利佳单位：生物工程学院职称：教授个人主页

因此姓名取「单位」之前的汉字串（:data:`NAME_PREFIX`）——**这也顺带保证了职称不会
串进方向字段**（项目红线 2：职称绝不写进方向）。

口径说明：

* ``department`` 记为「生物工程学院」：本校系统按**单位**组织，没有学科级列表，
  所以这一级是页面能给的、也是可核实的最细一级。
* 名录只列姓名与个人主页链接，不列研究方向，故 ``direction`` 一律
  :data:`NO_DIRECTION`（``--enrich`` 可据个人主页补）。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NO_DIRECTION, roster_row

_PAGE = ("https://faculty.dlut.edu.cn/xyjslb.jsp?totalpage=8&PAGENUM={page}"
         "&urltype=tsites.CollegeTeacherList&wbtreeid=1003&st=0&id=1229&lang=zh_CN")

SPECS = ({
    "key": "dlut_bioengineering",
    "code": "0836",
    "institution": "大连理工大学",
    "department": "生物工程学院",
    "discipline": "生物工程",
    "listing": _PAGE,
    "max_pages": 8,
},)

# 名录容器：每页 12 张教师卡片。
ROOT_SELECTORS = ("div.jsy", "ul.flex")
# 姓名：锚文本里「单位」之前的汉字串。
NAME_PREFIX = re.compile(r"^([\u4e00-\u9fff·]{2,8})(?=单位|职称|个人主页|$)")
PERSON_HREF = re.compile(r"faculty\.dlut\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
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
        href = urljoin(url, anchor.get("href") or "")
        if not PERSON_HREF.search(href):
            continue
        raw = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        match = NAME_PREFIX.match(raw)
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        note = (f"生物工程学院教师列表（所属：{spec['department']}）；"
                f"本校教师主页系统按单位组织、无学科级列表，故院系记到学院一级；"
                f"卡片上带职称但未列研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, href, url, "学校教师主页·单位列表", note,
        ))
    return rows
