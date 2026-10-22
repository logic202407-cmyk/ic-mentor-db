"""青岛大学 纺织服装学院「教师名录」两页（0821 纺织科学与工程）.

0821 全国设点单位同样极少：第四轮学科评估公开的只有 11 所，其中具有博士授权的
7 所（天津工业大学、东华大学、苏州大学、江南大学、浙江理工大学、武汉纺织大学、
西安工程大学），另有青岛大学、大连工业大学、中原工学院、四川大学等硕士单位。
东华大学已入库 61 条，本轮只需要再找一所**名录可点开、逐人可核**的单位。

实测（2026-10-23，普通 GET）：天津工业大学、苏州大学、江南大学、浙江理工大学、
武汉纺织大学、西安工程大学、大连工业大学、中原工学院等学院子站当前 TLS 握手
被重置（见报告），四川大学轻工学院的师资页是脚本壳页；青岛大学纺织服装学院的
静态教师名录可直达，每人一个 ``/info/<栏目号>/<id>.htm`` 个人页：

==========================  =======================================  ====
页面                        入口                                     人数
==========================  =======================================  ====
纺织工程系                   ``szdw/jsml/fzgcx.htm``                  44
服装设计与工程系             ``szdw/jsml/fzsjygcx.htm``               13
==========================  =======================================  ====

两页都在「师资队伍 → 教师名录」之下，按 教授 / 副教授 / 讲师 / 助理教授 分组。
纺织工程系对应 082101 纺织工程，服装设计与工程系对应 082104 服装设计与工程，
都隶属 0821 纺织科学与工程。学院另有「轻化工程系」（45 人，082103）与
「非织造材料与工程系」，本轮**不纳入**：补入量会突破判据上限（见下），
留作下一批来源，不是页面不可用。

算术（判据 ``max(原主导, N) / (原总数 + N) < 60%``）
----------------------------------------------------

0821 现为 61 条 / 1 所（东华大学 100%）。压到 60% 以下需
``61 / (61 + N) < 0.6`` ⇒ **N ≥ 41**；补入方自身不得独大需
``N / (61 + N) < 0.6`` ⇒ **N ≤ 91**。本模块 N = 44 + 13 = **57**，落在 [41, 91]：

* 补后总量 118；东华大学 ``61 / 118 = 51.69%``；青岛大学 ``57 / 118 = 48.31%``；
  最大机构 51.69% < 60%。

口径
----

* ``department`` 记到学院下的系名，两页各自成串。
* 名录只按职称分组，不列研究方向，故 ``direction`` 一律 ``NO_DIRECTION``；
  「教授 / 副教授 / 讲师 / 助理教授」只写进来源说明，绝不当方向（红线 2）。
* 姓名取锚文本，压掉空白后用 ``NAME_RE`` 全匹配兜底（红线 1）。拉丁字母姓名
  显式跳过并计数。
* 服装设计与工程系页面把同一位教师列了两次（同一姓名、两个条目），按姓名去重并
  **显式计数**；容器守卫：条目数 = 解析行数 + 跳过数 + 重复数，对不上就抛错。
* ``homepage`` 取每条的 ``/info/<栏目号>/<id>.htm`` 个人页，不回落名录页（红线 5）。
* 联系方式（红线 1）：两页正文不含邮箱与电话，页脚也没有联系方式行；落盘快照仍
  统一跑过脱敏通道，落盘后 EMAIL / PHONE 两条正则均无残留。解析器只读
  ``div.subProminent01`` 里的姓名与 href，不读页脚。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = (
    {
        "key": "qdu_textile_engineering",
        "code": "0821",
        "institution": "青岛大学",
        "department": "纺织服装学院·纺织工程系",
        "discipline": "纺织科学与工程",
        "listing": "https://ctc.qdu.edu.cn/szdw/jsml/fzgcx.htm",
        "max_pages": 1,
    },
    {
        "key": "qdu_costume_engineering",
        "code": "0821",
        "institution": "青岛大学",
        "department": "纺织服装学院·服装设计与工程系",
        "discipline": "纺织科学与工程",
        "listing": "https://ctc.qdu.edu.cn/szdw/jsml/fzsjygcx.htm",
        "max_pages": 1,
    },
)

BLOCK = "div.subProminent01"
ENTRY_LIST = "ul.subProminentList"
RANKS = ("教授", "副教授", "讲师", "助理教授")
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师")
_LATIN = re.compile(r"[A-Za-z]")
_NAV_NOISE = frozenset({"首页", "上页", "下页", "尾页", "教授", "副教授", "讲师", "助理教授"})
PERSON_HREF = re.compile(r"^https://ctc\.qdu\.edu\.cn/info/11\d\d/\d+\.htm$")
SOURCE_KIND = "学院师资队伍·教师名录"

EXPECTED = {"qdu_textile_engineering": 44, "qdu_costume_engineering": 13}


def _norm(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _note(department: str, rank: str) -> str:
    return (
        "青岛大学纺织服装学院「师资队伍 → 教师名录」名录，按职称分组公布"
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
        raise ValueError(f"教师名录没有 div.subProminent01 容器，页面结构变了：{url}")

    rows: list[dict] = []
    skipped_non_cjk: list[str] = []
    skipped_duplicate: list[str] = []
    seen: set[str] = set()
    total_entries = 0
    ranks: list[str] = []

    for block in blocks:
        heading = block.select_one("h3")
        rank = _norm(heading.get_text(" ", strip=True)) if heading else ""
        if rank not in RANKS:
            raise ValueError(f"教师名录出现未登记的职称分组：{rank!r}（{url}）")
        ranks.append(rank)
        entries = block.select(f"{ENTRY_LIST} > li")
        total_entries += len(entries)
        for item in entries:
            anchor = item.select_one("a[href]")
            if anchor is None:
                raise ValueError(f"{rank} 分组里有条目缺少个人页链接：{url}")
            homepage = urljoin(url, (anchor.get("href") or "").strip())
            if not PERSON_HREF.fullmatch(homepage):
                raise ValueError(f"条目的链接不是个人详情页：{homepage!r}（{url}）")
            name = _norm(anchor.get_text(" ", strip=True))
            if not name:
                raise ValueError(f"{rank} 分组里有姓名为空的条目：{url}")
            if _LATIN.search(name):
                skipped_non_cjk.append(name)
                continue
            if name in _NAV_NOISE:
                raise ValueError(f"教师名录容器里出现导航词：{name!r}（{url}）")
            if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
                raise ValueError(f"无法识别为姓名的条目：{name!r}（{url}）")
            if name in seen:
                # 同一位教师在同一页被列两次（实测服装设计与工程系有一例）。
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
            f"教师名录解析不完整：容器内 {total_entries} 个条目，解析 {len(rows)} 条、"
            f"非中文姓名跳过 {len(skipped_non_cjk)} 条、重复 {len(skipped_duplicate)} 条"
            f"（{url}）"
        )
    expected = EXPECTED.get(spec["key"])
    if expected is not None and len(rows) != expected:
        raise ValueError(
            f"教师名录人数与登记值不符：期望 {expected}，实际 {len(rows)}（{url}）"
        )
    return rows, {
        "entries": total_entries,
        "ranks": ranks,
        "skipped_non_cjk": skipped_non_cjk,
        "skipped_duplicate": skipped_duplicate,
    }


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one 青岛大学 纺织服装学院 教师名录 page."""
    return parse_with_stats(html, url, spec)[0]
