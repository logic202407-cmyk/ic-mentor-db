"""中国矿业大学（北京）能源与矿业学院 教师列表（0819 矿业工程）.

学院官网「师资队伍 → 师资概况 → 教师列表」是服务端渲染的静态页，全院教师在
``div.bg > div.w12.nl`` 的一张网格里平铺，每人的链接指向院内详情页
``../../info/<栏目>/<文章>.htm``::

    div.bg > div.w12.nl
      <a href="../../info/1234/5678.htm">袁亮</a>
      <a href="../../info/1234/5679.htm">…</a>
      …

**这是一所独立于中国矿业大学（徐州）的学校**：本校域名 ``cumtb.edu.cn``，徐州本部为
``cumt.edu.cn``，是两所不同的大学；现有 0819 的 110 条来自徐州本部，因此本来源
对 0819 是一个**新的机构**。

口径说明：

* 该页另按系分了四个子页（矿业科学与工程系、智能采矿工程系、资源科学与工程系、
  能源科学与工程系），但**主列表已经含全院教师**，因此只建一个 ``SPECS`` 条目，
  ``department`` 记为「能源与矿业学院」这一级——与 ``tsinghua_me.py``、``dlut_me.py``
  的做法一致：宁可按可核实的层级记录，也不给每人猜一个系。
* 名录里有一位外籍教师写成拉丁字母（如 ``DerekElsworth``），不符合 ``NAME_RE``，
  会被跳过——这类姓名无法与中文姓名同样核对，宁缺勿猜。
* 名录不列个人研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`；
  页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "cumtb_mining",
    "code": "0819",
    "institution": "中国矿业大学（北京）",
    "department": "能源与矿业学院",
    "discipline": "矿业工程",
    # 师资队伍 → 师资概况 → 教师列表。静态单页，无分页。
    "listing": "https://nyxy.cumtb.edu.cn/szdw/szgk1/jslb.htm",
    "max_pages": 1,
},)

# 名录容器：bg 里包着 w12.nl 的教师网格，栏目导航在它外面。
ROOT_SELECTORS = ("div.bg div.w12.nl", "div.bg")
# 详情页链接形如 ../../info/1234/5678.htm —— 指向个人页而非栏目。
PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
# 行政/非教学单位（合同第 5 条）；本页不会命中，保留作防御。
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
# 职称词，兜底防止职称串进方向字段（合同红线 2）。
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
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        homepage = urljoin(url, href)
        note = (f"能源与矿业学院「师资队伍 → 师资概况 → 教师列表」名单"
                f"（所属：{spec['department']}）；名录只列姓名，未列职称与个人研究方向，"
                f"也未在主列表上按系分组。本来源是一所独立于中国矿业大学（徐州）的学校；"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, homepage, url, "学院教师列表", note,
        ))
    return rows
