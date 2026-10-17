"""清华大学机械工程系 在职教师名录（0802 机械工程）.

系官网「师资队伍 → 在职教师」是服务端渲染的静态页，全部在职教师平铺在一张网格里::

    div.pageCon
      div.menu           ← 栏目导航（院士 / 在职教师 / 兼职教授 / 双聘教授 / …）
      div.content
        div.conItem
          <研究所标签行>   ← 机械制造研究所 / 摩擦学研究所 / 制造工程研究所 / …
          <字母索引行>     ← 全体 / A / B / C …
          <a href="/info/1096/2260.htm">姓名</a> × N

两条口径说明：

* **只收「在职教师」这一栏**。同页还挂着院士、兼职教授、双聘教授、名誉教授、
  访问教授与教辅人员——兼职/双聘/名誉/访问都不是本系在职教师，教辅不是教师岗，
  合并会把不同身份的人混成一批。院士通常是同一批人的重复标注。
* 研究所标签与字母索引只是**前端筛选器**，服务端输出的名单是**平铺**的，
  页面不提供"某人属于哪个研究所"的分组结构。因此 ``department`` 记为
  **机械工程系**这一级，而不是给每人编一个研究所——宁可按可核实的层级记录，
  也不猜。

名录不列个人研究方向，故 ``direction`` 一律为 :data:`NO_DIRECTION`；页面也不含
邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "tsinghua_me",
    "code": "0802",
    "institution": "清华大学",
    "department": "机械工程系",
    "discipline": "机械工程",
    # 师资队伍 → 在职教师。静态单页，无分页。
    "listing": "https://www.me.tsinghua.edu.cn/szdw/zzjs.htm",
    "max_pages": 1,
},)

# 名录容器：conItem 里面才是教师网格，栏目导航与页脚都在它外面。
ROOT_SELECTOR = "div.pageCon div.content div.conItem"
# 前端筛选标签与栏目名，不是人名。
TAB_WORD = re.compile(r"^全体$|研究所$|研究中心$|^机械工程系$|^[A-Z]{1,3}$|教辅人员$|"
                      r"兼职教授$|双聘教授$|名誉教授$|访问教授$|在职教师$|^院士$")
# 详情页链接形如 /info/1096/2260.htm —— 指向个人页而非栏目。
PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
# 行政/非教学单位（合同第 5 条）；本系名录不会命中，保留作为防御。
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
    for anchor in root.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or TAB_WORD.search(name):
            continue
        if _ADMIN.search(spec["department"]):
            continue
        seen.add(name)
        homepage = urljoin(url, href)
        note = (f"机械工程系「师资队伍 → 在职教师」名单（所属：{spec['department']}）；"
                f"名录只列姓名，未列职称与个人研究方向，也未按研究所分组。"
                f"本来源只收在职教师，不含兼职/双聘/名誉/访问教授与教辅人员；"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, homepage, url, "系在职教师名录", note,
        ))
    return rows
