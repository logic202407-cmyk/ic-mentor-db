"""华南理工大学 食品科学与工程学院 教授 师资名录（0832 食品科学与工程）.

入口是学院官网「师资队伍 → 教师风采 → 教授」栏目::

    https://www2.scut.edu.cn/sp/js_39841/list.htm    ← 第 1 页（等价于 list1.htm）
    https://www2.scut.edu.cn/sp/js_39841/list2.htm   ← 第 2 页
    https://www2.scut.edu.cn/sp/js_39841/list3.htm   ← 第 3 页

页面由服务端直接渲染（WebPlus 静态列表，普通 GET 即可拿全，不依赖脚本或接口），
自报「每页 16 记录 / 总共 48 记录 / 页码 1/3」。人员容器结构::

    div.teacher-list                       ← 名录容器（导航与页脚都在它外面）
      div.teacher-item                     ← 一条教师记录（共 16 条/页）
        div.teacher-img > a[href]          ← 头像链接，指向同一个人详情页
        div.teacher-name > a[href]         ← 姓名锚点（纯姓名，title 也是姓名）
                                             href = /sp/<年>/<月日>/c39841a<id>/page.htm

实测 2026-10-22：第 1–3 页各 16 条，合计 **48 条**，48 个互不相同的姓名与 48 个互不
相同的个人详情页；``list1.htm`` 与 ``list.htm`` 内容一致，第 4 页存在但已无教师条目
（分页到第 3 页为止），故 ``listing`` 用 ``list{page}.htm`` 模板、``max_pages`` 取 3。

为什么只收「教授」这一职称序列（48 人）
--------------------------------------

学院「队伍概况」页（``/sp/dwgkw/list.htm``）自报教职工 122 人、专任教师 97 人、
正高 52 人，并按**系**列出全部教师名单；但该页的姓名是**纯文本**，没有任何个人详情页
链接，无法满足本项目「每条 ``homepage`` 指向个人详情页」的要求。能同时给出姓名与
个人详情页的是「教师风采」按职称分列的各页：教授 48、副教授 25、研究员 4、
副研究员 8、教授级高级工程师 4……全收会远超本次补库的规模上限。

0832 现有 83 条：中国农业科学院 59 条（71.1%）、上海交通大学 24 条（28.9%）。
只收教授 48 条后：总量 83+48=131，中国农业科学院 59/131=45.0%，
华南理工大学 48/131=36.6%，最大机构回到 60% 以下且不再由新增学校独大；
48 也在「单校新增不超过 51 条」的上限内。副教授、研究员、讲师与实验/工程系列
留作独立的后续来源，各自成模块即可，不需要改本模块。

口径说明
--------

* 名录按**职称**分组，不列个人研究方向，因此每行 ``direction`` 一律
  :data:`NO_DIRECTION`（``方向待补``）；「教授」是职称，只写进来源说明，
  绝不当作方向（红线 2）。
* 姓名锚点本身是纯姓名；解析仍按红线 1 剥掉可能的职称后缀并用 ``NAME_RE``
  全匹配兜底。目前 48 人全部是汉字姓名；万一将来出现拉丁字母姓名，解析器
  **跳过并计数**，不音译、不截断（红线 1），并用「容器内条目数 = 解析数 + 跳过数」
  硬核对（红线 4）。
* 联系方式（红线 3）：每页页脚各有一处「书记院长信箱」邮箱与一处学院办公室座机
  （形如 ``0xx-xxxxxxxx``）。落盘的三份快照在写入前已把邮箱与电话替换为
  「联系方式已隐去」，落盘后 EMAIL / PHONE 两条正则均无残留；解析器只读
  ``div.teacher-list`` 内的姓名与 href，从不读取页脚联系方式。
* ``department`` 记为「食品科学与工程学院」：教授页按**职称**组织，没有给出系/所
  归属；学院「队伍概况」页虽按系列出，但同一批人没有详情页链接。学院这一级是
  本来源能给的、也是可核实的最细教学科研单位，不把教授硬塞进某个系。
* ``homepage`` 取 ``div.teacher-name`` 里姓名锚点的 href，即个人详情页
  （形如 ``https://www2.scut.edu.cn/sp/2025/0709/c39841a596996/page.htm``，实测
  详情页标题就是姓名），不是名录页。
* 本来源覆盖的是学院「教授」职称序列，**不代表学院全部教师**；导师资格与招生
  专业以当年招生公告为准。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# 单页列表模板；第 1 页 list.htm 与 list1.htm 同内容，故统一用 {page}。
LISTING = "https://www2.scut.edu.cn/sp/js_39841/list{page}.htm"

SPECS = ({
    "key": "scut_food",
    "code": "0832",
    "institution": "华南理工大学",
    "department": "食品科学与工程学院",
    "discipline": "食品科学与工程",
    "listing": LISTING,
    "max_pages": 3,
},)

# 人员容器：只有 div.teacher-list 里的是教师；导航、面包屑、页脚都在容器外。
CONTAINER = "div.teacher-list"
ITEM = "div.teacher-item"
NAME_LINK = "div.teacher-name a[href]"

# 个人详情页：/sp/<年>/<月日>/c39841a<文章>/page.htm（c39841 = 师资队伍·教授栏目）。
PERSON_HREF = re.compile(r"/sp/\d{4}/\d{4}/c39841a\d+/page\.htm")

# 页面自报：每页 16 条，共 48 条，3 页。
PUBLISHED_PER_PAGE = 16
PUBLISHED_ENTRIES = 48

# 实测：2026-10-22 三页各 16 人，合计 48 人。
EXPECTED_ROSTER = 48
EXPECTED_PER_PAGE = (16, 16, 16)

# 拉丁字母姓名：不音译、不截断，显式跳过并计数。本批 48 人全是汉字姓名，
# 故登记集合为空；若将来页面上出现外籍教师，应把其原名登记到这里。
SKIPPED_NON_CJK: frozenset[str] = frozenset()

# 红线 1 的兜底：万一锚文本是「姓名+职称」拼接，剥掉后缀再校验。长词优先，
# 否则「副研究员」会被「研究员」剥成「副」。
_TITLE_SUFFIX = re.compile(r"(?:副教授|助理教授|副研究员|研究员|教授|讲师|院士|高工|博士后)$")
# 剥完后仍含职称字样，说明不是「姓名+后缀」而是结构变了，直接报错。
_RANK = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
# 拉丁字母（允许空格、点、连字符、撇号）；用于识别并跳过非中文姓名。
_LATIN = re.compile(r"[A-Za-z][A-Za-z .'\-]*")


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one page of the SCUT food 教授 directory into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    boxes = soup.select(CONTAINER)
    if not boxes:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = []
    for box in boxes:
        entries.extend(box.select(ITEM))
    rows: list[dict] = []
    seen_names: set[str] = set()
    seen_pages: set[str] = set()
    skipped: list[str] = []

    for item in entries:
        anchor = item.select_one(NAME_LINK)
        if anchor is None:
            raise ValueError(f"教师条目缺少姓名锚点：{url}")
        href = (anchor.get("href") or "").strip()
        if not href or not PERSON_HREF.search(href):
            raise ValueError(f"教师条目的链接不是个人详情页：{href!r}（{url}）")

        name = _norm(anchor.get_text(" ", strip=True)) or _norm(anchor.get("title") or "")
        if not name:
            raise ValueError(f"教师条目缺少姓名：{url}")
        name = _TITLE_SUFFIX.sub("", name)

        if _LATIN.fullmatch(name):
            # 非中文姓名：不音译、不截断，显式跳过并计数（红线 1）。
            skipped.append(name)
            continue
        if not NAME_RE.fullmatch(name) or _RANK.search(name):
            raise ValueError(f"师资名录出现无法识别为姓名的条目：{name!r}（{url}）")

        homepage = urljoin(url, href)
        if name in seen_names or homepage in seen_pages:
            raise ValueError(f"同一页出现重复教师：{name!r}（{url}）")
        seen_names.add(name)
        seen_pages.add(homepage)

        note = ("华南理工大学食品科学与工程学院「师资队伍 → 教师风采 → 教授」名录，"
                "按职称分组公布；本条目属于「教授」这一职称序列。名录只列姓名，"
                "未列个人研究方向，故方向字段为“方向待补”，职称只写进来源说明、"
                "不作为研究方向。本来源只覆盖教授序列（48 人），不含副教授、研究员、"
                "讲师及实验/工程系列，也不代表学院全部教师；导师资格与招生专业以"
                "当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, homepage, url, "学院师资队伍（教授）", note,
        ))

    # 红线 4：核对「容器内恰好 N 人」——条目数必须等于解析出的姓名数加登记跳过的
    # 非汉字姓名数；否则说明有真人被静默漏掉，直接抛错而不是返回残名单。
    if len(entries) != len(rows) + len(skipped):
        raise ValueError(
            f"食品科学与工程学院教授名录解析不完整：容器内 {len(entries)} 个条目，"
            f"解析出 {len(rows)} 条、跳过 {len(skipped)} 条（{url}）。请检查页面结构。")
    return rows
