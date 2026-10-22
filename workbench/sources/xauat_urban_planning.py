"""西安建筑科技大学 建筑学院 城乡规划学系 师资名录（0833 城乡规划学）.

入口是学院官网「人物 → 师资队伍 → 城乡规划学系」::

    https://arch.xauat.edu.cn/rw/szdw/cxghxx.htm     ← 默认页，12 人
    https://arch.xauat.edu.cn/rw/szdw/cxghxx/1.htm   ← 3 人
    https://arch.xauat.edu.cn/rw/szdw/cxghxx/2.htm   ← 12 人
    https://arch.xauat.edu.cn/rw/szdw/cxghxx/3.htm   ← 12 人
    https://arch.xauat.edu.cn/rw/szdw/cxghxx/4.htm   ← 12 人
    https://arch.xauat.edu.cn/rw/szdw/cxghxx/5.htm   ← 12 人

站点分页是**倒序**的：默认页在页码条上标成最后一页，``/1.htm`` 反而是末页
（只有 3 人）。六个地址都是静态 HTML，普通 GET 即可拿全，不依赖脚本或接口；
合计 **63 个条目 / 63 个互不相同的姓名与个人页**。

人员容器结构（每个 ``div.list`` 内 12 条）::

    <div class="lists">
      <div class="list style">
        <a class="item" href="../../info/1401/26301.htm">
          <div class="mz">雷振东</div>          ← 姓名
          <div class="yx">教授</div>            ← 职称
          <div class="zc">硕士、博士生导师</div> ← 导师资格（不采集）
        </a>
        … 12 条 …
      </div>
    </div>

为什么是 59 条而不是 63 条
--------------------------

该系名录的 63 个条目按职称分为：教授 15、副教授 25、准聘副教授 3、讲师 16、
工程师 4。本模块只收**教学科研岗**（前四类，59 人）；4 名「工程师」属于工程/
实验技术岗，未纳入，属明确的收录范围，不代表该系只有 59 人。若以后要收工程
系列，另加一个来源即可，不需要改本模块。

0833 现状：63 条，同济大学 62 条（98.4%）、清华大学 1 条。本模块 59 条后：
总量 122，同济大学 62/122 = 50.8%，西安建筑科技大学 59/122 = 48.4%，最大机构
50.8% < 60%；59 也在「至少 41、至多 62」的区间内，不会让新来源变成新的独大机构。

口径说明
--------

* 名录按**职称**分组，不列个人研究方向，因此每行 ``direction`` 一律
  :data:`NO_DIRECTION`（``方向待补``）；「教授/副教授/讲师」是职称，只写进
  来源说明，绝不当作方向（红线 2）。
* 姓名取自 ``div.mz``，正常是纯姓名；解析仍按红线 1 剥掉可能的职称后缀并用
  ``NAME_RE`` 全匹配兜底。拉丁字母姓名**显式跳过并计数**，不音译、不截断。
* 容器守卫：每个 ``div.list`` 里的 ``a.item`` 条目数必须等于「解析行数 +
  非中文姓名跳过数 + 工程师系列范围排除数」；对不上就抛错（红线 4），
  不返回残缺名单。
* 联系方式（红线 3）：页面页脚有学院座机、传真与邮箱。落盘的五份快照在写入前
  已把座机/传真整段号码与邮箱替换为「联系方式已隐去」，落盘后 EMAIL / PHONE
  两条正则均无残留；解析器只读 ``div.list`` 里的姓名、职称与 href，从不读取
  页脚，也不读取 ``div.zc``（导师资格不是方向）。
* ``homepage`` 取每条卡片的 ``a.item[href]``：学院个人页
  （``arch.xauat.edu.cn/info/1401/<id>.htm``）或教师个人主页
  （``faculty.xauat.edu.cn/<id>/zh_CN/index.htm``）。指回栏目页/列表页的链接
  会被拒绝，不会把整份名录当成同一个人的主页。
* ``department`` 记为「建筑学院 城乡规划学系」：这是学院官网给出的系级单位，
  比「建筑学院」更细，且该页只列城乡规划学系教师（不混建筑学系/风景园林系）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://arch.xauat.edu.cn/rw/szdw/cxghxx"
_DEPARTMENT = "建筑学院 城乡规划学系"

# 一页一个 key：collect() 对不含 {page} 的 listing 只读一次，所以六页各登记一条。
SPECS = (
    {
        "key": "xauat_up_1",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}.htm",
        "max_pages": 1,
    },
    {
        "key": "xauat_up_2",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}/1.htm",
        "max_pages": 1,
    },
    {
        "key": "xauat_up_3",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}/2.htm",
        "max_pages": 1,
    },
    {
        "key": "xauat_up_4",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}/3.htm",
        "max_pages": 1,
    },
    {
        "key": "xauat_up_5",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}/4.htm",
        "max_pages": 1,
    },
    {
        "key": "xauat_up_6",
        "code": "0833",
        "institution": "西安建筑科技大学",
        "department": _DEPARTMENT,
        "discipline": "城乡规划学",
        "listing": f"{_BASE}/5.htm",
        "max_pages": 1,
    },
)

# 人员容器：导航、A-Z 字母索引与页脚都在 div.lists 外面。
CONTAINER = "div.lists"
ENTRY = "div.list a.item[href]"
NAME_FIELD = "div.mz"
RANK_FIELD = "div.yx"
ADVISOR_FIELD = "div.zc"

# 教学科研岗（收录）与工程/实验技术岗（范围排除）。长词在前，避免
# 「准聘副教授」被当成「副教授」。
TEACHING_RANKS = (
    "准聘副教授", "助理教授", "副教授", "教授",
    "副研究员", "助理研究员", "研究员", "讲师",
)
SUPPORT_RANKS = ("高级工程师", "工程师", "实验师", "助理工程师")

# 姓名后可能粘连职称后缀；剥掉后再用 NAME_RE 校验。
_TITLE_SUFFIX = re.compile(
    r"(?:博士生导师|硕士生导师|助理研究员|副研究员|准聘副教授|助理教授|"
    r"副教授|教授|研究员|讲师|院士|高工|博士后)+$"
)
# 剥完仍含职称字样，说明结构变了，不能当人名收下。
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师")
_LATIN = re.compile(r"[A-Za-z]")
# 容器里若出现这些栏目词，说明分页/导航被并进了名录，直接抛错而不是当人名。
_NAV_NOISE = frozenset({
    "首页", "上页", "下页", "上一页", "下一页", "尾页", "末页",
    "师资队伍", "城乡规划学系", "建筑学院", "教师主页", "知名校友", "诚聘英才",
})

# 个人详情页：学院个人页或教师个人主页；名录页/栏目页一律拒绝。
PERSON_HREF = re.compile(
    r"^(?:https://arch\.xauat\.edu\.cn/info/1401/\d+\.htm|"
    r"https://faculty\.xauat\.edu\.cn/[A-Za-z0-9_.-]+/zh_CN/index\.htm)$"
)

# 拉丁字母姓名：不音译、不截断，显式跳过并计数。本批 63 个条目全是汉字姓名，
# 故登记集合为空；若将来出现外籍教师，应把其原名登记到这里。
SKIPPED_NON_CJK: frozenset[str] = frozenset()


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _rank(card) -> str:
    """Return the card's 职称, checking the main field then the fallback field.

    Two cards on the site have an empty ``div.yx`` and put 讲师 in ``div.zc``;
    professors use ``div.zc`` for 导师资格, which is **not** a rank.
    """
    for selector in (RANK_FIELD, ADVISOR_FIELD):
        node = card.select_one(selector)
        if node is None:
            continue
        text = _norm(node.get_text(" ", strip=True))
        if not text:
            continue
        for rank in TEACHING_RANKS + SUPPORT_RANKS:
            if text == rank or text.startswith(rank):
                return rank
    return ""


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one page of the XAUAT 城乡规划学系 directory into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    boxes = soup.select(CONTAINER)
    if not boxes:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = []
    for box in boxes:
        entries.extend(box.select(ENTRY))

    rows: list[dict] = []
    seen_names: set[str] = set()
    seen_pages: set[str] = set()
    skipped_non_cjk: list[str] = []
    skipped_support: list[str] = []

    for card in entries:
        href = (card.get("href") or "").strip()
        if not href:
            raise ValueError(f"城乡规划学系条目缺少链接：{url}")
        homepage = urljoin(url, href)
        if not PERSON_HREF.fullmatch(homepage):
            raise ValueError(f"条目的链接不是个人详情页：{homepage!r}（{url}）")

        name_node = card.select_one(NAME_FIELD)
        if name_node is None:
            raise ValueError(f"城乡规划学系条目缺少姓名：{url}")
        name = _norm(name_node.get_text(" ", strip=True))
        if not name:
            raise ValueError(f"城乡规划学系条目姓名为空：{url}")
        name = _TITLE_SUFFIX.sub("", name)

        if _LATIN.search(name):
            # 非中文姓名：不音译、不截断，显式跳过并计数（红线 1）。
            skipped_non_cjk.append(name)
            continue

        if name in _NAV_NOISE:
            raise ValueError(f"城乡规划学系名录容器里出现导航词：{name!r}（{url}）")
        if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
            raise ValueError(f"城乡规划学系名录出现无法识别为姓名的条目：{name!r}（{url}）")

        if name in seen_names or homepage in seen_pages:
            raise ValueError(f"同一页出现重复教师：{name!r}（{url}）")
        seen_names.add(name)
        seen_pages.add(homepage)

        rank = _rank(card)
        if rank in SUPPORT_RANKS:
            # 工程/实验技术岗：本来源只收教学科研岗，显式计数而不是静默丢弃。
            skipped_support.append(name)
            continue
        if rank not in TEACHING_RANKS:
            raise ValueError(
                f"城乡规划学系条目缺少可识别的职称：{name!r}（{url}）"
            )

        note = (
            "西安建筑科技大学建筑学院城乡规划学系「人物 → 师资队伍 → "
            f"城乡规划学系」名录，按职称分组公布（职称：{rank}）。"
            "名录只列姓名与职称，未列个人研究方向，故方向字段为“方向待补”，"
            "职称只写进来源说明、不作为研究方向。本模块只收教学科研岗"
            "（教授/副教授/准聘副教授/讲师），不含工程师系列（工程/实验技术岗）；"
            "导师资格与招生专业以当年招生公告为准。"
        )
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, homepage, url, "学院师资队伍（城乡规划学系）", note,
        ))

    # 红线 4：核对「容器内恰好 N 人」——条目数必须等于解析出的姓名数加两类
    # 显式跳过数（非中文姓名、工程系列）。否则说明有真人被静默漏掉，直接抛错。
    accounted = len(rows) + len(skipped_non_cjk) + len(skipped_support)
    if len(entries) != accounted:
        raise ValueError(
            f"城乡规划学系名录解析不完整：容器内 {len(entries)} 个条目，"
            f"解析出 {len(rows)} 条、非中文姓名跳过 {len(skipped_non_cjk)} 条、"
            f"工程师系列排除 {len(skipped_support)} 条（{url}）。请检查页面结构。"
        )
    return rows
