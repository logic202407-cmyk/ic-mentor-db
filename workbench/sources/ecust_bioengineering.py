"""华东理工大学生物工程学院教师分布名录（0836 生物工程）。

华东理工大学是国内生物工程/生物化工办学历史最长的高校：学院官网《学院简介》
写明“1991 年获批全国第一个生物化工博士点”“2002 年生物化工被批准为国家重点
学科”“2015 年国内第一个生物工程博士学位授权一级学科获得批准”，研究生培养
设置生物工程（一级学科）、生物学（一级学科）与生物化工（二级学科）三个学术型
博士点。因此 **生物工程学院就是本校 0836 生物工程的办学主体**。

“师资队伍 → 教师分布”（``/jsfb1/list.htm``）把学院全体教职工**按教学科研单位
分组列全**：服务端直接渲染，普通 GET 即可拿到完整名单，无分页、无脚本、无接口。
页面结构是 ``div.paging_content`` 内一串相邻段落::

    <p><strong><span style="color:#e36c09;">生物工程系</span></strong></p>  ← 单位标题
    <p><a href=".../page.htm">郑高伟</a>、蔡孟浩、<a …>白云鹏</a>、…</p>      ← 姓名

* 单位标题段一定含 ``<strong>``，姓名段一定不含；据此按文档顺序推进“当前单位”，
  与 ``whu.py`` 的状态机同一思路。唯一例外是一个只有空 ``<strong>`` 的占位段，
  它把当前单位置空，紧随其后的姓名段（本页为 0 条）会被跳过，不会串到上一单位。
* “生物反应器工程全国重点实验室”一个单位下的姓名被拆成三个 ``<p>``，状态机
  天然把它们并回同一个单位。
* 姓名之间用 ``、`` 或全角逗号分隔，部分姓名内部带空格（“花 强”“张 敬宇”），
  故**先去空白再切分**：先切分后去空白会把“张 敬宇”切成“张”和“敬宇”，而后者
  恰好是合法的两字姓名，会凭空造出一个人。
* 有个人主页的姓名带 ``a[href]``（``biotech.ecust.edu.cn/…/page.htm``），作为
  ``homepage``；没有链接的姓名回落到名录页。
* 页面不给任何职称，也没有个人研究方向，故方向一律 :data:`NO_DIRECTION`，
  绝不拿“教授/研究员”之类去填（契约红线 2）。

只收与 0836 对应的教学科研单位（``BIOENGINEERING_UNIT``）：

* 同一张表上还列着 **食品科学与工程系**（0832 食品科学与工程）与
  **应用生物学系**（0710 生物学）。它们属于另外两个一级学科，不并入 0836，
  否则等于替这些老师改了学科。
* **学院党委 / 学院党政办公室 / 学院思政办公室** 是非教学单位（契约第 5 条），
  整段跳过。其中几位老师（如刘琴、王启要、高蓓、田锡炜）在其他教学科研单位
  下另有列名，仍会以自己的科研单位收录。
* 单位取默认拒绝：只有出现在 ``BIOENGINEERING_UNIT`` 里的分组才会被读取，
  页面以后新增的栏目不会静默混进来。
* 同一个老师可能同时挂在多个单位（如郑高伟在“生物工程系”与“生物反应器工程
  全国重点实验室”都出现）。本模块**每人只出一行**：``department`` 取页面上首次
  出现的单位，其余单位写进备注——否则同一个人会因跨单位而在库里变成多条记录。
* 学院另有“导师风采”（按导师组罗列，无院系、无职称）与“杰出人才”两个栏目，
  与教师分布高度重叠且信息更少，不另建来源，以免产出重复条目。

本模块只覆盖教师分布页上属于 0836 单位的教职工，不代表学院全部人员（学院简介
自称教职工 182 人、专任教师 125 人，本来源 116 条）；每条记录的备注里都写明
这一点，避免被读成全院名单。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "ecust_bioengineering",
    "code": "0836",
    "institution": "华东理工大学",
    "department": "生物工程学院",
    "discipline": "生物工程",
    # 师资队伍 → 教师分布。单页静态渲染，无 {page} 分页。
    "listing": "https://biotech.ecust.edu.cn/jsfb1/list.htm",
    "max_pages": 1,
},)

# 名录容器：只有它里面的段落是单位标题与姓名，导航与页脚都在它外面。
ROSTER_BOX = "div.paging_content"

# 0836 生物工程对应的教学科研单位（研究院、全国重点实验室都是合法科研单位）。
# 默认拒绝：不在此集合内的分组标题一律不读。
BIOENGINEERING_UNIT = frozenset({
    "生物工程系",
    "生物反应器工程全国重点实验室",
    "国家生化工程技术研究中心（上海）",
    "鲁华所",
    "阿华所",
    "动物细胞室",
    "海洋室",
    "生物分离室",
    "上海生物技术产业技术研究院",
    "上海市发酵工程实验教学中心",
    "发酵工业分离提取技术研发中心",
    "中国轻工业生物基材料工程重点实验室",
})

# 同一张表里属于其他一级学科的单位：食品科学与工程系（0832）、应用生物学系（0710）。
OTHER_DISCIPLINE_UNIT = frozenset({"食品科学与工程系", "应用生物学系"})

# 非教学单位（契约第 5 条）：党委、办公室、思政办等，整段跳过。本页的这三个
# 分组本来也不在 BIOENGINEERING_UNIT 里，这里是第二道防线。
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|工会|离退休|办公室|机关|人事|财务|教务|"
                                 r"学生工作|思政|行政|校友|后勤|招聘")

# 姓名分隔符。**不含空格**：空格属于姓名本身（“花 强”“张 敬宇”），切分前先去掉。
NAME_SEPARATOR = re.compile(r"[、，,;；/]+")
# 段落里的换行等标记在原文中起分隔作用。
SEPARATOR_TAGS = frozenset({"br", "hr"})


def _compact(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _names(text: str) -> list[str]:
    """把一段文本按分隔符切成姓名，只保留 ``NAME_RE`` 认可的 2–8 字汉字姓名。"""
    return [part for part in NAME_SEPARATOR.split(_compact(text))
            if NAME_RE.fullmatch(part)]


def _pieces(node):
    """按文档顺序把段落拆成 ``("text", 文本)`` / ``("link", a 标签)``。

    ``a`` 标签整体交出，不再向内展开，否则它内部的文字会被重复读一遍。
    """
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            yield "text", str(child)
        elif child.name == "a":
            yield "link", child
        elif child.name in SEPARATOR_TAGS:
            yield "text", "、"
        else:
            yield from _pieces(child)


def _people(paragraph) -> list[tuple[str, str]]:
    """取一个姓名段里的 ``(姓名, 个人主页 href)``，按出现顺序；无链接的回空串。"""
    people: list[tuple[str, str]] = []
    buffer = ""
    for kind, value in _pieces(paragraph):
        if kind == "text":
            buffer += value
            continue
        people.extend((name, "") for name in _names(buffer))
        buffer = ""
        href = (value.get("href") or "").strip()
        people.extend((name, href) for name in _names(value.get_text(" ", strip=True)))
    people.extend((name, "") for name in _names(buffer))
    return people


def _is_unit_heading(paragraph) -> bool:
    """单位标题段的标志：含 ``<strong>``、无链接、且整段没有任何姓名分隔符。"""
    if paragraph.find("strong") is None or paragraph.find("a") is not None:
        return False
    return not NAME_SEPARATOR.search(_compact(paragraph.get_text(" ", strip=True)))


def _skip(unit: str) -> bool:
    """非教学单位、其他一级学科的单位，以及任何没有登记过的分组，都不读。"""
    if not unit or unit in OTHER_DISCIPLINE_UNIT:
        return True
    if ADMINISTRATIVE_UNIT.search(unit):
        return True
    return unit not in BIOENGINEERING_UNIT


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    # 姓名 → {首次出现的单位 + 该页列出他的其他单位, 个人主页}，保持文档顺序。
    roster: dict[str, dict] = {}
    for box in soup.select(ROSTER_BOX):
        unit = ""
        for paragraph in box.find_all("p", recursive=False):
            if _is_unit_heading(paragraph):
                unit = _compact(paragraph.get_text(" ", strip=True))
                continue
            if _skip(unit):
                continue
            for name, href in _people(paragraph):
                record = roster.setdefault(name, {"units": [], "href": ""})
                if unit not in record["units"]:
                    record["units"].append(unit)
                if not record["href"] and href:
                    record["href"] = href

    rows: list[dict] = []
    for name, record in roster.items():
        units = record["units"]
        unit, others = units[0], units[1:]
        homepage = urljoin(url, record["href"]) if record["href"] else url
        listed = unit if not others else f"{unit}（该页另在{'、'.join(others)}下列出）"
        note = (f"华东理工大学生物工程学院教师分布名录按教学科研单位分组列出（{listed}）；"
                f"名录不含个人职称与研究方向。本来源只收 0836 生物工程对应的教学科研"
                f"单位，同页的食品科学与工程系（0832 食品科学与工程）与应用生物学系"
                f"（0710 生物学）属于其他一级学科，未收录；本来源只覆盖上述单位，"
                f"不代表学院全部人员。导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], unit, spec["code"],
            NO_DIRECTION, homepage, url, "学院教师分布名录", note,
        ))
    return rows
