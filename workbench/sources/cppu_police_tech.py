"""中国人民警察大学 研究生导师名录（0838 公安技术）.

学校官网「师资队伍 → 研究生导师」是一张**静态单页**，把全校研究生导师按
**教学单位**分组公布：

    https://www.cppu.edu.cn/szdw/yjsds.htm

每个单位一个 ``div.inner-hd h3`` 标题，紧随其后 ``div.inner-cont ul.list1``，
名单里每个人的姓名只是 ``li h4`` 文本，**没有 href**；同页还有 ``info/1029/6073.htm``
的文章版，结构相同、内容相同。因此本来源的 ``homepage`` 只能回落到名录页本身。

收录口径
--------

学校「公安技术一级学科简介」把 0838 分为五个方向，并明确由下列教学单位承担：

* 智慧警务与大数据技术          —— 智慧警务学院
* 智能警用装备技术              —— 警务装备技术学院
* 涉火涉爆犯罪侦查技术          —— 防火工程学院
* 食品药品犯罪侦查技术          —— 侦查学院
* 移民与出入境安全管控技术      —— 移民管理学院

本模块收录前三个单位（``智慧警务学院``、``警务装备技术学院``、``防火工程学院``），
共 **65 人**。不收录侦查学院、移民管理学院：这两个单位以公安学（侦查学、移民管理）
为主，把整单位导师并入 0838 会把大量 0306 人员划过来；同理也不收公安政治学院、
公安法学院、马克思主义学院、警务指挥学院、特勤学院、救援指挥学院、维和警察培训
中心、国际执法合作学院等非公安技术单位。

必须说明的口径限制：该页**只按教学单位分组，不逐人标注学科**。上述三个单位也同时
承担其他学科（智慧警务学院有公安情报学，防火工程学院有消防工程/安全科学与工程），
所以这是**单位级**归类，不是逐人学科认定；模块的 note 与测试都写明这一点，不把
单位内所有人当成 0838。若以后学校公布逐人学科归属，应改为按人过滤。

红线执行
--------

* 姓名取 ``li h4`` 文本，先剥「教授/副教授/讲师/研究员/高工/院士/教官/导师」等
  职称后缀，再用 :data:`NAME_RE` 全匹配；非中文姓名显式跳过并计数。
* ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱、电话（实测 0/0），解析器只读姓名与单位标题，不读页脚。
* 容器守卫：三个单位容器内条目数必须等于「解析数 + 非中文跳过数」，对不上抛错。
* ``homepage``：该页不提供个人详情页，回落名录页；这是本来源已知的、唯一的
  红线偏差，测试里显式断言并计数，不伪装成个人主页。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://www.cppu.edu.cn/szdw/yjsds.htm"

SPECS = ({
    "key": "cppu_police_tech",
    "code": "0838",
    "institution": "中国人民警察大学",
    "department": "智慧警务学院、警务装备技术学院、防火工程学院（公安技术方向研究生导师）",
    "discipline": "公安技术",
    # 师资队伍 → 研究生导师。单页静态名录，无分页。
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：整页导航、页脚都在 div.sr_inner7 外面。
CONTAINER = "div.sr_inner7"
UNIT_BOX = "div.inner-items"
UNIT_HEADING = "div.inner-hd h3"
NAME_ENTRY = "div.inner-cont li h4"

# 与 0838 公安技术五个方向对应的教学单位中，本模块收录的三个。
IN_SCOPE = (
    "智慧警务学院",
    "警务装备技术学院",
    "防火工程学院",
)

# 明确不收录的单位：公安学、法学、思政、指挥、救援、维和、国际执法等。
OUT_OF_SCOPE = (
    "移民管理学院",
    "侦查学院",
    "警务指挥学院",
    "特勤学院",
    "公安政治学院",
    "公安法学院",
    "涉外安保学院",
    "救援指挥学院",
    "维和警察培训中心",
    "国际执法合作学院",
)

# 姓名后可能粘连职称后缀；剥掉后再用 NAME_RE 校验。
_TITLE_SUFFIX = re.compile(
    r"(?:博士研究生导师|硕士研究生导师|博士生导师|硕士生导师|"
    r"助理研究员|副研究员|高级工程师|高级实验师|助理实验师|"
    r"副教授|教授|研究员|讲师|助教|院士|高工|工程师|实验师|教官|导师|博士后)+$"
)
# 剥完仍含职称字样，说明结构变了，不能当人名收下。
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师|教官|工程师|实验师")
_LATIN = re.compile(r"[A-Za-z]")
# 容器里若出现这些栏目词，说明分页/导航被并进了名录，直接抛错而不是当人名。
_NAV_NOISE = frozenset({
    "首页", "上页", "下页", "上一页", "下一页", "尾页", "末页",
    "师资队伍", "研究生导师", "队伍概况", "师德标兵", "名师风采", "人才引进",
})


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _note(unit: str) -> str:
    return (
        f"学校「师资队伍 → 研究生导师」按教学单位分组公布（所属：{unit}）；"
        "该页只列姓名，不提供个人详情页，故 homepage 回落名录页；"
        "名录未列职称与个人研究方向，direction 一律为“方向待补”。"
        "公安技术一级学科含智慧警务与大数据技术、智能警用装备技术、"
        "涉火涉爆犯罪侦查技术等方向，分别由上述教学单位承担；"
        "同一单位同时承担公安情报学、消防工程等其他学科，故本来源为"
        "单位级归类，不代替逐人学科认定。导师资格与招生方向以当年招生公告为准。"
    )


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse the CPPU graduate-supervisor page into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = soup.select_one(CONTAINER)
    if root is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    skipped_non_cjk: list[str] = []
    selected_entries = 0

    for box in root.select(UNIT_BOX):
        heading = box.select_one(UNIT_HEADING)
        unit = _norm(heading.get_text(" ", strip=True)) if heading is not None else ""
        if unit not in IN_SCOPE:
            # 默认拒绝：未登记的单位不会悄悄混进来。
            continue

        entries = box.select(NAME_ENTRY)
        selected_entries += len(entries)
        for node in entries:
            name = _norm(node.get_text(" ", strip=True))
            if not name:
                raise ValueError(f"{unit} 名录出现空姓名（{url}）")
            name = _TITLE_SUFFIX.sub("", name)

            if _LATIN.search(name):
                # 非中文姓名：不音译、不截断，显式跳过并计数（红线 1）。
                skipped_non_cjk.append(name)
                continue
            if name in _NAV_NOISE:
                raise ValueError(f"{unit} 名录容器里出现导航词：{name!r}（{url}）")
            if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
                raise ValueError(f"{unit} 名录出现无法识别为姓名的条目：{name!r}（{url}）")
            if name in seen:
                raise ValueError(f"同一页出现重复导师：{name!r}（{url}）")
            seen.add(name)

            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, url, url, "学校研究生导师名录", _note(unit),
            ))

    # 红线 4：三个单位的容器条目数必须等于「解析数 + 非中文跳过数」。
    accounted = len(rows) + len(skipped_non_cjk)
    if selected_entries != accounted:
        raise ValueError(
            f"研究生导师名录解析不完整：三个单位容器内 {selected_entries} 个条目，"
            f"解析出 {len(rows)} 条、非中文姓名跳过 {len(skipped_non_cjk)} 条（{url}）。"
            "请检查页面结构。"
        )
    return rows
