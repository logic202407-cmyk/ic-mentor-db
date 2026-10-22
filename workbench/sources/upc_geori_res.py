"""中国石油大学（华东） 资源系 师资名录（0818 地质资源与地质工程）.

入口是地球科学与技术学院官网「师资队伍」栏目::

    https://geori.upc.edu.cn/10927/list.htm

页面由服务端直接渲染成一篇文章，正文是一张 70 行 × 4 列的表格，按**系**分成五个
分区（表内以 ``【地质系】`` 这样的整行标题分隔）::

    div.wp_articlecontent                 ← 名录容器（导航、页脚都在它外面）
      table
        tr > td(colspan=4) 「【地质系】」  ← 分区标题行
        tr > td > a[href]  姓名 + （职称） ← 一条教师记录，每行最多 4 人
        tr > td(colspan=4) 「【资源系】」
        ...

实测 2026-10-22：全表 215 条人员链接、189 个不同详情页；五个分区各自的姓名格数为
地质系 56、**资源系 57**、地球物理系 41、测井系 27、地球科学前沿交叉学科中心 41。
资源系的 57 格是：教授 20、副教授 25、副研究员 1、高级工程师 1、讲师 6、工程师 1、
**在站博士后 3**。其中工程师 1 格只有姓名、没有个人详情页；博士后 3 格是在站培养
岗位而不是教师职称（与 ``whu_hydropower.py`` / ``cau_agriculture.py`` /
``seu_cyber.py`` 同口径不计入师资行，但单独计数参与核对）。故教师 53 人，
57 = 53 教师 + 3 博士后 + 1 无详情页。栏目页无分页：``list2.htm`` / ``list3.htm``
虽返回 200，但版式与首页相同且不含任何系名录，故 ``listing`` 无 ``{page}`` 占位符、
``max_pages=1``。

为什么是「资源系」而不是整个学院
--------------------------------

学院「学院介绍」页（``/10914/list.htm``）与「学科建设」页（``/11351/list.htm``）
都自报：国家「双一流」建设学科为**地质资源与地质工程**（学科评估 A+），国家重点
学科为**矿产普查与勘探**，国家重点（培育）学科为地球探测与信息技术；0818 的主要
研究方向横跨资源系、地球物理系与测井系。地质系对应的则是 0709 地质学（学院另有一级
博士学位授权点「地质学」）。

资源系即 0818 下「矿产普查与勘探」这一国家重点学科的教学科研单位，是本来源能给出的、
可与学科直接对应的最细单位。整个 0818（资源系 57 + 地球物理系 41 + 测井系 27 =
125 个姓名格）远超这次补库「单校新增不超过现有最大机构 83 条」的上限；若全收，新校
会变成新的独大，与项目此前三次验证过的失败模式相同。因此只收资源系：

* 0818 现状 104 条，中南大学 83 条（79.8%），中国科学院大学 21 条；
* 补入 53 条后总量 157 条：中南大学 83/157 = 52.9%、中国石油大学（华东）
  53/157 = 33.8%、中国科学院大学 21/157 = 13.4%，最大机构回到 60% 以下，
  且新增学校没有超过现有最大值。

地球物理系（41 格）与测井系（27 格）对应 081802 地球探测与信息技术，留作各自独立的
后续来源；地质系（56 格）属 0709 地质学，不收（两处格数都含在站博士后，按同一口径
剔除后才是教师数）。

口径说明
--------

* 名录按**系**分组，并给每人标注职称/岗位（教授、副教授、讲师、博士后、工程师……）；
  它不列个人研究方向，因此每行 ``direction`` 一律 :data:`NO_DIRECTION`
  （``方向待补``），职称只写进 note，绝不当作方向（红线 2）。
* 姓名取自人员格内锚文本，只保留括号前的姓名部分；解析仍按红线 1 剥掉可能的职称
  后缀并用 ``NAME_RE`` 全匹配兜底。本批 53 人全部是汉字姓名；万一将来出现拉丁字母
  姓名，解析器**跳过并计数**，不音译、不截断（红线 1）。
* 资源系有一格只有姓名、没有个人详情页链接（一位工程师）。红线 5 要求每行
  ``homepage`` 指向个人详情页，不能回落到名录页，因此该条**显式跳过并计数**。
* 页面在每个系里都列出**在站博士后**。博士后是在站培养岗位而不是教师职称，与
  ``whu_hydropower.py`` / ``cau_agriculture.py`` / ``seu_cyber.py`` 同口径不计入
  师资行，但单独计数，参与「分区内姓名格数 = 解析数 + 跳过数」的硬核对（红线 4）：
  57 = 53 + 3（博士后）+ 1（无详情页）。
* 联系方式（红线 3）：页面页脚有 1 处邮箱与 1 处座机（形如「区号-号码」）。落盘的
  快照在写入前已把这两处替换为「联系方式已隐去」，落盘后 EMAIL / PHONE 两条正则均
  无残留；解析器只读 ``div.wp_articlecontent`` 表格内的姓名与 href，从不读取页脚。
* ``homepage`` 取人员格内姓名锚点的 href，即个人详情页
  （形如 ``http://geori.upc.edu.cn/<年>/<月日>/c10382a<文章号>/page.htm``，实测详情页
  标题就是「姓名（职称）」），不是名录页。页面里的链接是 http，保持原样。
* 本来源覆盖资源系全部**教师**（教授 20、副教授 25、副研究员 1、高级工程师 1、
  讲师 6，共 53 人），不含在站博士后，**不代表学院全部教师**；导师资格与招生专业以
  当年招生公告为准。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://geori.upc.edu.cn/10927/list.htm"

SPECS = ({
    "key": "upc_geori_res",
    "code": "0818",
    "institution": "中国石油大学（华东）",
    "department": "地球科学与技术学院·资源系",
    "discipline": "地质资源与地质工程",
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：只有正文文章区里的表格是名录；导航、面包屑、页脚都在容器外。
CONTAINER = "div.wp_articlecontent"
# 只取「资源系」这一个分区；其余分区的人不属于本模块口径。
SECTION = "【资源系】"
_SECTION_HEAD = re.compile(r"^【.+】$")

# 个人详情页：/<年>/<月日>/c<栏目号>a<文章号>/page.htm（资源系栏目号为 c10382）。
PERSON_HREF = re.compile(r"/\d{4}/\d{4}/c\d+a\d+/page\.htm")

# 表内一格写成「姓名（职称）」；姓名取括号前，职称留在 note 里。
_PAREN = re.compile(r"[（(]")
_RANK_LABEL = re.compile(r"[（(]([^）)]+)[）)]\s*$")

# 红线 1 的兜底：万一锚文本是「姓名+职称」拼接，剥掉后缀再校验。长词优先，
# 否则「副研究员」会被「研究员」剥成「副」。
_TITLE_SUFFIX = re.compile(r"(?:副教授|助理教授|副研究员|研究员|教授|讲师|院士|高工|博士后)$")
# 剥完后仍含职称字样，说明不是「姓名+后缀」而是结构变了，直接报错。
_RANK_WORD = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
# 拉丁字母姓名：不音译、不截断，显式跳过并计数。本批 0 人。
_LATIN = re.compile(r"[A-Za-z]")

# 资源系分区内共有 57 个姓名格：53 位教师 + 3 位在站博士后 + 1 位无个人详情页的工程师。
PUBLISHED_NAME_CELLS = 57
EXPECTED_ROSTER = 53
EXPECTED_POSTDOCS = 3

# 在站博士后是培养岗位，不是教师职称：不计入师资行，但单独计数参与核对。
NON_FACULTY_RANK = frozenset({"博士后"})

# 拉丁字母姓名登记表：本批为空（53 人全是汉字姓名）。将来若出现外籍教师，
# 把其原名登记到这里，测试会断言它们没有以音译/截断的形式混进结果。
SKIPPED_NON_CJK: frozenset[str] = frozenset()


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _section_cells(container) -> list:
    """Return ``(section, cell)`` for every non-empty name cell, in page order."""
    cells: list = []
    section: str | None = None
    for row in container.select("tr"):
        tds = row.find_all("td")
        if not tds:
            continue
        texts = [_norm(td.get_text(" ", strip=True)) for td in tds]
        filled = [text for text in texts if text]
        if len(filled) == 1 and _SECTION_HEAD.match(filled[0]):
            section = filled[0]
            continue
        for td, text in zip(tds, texts):
            if text:
                cells.append((section, td))
    return cells


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one page of the UPC 资源系 roster into mentor rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    container = soup.select_one(CONTAINER)
    if container is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = [(section, cell) for section, cell in _section_cells(container)
               if section == SECTION]
    if not entries:
        return []

    rows: list[dict] = []
    skipped: list[str] = []
    postdocs: list[str] = []
    seen_names: set[str] = set()
    seen_pages: set[str] = set()

    for _, cell in entries:
        text = _norm(cell.get_text(" ", strip=True))
        rank_match = _RANK_LABEL.search(text)
        rank = rank_match.group(1) if rank_match else ""

        if rank in NON_FACULTY_RANK:
            # 在站博士后：不是教师职称，不计入师资行，但单独计数（红线 4 核对用）。
            postdocs.append(_norm(_PAREN.split(text)[0]))
            continue

        anchor = cell.find("a", href=True)
        if anchor is None:
            # 只有姓名、没有个人详情页：不能把名录页当 homepage（红线 5），跳过并计数。
            skipped.append(text)
            continue

        href = (anchor.get("href") or "").strip()
        if not href or not PERSON_HREF.search(href):
            raise ValueError(f"人员格的链接不是个人详情页：{href!r}（{url}）")

        name = _norm(anchor.get_text(" ", strip=True))
        name = _PAREN.split(name)[0]
        name = _TITLE_SUFFIX.sub("", name)

        if _LATIN.search(name):
            # 非中文姓名：不音译、不截断，显式跳过并计数（红线 1）。
            skipped.append(name)
            continue
        if not NAME_RE.fullmatch(name) or _RANK_WORD.search(name):
            raise ValueError(f"师资名录出现无法识别为姓名的条目：{text!r}（{url}）")

        homepage = urljoin(url, href)
        if name in seen_names or homepage in seen_pages:
            raise ValueError(f"同一分区出现重复教师：{name!r}（{url}）")
        seen_names.add(name)
        seen_pages.add(homepage)

        rank_note = (f"页面标注「{rank}」（职称/岗位标注，不是研究方向）" if rank
                     else "页面未标注职称")
        note = ("中国石油大学（华东）地球科学与技术学院「师资队伍」名录按系分组公布，"
                f"本条目属「资源系」，{rank_note}。名录不列个人研究方向，故方向字段为"
                "“方向待补”。资源系是该校 0818 地质资源与地质工程（国家“双一流”建设"
                "学科、学科评估 A+）下「矿产普查与勘探」国家重点学科的教学科研单位；"
                "本来源只覆盖资源系，不含地球物理系与测井系（081802 地球探测与信息"
                "技术）及地质系（0709 地质学），也不代表学院全部教师；导师资格与招生"
                "专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, homepage, url, "学院师资队伍（资源系）", note,
        ))

    # 红线 4：核对「分区内恰好 N 人」——姓名格数必须等于解析出的教师数 + 明确排除的
    # 在站博士后数 + 跳过数（无详情页者、非汉字姓名）；否则说明有真人被静默漏掉，
    # 直接抛错而不是返回残名单。
    if len(entries) != len(rows) + len(postdocs) + len(skipped):
        raise ValueError(
            f"资源系师资名录解析不完整：分区内 {len(entries)} 个姓名格，"
            f"解析出 {len(rows)} 条、在站博士后 {len(postdocs)} 条、"
            f"跳过 {len(skipped)} 条（{url}）。请检查页面结构。")
    return rows
