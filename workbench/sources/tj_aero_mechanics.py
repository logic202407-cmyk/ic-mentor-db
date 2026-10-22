"""同济大学 航空航天与力学学院 教师名录（0801 力学）.

学院「师资队伍 → 教师名录」按拼音与按职称各有一张页，两页列的是**同一批人**，
因此本项目**只用按拼音那张**（``/jsmlwapyw/list.htm``），避免重复入库。

页面结构：整个右侧是 ``div.box``，里面既含左侧导航（学院概况、院长致辞、现任领导…）
又含真正的名录。名录在 ``div.nycon`` 里，每人一个 ``c<数字>a<数字>/page.htm`` 链接::

    <div class="nycon"> … <a href="12/68/c22266a201320/page.htm">姓名</a> … </div>

**为什么只取 ``div.nycon``**：``div.box`` 会把 9 条导航（学院概况/院长致辞/现任领导/
组织机构/系所信息/专业介绍/科研项目/研究成果/师资队伍）当成姓名——它们都是 2-8 个
汉字，光靠姓名正则筛不掉。这一点在测试里用"必须恰好 73 人"钉住。

**为什么这份来源对 0801 重要**：该学科此前 131 条里 96 条来自北京大学（73.3%）。
同济这个学院是力学一级学科的对口办学单位，补进来后最大机构降到约 47%，**达标**。

口径说明：

* ``department`` 记为「航空航天与力学学院」——页面按学院组织，不细分系所。
* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_LISTING = "https://aero-mech.tongji.edu.cn/jsmlwapyw/list.htm"

SPECS = (
    {
        "key": "tj_aero_mechanics",
        "code": "0801",
        "institution": "同济大学",
        "department": "航空航天与力学学院",
        "discipline": "力学",
        "listing": _LISTING,
        "max_pages": 1,
    },
)

# 名录容器：必须限定在这里，否则会把左侧导航当成姓名。
ROOT_SELECTOR = "div.nycon a[href]"
PERSON_HREF = re.compile(r"c\d+a\d+/page\.htm")
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
# 导航词（即使落在容器内也要挡掉）
_NAV = re.compile(r"学院|致辞|领导|机构|系所|专业|科研|成果|师资|首页|名录|教授$|研究员$")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select(ROOT_SELECTOR):
        href = (anchor.get("href") or "").strip()
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        note = (f"同济大学航空航天与力学学院「师资队伍 → 教师名录（按拼音）」名单；"
                f"页面另有「按职称」一张，列同一批人，本项目只用按拼音那张以免重复入库；"
                f"名录只列姓名与个人主页，未列个人研究方向；导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, urljoin(url, href), url, "学院师资队伍（按拼音）", note,
        ))
    return rows
