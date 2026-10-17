"""大连理工大学机械工程学院 教师名录（0802 机械工程）.

学院「师资队伍 → 教师名录」是一张静态 JSP 页，把全院教师平铺在一张网格里，
每个人的链接指向校教师主页系统 ``faculty.dlut.edu.cn/<主页名>/zh_CN/index.htm``::

    div.ny > div.main
      <a href="http://faculty.dlut.edu.cn/guodm/zh_CN/index.htm">郭东明</a>
      <a href="http://faculty.dlut.edu.cn/1990011023/zh_CN/index.htm">…</a>
      …

**收录规则（可核实、不猜）**：只收链接指向 ``faculty.dlut.edu.cn`` 的教师，
共 184 位。理由是这条规则可以用链接本身验证——凡命中者必定有公开个人主页，
因此每条记录都有真实的 ``homepage`` 可供 ``--enrich`` 读取方向。同页另有约 37 位
教师的主页仍挂在学院旧版 IP 主机（``202.118.76.111:8080``）上，那种地址不适合作为
公开来源链接发布，故本轮不收；页面上其余「师资概况 / 本院院士 / 杰出人才 /
教授信息 / 硕导信息 / 博导信息 / 按职称查询 / 精确查找」等是**栏目与筛选标签**，
不是人名，按标签集合与链接规则双重排除。

口径说明：

* 该页**只按职称与筛选条件组织**，不提供「某人属于哪个系」的分组，因此
  ``department`` 记为**机械工程学院**这一级，不给每人编一个系。
* 名录不列个人研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`；
  页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "dlut_me",
    "code": "0802",
    "institution": "大连理工大学",
    "department": "机械工程学院",
    "discipline": "机械工程",
    # 师资队伍 → 教师名录。静态页，无分页。
    "listing": ("https://me.dlut.edu.cn/jsml.jsp"
                "?urltype=tree.TreeTempUrl&wbtreeid=1028"),
    "max_pages": 1,
},)

# 名录容器；栏目导航在 div.ny 之外，页脚在其后。
ROOT_SELECTOR = "div.ny div.main"
# 只有指向校教师主页系统的链接才算"有公开个人主页的教师"。
PERSON_HREF = re.compile(r"^https?://faculty\.dlut\.edu\.cn/")
# 栏目与筛选标签（不是人名），与链接规则双重排除。
LABEL = re.compile(r"师资|队伍|概况|名录|院士|人才|信息|查询|^按|^本院|^硕导|^博导|"
                   r"^教授$|^研究员$|^副教授$|^副研究员$|^讲师$|^高级实验师$|^实验师$|"
                   r"^助理研究员$|^精确查找$|^联系方式$")
# 行政/非教学单位（合同第 5 条）；本名录不会命中，保留作防御。
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
# 职称词，兜底防止职称串进方向字段（合同红线 2）。
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = soup.select_one(ROOT_SELECTOR)
    if root is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in root.select("a[href]"):
        homepage = urljoin(url, anchor.get("href") or "")
        if not PERSON_HREF.match(homepage):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or LABEL.search(name):
            continue
        seen.add(name)
        note = (f"机械工程学院「师资队伍 → 教师名录」名单（所属：{spec['department']}）；"
                f"名录只列姓名与校教师主页链接，未列职称与个人研究方向，也未按系分组。"
                f"本来源只收个人主页在 faculty.dlut.edu.cn 上的教师；"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, homepage, url, "学院教师名录", note,
        ))
    return rows
