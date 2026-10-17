"""四个单一机构学科的第二机构：中南大学 安全 + 大连理工 船舶／交通运输／生物医学工程.

这四所单位都来自**已确认可用的校级教师主页系统**，因此一次能给四个"只有一所机构"
的学科各补上第二所：

====================  ======  ==============================  ==========
学科                  学校    入口                             页面形态
====================  ======  ==============================  ==========
0837 安全科学与工程    中南    学科列表 id=1131（共35条, 2页）   学科级
0824 船舶与海洋工程    大连理工 单位列表 id=1211（共75条, 7页）   单位级
0823 交通运输工程      大连理工 单位列表 id=1216（共12条, 1页）   单位级
0831 生物医学工程      大连理工 单位列表 id=1315（共31条, 3页）   单位级
====================  ======  ==============================  ==========

**两套页面形态不同，所以共有两种取人规则**：

* 中南大学（``DisciplineTeacherList``）：锚文本就是姓名。
* 大连理工（``CollegeTeacherList``）：每张卡片在 ``div.jsy`` 里，锚文本是
  「姓名单位：…职称：…个人主页」的拼接，姓名取「单位」之前的汉字串——这顺带保证
  **职称不会串进方向字段**（项目红线 2）。

两者都只收**指向个人主页**的链接（``/<主页名>/zh_CN/index.htm``），这条规则本身
就能排除导航。

说明：``--only`` 可只采其中某个 key；``department`` 记到页面能给的最细一级
（中南是学科、大连理工是单位）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_CSU = "https://faculty.csu.edu.cn/xk.jsp?totalpage={total}&PAGENUM={page}&id={id}"
_CSU += "&urltype=tsites.DisciplineTeacherList&wbtreeid=1003&st=0&lang=zh_CN"
_DLUT = "https://faculty.dlut.edu.cn/xyjslb.jsp?totalpage={total}&PAGENUM={page}"
_DLUT += "&urltype=tsites.CollegeTeacherList&wbtreeid=1003&st=0&id={id}&lang=zh_CN"

SPECS = (
    {
        "key": "csu_safety",
        "code": "0837",
        "institution": "中南大学",
        "department": "安全科学与工程（学科列表）",
        "discipline": "安全科学与工程",
        "listing": _CSU.format(total=2, page="{page}", id=1131),
        "max_pages": 2,
    },
    {
        "key": "dlut_ship",
        "code": "0824",
        "institution": "大连理工大学",
        "department": "船舶工程学院",
        "discipline": "船舶与海洋工程",
        "listing": _DLUT.format(total=7, page="{page}", id=1211),
        "max_pages": 7,
    },
    {
        "key": "dlut_transport",
        "code": "0823",
        "institution": "大连理工大学",
        "department": "交通运输系",
        "discipline": "交通运输工程",
        "listing": _DLUT.format(total=1, page="{page}", id=1216),
        "max_pages": 1,
    },
    {
        "key": "dlut_bme",
        "code": "0831",
        "institution": "大连理工大学",
        "department": "生物医学工程学院",
        "discipline": "生物医学工程",
        "listing": _DLUT.format(total=3, page="{page}", id=1315),
        "max_pages": 3,
    },
)

CSU_PERSON = re.compile(r"faculty\.csu\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm")
DLUT_PERSON = re.compile(r"faculty\.dlut\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm")
# 大连理工卡片：锚文本里「单位」之前的汉字串即姓名。
DLUT_NAME = re.compile(r"^([\u4e00-\u9fff·]{2,8})(?=单位|职称|个人主页|$)")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
_NAV = re.compile(r"首页|单位列表|学科列表|教师查询|登录|English|下页|尾页|上页|当前位置|共\d+条")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []

    if "csu.edu.cn" in spec["listing"]:
        # 学科级：全文档按个人主页链接取人，锚文本即姓名。
        anchors = soup.select("a[href]")
        person_re, flattened = CSU_PERSON, False
        source_note = "学校教师主页·学科列表"
    else:
        # 单位级：卡片在 div.jsy 里，锚文本是拼接串。
        cards = soup.select("div.jsy")
        anchors = []
        for card in cards:
            anchors.extend(card.select("a[href]"))
        person_re, flattened = DLUT_PERSON, True
        source_note = "学校教师主页·单位列表"

    for anchor in anchors:
        href = urljoin(url, anchor.get("href") or "")
        if not person_re.search(href):
            continue
        raw = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if flattened:
            match = DLUT_NAME.match(raw)
            if not match:
                continue
            name = match.group(1)
        else:
            name = raw
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        note = (f"{spec['department']}教师列表（{spec['discipline']}，"
                f"{spec['institution']}）；该校教师主页系统按"
                f"{'学科' if not flattened else '单位'}组织，院系记到该级；"
                f"名录未列研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, href, url, source_note, note,
        ))
    return rows
