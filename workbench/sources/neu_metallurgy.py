"""东北大学 冶金学院 教师名录（0806 冶金工程）.

学院官网「师资队伍 → 教师名录」是一张服务端渲染的静态页，把全院教师列在同一页里。
每人的链接有两种形态，都指向**个人页**而不是栏目页::

    <a href="http://adminweb.neu.edu.cn/_s12/10570/.../c1234a56789/page.psp">姜周华</a>
    <a href="http://faculty.neu.edu.cn/lihuabing/zh_CN/index.htm">李花兵</a>

因此收录规则是「链接必须落在 ``c<栏目>a<文章>/page.psp|page.htm`` 或
``faculty.neu.edu.cn/`` 之下」——这条规则可以用链接本身验证，且天然排除了该页
50 多个指向 ``/<栏目>/list.htm`` 的导航链接。

**一个容易踩的坑，记在这里**：本校的详情页后缀是 ``page.psp``（不是常见的 ``page.htm``），
而且相当一部分教师直接链到校级教师主页系统。第一版规则只认 ``/info/``、``page.htm``、
``c\\d+a\\d+`` 三种形态，结果在这页上返回 **0 行**——不是页面没有名录，是规则漏了形态。
判断"页面是否列人"时，**先看链接形态，再下结论**。

口径说明：

* ``department`` 记为「冶金学院」这一级：该页不按系分组，只在页内按职称/拼音排列。
* 名录不列个人研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "neu_metallurgy",
    "code": "0806",
    "institution": "东北大学",
    "department": "冶金学院",
    "discipline": "冶金工程",
    # 师资队伍 → 教师名录。静态单页，无分页。
    "listing": "https://www.som.neu.edu.cn/10570/list.htm",
    "max_pages": 1,
},)

# 详情页链接的两种形态：WebPlus 文章页（.psp/.htm）与校教师主页系统。
PERSON_HREF = re.compile(r"c\d+a\d+/page\.(?:psp|htm)|faculty\.neu\.edu\.cn/")
# 行政/非教学单位（合同第 5 条）；本页不会命中，保留作防御。
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
# 职称词，兜底防止职称串进方向字段（合同红线 2）。
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
# 栏目文字（不是人名）。链接规则已经过滤掉导航，这里只作一道保险。
_NAV = re.compile(r"首页|学院|学校|师资|队伍|名录|概况|人才|联系|导航|公告|招生|就业|科研|"
                  r"党建|领导|内网|校友|组织|行政|教务|研究生|本科|工会|团委|医院|全体|"
                  r"研究所|中心|院士|信息|查询|教授|研究员|讲师|实验师|团队|平台|实验|"
                  r"下载|名单|诚聘|培养|学位|学科|机构|简介|沿革|治学|设置|建设|流动")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", anchor.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name) or name in seen or _NAV.search(name):
            continue
        seen.add(name)
        homepage = urljoin(url, href)
        note = (f"冶金学院「师资队伍 → 教师名录」名单（所属：{spec['department']}）；"
                f"名录只列姓名与个人页链接，未列职称与个人研究方向，也未按系分组。"
                f"导师资格与招生方向以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, homepage, url, "学院教师名录", note,
        ))
    return rows
