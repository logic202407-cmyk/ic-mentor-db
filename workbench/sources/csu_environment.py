"""中南大学 环境科学与工程 教师列表（0830 环境科学与工程）.

中南大学教师个人主页系统（``faculty.csu.edu.cn``）按一级学科提供教师列表。
「学科列表 → 工学 → 环境科学与工程」对应 ``id=1130``，页面标题即
「环境科学与工程教师列表」，自报「共45条」，每页 20 条，故 ``totalpage=3``。

**``totalpage`` 是请求参数**：传小了只会拿回首页（同校冶金 1115、地质 1126、
材料 1114、矿业 1127 四个来源已各踩过一次）。45 条须传 3。

**为什么归属可靠**：页面自身声明学科名与条数，不是"某学院全体教师再推断"——
与 0838 拒绝"把全校博导名单归入公安技术"是同一标准。

口径说明：

* ``department`` 记为「环境科学与工程（学科列表）」：该页按学科组织，不按学院分组。
* 名录不列职称与研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_PAGE = ("https://faculty.csu.edu.cn/xk.jsp?totalpage=3&PAGENUM={page}"
         "&id=1130&urltype=tsites.DisciplineTeacherList&wbtreeid=1003&st=0&lang=zh_CN")

SPECS = ({
    "key": "csu_environment",
    "code": "0830",
    "institution": "中南大学",
    "department": "环境科学与工程（学科列表）",
    "discipline": "环境科学与工程",
    "listing": _PAGE,
    "max_pages": 3,
},)

PERSON_HREF = re.compile(r"faculty\.csu\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
_NAV = re.compile(r"首页|单位列表|学科列表|教师查询|关于主页|登录|English|下页|尾页|上页|"
                  r"哲学|经济学|法学|教育学|文学|理学|工学|医学|管理学|艺术学|交叉学科|"
                  r"当前位置|共\d+条")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select("a[href]"):
        href = urljoin(url, anchor.get("href") or "")
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        note = (f"中南大学教师个人主页系统「学科列表 → 工学 → 环境科学与工程」教师列表"
                f"（页面自报共 45 条、每页 20 条、按 totalpage=3 取全）；"
                f"该列表由页面自身按一级学科声明，不是「学院全体教师再推断」；"
                f"名录未列职称与个人研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, href, url, "学校教师主页·学科列表", note,
        ))
    return rows
