"""西南石油大学 / 东北石油大学 石油与天然气工程（0820）教师名录.

0820 石油与天然气工程此前只有中国石油大学（北京）一所学校（``cup.py``），
跨校比较无从谈起。本模块一次接入**两所**石油主干高校的**院级**教师名录，
每所各五个单位、共十个 ``SPECS`` 条目，共用同一个 ``parse``：

===============  ====================================  ======================
学校              单位（页面原名）                        名录地址
===============  ====================================  ======================
西南石油大学       石油工程教研室                          ``/sgy/szdw/jsml/sugc.htm``
西南石油大学       油气储运工程教研室                       ``/sgy/szdw/jsml/yqcy.htm``
西南石油大学       海洋油气工程教研室                       ``/sgy/szdw/jsml/hyyq.htm``
西南石油大学       流体与热工教研室                         ``/sgy/szdw/jsml/ltrg.htm``
西南石油大学       石油工程实验中心                         ``/sgy/szdw/jsml/syzx.htm``
东北石油大学       油气田开发工程系                         ``/szdw1/zyjsmlx/yqtkfgcx.htm``
东北石油大学       油气井工程系                            ``/szdw1/zyjsmlx/yqjgcx.htm``
东北石油大学       油气储运工程系                          ``/szdw1/zyjsmlx/yqcygcx.htm``
东北石油大学       实验中心                              ``/szdw1/zyjsmlx/syzx.htm``
东北石油大学       提高采收率研究所                         ``/szdw1/zyjsmlx/tgcslyjs.htm``
===============  ====================================  ======================

两校页面结构完全不同，但都**不用 JavaScript 渲染**，普通 GET 就能拿到完整名单，
且都**没有分页**（页面里没有 ``下一页``／``共 N 条`` 一类翻页控件，实测每个单位
的全部姓名都在同一张静态页里），因此十个条目的 ``max_pages`` 都是 1、
``listing`` 里没有 ``{page}`` 占位符。

西南石油大学（``www.swpu.edu.cn/sgy/``，即石油与天然气工程学院）
----------------------------------------------------------------

``师资队伍 → 教师名录`` 下按**教研室／实验中心**分成七个页面，其中前五个是教学与
实验单位，本模块收录；``学工团队`` 与 ``管理团队`` 属非教学单位（合同第 5 条），
不建来源条目。页面结构::

    <div class="teacher-list">
      <div class="js">                       ← 一个职称分组
        <p>教授/研究员<span>(按姓氏拼音排序)</span></p>   ← 组标题（职称）
        <div class="lb"><ul>
          <li><a href="sugc/js/by.htm" title="白杨">白杨</a></li>   ← 姓名 + 个人页
          …
        </ul></div>
      </div>
      <div class="js clear"> …副教授/副研究员… </div>
      <div class="js clear"> …讲师/助理研究员… </div>
    </div>

组标题与该组名单是 ``div.js`` 内部的**兄弟**关系，所以本模块只遍历
``div.teacher-list`` 的**直接子元素**并保持文档顺序，一格一格地给后续名单定组；
用扁平的 ``find_all('div')`` 走会把导航区（``师资队伍``／``教师名录``／``荣休教师``
这些同样由 ``<a>`` 组成的菜单项）一并卷进来，还会让嵌套元素重置组名。

东北石油大学（``sygcxy.nepu.edu.cn``，即石油工程学院）
-------------------------------------------------------

``师资队伍 → 学院教师名录`` 下按**系／实验中心／研究所**分成六个页面，本模块收录
其中五个；``学生工作组`` 是非教学单位，不建条目。页面结构::

    <div class="szdw">
      <div>                                   ← 有的分组外面多套一层普通 div
        <div class="box">
          <div class="top flex"><div class="ll flex">
            <img …><big>教授</big><small>（按姓氏拼音排序）</small>   ← 组标题（职称）
          </div></div>
          <div class="bottom"><ul class="ls16 flex">
            <li><a href="../../info/2912/24571.htm" title="曹晓春">曹晓春</a></li>
            …
          </ul></div>
        </div>
      </div>
      <div class="box"> …副教授… </div>
      …
      <ul class="ls14 flex"> …实验室快速链接… </ul>
      <div class="box"> …联系方式… </div>       ← 无 div.top/div.bottom，天然被排除
    </div>

同一页里 ``<div class="box">`` 有时是 ``div.szdw`` 的直接子元素、有时被一层普通
``div`` 包着（两种写法在同一站点内混用），所以本模块按文档顺序逐个子元素判断：
子元素自己是 ``box`` 就用它，否则取它内部的 ``box``。组标题与名单都取自**同一个**
``box``（``div.top`` 对 ``div.bottom``），因此组名不可能被别的分组改写。
页面末尾的 ``联系方式`` 块没有 ``div.top``／``div.bottom``，实验室快速链接是
``ul`` 而不是 ``box``，都被结构本身排除。

口径说明（两校一致）
--------------------

* **研究方向一律留空**：两份名录都只给姓名与职称，页面本身没有写任何人的研究方向，
  因此每一条的 ``direction`` 都是 :data:`NO_DIRECTION`（``方向待补``）。职称只写进
  备注，绝不进入方向字段（项目红线 2）；个人页地址作为 ``homepage`` 留给采集器的
  ``--enrich`` 环节去读方向。
* **不读取任何联系方式**：两页正文里都有学院电话／邮箱（东北石油大学页脚还印着
  ``0459-6503482`` 与一个 ``@`` 邮箱），本模块只从名单容器里取 ``<a>`` 的姓名，
  联系方式所在区块根本不在取值路径上（项目红线 1）。
* **姓名里的空格先去掉再校验**：东北石油大学把 ``李　玮``／``索　彧`` 这类两字名
  排成三格宽，全角空格 U+3000 在 ``NAME_RE`` 校验**之前**就被 ``_compact`` 去掉了。
* **非汉字姓名会被跳过**：东北石油大学油气田开发工程系名录里的 ``LuJing`` 是拼音
  写法，不符合 ``NAME_RE``，宁缺勿猜，故该系是本模块唯一"页面姓名数 ≠ 收录数"
  （33 → 32）的条目。
* **同名不同人不会被合并**：``张涛`` 同时出现在西南石油大学的``石油工程教研室``
  （副教授，个人页 ``sugc/fjs/zt.htm``）与``流体与热工教研室``（教授，个人页
  ``ltrg/js/zhangtao.htm``），两处职称与个人页都不同，应当是两个人；采集器按
  ``(学校, 院系, 姓名)`` 去重，因此两条都会保留，各自引用自己的名录页。
* 收录的教师**不含**两校的学工／管理团队，也不含博士后（两页都没有博士后分组），
  所以不代表学院全部人员；这一句在每个条目的备注里也写明。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SWPU = "西南石油大学"
NEPU = "东北石油大学"

# 名录页面里组标题后面的小字注记，取职称时要摘掉。
SORT_NOTE_RE = re.compile(r"[（(]按姓氏拼音排序[)）]")

SPECS = (
    # ── 西南石油大学 石油与天然气工程学院（石工院 www.swpu.edu.cn/sgy/）──
    {
        "key": "swpu_petroleum_engineering",
        "code": "0820",
        "institution": SWPU,
        "department": "石油工程教研室",
        "discipline": "石油与天然气工程",
        # 师资队伍 → 教师名录 → 石油工程教研室（静态页，无分页）。
        "listing": "http://www.swpu.edu.cn/sgy/szdw/jsml/sugc.htm",
        "max_pages": 1,
    },
    {
        "key": "swpu_oil_gas_storage",
        "code": "0820",
        "institution": SWPU,
        "department": "油气储运工程教研室",
        "discipline": "石油与天然气工程",
        "listing": "http://www.swpu.edu.cn/sgy/szdw/jsml/yqcy.htm",
        "max_pages": 1,
    },
    {
        "key": "swpu_offshore_petroleum",
        "code": "0820",
        "institution": SWPU,
        "department": "海洋油气工程教研室",
        "discipline": "石油与天然气工程",
        "listing": "http://www.swpu.edu.cn/sgy/szdw/jsml/hyyq.htm",
        "max_pages": 1,
    },
    {
        "key": "swpu_fluid_thermal",
        "code": "0820",
        "institution": SWPU,
        "department": "流体与热工教研室",
        "discipline": "石油与天然气工程",
        "listing": "http://www.swpu.edu.cn/sgy/szdw/jsml/ltrg.htm",
        "max_pages": 1,
    },
    {
        "key": "swpu_petroleum_lab",
        "code": "0820",
        "institution": SWPU,
        "department": "石油工程实验中心",
        "discipline": "石油与天然气工程",
        # 实验中心列的是正高级实验师/高级实验师/实验师/助理实验师，同属学院教学队伍。
        "listing": "http://www.swpu.edu.cn/sgy/szdw/jsml/syzx.htm",
        "max_pages": 1,
    },
    # ── 东北石油大学 石油工程学院（sygcxy.nepu.edu.cn）──
    {
        "key": "nepu_reservoir_engineering",
        "code": "0820",
        "institution": NEPU,
        "department": "油气田开发工程系",
        "discipline": "石油与天然气工程",
        # 师资队伍 → 学院教师名录 → 油气田开发工程系（静态页，无分页）。
        "listing": "https://sygcxy.nepu.edu.cn/szdw1/zyjsmlx/yqtkfgcx.htm",
        "max_pages": 1,
    },
    {
        "key": "nepu_well_engineering",
        "code": "0820",
        "institution": NEPU,
        "department": "油气井工程系",
        "discipline": "石油与天然气工程",
        "listing": "https://sygcxy.nepu.edu.cn/szdw1/zyjsmlx/yqjgcx.htm",
        "max_pages": 1,
    },
    {
        "key": "nepu_oil_gas_storage",
        "code": "0820",
        "institution": NEPU,
        "department": "油气储运工程系",
        "discipline": "石油与天然气工程",
        "listing": "https://sygcxy.nepu.edu.cn/szdw1/zyjsmlx/yqcygcx.htm",
        "max_pages": 1,
    },
    {
        "key": "nepu_petroleum_lab",
        "code": "0820",
        "institution": NEPU,
        "department": "实验中心",
        "discipline": "石油与天然气工程",
        "listing": "https://sygcxy.nepu.edu.cn/szdw1/zyjsmlx/syzx.htm",
        "max_pages": 1,
    },
    {
        "key": "nepu_eor_institute",
        "code": "0820",
        "institution": NEPU,
        "department": "提高采收率研究所",
        "discipline": "石油与天然气工程",
        # 研究所是科研单位，合同第 5 条明确保留（只排除党委/工会/离退休/办公室）。
        "listing": "https://sygcxy.nepu.edu.cn/szdw1/zyjsmlx/tgcslyjs.htm",
        "max_pages": 1,
    },
)

# 姓名里不可能出现的词：名录容器内不会命中，留作防御，避免导航/栏目文字混入。
NAME_NOISE = re.compile(r"教研室|实验室|实验中心|研究所|工作组|团队|学院|教师|名录|"
                        r"师资|队伍|教授|导师|首页|更多|下载|荣休|杰出|联系方式")
# 跳过非教学单位的兜底（合同第 5 条）；本模块的 SPECS 已不含这些单位。
NON_TEACHING = re.compile(r"党委|工会|离退休|办公室|招聘|学生工作|学工")


def _compact(node) -> str:
    """取文本并去掉**所有**空白，含全角空格 U+3000 与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def _rank(node) -> str:
    """组标题里的职称：``教授（按姓氏拼音排序）`` → ``教授``。"""
    return SORT_NOTE_RE.sub("", _compact(node)).strip()


def _homepage(url: str, anchor) -> str:
    """个人页地址；``#``／空链接／javascript 一律回落到名录页本身。"""
    href = (anchor.get("href") or "").strip()
    if href in ("", "#") or href.lower().startswith("javascript"):
        return url
    target = urljoin(url, href)
    return target if target.startswith("http") else url


def _row(name: str, rank: str, url: str, homepage: str, spec: dict,
         unit_note: str) -> dict:
    note = (f"{spec['institution']}「{unit_note}」按职称分组列出"
            f"（职称分组：{rank or '页面未标注'}）；"
            f"名录不列个人研究方向，方向留待补。"
            f"本来源覆盖该院教师名录的五个院级单位页面（系/教研室、实验中心与研究所），"
            f"不含学工/学生工作组与管理团队，也不代表学院全部人员。"
            f"导师资格与招生专业以当年招生公告为准。")
    return roster_row(
        name, spec["institution"], spec["department"], spec["code"],
        NO_DIRECTION, homepage, url, "学院教师名录", note,
    )


def _parse_swpu(soup: BeautifulSoup, url: str, spec: dict) -> list[dict]:
    """西南石油大学石工院：``div.teacher-list`` 下 ``div.js`` 组，组内 ``p`` + ``div.lb``。"""
    root = soup.select_one("div.teacher-list")
    if root is None:
        return []
    # 只走名称容器的直接子元素，保持文档顺序：一个 div.js 就是一个职称分组。
    groups = [child for child in root.find_all("div", recursive=False)
              if "js" in (child.get("class") or [])]
    unit_note = f"师资队伍 → 教师名录 → {spec['department']}"
    rows: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        heading = group.find("p")
        rank = _rank(heading) if heading is not None else ""
        roster_box = group.select_one("div.lb")
        if roster_box is None or NON_TEACHING.search(rank):
            continue
        for anchor in roster_box.select("a"):
            name = _compact(anchor)
            if not NAME_RE.fullmatch(name) or name in seen or NAME_NOISE.search(name):
                continue
            seen.add(name)
            rows.append(_row(name, rank, url, _homepage(url, anchor), spec, unit_note))
    return rows


def _parse_nepu(soup: BeautifulSoup, url: str, spec: dict) -> list[dict]:
    """东北石油大学石工院：``div.szdw`` 下的 ``div.box``，标题 ``div.top`` + 名单 ``div.bottom``。"""
    root = soup.select_one("div.szdw")
    if root is None:
        return []
    unit_note = f"师资队伍 → 学院教师名录 → {spec['department']}"
    rows: list[dict] = []
    seen: set[str] = set()
    # 直接子元素里，box 有的是自己、有的被一层普通 div 包着：两种都按文档顺序取。
    for child in root.find_all("div", recursive=False):
        if "box" in (child.get("class") or []):
            boxes = [child]
        else:
            boxes = child.find_all("div", class_="box")
        for box in boxes:
            top = box.select_one("div.top")
            bottom = box.select_one("div.bottom")
            if top is None or bottom is None:
                # 页脚的“联系方式”等区块没有这一对子元素，天然跳过。
                continue
            big = top.find("big")
            rank = _rank(big if big is not None else top)
            if NON_TEACHING.search(rank):
                continue
            for anchor in bottom.select("a"):
                name = _compact(anchor)
                if not NAME_RE.fullmatch(name) or name in seen or NAME_NOISE.search(name):
                    continue
                seen.add(name)
                rows.append(_row(name, rank, url, _homepage(url, anchor), spec, unit_note))
    return rows


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    if spec.get("institution") == SWPU:
        return _parse_swpu(soup, url, spec)
    return _parse_nepu(soup, url, spec)
