"""上海理工大学 健康科学与工程学院 生物医学工程学科导师名录（0831 生物医学工程）.

上海理工大学以医疗器械与生物医学工程为传统优势方向：健康科学与工程学院（原医疗
器械与食品学院）设有生物医学工程系、医学人工智能系、康复工程与技术系等教学科研
单位。学院官网「导师信息 → 生物医学工程」栏目按**学科**公布本学科的研究生导师名录::

    https://jiankang.usst.edu.cn/18088/list1.htm   ← 第 1 页
    https://jiankang.usst.edu.cn/18088/list2.htm   ← 第 2 页 … 第 7 页

页面由服务端直接渲染（WebPlus 静态列表，普通 GET 即可拿全，不依赖脚本或接口），
自报「总共 93 记录 / 每页 14 记录 / 页码 1/7」，``list1.htm`` 与首页 ``list.htm``
内容一致，故 ``listing`` 用 ``list{page}.htm`` 模板、``max_pages`` 取 7。人员容器结构:

    div.col_news_list                         ← 名录容器（导航、分页都在它外面）
      ul.news_list.list2
        li.news                               ← 一条导师记录
          a.news_wz[href]                     ← 个人详情页 /<年>/<月日>/c<栏>a<id>/page.htm
            div.news_title                    ← 纯姓名
            div.news_meta                     ← 发布日期，不是人名

实测 2026-10-22：第 1 页 14 条、第 2–6 页各 14 条、第 7 页 9 条，合计 **93 条**
（93 个互不相同的姓名，页面自报的 93 条对得上）。

为什么只收 92 条（少的那 1 条）
-------------------------------

总第 26 条（第 2 页第 12 条）是一位外籍导师，姓名是拉丁字母（名 + 中名 + 姓），
既不在 ``NAME_RE``（2–8 个汉字/间隔号）的范围内，也不该被截断或音译成臆造的中文名，
因此**明确跳过**并在 :data:`SKIPPED_NON_CJK` 里登记。解析器对容器内条目做核对：
「条目数 = 解析出的姓名数 + 登记跳过的非汉字姓名数」，任何其他无法通过 ``NAME_RE``
的条目都会抛错，而不是静默少收人（红线 4）。

为什么可以作为 0831 的新增机构
-----------------------------

0831 原本只有上海交通大学（47 条，60.3%）与大连理工大学（31 条）两所；本模块
新增第三所高校 **上海理工大学** 92 条。按补后 78+92=170 条计算，上海交通大学
47/170=27.6%，最大机构变为上海理工大学 92/170=54.1%，低于 60% 的集中度上限；
且上海理工大学此前在 0831 中没有任何记录，不是被主导校（上海交通大学）。

口径说明
--------

* 名录按**发布时间**倒序列出导师，不按职称分组，也不列个人研究方向，因此每行
  ``direction`` 一律 :data:`NO_DIRECTION`（``方向待补``）；页面没有给出的信息
  不臆造（红线 2）。
* ``department`` 记为「健康科学与工程学院」：页面按**学科**（生物医学工程）组织，
  没有给出更细的系/所归属，学院这一级是页面能给的、也是可核实的最细教学科研单位；
  不写成某个系，避免把跨系的导师硬塞进一个系。
* ``homepage`` 取姓名锚点的 href，即该导师的个人详情页（形如
  ``https://jiankang.usst.edu.cn/2026/0608/c18088a363826/page.htm``），不是名录页。
  实测详情页标题就是姓名，页内有职称、导师资格、学科专业与联系方式；本模块只取
  列表页上的姓名与 href，**从不读取详情页**，更不把邮箱、电话写进任何字段（红线 3）。
* 名录页页脚与版权栏各有一处学院总机（``0xx-xxxxxxxx`` 形式），落盘快照前已按项目
  规则连同邮箱一起替换为「联系方式已隐去」；7 页共 14 处，落盘后 EMAIL / PHONE
  两条正则均无残留。
* 本来源覆盖的是「生物医学工程」学科的导师名录，**不代表学院全部教师**（学院另设
  「教师名录」并按系部筛选，属另一个来源的取数口径）；导师资格与招生专业以当年
  招生公告为准。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# 单页列表模板；第 1 页是 list1.htm（与 list.htm 同内容），故统一用 {page}。
LISTING = "https://jiankang.usst.edu.cn/18088/list{page}.htm"

SPECS = ({
    "key": "usst_bme",
    "code": "0831",
    "institution": "上海理工大学",
    "department": "健康科学与工程学院",
    "discipline": "生物医学工程",
    "listing": LISTING,
    "max_pages": 7,
},)

# 人员容器：只有它里面的条目是导师；导航、面包屑与分页都在容器外。
ROSTER_BOX = "div.col_news_list"
ROSTER = "ul.news_list li.news"
NAME_BOX = "div.news_title"
LINK = "a.news_wz[href]"

# 页面自报的条目数（93）与能落库的姓名数（92）：差 1 条是下面登记的外籍导师。
PUBLISHED_ENTRIES = 93
EXPECTED_ROSTER = 92
EXPECTED_PER_PAGE = (14, 13, 14, 14, 14, 14, 9)

# 总第 26 条（第 2 页第 12 条）：拉丁字母姓名，无法通过 NAME_RE；明确跳过，不做音译或截断。
# 这里按解析时的「去空白」形式登记，避免空格写法变化后漏判。
SKIPPED_NON_CJK = frozenset({"GaneshKumarJaganathan"})

# 红线 1 的兜底：万一锚文本是「姓名+职称」拼接，剥掉后缀再校验。长词优先，
# 否则「副研究员」会被「研究员」剥成「副」。
_TITLE_SUFFIX = re.compile(r"(?:副教授|助理教授|副研究员|研究员|教授|讲师|院士|高工|博士后)$")
# 剥完后仍含职称字样，说明不是「姓名+后缀」而是结构变了，直接报错。
_RANK = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one page of the USST BME supervisor directory into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    boxes = soup.select(ROSTER_BOX)
    if not boxes:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = []
    for box in boxes:
        entries.extend(box.select(f"{ROSTER} {LINK}"))

    rows: list[dict] = []
    seen: set[str] = set()
    skipped = 0
    for anchor in entries:
        title = anchor.select_one(NAME_BOX)
        name = _norm(title.get_text(" ", strip=True)) if title else ""
        href = (anchor.get("href") or "").strip()
        if not name or not href:
            raise ValueError(f"导师名录条目缺少姓名或详情页链接：{url}")

        name = _TITLE_SUFFIX.sub("", name)
        if name in SKIPPED_NON_CJK:
            skipped += 1
            continue
        if not NAME_RE.fullmatch(name) or _RANK.search(name):
            raise ValueError(f"导师名录出现无法识别为姓名的条目：{name!r}（{url}）")
        if name in seen:
            raise ValueError(f"导师名录同一页出现重复姓名：{name!r}（{url}）")
        seen.add(name)
        note = ("上海理工大学健康科学与工程学院「导师信息 → 生物医学工程」名录；"
                "该名录按发布时间列本学科研究生导师，不列个人研究方向与职称，"
                "故方向字段为“方向待补”，职称不写入方向。本来源只覆盖该学科导师名录，"
                "不代表学院全部教师；导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, urljoin(url, href), url, "学院导师信息名录", note,
        ))

    # 红线 4：核对「容器内恰好 N 人」——条目数必须等于解析出的姓名数加登记跳过的
    # 非汉字姓名数；否则说明有真人被静默漏掉，直接抛错而不是返回残名单。
    if len(entries) != len(rows) + skipped:
        raise ValueError(
            f"生物医学工程导师名录解析不完整：容器内 {len(entries)} 个条目，"
            f"解析出 {len(rows)} 条、跳过 {skipped} 条（{url}）。请检查页面结构。")
    return rows
