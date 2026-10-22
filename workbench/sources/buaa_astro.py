"""北京航空航天大学 宇航学院 航天飞行器技术系 教师名录（0825 航空宇航科学与技术）.

北航宇航学院（School of Astronautics）官网「师资队伍 → 教师风采」按**系**公布教师
名录，服务端直接渲染（博达/WebPlus 静态列表，普通 GET 即可拿全，不依赖脚本或接口）::

    https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx.htm    ← 航天飞行器技术系 第 1 页
    https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/3.htm  ← 第 2 页
    https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/2.htm  ← 第 3 页
    https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/1.htm  ← 第 4 页（3 人）

分页目录名是**倒序**的（第 2 页在 ``/3.htm``，第 4 页在 ``/1.htm``），无法用一个
``{page}`` 模板推出所有页，因此按「一页一个 key」把四页各自登记成一个 SPEC。

页面结构（每人一张卡片）::

    div.con_p_lis                       ← 右侧名录容器（左侧导航在 div.con_ll，不在里面）
      ul.clearfix
        li#line_u15_0
          a[href="../../info/1011/4663.htm"]   ← 个人详情页
            p.mingzi     ← 纯姓名
            p.zhicheng   ← "职称/职位：教授/博导"（职称，不是人名，也不是研究方向）

实测 2026-10-22：四页各 12/12/12/3 条，合计 **39 人**，39 个姓名互不重复，对应
39 个不同的个人详情页；卡片职称行全是教授/研究员/副教授/副研究员/讲师，没有博士后
或实验技术人员混入（页面的筛选器可以按这些类别过滤，但默认展示的就是这 39 人）。

为什么选它作为 0825 的「一所新高校」
----------------------------------
0825 此前 75 条、只有两所机构：上海交通大学 62 条（82.7%）、中南大学 13 条。
本模块新增北京航空航天大学 39 条，补后共 114 条：

* 上海交通大学 62/114 = 54.4%（原主导校，本次**没有**新增）
* 北京航空航天大学 39/114 = 34.2%（新增机构，不是主导校）
* 中南大学 13/114 = 11.4%

最大机构 62/114 = 54.4%，低于 60% 的集中度上限；同时 39 ≤ 62，新校不会取代原
主导校变成新的独大。这就是只取**一个系**而不是整院的原因：宇航学院三个系
（航天飞行器技术系 39、航天智能科学与技术系 37、宇航推进系 48）合计 124 人，
既超过本次 N ≤ 62 的上限，也会把导航/制导与控制、信息处理方向的教师大量并入
0825，归属不如飞行器设计直接。因此本模块只取航天飞行器技术系（0825 的飞行器
设计方向），``department`` 记为「宇航学院·航天飞行器技术系」，不冒充整院师资。

为什么这不是「合设学院」的弱归属
--------------------------------
本项目此前拒绝了大连理工「力学与航空航天学院」的 184 条、同济「航空航天与力学
学院」按力学口径的合并，原因是学院把 0801 力学与 0825 航空宇航合设。北航宇航
学院**不是**这种结构：学院三个系里没有力学系，本院教师整体属于航空宇航科学与
技术；本模块进一步只取其中一个系，不存在把力学教师算进 0825 的问题。

口径说明
--------
* 名录按职称层次排序列出教师，不列个人研究方向，故每行 ``direction`` 一律
  :data:`NO_DIRECTION`（``方向待补``）；职称只写进 note，绝不作为方向（红线 2）。
* 页面不列邮箱、电话；页脚的学院电话与邮箱在快照落盘前已替换为「联系方式已隐去」。
  本模块只取列表页上的姓名与个人详情页链接，**从不读取详情页**，更不把任何联系
  方式写进字段（红线 3；落盘后 EMAIL / PHONE 两条正则均无残留）。
* ``homepage`` 取卡片锚点的 href，即 ``https://www.sa.buaa.edu.cn/info/1011/<id>.htm``
  形式的个人详情页，不是名录页（红线 5）；四页 39 人对应 39 个不同的详情页。
* 导航（学院概况、师资队伍、教师风采、筛选器…）都在人员容器外；姓名取自
  ``p.mingzi`` 而不是整张卡片的文本，避免把「职称/职位」拼进姓名。解析后仍用
  「容器内条目数 = 解析出的姓名数 + 登记跳过的非汉字姓名数」核对（红线 1、4），
  对不上直接抛错而不是悄悄少收人。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://www.sa.buaa.edu.cn/szdw/jsfc/"
_DEPARTMENT = "宇航学院·航天飞行器技术系"

SPECS = (
    {
        "key": "buaa_astro_p1",
        "code": "0825",
        "institution": "北京航空航天大学",
        "department": _DEPARTMENT,
        "discipline": "航空宇航科学与技术",
        "listing": _BASE + "htfxqjsx.htm",
        "max_pages": 1,
    },
    {
        "key": "buaa_astro_p2",
        "code": "0825",
        "institution": "北京航空航天大学",
        "department": _DEPARTMENT,
        "discipline": "航空宇航科学与技术",
        "listing": _BASE + "htfxqjsx/3.htm",
        "max_pages": 1,
    },
    {
        "key": "buaa_astro_p3",
        "code": "0825",
        "institution": "北京航空航天大学",
        "department": _DEPARTMENT,
        "discipline": "航空宇航科学与技术",
        "listing": _BASE + "htfxqjsx/2.htm",
        "max_pages": 1,
    },
    {
        "key": "buaa_astro_p4",
        "code": "0825",
        "institution": "北京航空航天大学",
        "department": _DEPARTMENT,
        "discipline": "航空宇航科学与技术",
        "listing": _BASE + "htfxqjsx/1.htm",
        "max_pages": 1,
    },
)

# 人员容器：只有它里面的卡片是教师；导航、面包屑、筛选器与分页都在容器外。
ROSTER_BOX = "div.con_p_lis"
ROSTER_LIST = "ul.clearfix"
NAME_BOX = "p.mingzi"
LINK = "a[href]"

# 个人详情页：https://www.sa.buaa.edu.cn/info/1011/4663.htm
PERSON_PAGE = re.compile(r"^https://www\.sa\.buaa\.edu\.cn/info/\d+/\d+\.htm$")

# 页面自报的每页条数与可落库总数（实测四页 12/12/12/3）。
EXPECTED_PER_PAGE = (12, 12, 12, 3)
EXPECTED_ROSTER = 39

# 红线 1 的兜底：万一 p.mingzi 里混进「姓名+职称」拼接，剥掉后缀再校验。长词优先，
# 否则「副研究员」会被「研究员」剥成「副」。
_TITLE_SUFFIX = re.compile(r"(?:副教授|助理教授|副研究员|研究员|教授|讲师|院士|高工|博士后)$")
# 剥完后仍含职称字样，说明不是「姓名+后缀」而是结构变了，直接报错。
_RANK = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
# 拉丁字母姓名（外籍教师）：不做音译、不截断，显式跳过并计数。
_LATIN_NAME = re.compile(r"^[A-Za-z][A-Za-z .'’\-]{0,59}$")

_NOTE = ("北京航空航天大学宇航学院「师资队伍 → 教师风采 → 航天飞行器技术系」教师名录；"
         "该名录按职称层次排序列出本系专任教师，不列个人研究方向，故方向字段为"
         "“方向待补”；职称只留在来源说明中，不作为研究方向。本来源只覆盖航天飞行器"
         "技术系，不代表宇航学院全部教师；导师资格与招生专业以当年招生公告为准。")


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one page of the BUAA astronautics faculty directory into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    boxes = soup.select(ROSTER_BOX)
    if not boxes:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = []
    for box in boxes:
        for roster in box.select(ROSTER_LIST):
            entries.extend(roster.find_all("li", recursive=False))

    rows: list[dict] = []
    seen: set[str] = set()
    skipped: list[str] = []
    for item in entries:
        anchor = item.select_one(LINK)
        name_node = item.select_one(NAME_BOX)
        if anchor is None or name_node is None:
            raise ValueError(f"教师名录条目缺少姓名或详情页链接：{url}")

        raw = _norm(name_node.get_text(" ", strip=True))
        href = urljoin(url, (anchor.get("href") or "").strip())
        if not PERSON_PAGE.match(href):
            raise ValueError(f"教师名录条目的链接不是个人详情页：{href!r}（{url}）")

        name = _TITLE_SUFFIX.sub("", raw)
        if not name:
            raise ValueError(f"教师名录出现空姓名：{raw!r}（{url}）")
        if not NAME_RE.fullmatch(name):
            if _LATIN_NAME.fullmatch(name):
                # 非中文姓名不音译、不截断，登记跳过，由下面的容器守卫计数。
                skipped.append(name)
                continue
            raise ValueError(f"教师名录出现无法识别为姓名的条目：{name!r}（{url}）")
        if _RANK.search(name):
            raise ValueError(f"教师名录姓名仍含职称：{name!r}（{url}）")
        if name in seen:
            raise ValueError(f"教师名录同一页出现重复姓名：{name!r}（{url}）")
        seen.add(name)

        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, href, url, "学院师资队伍·教师风采", _NOTE,
        ))

    # 红线 4：核对「容器内恰好 N 人」——条目数必须等于解析出的姓名数加登记跳过的
    # 非汉字姓名数；否则说明有真人被静默漏掉，直接抛错而不是返回残名单。
    if len(entries) != len(rows) + len(skipped):
        raise ValueError(
            f"航天飞行器技术系教师名录解析不完整：容器内 {len(entries)} 个条目，"
            f"解析出 {len(rows)} 条、跳过 {len(skipped)} 条（{url}）。请检查页面结构。")
    return rows
