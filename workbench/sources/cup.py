"""中国石油大学（北京）石油工程学院研究生导师名录（0820 石油与天然气工程）.

石油工程学院把研究生导师名单以 HTML 表格的形式挂在 ``oil/zsjy/sbdsjj/`` 下
（“硕博导师简介”栏目，共四份名单）。本模块读取其中的“学术型硕士研究生指导教师”
名单：它是四份名单里挂在 082000 石油与天然气工程下且人数最多的一份（学术型博士
名单另有 85 人；专业型硕士与工程博士名单用的是专业学位代码 085706，不属于 0820
这个一级学科，故未采用）。

表格结构（同一页内自洽，不依赖任何外部信息）::

    <tr><td rowspan=146>082000石油与天然气工程
                          01油气藏渗流理论与开发技术 … 11CO2地质利用与封存理论与技术</td>
        <td>高德利</td><td>教授</td><td>男</td><td>2</td>…</tr>
    <tr><td>李根生</td><td>教授</td><td>男</td><td>3</td>…</tr>
    …

* 带 ``rowspan`` 的首个单元格是**分组行**：里面写着 6 位招生专业代码和该专业的
  编号—方向对照表。``code[:4]`` 就是一级学科代码，本模块只保留等于 ``spec["code"]``
  的分组，所以同一张表里的“080100 力学”分组不会被错误归入 0820。
* 分组行本身还可能带着该组的**第一位导师**（上例的 高德利），因此分组行的姓名/职称/
  研究方向比普通行右移一列；两种位移都在这里显式处理。
* 普通导师行的“研究方向”列填的是对照表里的**编号**（``01，05，09，10``、``2``），
  所以方向由同一页给出的对照表还原；编号对不上对照表时（名录里有一行把出生日期
  填进了这一列）不做任何猜测，方向留 ``方向待补``。
* “联系电话”列**从不读取**——项目不保存任何联系方式。备注列只在“不含数字、不含 @、
  长度不超过 12 字”时才采用，这样即使换了名单布局也不可能把电话号带进备注。
* 师资队伍栏目（``oil/jsdw/…``）的名录由 JavaScript 渲染，普通 GET 只能拿到空壳，
  故不作为来源。

学院自身导航把 ``/jsdw/<slug>/`` 目录标注为系名（油气井工程系、油气田开发工程系、
油气储运工程系、海洋油气工程系、工程力学系），个人主页多数就落在这些目录下，因此
``department`` 优先取该系名，取不到时回落到 ``spec["department"]``。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "cup_petroleum",
    "code": "0820",
    "institution": "中国石油大学（北京）",
    "department": "石油工程学院",
    "discipline": "石油与天然气工程",
    # 石油工程学院“硕博导师简介” → 石油工程学院学术型硕士研究生指导教师。
    # 栏目索引：https://www.cup.edu.cn/oil/zsjy/sbdsjj/index.htm
    "listing": ("https://www.cup.edu.cn/oil/zsjy/sbdsjj/"
                "b371f65c056b48b6afef5a95f33c9580.htm"),
    "max_pages": 1,
},)

# 分组行首格：“082000石油与天然气工程01…”。6 位是招生专业代码，前 4 位是一级学科。
_GROUP_RE = re.compile(r"^(\d{6})(.*)$", re.S)
# 对照表里的方向编号：两位数字，且两侧都不能再是数字（这样 “CO2” 里的 2 不会误配）。
_CODE_RE = re.compile(r"(?<!\d)(\d{2})(?!\d)")
_NUMBER_RE = re.compile(r"\d+")
# 表头文字同样是 2–8 个汉字，会被 NAME_RE 放过，必须在调用 roster_row 之前剔除。
_COLUMN_HEADS = frozenset({
    "姓名", "职称", "性别", "研究方向", "出生年份", "出生年月",
    "是否博导", "导师类型", "联系电话", "备注", "学科名称及研究方向",
})
# 备注列只有在完全不含数字与 @ 时才采用，从结构上排除电话号与邮箱。
_UNSAFE_REMARK_RE = re.compile(r"[\d@]")
_REMARK_MAX = 12


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def _legend(cell) -> tuple[str, dict[int, str]]:
    """解析分组行首格，返回 ``(6 位招生专业代码, {方向编号: 方向名称})``。"""
    text = _compact(cell)
    match = _GROUP_RE.match(text)
    if match is None:
        return "", {}
    rest = match.group(2)
    marks = [(m.start(), int(m.group(1))) for m in _CODE_RE.finditer(rest)]
    legend: dict[int, str] = {}
    for index, (start, code) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(rest)
        name = rest[start + 2:end].strip()
        if name:
            legend[code] = name
    return match.group(1), legend


def _direction(cell, legend: dict[int, str]) -> str:
    """把“研究方向”列里的编号按同页对照表还原；任何编号对不上就不猜。"""
    numbers = [int(value) for value in _NUMBER_RE.findall(_compact(cell))]
    if not numbers or any(number not in legend for number in numbers):
        return NO_DIRECTION
    return "；".join(dict.fromkeys(legend[number] for number in numbers))


def _units(soup: BeautifulSoup, url: str) -> dict[str, str]:
    """从页面自身导航取 ``/jsdw/<slug>/`` → 系名 的对照，用于细分院系。"""
    units: dict[str, str] = {}
    for anchor in soup.select("a[href]"):
        label = _compact(anchor)
        if not label.endswith("系") or len(label) > 8:
            continue
        target = urljoin(url, anchor["href"])
        if "/jsdw/" not in target:
            continue
        slug = target.rstrip("/").split("/")[-2]
        if slug:
            units.setdefault(slug, label)
    return units


def _remark(cell) -> str:
    """备注列：只在完全不含数字/@ 且很短时采用，结构上排除联系方式。"""
    value = _compact(cell)
    if not value or len(value) > _REMARK_MAX or _UNSAFE_REMARK_RE.search(value):
        return ""
    return value


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    tables = soup.find_all("table")
    if not tables:
        return []
    table = max(tables, key=lambda node: len(node.find_all("tr")))
    units = _units(soup, url)
    heading = soup.select_one("div.subArticleTitle h2")
    roster = (_compact(heading) if heading is not None
              else f"{spec['department']}研究生导师名录")

    rows: list[dict] = []
    legend: dict[int, str] = {}
    subject = ""
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        header = cells[0]
        if header.get("rowspan"):
            # 分组行：更新当前招生专业与其方向对照表。
            code, legend = _legend(header)
            subject = code if code[:4] == spec["code"] else ""
            if not subject:
                continue
            # 分组行自带本组第一位导师时，姓名起于第 2 格，各列整体右移一列。
            offset = 1
        elif subject:
            offset = 0
        else:
            continue
        if len(cells) < offset + 4:
            continue
        name = _compact(cells[offset])
        if name in _COLUMN_HEADS or not NAME_RE.fullmatch(name):
            continue
        rank = _compact(cells[offset + 1])
        direction = _direction(cells[offset + 3], legend)
        remark = _remark(cells[-1])
        anchor = cells[offset].find("a")
        href = urljoin(url, anchor["href"]) if anchor and anchor.get("href") else ""
        homepage = href if href.startswith("http") else url
        unit = units.get(homepage.rstrip("/").split("/")[-2]) or spec["department"]
        note = (f"{roster}；招生专业：{subject} {spec['discipline']}"
                f"{'；职称：' + rank if rank else ''}"
                f"{'；' + remark if remark else ''}。"
                f"{'研究方向按名录同一页给出的编号对照表还原' if direction != NO_DIRECTION else '名录未标注个人研究方向'}。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], unit, spec["code"],
            direction, homepage, url, "学院研究生导师名录", note,
        ))
    return rows
