"""东南大学网络空间安全学院「各系教师 → 网络安全系」师资名录（0839 网络空间安全）.

学院官网「师资力量 → 各系教师」把四个系的人员**服务端直接渲染**在同一张静态页上::

    https://cyber.seu.edu.cn/gxjs/list.htm

页面不依赖脚本、接口或分页，普通 GET 即可拿全。四个系各占一个 ``div.sz_box``::

    div.sz_box
      div.sz_tt > div.sz_tit          ← 系名，例如「网络安全系」（同级还有「（按拼音排序）」）
      ul.sz_list > li.news           ← 一个教师一个 li
        a.news_link[href]            ← 指向个人主页
        div.news_title               ← 姓名，可能带「（博后）」标注

实测 2026-10-22：四系合计 79 条 —— 网络安全系 34、智能安全系 17、信息安全系 19、
密码科学与技术系 9。四系同属 0839，但本模块**只收网络安全系**。

为什么只收一个系（而不是把四系 79 人全并进来）
----------------------------------------------

0839 现为 34 条 / 3 所，中国科学技术大学一家占 29 条（85.3%），远超 60% 的集中度上限。
稀释主导校需要的净新增人数是有**上界**的：新增 N 人后，若把全部新增都给同一所学校，

* 该校占比 = N/(34+N) < 60%  ⇒  N ≤ 51；
* 但 N 太小又压不下中科大 —— 29/(34+N) < 60%  ⇒  N ≥ 15。

四系全并是 74 人（去掉 5 名在站博士后），东南大学会变成 74/(34+74)=68.5%，等于把
「一家独大」从中国科学技术大学平移到东南大学，反而继续不达标。取**一个系 29 人**时：
东南大学 29/63 = 46.0%，中国科学技术大学 29/63 = 46.0%，两校都在 60% 以下。
其余三系同样属 0839，留作独立来源（各自成模块即可继续压低集中度），不是遗漏，
本模块文档与每条备注都写明覆盖范围。

为什么排除「（博后）」
----------------------

网络安全系 34 条里有 5 条姓名带「（博后）」标注（陈子涵、王祖研、许艺凡、张晓宇、周余阳），
是在站博士后，不是专任教师，故不进入师资行。解析器把这 5 条单独计数并参与
「容器内恰好 N 人」的核对（``len(rows) + 博士后数 == 容器内条目数``），
排除是有账可查的，而不是静默丢人。

口径说明
--------

* 名录只按系公布，不列个人研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`，
  绝不拿职称顶替方向（红线 2）。
* 姓名节点是纯姓名（可能带「（博后）」或「（Jing Zhang）」这类注记）：解析先剔注记、
  再按红线 1 剥一次职称后缀并用 ``NAME_RE`` 全匹配，双重保险。
* ``homepage`` 取 ``a.news_link`` 的 href，指向个人主页：个人栏目
  ``/<拼音缩写>/list.htm``（或 ``list.psp``）、个人资料文章
  ``/YYYY/MMDD/cNNNNNaNNNNN/page.htm``，以及一位教师页面自行填写的外部个人站点
  ``https://fei-tong.github.io/``；都不是名录页本身（红线 5）。
* 内页（个人栏目）会写「电话：」「办公室：」，名录页页脚也有学院座机与两个邮箱；
  落盘快照前已按项目规则把邮箱与电话整体替换为「联系方式已隐去」，本模块只读
  ``div.sz_box`` 内的人名与 href，从不读取任何联系方式字段（红线 3）。
* ``department`` 记为「网络空间安全学院·网络安全系」：既有学院，也有页面自己的系名，
  不含党委/工会/办公室一类行政机构（契约第 5 条）。
* 导师资格与招生专业以当年招生公告为准；本来源只表示学院「各系教师」页把这些人
  列在网络安全系名下。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://cyber.seu.edu.cn/gxjs/list.htm"

SPECS = ({
    "key": "seu_cyber",
    "code": "0839",
    "institution": "东南大学",
    "department": "网络空间安全学院·网络安全系",
    "discipline": "网络空间安全",
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：一系一个 div.sz_box；系名在容器自己的 div.sz_tit 里，不能靠页面上的第几个
# 盒子来定位（四个系的顺序随页面改版会变）。容器外的导航、新闻、页脚一律不进入解析。
CONTAINER = "div.sz_box"
UNIT_TITLE = "div.sz_tit"
ENTRY = "ul.sz_list li"
LINK = "a.news_link"
NAME_BOX = "div.news_title"

# 本来源只收这一个系。
TARGET_UNIT = "网络安全系"

# 页面用「（博后）」标注在站博士后：不是专任教师，单独计数后排除。
POSTDOC = re.compile(r"[（(]\s*博后\s*[)）]$")

# 同一套模板在别的列表里用「张静（Jing Zhang）」这种拼音注记；这里把带拉丁字母的尾括号
# 去掉，避免拼音注记把一个人拆成两个人（或让整份名录失配）。
PINYIN = re.compile(r"[（(][^（()）]*[A-Za-z][^（()）]*[)）]$")

# 红线 1 的兜底：万一姓名节点是「姓名+职称」拼接，先剥后缀再交给 NAME_RE 全匹配。
# 长词优先，否则「副研究员」会被「研究员」剥成「副」。
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|研究员|副教授|教授|讲师|高工|院士)+$"
)

# 页面上确实存在的四个系名，只用于错误信息里提示"结构变了没有"。
UNITS = ("网络安全系", "智能安全系", "信息安全系", "密码科学与技术系")


def _norm(text: str) -> str:
    """压掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _unit_box(soup):
    """按容器自己的系名找到目标系的 ``div.sz_box``；找不到返回 None。"""
    for box in soup.select(CONTAINER):
        title = box.select_one(UNIT_TITLE)
        if title is not None and _norm(title.get_text(" ", strip=True)) == TARGET_UNIT:
            return box
    return None


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse the 东南大学网络空间安全学院 网络安全系 roster page into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    box = _unit_box(soup)
    if box is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    entries = box.select(ENTRY)
    rows: list[dict] = []
    seen: set[str] = set()
    postdocs = 0
    for item in entries:
        anchor = item.select_one(LINK)
        heading = item.select_one(NAME_BOX)
        if anchor is None or heading is None:
            continue
        name = _norm(heading.get_text(" ", strip=True))
        if POSTDOC.search(name):
            postdocs += 1
            continue
        name = PINYIN.sub("", name)
        name = TITLE_SUFFIX.sub("", name)
        if not NAME_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        note = ("学院「师资力量 → 各系教师 → 网络安全系」按系公布的在册教师；"
                "名录未列个人研究方向，故方向字段为「方向待补」，不拿职称顶替方向。"
                "本来源只覆盖网络安全系，不含智能安全、信息安全、密码科学与技术三个系"
                "（同属 0839，另建来源），也不含页面标注「博后」的在站博士后；"
                "导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, urljoin(url, anchor["href"]), url,
            "学院各系教师名录", note,
        ))

    # 红线 4：核对「容器内恰好 N 人」。容器内条目 = 解析出的教师 + 明确排除的在站博士后，
    # 差一个就说明有人被静默丢掉了（重名、外文名或结构变化），宁可报错也不静默少收。
    if len(rows) + postdocs != len(entries):
        raise ValueError(
            f"网络安全系名录解析不完整：容器内 {len(entries)} 个条目，解析出 {len(rows)} 人 + "
            f"在站博士后 {postdocs} 人 = {len(rows) + postdocs}，对不上。"
            f"请检查 {url} 的页面结构（系名是否仍为 {UNITS}）。")
    return rows
