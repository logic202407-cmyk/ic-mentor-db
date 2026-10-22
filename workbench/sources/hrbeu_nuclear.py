"""哈尔滨工程大学 核科学与技术学院 教师介绍（0827 核科学与技术）.

学院「师资队伍 → 教师介绍」是一张**静态整页**名录，把全院教师按内设机构分成
9 组，每组一个 ``div.newlist1``，组内 ``ul.list`` 里每人一个指向个人详情页的
链接::

    <div class="newlist1">
      <h2>核技术系</h2>
      <ul class="list">
        <li><a href="http://faculty.hrbeu.edu.cn/wangxiang1">
              <h3 class="l1 txt1">王翔</h3></a></li>
        ...
      </ul>
    </div>

**为什么只收「核技术系」「核化工系」这两组**：整页 9 组共 120 人，其中
3 个研究中心/研究所 69 人、实验中心 7 人、三个行政办公室 19 人。行政办公室
按项目合同第 5 条必须剔除；而把 5 个教学科研机构全部入库（94 人）会让本校
在本学科占到约 70%，反而违反项目「最大单一机构占比 < 60%」的硬标准
（0801 力学就踩过这个坑，见 ``workbench/tools/distribution_audit.py`` 的说明）。
因此本模块把口径限定为学院仅有的两个**系**，两系名单**完整**收录
（12 + 13 = 25 人）：不挑人、不截断，也不把行政与教辅人员算作师资。

口径说明：

* ``department`` 逐行记为「核科学与技术学院·核技术系 / ·核化工系」。
* 名录只列姓名与个人详情页，不列职称与研究方向，``direction`` 一律
  :data:`NO_DIRECTION`。
* 个人详情页有两种形态，都是"人"的页面而非名录页：学院站内
  ``/info/<栏目>/<id>.htm`` 与学校教师主页 ``faculty.hrbeu.edu.cn/<拼音>``。
* 原页面页脚有一处院办座机，落快照前已替换为「联系方式已隐去」；本模块
  从不读取任何联系方式字段。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_LISTING = "https://cnst.hrbeu.edu.cn/szdw/jsjs.htm"

SPECS = ({
    "key": "hrbeu_nuclear",
    "code": "0827",
    "institution": "哈尔滨工程大学",
    "department": "核科学与技术学院",
    "discipline": "核科学与技术",
    "listing": _LISTING,
    "max_pages": 1,
},)

# 只收学院这两个「系」的完整名单；研究中心/研究所/实验中心与行政办公室不入库。
UNITS = ("核技术系", "核化工系")
UNIT_DEPARTMENT = {
    "核技术系": "核科学与技术学院·核技术系",
    "核化工系": "核科学与技术学院·核化工系",
}
# 人员容器：div.newlist1 > h2(机构名) + ul.list > li > a
_PERSON_ANCHOR = "ul.list > li > a[href]"
# 个人详情页：站内 detail 页，或学校教师主页（个人拼音路径）。
_PERSON_HREF = re.compile(
    r"^(?:https?://cnst\.hrbeu\.edu\.cn/info/\d+/\d+\.htm"
    r"|https?://faculty\.hrbeu\.edu\.cn/[A-Za-z0-9_])"
)
# 页面若把职称拼在姓名后（「张三教授」），先剥后缀，再用 NAME_RE 校验。
_TITLE_SUFFIX = re.compile(
    r"(?:副教授|助理教授|教授|副研究员|研究员|高级工程师|高工|工程师|实验师|"
    r"博士后|院士|助教)+$"
)
# 剥后缀后仍含职称词，说明不是纯姓名（例如「教授」本身会被 NAME_RE 放过）。
_TITLE_WORD = re.compile(r"教授|讲师|研究员|高工|院士|博士后")
# 导航/栏目词：落在容器里也不是人名（防御用）。
_NAV = re.compile(r"学院|师资|教师介绍|名录|首页|上页|下页|尾页|共\d+条|中心$|办公室$|系$")


def _squash(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _person_name(anchor) -> str:
    """取姓名：优先 ``h3.txt1``；若职称被拼在姓名后，剥掉后缀再返回。"""
    heading = anchor.find("h3", class_="txt1")
    raw = heading.get_text(" ", strip=True) if heading else anchor.get_text(" ", strip=True)
    name = _squash(raw)
    stripped = _TITLE_SUFFIX.sub("", name)
    return stripped


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    for block in soup.select("div.newlist1"):
        heading = block.find("h2")
        unit = _squash(heading.get_text()) if heading else ""
        if unit not in UNITS:
            continue
        department = UNIT_DEPARTMENT[unit]
        for anchor in block.select(_PERSON_ANCHOR):
            name = _person_name(anchor)
            if not NAME_RE.fullmatch(name) or name in seen:
                continue
            if _TITLE_WORD.search(name) or _NAV.search(name):
                continue
            homepage = urljoin(url, (anchor.get("href") or "").strip())
            if not _PERSON_HREF.search(homepage) or homepage == url:
                continue
            seen.add(name)
            note = (f"哈尔滨工程大学核科学与技术学院「师资队伍 → 教师介绍」页"
                    f"（静态整页，按内设机构分 9 组共 120 人）；"
                    f"本模块只收学院两个系之一「{unit}」的完整名单，"
                    f"研究中心/研究所/实验中心与行政办公室不入库；"
                    f"名录只列姓名与个人详情页，未列职称与研究方向；"
                    f"导师资格以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], department, spec["code"],
                NO_DIRECTION, homepage, url, "学院师资队伍（教师介绍）", note,
            ))
    return rows
