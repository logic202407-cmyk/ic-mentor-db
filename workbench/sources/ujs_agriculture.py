"""江苏大学 农业工程学院 教师列表（0828 农业工程）.

江苏大学教师主页系统（``faculty.ujs.edu.cn``）提供**学院列表**（``xylb.jsp``，
``CollegeTeacherList``）。农业工程学院对应 ``id=1164``，学院列表页上直接标着
「农业工程学院(33)」，进入后页面自报「共33条」，每页实为 6 人，共 6 页，故 ``totalpage=6``。

教师卡片在 ``div.page`` 内，每人链到个人主页::

    http://faculty.ujs.edu.cn/<主页名>/zh_CN/index.htm

**这是江苏大学的传统优势学科**（农业工程为国家重点学科），因此把它作为 0828 的第二
机构是合适的；``department`` 记到「农业工程学院」这一级——系统按**学院**组织，
没有学科级列表，学院这一级就是页面能给的、也是可核实的最细一级。

口径说明：

* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`（``--enrich`` 可补）。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_PAGE = ("https://faculty.ujs.edu.cn/jg_xylb.jsp?totalpage=6&PAGENUM={page}"
         "&urltype=tsites.CollegeTeacherList&wbtreeid=1003&st=0&id=1164&lang=zh_CN")

SPECS = ({
    "key": "ujs_agriculture",
    "code": "0828",
    "institution": "江苏大学",
    "department": "农业工程学院",
    "discipline": "农业工程",
    "listing": _PAGE,
    "max_pages": 6,
},)

# 名录分散在多个 div.page 里（每页只覆盖一部分），因此不限定单一容器：
# 直接用「个人主页链接」这条强规则在全文档上取人，比猜容器稳。
ROOT_SELECTORS = ("div.page", "body")
PERSON_HREF = re.compile(r"faculty\.ujs\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
_NAV = re.compile(r"首页|单位列表|学院列表|教师查询|登录|English|下页|尾页|上页|当前位置|共\d+条")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    # 名录分散在多个 div.page 里（每页只覆盖一部分），因此把该选择器的**全部**命中
    # 都遍历一遍，而不是只取第一个；最后再回落到全文档。个人主页链接这条规则本身
    # 足够强，能保证只捞到教师。
    nodes = []
    for selector in ROOT_SELECTORS:
        nodes = soup.select(selector)
        if nodes:
            break
    if not nodes:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    anchors = []
    for node in nodes:
        anchors.extend(node.select("a[href]"))
    for anchor in anchors:
        href = urljoin(url, anchor.get("href") or "")
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        note = (f"江苏大学教师主页系统「学院列表 → 农业工程学院」教师列表"
                f"（学院列表页标注 33 人、页面自报共 33 条、每页 12 条、按 totalpage=3 取全）；"
                f"该校系统按学院组织、无学科级列表，故院系记到学院一级；"
                f"名录未列研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, href, url, "学校教师主页·学院列表", note,
        ))
    return rows
