"""山东科技大学 测绘与空间信息学院「师资总览」名录（0816 测绘科学与技术）.

入口是学院「师资队伍 → 师资总览」的静态页::

    https://gc.sdust.edu.cn/szdw/szzl.htm

该页把学院七个单元**一次性服务端渲染**在同一张静态 HTML 上，不依赖脚本、接口或
翻页（实测 2026-10-23 普通 GET 即可拿全，无「下一页」「共 N 条」一类分页控件）::

    div.teacher_zhpgae
      div.teacher_item                  ← 一个单元（系 / 办公室 / 中心）
        div.tit > p                     ← 单元名，例如「测绘工程系」
        h2.teacher_zitem                ← 职称分组，例如「教授」
        div.teacher_list > ul > li > a  ← 一个人一个条目，href 指向个人详情页

实测七个单元的 ``li`` 条目数：综合办公室 6、学生工作办公室 9、实验中心 6、
测绘工程系 29（教授 14 / 副教授 12 / 讲师 3）、地理信息科学系 19（8 / 6 / 5）、
遥感科学与技术系 20（7 / 8 / 5）、海洋测绘系 20（10 / 9 / 1），合计 **109 条**，
109 个互不相同的姓名与 109 个互不相同的个人详情页。

为什么收 88 人而不是 109 条
-------------------------

「师资总览」把党政管理、学生工作与实验教辅也列在同一页上：

* 综合办公室 6 人（党委书记、办公室主任等党政管理岗）；
* 学生工作办公室 9 人（辅导员）；
* 实验中心 6 人（实验教辅；页面未给职称分组，个人页也没有正文可核）。

这三类都不是教学科研岗，按项目口径（跳过党委／工会／办公室等非教学单位）**显式
跳过并计数**，不进名录。四个系 88 人（教授 39 / 副教授 35 / 讲师 14）是专任教师，
构成本来源的全部行。容器守恒：109 = 88 条解析 + 21 条非教学单位排除 + 0 条非中文
姓名跳过，对不上就抛错，不返回残缺名单。

算术（为什么是 88）
------------------

0816 测绘科学与技术现为 **126 条 / 2 所**：武汉大学 114 条（90.48%）、中国科学院
大学 12 条（9.52%）。唯一判据是 ``max(原主导, 补入量 N) / (原总数 + N) < 60%``：

* 把武汉大学压到 60% 以下：``114 / (126 + N) < 0.6`` ⇒ **N ≥ 65**；
* 自己不得变成新的独大：``N / (126 + N) < 0.6`` ⇒ ``N ≤ 188``。

本模块 N = 88，落在 [65, 188] 内：补后总量 214，武汉大学 ``114 / 214 = 53.27%``、
山东科技大学 ``88 / 214 = 41.12%``，最大机构 53.27% < 60%。

口径说明
--------

* ``department`` 记为「测绘与空间信息学院·<系名>」：既有学院，也有页面自己的系名，
  四个系各自成串，不含综合办公室／学生工作办公室／实验中心。
* 名录按系与职称分组，不列个人研究方向，因此每行 ``direction`` 一律
  :data:`NO_DIRECTION`（「方向待补」）；「教授 / 副教授 / 讲师」是职称，只写进来源
  说明，绝不当作方向（红线 2）。
* 姓名取锚文本，正常是纯姓名，个别带全角空格（如「刘  峰」）；解析先压掉空白，
  再剥掉页面自带的标记符与可能的职称后缀，最后用 ``NAME_RE`` 全匹配兜底（红线 1）。
  拉丁字母姓名**显式跳过并计数**，不音译、不截断。
* 页面上有 13 个姓名末尾带 ``*``（个人详情页的标题也带）。抽样详情页显示这些人是
  「学术教授 / 学术副教授」系列；站点没有解释该标记的含义，故本模块只把标记从姓名
  里剥掉，不据此推断职称或聘任类型（不造数据）。
* 容器守卫：七个单元的 ``li`` 条目数必须等于「解析行数 + 非中文姓名跳过数 +
  非教学单位排除数」；对不上就抛错（红线 4）。
* 联系方式（红线 3）：名录页模板**不含邮箱与电话**（页脚只有一个「电话：… 邮箱：…」
  行，实测各一处）。落盘的名录快照在写入前已把这两处替换为「联系方式已隐去」，
  落盘后 EMAIL / PHONE 两条正则均无残留；解析器只读 ``div.teacher_item`` 里的姓名、
  职称分组与 href，从不读取页脚，也不读取个人详情页。
* ``homepage`` 取每个条目的 ``a[href]``，指向学院个人详情页
  ``gc.sdust.edu.cn/info/<栏目号>/<id>.htm``；栏目号须不属于综合办公室（1083）、
  学生工作办公室（1084）、实验中心（1085）这三个非教学栏目，也不允许回落成名录页
  本身（红线 5）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://gc.sdust.edu.cn/szdw/szzl.htm"

SPECS = ({
    "key": "sdust_survey",
    "code": "0816",
    "institution": "山东科技大学",
    "department": "测绘与空间信息学院",
    "discipline": "测绘科学与技术",
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：页头、导航、面包屑、页脚都在 div.teacher_zhpgae 外面。
CONTAINER = "div.teacher_zhpgae"
BLOCK = "div.teacher_item"
UNIT_TITLE = "div.tit p"
RANK_HEADING = "h2.teacher_zitem"
ENTRY_LIST = "div.teacher_list"

# 教学科研单位（收录）与非教学单位（显式排除，只计数不建行）。
TEACHING_UNITS = ("测绘工程系", "地理信息科学系", "遥感科学与技术系", "海洋测绘系")
SUPPORT_UNITS = ("综合办公室", "学生工作办公室", "实验中心")

# 页面给教学科研岗用的三个职称分组标题；出现新标题说明结构变了，应该有人复核。
TEACHING_RANKS = ("教授", "副教授", "讲师")

# 本页七个单元的条目数（逐个数自页面自身的人员格），供审计与测试核对。
EXPECTED_ENTRIES = 109
EXPECTED_ROWS = 88
EXPECTED_SUPPORT = {"综合办公室": 6, "学生工作办公室": 9, "实验中心": 6}

# 姓名后可能粘连页面标记符（* / ＊）或职称后缀；剥掉后再用 NAME_RE 校验。
# 长词在前，避免「副研究员」被「研究员」剥成「副」。
_MARKER = re.compile(r"[*＊]+$")
_TITLE_SUFFIX = re.compile(
    r"(?:博士生导师|硕士生导师|助理研究员|副研究员|准聘副教授|助理教授|"
    r"副教授|教授|研究员|讲师|院士|高工|博士后)+$"
)
# 剥完仍含职称字样，说明结构变了，不能当人名收下。
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师")
_LATIN = re.compile(r"[A-Za-z]")
# 容器里若出现这些栏目词，说明分页/导航被并进了名录，直接抛错而不是当人名。
_NAV_NOISE = frozenset({
    "首页", "上页", "下页", "上一页", "下一页", "尾页", "末页", "查看更多",
    "师资队伍", "师资总览", "教师名录", "测绘工程系", "地理信息科学系",
    "遥感科学与技术系", "海洋测绘系", "综合办公室", "学生工作办公室", "实验中心",
})

# 个人详情页：学院新闻系统的 /info/<栏目号>/<id>.htm；名录页/栏目页一律拒绝。
PERSON_HREF = re.compile(r"^https://gc\.sdust\.edu\.cn/info/(\d+)/\d+\.htm$")
# 三个非教学栏目：即使出现在教学系的人员格里也说明结构错了，不能当个人页收下。
NON_TEACHING_CATEGORIES = frozenset({"1083", "1084", "1085"})

# 拉丁字母姓名：不音译、不截断，显式跳过并计数。本批 109 个条目全是汉字姓名，
# 故登记集合为空；若将来出现外籍教师，应把其原名登记到这里。
SKIPPED_NON_CJK: frozenset[str] = frozenset()

SOURCE_KIND = "学院师资队伍（师资总览）"


def _norm(text: str) -> str:
    """去掉所有空白，含全角空格（U+3000）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _department(unit: str) -> str:
    return f"测绘与空间信息学院·{unit}"


def _note(unit: str, rank: str) -> str:
    return (
        "山东科技大学测绘与空间信息学院「师资队伍 → 师资总览」名录，按系与职称"
        f"分组公布（系：{unit}；职称：{rank}）。名录只列姓名与职称，未列个人研究"
        "方向，故方向字段为「方向待补」，职称只写进来源说明、不作为研究方向。"
        "学院名录同时列出综合办公室、学生工作办公室、实验中心等非教学单位人员，"
        "本来源不纳入；导师资格与招生专业以当年招生公告为准。"
    )


def _clean_name(text: str) -> str:
    """压空白、剥页面标记符与可能的职称后缀，返回候选姓名（未校验）。"""
    name = _norm(text)
    name = _MARKER.sub("", name)
    return _TITLE_SUFFIX.sub("", name)


def parse_with_stats(html: str, url: str, spec: dict) -> tuple[list[dict], dict]:
    """解析「师资总览」一页，返回 (行, 统计)。

    统计里 ``entries`` 是容器内的 ``li`` 总数，``skipped_non_cjk`` 是非中文姓名，
    ``excluded`` 是按范围排除的非教学单位人数。三者与行数必须守恒。
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    container = soup.select_one(CONTAINER)
    if container is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return [], {"entries": 0, "skipped_non_cjk": [], "excluded": {}}

    blocks = container.select(BLOCK)
    if not blocks:
        raise ValueError(f"师资总览容器里没有单元块，页面结构变了：{url}")

    # 人员格只能长在单元块里；若容器里出现游离的 teacher_list，说明结构变了。
    block_lists = sum(len(block.select(ENTRY_LIST)) for block in blocks)
    if len(container.select(ENTRY_LIST)) != block_lists:
        raise ValueError(f"师资总览里出现单元块之外的人员格，页面结构变了：{url}")

    rows: list[dict] = []
    skipped_non_cjk: list[str] = []
    excluded: dict[str, int] = {}
    seen_names: set[str] = set()
    seen_pages: set[str] = set()
    total_entries = 0
    seen_units: list[str] = []
    visited_lists = 0

    for block in blocks:
        title_node = block.select_one(UNIT_TITLE)
        if title_node is None:
            raise ValueError(f"师资总览的单元块缺少单元名：{url}")
        unit = _norm(title_node.get_text(" ", strip=True))
        seen_units.append(unit)
        rank = ""

        for child in block.children:
            if getattr(child, "name", None) is None:
                continue
            classes = child.get("class") or []
            if child.name == "h2" and "teacher_zitem" in classes:
                rank = _norm(child.get_text(" ", strip=True))
                continue
            if not (child.name == "div" and "teacher_list" in classes):
                continue

            entries = child.select("li")
            visited_lists += 1
            total_entries += len(entries)

            if unit in SUPPORT_UNITS:
                # 党政管理 / 学生工作 / 实验教辅：按范围排除，显式计数而不是静默丢弃。
                excluded[unit] = excluded.get(unit, 0) + len(entries)
                continue
            if unit not in TEACHING_UNITS:
                raise ValueError(f"师资总览出现未登记的单元：{unit!r}（{url}）")
            if rank not in TEACHING_RANKS:
                raise ValueError(
                    f"{unit} 的人员格不在已知职称分组下（当前分组：{rank or '空'}），"
                    f"页面结构变了：{url}"
                )

            for item in entries:
                anchor = item.select_one("a[href]")
                if anchor is None:
                    raise ValueError(f"{unit} 的条目缺少个人页链接：{url}")
                homepage = urljoin(url, (anchor.get("href") or "").strip())
                match = PERSON_HREF.fullmatch(homepage)
                if match is None or match.group(1) in NON_TEACHING_CATEGORIES:
                    raise ValueError(
                        f"条目的链接不是教学科研岗的个人详情页：{homepage!r}（{url}）"
                    )

                name = _clean_name(anchor.get_text(" ", strip=True))
                if not name:
                    raise ValueError(f"{unit} 的某条目姓名为空：{url}")
                if _LATIN.search(name):
                    # 非中文姓名：不音译、不截断，显式跳过并计数（红线 1）。
                    skipped_non_cjk.append(name)
                    continue
                if name in _NAV_NOISE:
                    raise ValueError(f"师资总览容器里出现导航词：{name!r}（{url}）")
                if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
                    raise ValueError(
                        f"师资总览出现无法识别为姓名的条目：{name!r}（{url}）"
                    )
                if name in seen_names or homepage in seen_pages:
                    raise ValueError(f"同一页出现重复教师：{name!r}（{url}）")
                seen_names.add(name)
                seen_pages.add(homepage)

                rows.append(roster_row(
                    name, spec["institution"], _department(unit), spec["code"],
                    NO_DIRECTION, homepage, url, SOURCE_KIND, _note(unit, rank),
                ))

    if visited_lists != block_lists:
        # 人员格被套进了别的层（不再是单元块的直接子节点），说明结构变了：
        # 这时按直接子节点遍历会漏人，必须抛错而不是只收看到的那几个格。
        raise ValueError(
            f"师资总览有 {block_lists - visited_lists} 个人员格不在单元块的直接子层，"
            f"页面结构变了：{url}"
        )
    missing = [unit for unit in TEACHING_UNITS if unit not in seen_units]
    if missing:
        # 某个系整块消失（改版、改名或前端改成渲染壳页）时不能假装名录只有剩下的人。
        raise ValueError(f"师资总览缺少教学系：{'、'.join(missing)}（{url}）")
    if not total_entries:
        raise ValueError(f"师资总览的人员格是空的，页面结构变了：{url}")

    # 红线 4：核对「容器内恰好 N 人」——条目数必须等于解析数 + 两类显式跳过数。
    accounted = len(rows) + len(skipped_non_cjk) + sum(excluded.values())
    if total_entries != accounted:
        raise ValueError(
            f"师资总览解析不完整：容器内 {total_entries} 个条目，解析出 {len(rows)} 条、"
            f"非中文姓名跳过 {len(skipped_non_cjk)} 条、非教学单位排除 "
            f"{sum(excluded.values())} 条（{url}）。请检查页面结构。"
        )
    return rows, {
        "entries": total_entries,
        "skipped_non_cjk": skipped_non_cjk,
        "excluded": excluded,
        "units": seen_units,
    }


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one 山东科技大学 测绘与空间信息学院 师资总览 page."""
    return parse_with_stats(html, url, spec)[0]
