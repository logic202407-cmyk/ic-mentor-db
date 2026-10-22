"""中山大学软件工程学院 师资队伍（0835 软件工程）.

学院官网「师资队伍」页（``/teacher``）是一张服务端渲染的静态页，把全院教师按职称
分组一次性列出。每张卡片是一个 ``div.list-images-1-1``::

    <div class="list-images-1-1 inside-tb">
      <div class="list-left t-c inside-b ...">
        <a href="/teacher/100"><img src="…"></a>          ← 头像，也指向本人详情页
      </div>
      <div class="list-content">
        <h4 class="list-title one-line">
          <strong>郑子彬 </strong>                         ← 姓名（只取 strong）
          <span class="text-light">教授</span>             ← 职称（不在 strong 里）
        </h4>
        <div class="list-text inside-tb">
          <p class="three-line text-light"><strong>现任职务：</strong><span>院长</span></p>
          <p class="two-line text-light"><strong>研究方向：</strong>软件可靠性，…</p>
        </div>
        <div class="list-bottom clearfix">
          <div class="list-more outside-r">
            <a href="/teacher/100" target="_blank">了解更多</a>   ← 本人详情页
          </div>
        </div>
      </div>
    </div>

**姓名与职称在 DOM 里是分开的**：``strong`` 只含姓名，职称在同级兄弟节点
``span.text-light`` 里，所以姓名天然不带职称；模块另留一层 :data:`TITLE_SUFFIX`
兜底——万一哪张卡片把「张三教授」写进 ``strong``，先剥后缀再用 ``NAME_RE`` 校验。

**一页就是全集**：``/teacher`` 上共 48 张卡片。按职称分的五个子页
（``/teacher/professor`` 11、``/teacher/associate_professor`` 19、
``/teacher/assistant_professor`` 1、``/teacher/lecturer`` 2、
``/teacher/researcher`` 7）合计正好 40 人，与合并页里的 40 张专任教师卡片一一对应，
说明合并页没有截断，故 ``max_pages`` 取 1，``listing`` 里也没有 ``{page}`` 占位符。

**收录范围**：只收专任教师序列的五个职称分组（教授／副教授／助理教授／讲师·教员／
研究员·副研究员），共 40 人；``外聘教授``（1）、``校外导师``（4）、``荣休教师``（3）
不是本院在编专任教师，不收录（与合同第 5 条同一标准：非教学岗位不入库）。
48 = 40 + 1 + 4 + 3，全部卡片都被归类，没有静默丢弃。

**口径说明**：

* 页面其实写了「研究方向」，但按项目红线 2，``direction`` 一律
  :data:`NO_DIRECTION`，页面文字绝不进方向字段。
* 页面写了 Email 并带 ``mailto:`` 链接；本模块只读 ``h4`` 与 ``/teacher/<id>``
  链接，任何联系方式都不进 row。快照（fixture）落盘前把 6 处邮箱锚整体替换成
  「联系方式已隐去」；该页没有电话。
* 姓名带「（双聘）」标记的 4 人（武汇岳、徐宇、林淑金、陈湘萍）是学院公示的双聘
  教师：剥掉标记保留姓名，双聘事实写进备注，既不丢人，也不把他们说成全职。
* 唯一的非汉字姓名 ``C.K.MichaelTse``（校外导师）不符合 ``NAME_RE``，显式跳过并
  计数（:func:`scan` 的 ``non_cjk``），宁缺勿猜。
* 每人 ``homepage`` 都指向本人的 ``/teacher/<id>`` 详情页（头像与「了解更多」同址）；
  找不到详情页链接的卡片不产出 row，绝不拿名录页顶替。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "sysu_software",
    "code": "0835",
    "institution": "中山大学",
    "department": "软件工程学院",
    "discipline": "软件工程",
    # 师资队伍 → 全部职称分组；全院专任教师在这张静态页上一次列全，无分页。
    "listing": "https://sse.sysu.edu.cn/teacher",
    "max_pages": 1,
},)

# 名录容器：一张卡片一位教师；导航与页脚都在它外面。
CARD = "div.list-images-1-1"
# 卡片内的姓名/职称容器。
TITLE = "h4.list-title"
RANK_NODE = "span.text-light"
# 详情页链接：「了解更多」优先，头像链接同址，作为兜底。
DETAIL_LINK = "div.list-more a[href]"
AVATAR_LINK = "div.list-left a[href]"
# 个人详情页形态：/teacher/<数字>。这条规则本身就能排除导航与 mailto:。
PERSON_PAGE = re.compile(r"/teacher/\d+/?")

# 专任教师序列的五个职称分组，逐字取自页面。
TEACHING_RANKS = frozenset({
    "教授", "副教授", "助理教授", "讲师/教员", "研究员/副研究员",
})
# 页面上的非教学分组：不是本院在编专任教师，不收录。
NON_TEACHING_RANKS = frozenset({
    "外聘教授", "校外导师", "荣休教师", "院外研究生导师",
})
# 「（双聘）」这类任职标记，是任职方式而不是姓名的一部分。
APPOINTMENT_MARK = re.compile(r"[（(](?:双聘|兼|兼职|院聘)[）)]$")
# 防御性职称后缀：页面把姓名与职称分开渲染，本不该命中；命中则剥掉再校验。
TITLE_SUFFIX = re.compile(
    r"(?:特聘教授|讲座教授|助理教授|副教授|教授|副研究员|研究员|"
    r"高级工程师|高工|讲师|助教|院士)$"
)


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格（“张 三”）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def _clean_name(raw: str) -> str:
    """把卡片标题里的姓名取出来：去空白 → 去任职标记 → 去职称后缀。"""
    text = re.sub(r"[\s\u3000\xa0]+", "", raw or "")
    text = APPOINTMENT_MARK.sub("", text)
    return TITLE_SUFFIX.sub("", text)


def scan(html: str, url: str, spec: dict) -> tuple[list[dict], dict]:
    """解析一页名录，返回 ``(rows, stats)``。

    ``stats`` 是给人看的核对账本，不进入语料：卡片总数、被排除的职称分组、
    非汉字姓名、缺详情页的卡片。它让「48 张卡片 = 40 行 + 8 张非教学卡片」
    可以被重新算一遍，而不是只能相信解析器的沉默。
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    stats: dict = {
        "cards": 0,
        "rows": 0,
        "non_cjk": [],
        "excluded_rank": {},
        "unknown_rank": [],
        "no_detail": [],
    }

    cards = soup.select(CARD)
    stats["cards"] = len(cards)
    for card in cards:
        head = card.select_one(TITLE)
        if head is None:
            stats["unknown_rank"].append(("<no h4.list-title>", ""))
            continue
        strong = head.find("strong")
        raw_name = _compact(strong) if strong is not None else _compact(head)
        rank_node = head.select_one(RANK_NODE)
        rank = _compact(rank_node) if rank_node is not None else ""
        name = _clean_name(raw_name)

        if not NAME_RE.fullmatch(name):
            # 非汉字姓名无法可靠核对身份，宁缺勿猜。
            stats["non_cjk"].append(raw_name)
            continue
        if rank in NON_TEACHING_RANKS:
            stats["excluded_rank"][rank] = stats["excluded_rank"].get(rank, 0) + 1
            continue
        if rank not in TEACHING_RANKS:
            # 页面若新增了未识别分组，先不入库，等人工确认，不猜。
            stats["unknown_rank"].append((name, rank))
            continue

        anchor = card.select_one(DETAIL_LINK) or card.select_one(AVATAR_LINK)
        href = (anchor.get("href") or "").strip() if anchor is not None else ""
        absolute = urljoin(url, href) if href else url
        # 红线 5：homepage 必须是本人详情页，不能拿名录页顶替。
        if not PERSON_PAGE.search(absolute) or urlparse(absolute).scheme not in (
                "http", "https"):
            stats["no_detail"].append(name)
            continue
        if name in seen:
            continue
        seen.add(name)

        dual = "（双聘）" in raw_name
        note = ("中山大学软件工程学院「师资队伍」页按职称分组公布"
                f"（职称：{rank}）；该页同时列出研究方向与联系方式，"
                f"按项目口径研究方向不入库、联系方式已隐去。"
                + ("该教师为学院公示的双聘教师。" if dual else "")
                + "本来源覆盖该页五个专任教师职称分组，不含外聘教授、"
                  "校外导师与荣休教师；导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, absolute, url, "学院师资队伍（按职称）", note,
        ))

    stats["rows"] = len(rows)
    return rows, stats


def parse(html: str, url: str, spec: dict) -> list[dict]:
    rows, _ = scan(html, url, spec)
    return rows
