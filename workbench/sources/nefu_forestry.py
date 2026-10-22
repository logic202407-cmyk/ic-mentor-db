"""东北林业大学 材料科学与工程学院「师资队伍」两页（0829 林业工程）.

全国开设 0829 林业工程一级学科的单位本来就少：第四轮学科评估公开结果只有
东北林业大学、南京林业大学、北京林业大学、福建农林大学、中南林业科技大学、
浙江农林大学、西南林业大学、内蒙古农业大学、北华大学 9 所高校（另加已入库的
中国林业科学研究院）；2012 年那一轮参评的还有安徽农业大学、广西大学。本轮把
「全国只有一所」证伪，只需要在这些单位里找到一所**能公开、逐人、可点开**的名录。

实测（2026-10-23，普通 GET）：多数林科院校的学院子站当前不可达（TLS 握手被重置，
见报告），但东北林业大学材料科学与工程学院的两个学科级师资页可以直达，并且
每个人一个 ``/info/<栏目号>/<id>.htm`` 个人详情页：

======================  ============================================  ====
页面                    入口                                           人数
======================  ============================================  ====
木材科学与工程          ``xkjs/szdw/mckxygc.htm``（1043/1044/1045）     40
林产化工                ``xkjs/szdw/lchg.htm``（1046/1047）             21
======================  ============================================  ====

两页都在「学科建设 → 师资队伍」之下，按 教授 / 副教授 / 讲师 分组，标题分别写作
「木材科学与工程」「林产化工」。前者对应二级学科 082902 木材科学与技术、后者对应
082903 林产化学加工工程，都隶属 0829 林业工程，归属由学院自己的学科栏目给出，
不是按关键词猜的。

算术（判据 ``max(原主导, N) / (原总数 + N) < 60%``）
----------------------------------------------------

0829 现为 49 条 / 1 所（中国林业科学研究院 100%）。把原主导压到 60% 以下需
``49 / (49 + N) < 0.6`` ⇒ **N ≥ 33**；补入方自己不得成为新的独大需
``N / (49 + N) < 0.6`` ⇒ **N ≤ 73**。本模块 N = 40 + 21 = **61**，落在 [33, 73]：

* 补后总量 110；中国林业科学研究院 ``49 / 110 = 44.55%``；东北林业大学
  ``61 / 110 = 55.45%``；最大机构 55.45% < 60%。

口径
----

* ``department`` 记到学院下的专业/学科页名，两页各自成串。
* 名录只按职称分组，不列研究方向，故 ``direction`` 一律 ``NO_DIRECTION``；
  「教授 / 副教授 / 讲师」只写进来源说明，绝不当方向（红线 2）。
* 姓名取锚文本。木材页首位锚文本是「李坚院士简介」，需剥掉「院士简介」这一页面
  自带后缀；剥后用 ``NAME_RE`` 全匹配兜底（红线 1）。拉丁字母姓名显式跳过并计数。
* 容器守卫：``div.li1`` 内 ``ul > li`` 的条目数必须等于解析行数 + 跳过数，对不上
  就抛错（红线 4）。
* ``homepage`` 取每条的 ``/info/<栏目号>/<id>.htm`` 个人页，不回落名录页（红线 5）。
* 联系方式（红线 1）：两页正文不含邮箱与电话，页脚也没有联系方式行；落盘快照仍
  统一跑过脱敏通道，落盘后 EMAIL / PHONE 两条正则均无残留。解析器只读
  ``div.li1`` 里的姓名与 href，不读页脚。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = (
    {
        "key": "nefu_forestry_wood",
        "code": "0829",
        "institution": "东北林业大学",
        "department": "材料科学与工程学院·木材科学与工程（木材科学与技术）",
        "discipline": "林业工程",
        "listing": "https://cailiao.nefu.edu.cn/xkjs/szdw/mckxygc.htm",
        "max_pages": 1,
    },
    {
        "key": "nefu_forestry_chem",
        "code": "0829",
        "institution": "东北林业大学",
        "department": "材料科学与工程学院·林产化工（林产化学加工工程）",
        "discipline": "林业工程",
        "listing": "https://cailiao.nefu.edu.cn/xkjs/szdw/lchg.htm",
        "max_pages": 1,
    },
)

BLOCK = "div.li1"
RANKS = ("教授", "副教授", "讲师")
# 页面自带的姓名后缀：木材页首位是「李坚院士简介」，其余条目是纯姓名。
_TITLE_SUFFIX = re.compile(r"(?:院士简介|个人简介|简介)$")
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师")
_LATIN = re.compile(r"[A-Za-z]")
_NAV_NOISE = frozenset({"首页", "上页", "下页", "尾页", "教授", "副教授", "讲师"})
PERSON_HREF = re.compile(r"^https://cailiao\.nefu\.edu\.cn/info/10(?:4[3-8])/\d+\.htm$")
SOURCE_KIND = "学院学科建设·师资队伍"

EXPECTED = {"nefu_forestry_wood": 40, "nefu_forestry_chem": 21}


def _norm(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _clean_name(text: str) -> str:
    return _TITLE_SUFFIX.sub("", _norm(text))


def _note(department: str, rank: str) -> str:
    return (
        "东北林业大学材料科学与工程学院「学科建设 → 师资队伍」名录，按职称分组公布"
        f"（{department}；职称：{rank}）。名录只列姓名与职称，未列个人研究方向，"
        "故方向字段为「方向待补」，职称只写进来源说明、不作为研究方向。"
        "导师资格与招生专业以当年招生公告为准。"
    )


def parse_with_stats(html: str, url: str, spec: dict) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    blocks = soup.select(BLOCK)
    if not blocks:
        raise ValueError(f"师资页没有 div.li1 容器，页面结构变了：{url}")

    rows: list[dict] = []
    skipped_non_cjk: list[str] = []
    skipped_duplicate: list[str] = []
    seen: set[str] = set()
    total_entries = 0
    ranks: list[str] = []

    for block in blocks:
        heading = block.select_one("h1")
        rank = _norm(heading.get_text(" ", strip=True)) if heading else ""
        if rank not in RANKS:
            raise ValueError(f"师资页出现未登记的职称分组：{rank!r}（{url}）")
        ranks.append(rank)
        entries = block.select("ul > li")
        total_entries += len(entries)
        for item in entries:
            anchor = item.select_one("a[href]")
            if anchor is None:
                raise ValueError(f"{rank} 分组里有条目缺少个人页链接：{url}")
            homepage = urljoin(url, (anchor.get("href") or "").strip())
            if not PERSON_HREF.fullmatch(homepage):
                raise ValueError(f"条目的链接不是个人详情页：{homepage!r}（{url}）")
            name = _clean_name(anchor.get_text(" ", strip=True))
            if not name:
                raise ValueError(f"{rank} 分组里有姓名为空的条目：{url}")
            if _LATIN.search(name):
                skipped_non_cjk.append(name)
                continue
            if name in _NAV_NOISE:
                raise ValueError(f"师资容器里出现导航词：{name!r}（{url}）")
            if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
                raise ValueError(f"无法识别为姓名的条目：{name!r}（{url}）")
            if name in seen:
                skipped_duplicate.append(name)
                continue
            seen.add(name)
            rows.append(roster_row(
                name, spec["institution"], spec["department"], spec["code"],
                NO_DIRECTION, homepage, url, SOURCE_KIND,
                _note(spec["department"], rank),
            ))

    accounted = len(rows) + len(skipped_non_cjk) + len(skipped_duplicate)
    if total_entries != accounted:
        raise ValueError(
            f"师资页解析不完整：容器内 {total_entries} 个条目，解析 {len(rows)} 条、"
            f"非中文姓名跳过 {len(skipped_non_cjk)} 条、重复 {len(skipped_duplicate)} 条"
            f"（{url}）"
        )
    expected = EXPECTED.get(spec["key"])
    if expected is not None and len(rows) != expected:
        raise ValueError(
            f"师资页人数与登记值不符：期望 {expected}，实际 {len(rows)}（{url}）"
        )
    return rows, {
        "entries": total_entries,
        "ranks": ranks,
        "skipped_non_cjk": skipped_non_cjk,
        "skipped_duplicate": skipped_duplicate,
    }


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one 东北林业大学 材料科学与工程学院 师资队伍 page."""
    return parse_with_stats(html, url, spec)[0]
