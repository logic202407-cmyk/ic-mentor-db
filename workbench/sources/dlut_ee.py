"""大连理工大学 电气工程学院 教师名录（0808 电气工程）.

学院官网「师资队伍 → 教师名录」（``/szdw/jsml.htm``）是**单页静态名录**，由服务端
直接渲染，普通 GET 即可拿全，不依赖脚本、接口或分页参数::

    section.team-page-section.teampage
      div.text-center > h3  正高级                 ← 职称分组标题（正高级/副高级/中级/博士后）
      div.row.clearfix
        div.team-block                      ← 一张教师卡片 = 一条名录条目（共 57 条）
          div.inner-box
            a[href=个人主页]
              div.image > img                ← 证件照（本站 jspic 目录）
              div.lower-content
                h3  姓名                     ← 卡片里唯一的文字
                <!--div class="designation">教授</div-->   ← 卡片内的职称块被页面注释掉了

所以 ``max_pages`` 为 1、``listing`` 里没有 ``{page}`` 占位符：这一页就是整份名录，
页面自己也没有「上一页/下一页」「共 N 条」之类的分页控件。

57 条里有 7 条没有个人主页
--------------------------

名录页给每位教师挂了 ``faculty.dlut.edu.cn/<工号或账号>/zh_CN/index.htm`` 形式的
个人主页，但 57 条中有 7 条**没有可用的个人主页**：5 条的锚点是空 ``#``，另 2 条连
锚点都没有（只有姓名与证件照）。这 7 人不编造主页、也不回落到名录页本身——把 7 个
人指到同一份名单会被下游 ``--enrich`` 读成同一个人的资料（项目红线：每条 ``homepage``
必须指向个人详情页）。因此它们**显式跳过并计数**，由 :func:`parse_with_skips` 的
``skipped`` 报告出来；容器守卫要求「卡片数 = 解析数 + 跳过数」（57 = 50 + 7），对不上
即抛错。

分组口径
--------

* **职称只写进 note**：名录按 正高级 / 副高级 / 中级 / 博士后 四组排列（18 / 23 / 11 / 5
  条），卡片本身只印姓名。分组标题是职称，不是研究方向，所以每一行的 ``direction``
  一律是 :data:`NO_DIRECTION`（``方向待补``），职称只作为「本条目所在名录分组」写进
  ``note``（与 ``collect_thin_discipline_depth`` 对职称分组的处理一致）。
* 学院另有一张「师资队伍」概况页，把教师按四个研究方向（电力系统及其自动化、高电压与
  绝缘技术、电力电子与电能变换、新能源发电与电能存储）加实验教学中心分组列出。那是
  **研究方向分组**，少 5 人（概况页 52 人、名录 57 人），且把方向写进 ``direction``
  违反项目红线 2；所以本模块只取名录页，``department`` 统一记为「电气工程学院」，
  不按方向拆系。
* 57 个姓名互不重复、全部落在 :data:`NAME_RE` 范围内，没有拉丁字母姓名，故本次
  ``skipped`` 里只有「无个人主页」一类。姓名若再带职称后缀，解析器先剥后缀再校验，
  校验不过即抛错。
* 本来源只表示：学院「教师名录」页在册列出的教师有这些人。学院行政、实验技术等岗位
  另有机构页，名录不区分岗位：57 条里有 4 位实验教学中心的教师，另有 5 位博士后
  （这 5 位没有个人主页，已跳过）。因此这 57 条**不能**读成「学院专任教师总数」。
* 联系方式（项目红线 1）：名录页页脚有学院的联系方式，快照落盘前已按仓库规则脱敏为
  「联系方式已隐去」，本模块从不读取任何联系方式字段。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "dlut_ee",
    "code": "0808",
    "institution": "大连理工大学",
    "department": "电气工程学院",
    "discipline": "电气工程",
    "listing": "https://ee.dlut.edu.cn/szdw/jsml.htm",
    "max_pages": 1,
},)

# 名录容器：一页 57 张卡片，导航、页脚都在它外面，不会被当成人名。
CARD_SELECTOR = "div.team-block"
# 名录所在的分节；职称分组标题也在这个分节里，与卡片同层。
SECTION_SELECTOR = "section.team-page-section"
# 个人主页：faculty.dlut.edu.cn/<账号>/zh_CN/…；站点自己会写出连续两个斜杠，原样保留。
PERSONAL_PAGE = re.compile(r"^https?://faculty\.dlut\.edu\.cn/{1,2}[0-9A-Za-z_]+/zh_CN/")
# 卡片里的姓名藏在 h3，去掉零宽字符与全部空白后再校验。
_BLANK = re.compile(r"[\s\u3000\xa0\u200b\u200c\u200d\ufeff]+")
# 拼接式姓名（「张三教授」）先剥后置职称再校验；单独一个职称词则原样交给 NAME_RE 拒绝。
_RANK_SUFFIX = re.compile(
    r"(?:长聘教授|助理教授|副教授|教授|副研究员|研究员|高级工程师|工程师|"
    r"高级实验师|实验师|讲师|助教|院士|博导|硕导)+$"
)
# 拉丁字母姓名不在 NAME_RE 范围内：显式跳过并登记，不做音译/截断。
_NON_CJK = re.compile(r"[A-Za-z]")
# 没有个人主页的锚点形态。
_EMPTY_HREF = frozenset({"", "#"})
# 职称分组标题里的词；只用来识别标题，绝不进方向字段。
_RANK_GROUP = re.compile(r"^(正高级|副高级|中级|博士后)$")

# 名录页的实录（2026-10-22 快照）：57 张卡片，按 18/23/11/5 分成四个职称组，
# 50 条有个人主页、7 条没有。
PUBLISHED_ENTRIES = 57
EXPECTED_ROSTER = 50
# 入库行在各职称分组里的条数：正高级少 1（姜楠无主页）、副高级少 1（刘东平无主页）、
# 博士后 5 位全部无主页。
EXPECTED_BY_GROUP = {"正高级": 17, "副高级": 22, "中级": 11, "博士后": 0}
# 7 位在册但没有个人主页的教师：跳过并计数，不编造主页、也不回落到名录页。
SKIPPED_NO_HOMEPAGE = (
    "姜楠", "刘东平", "陈百通", "孟兆通", "裴忠晨", "宋雨嘉", "张立岩",
)
SKIPPED_NON_CJK: tuple[str, ...] = ()

_NOTE = (
    "大连理工大学电气工程学院「师资队伍 → 教师名录」单页公布的在册教师名单"
    "（页面按职称分组、组内按姓名拼音排序，共 57 条；本条目所在分组：{group}）；"
    "名录只印姓名，不列个人研究方向，故方向留待补——职称分组是职称，不是方向。"
    "学院另有一张按研究方向分组的师资概况页，本模块不采其分组。"
    "本来源不代表学院专任教师总数；导师资格与招生专业以当年招生公告为准。"
)


def _name(text: str) -> str:
    """把卡片里的姓名文字变成裸姓名；带职称后缀的先剥后缀。"""
    raw = _BLANK.sub("", text or "")
    if not raw:
        return ""
    stripped = _RANK_SUFFIX.sub("", raw)
    return stripped or raw


def _rank_groups(soup: BeautifulSoup) -> dict[int, str]:
    """把卡片映射到它所在的职称分组标题；只在名录分节内按文档顺序走。"""
    section = soup.select_one(SECTION_SELECTOR)
    if section is None:
        return {}
    groups: dict[int, str] = {}
    current = ""
    index = 0
    for node in section.find_all(["h3", "div"]):
        classes = node.get("class") or []
        if node.name == "h3" and "lower-content" not in classes:
            heading = _BLANK.sub("", node.get_text(" ", strip=True))
            if _RANK_GROUP.match(heading):
                current = heading
            continue
        if "team-block" not in classes:
            continue
        groups[index] = current
        index += 1
    return groups


def parse_with_skips(html: str, url: str, spec: dict) -> tuple[list[dict], list[dict]]:
    """解析一页名录，返回 (rows, skipped)。

    ``skipped`` 的每一项是 ``{"name": ..., "reason": ...}``，只登记**在册但无法入库**
    的条目（非中文姓名、没有个人主页），供调用方与容器守卫核对。
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    groups = _rank_groups(soup)
    rows: list[dict] = []
    skipped: list[dict] = []
    entries = 0
    for card in soup.select(CARD_SELECTOR):
        group = groups.get(entries, "")
        entries += 1
        anchor = card.select_one("a[href]")
        holder = card.select_one("h3") or anchor
        raw = holder.get_text(" ", strip=True) if holder is not None else ""
        name = _name(raw)
        if not name:
            raise ValueError(f"名录卡片没有姓名文字：{raw!r}")
        if not NAME_RE.fullmatch(name):
            if _NON_CJK.search(name):
                # 登记时保留页面原样（含空格），便于人工核对；姓名不做音译/截断。
                skipped.append({"name": re.sub(r"\s+", " ", raw).strip(),
                                "reason": "non_cjk"})
                continue
            raise ValueError(f"名录卡片姓名无法校验：{name!r}")

        href = (anchor.get("href") or "").strip() if anchor is not None else ""
        if href in _EMPTY_HREF:
            skipped.append({"name": name, "reason": "no_homepage"})
            continue
        if not PERSONAL_PAGE.match(href):
            # 链接形态变了：宁可让采集停下来，也不要把导航或栏目页当个人主页。
            raise ValueError(f"名录卡片的链接不是个人主页：{name!r} → {href!r}")

        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, href, url, "学院教师名录", _NOTE.format(group=group or "未标注"),
        ))

    if entries != len(rows) + len(skipped):
        raise ValueError(
            f"名录容器内 {entries} 条，解析 {len(rows)} 条 + 跳过 {len(skipped)} 条，对不上"
        )
    return rows, skipped


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """返回一页名录里的导师行（跳过项只计数，不进返回值）。"""
    rows, _ = parse_with_skips(html, url, spec)
    return rows
