"""北京大学 力学与工程科学学院 师资名录（0801 力学）.

学院「师资队伍」按**拼音首字母**分 20 个索引页（B/C/D/F/H/J/K/L/M/N/O/P/Q/R/S/T/W/X/Y/Z），
每页列出该字母开头的教师，每人的链接形如 ``6427bd39b...htm``（32 位十六进制串）::

    /jzyg/szdw/L/6427bd39b3c99416d83ce89f353e15023.htm

``SPECS`` 由字母表生成——一个字母一个 key，共 20 个，各配一份离线快照。
这样既保持"一 key 一快照"的契约，也不用手写 20 段重复配置。

**为什么这份来源对 0801 重要**：该学科此前 35 条里 34 条来自上海交通大学（97.1%）。
北京大学力学与工程科学学院是**力学一级学科的对口办学单位**，归属清晰，不是弱归属。

口径说明：

* ``department`` 记为「力学与工程科学学院」——页面按教学单位组织，不给更细的系。
* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://mech.pku.edu.cn/jzyg/szdw"
LETTERS = tuple("BCDFHJKLMNOPQRSTWXYZ")

SPECS = tuple(
    {
        "key": f"pku_mechanics_{letter.lower()}",
        "code": "0801",
        "institution": "北京大学",
        "department": "力学与工程科学学院",
        "discipline": "力学",
        "listing": f"{_BASE}/{letter}/index.htm",
        "max_pages": 1,
    }
    for letter in LETTERS
)

# 教师详情页：32 位十六进制串 .htm（不带目录前缀，相对当前字母页）。
PERSON_HREF = re.compile(r"[0-9a-f]{20,}\.htm$")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
# 首字母索引本身与"师资队伍"等栏目名不是人名。
_NAV = re.compile(r"师资|队伍|索引|首页|学院|概况|招聘|联系我们")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        note = (f"北京大学力学与工程科学学院「师资队伍」按拼音首字母索引公布"
                f"（所属：{spec['department']}，本页为首字母 "
                f"{spec['listing'].rstrip('/').split('/')[-2]} 组）；"
                f"名录只列姓名，未列职称与个人研究方向；"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, urljoin(url, href), url, "学院师资队伍（拼音索引）", note,
        ))
    return rows
