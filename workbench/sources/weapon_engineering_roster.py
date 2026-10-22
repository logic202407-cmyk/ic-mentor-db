"""北京理工大学 机电学院兵器四系 + 西安工业大学 兵器学院（0826 兵器科学与技术）.

0826 是三个学科里最容易被判成「全国只有一所」的：第四轮学科评估只公开了 9 所
（北京理工大学 A+、南京理工大学 A+、西北工业大学 B、空军工程大学 B-、火箭军
工程大学 B-、解放军理工大学 C+、装备学院 C、中北大学 C-、海军工程大学 C-），
军事科学院（已入库 104 条）不在公开评估名单里。本轮普查确认：**设点单位不止一所，
但能公开逐人点开的极少**——

* 北京理工大学机电学院「师资名录」按兵器系静态分页，每系一页、每人一个
  ``/szdw/szml/<系>/qb0X/<32位十六进制>.htm`` 个人页（实测 2026-10-23）；
* 西安工业大学兵器科学与技术学院「师资队伍」两页同样是静态名录 + 个人页；
* 南京理工大学机械工程学院返回 202 挑战页、西北工业大学机电学院名录只有纯文本
  姓名无个人链接、中北大学/沈阳理工大学/长春理工大学/重庆理工大学等学院子站
  TLS 握手被重置（见报告）。

本模块只纳入**补入量落在判据区间内**的单位：

=====================================  ==============================  ====
来源                                    入口                            人数
=====================================  ==============================  ====
北理工 机电学院·兵器飞航系              ``szml/wrfhgcx/qb01/``            29
北理工 机电学院·兵器控制系              ``szml/jdxtgcx/qb02/``            29
北理工 机电学院·兵器力学系              ``szml/lxgcx/qb03/``              35
北理工 机电学院·兵器能源系              ``szml/nyydlgcx/qb04/``           31
西安工业大学 兵器学院·二三级教授        ``szdw/esjjs.htm``                 8
西安工业大学 兵器学院·硕士博士导师      ``szdw/ssbsds.htm``                7
=====================================  ==============================  ====

北理工另有兵器探测系（19 人）与兵器智能系（38 人）两页未纳入：全纳入会使补入量
达到 181，突破 ``N ≤ 155`` 的上限；其中兵器智能系的栏目路径指向「智能机器人
研究所」，归入 0826 的把握也弱于前四个系。

算术（判据 ``max(原主导, N) / (原总数 + N) < 60%``）
----------------------------------------------------

0826 现为 104 条 / 1 所（军事科学院 100%）。压到 60% 以下需
``104 / (104 + N) < 0.6`` ⇒ **N ≥ 70**；补入方自身不得独大需
``N / (104 + N) < 0.6`` ⇒ **N ≤ 155**。本模块 N = 124 + 15 = **139**，落在
[70, 155]：

* 补后总量 243；军事科学院 ``104 / 243 = 42.80%``；北京理工大学
  ``124 / 243 = 51.03%``；西安工业大学 ``15 / 243 = 6.17%``；最大机构
  51.03% < 60%。

口径
----

* 北理工四条按页面自己的系名成串；西安工业大学两条按「二三级教授 / 硕士博士导师」
  分组。两组页面都属兵器科学与技术学院/兵器系，归属由学院与系名给出。
* 北理工页面是「全部职称」卡片：姓名在卡片的 ``div.title``，同卡片的 ``div.info``
  含职称与联系方式；解析器**只读 div.title 与 href，完全不读 div.info**，因此
  联系方式不会进入任何字段（红线 1）。
* 名录不列研究方向，故 ``direction`` 一律 ``NO_DIRECTION``；职称只写进来源说明，
  绝不当方向（红线 2）。
* 姓名取锚文本/卡片标题，压掉空白后用 ``NAME_RE`` 全匹配兜底（红线 1）。拉丁字母
  姓名显式跳过并计数；同一页/跨页重复姓名显式去重并计数。
* 容器守卫：条目数 = 解析行数 + 跳过数 + 重复数，对不上就抛错（红线 4）。
* ``homepage`` 取每条的详情页，不回落名录页（红线 5）。
* 联系方式（红线 1）：北理工页面正文含邮箱，落盘快照在写入前已把邮箱替换为
  「联系方式已隐去」，落盘后 EMAIL / PHONE 两条正则均无残留；解析器本身不读
  这些字段。西安工业大学两页不含联系方式。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = (
    {
        "key": "bit_weapon_flight",
        "code": "0826",
        "institution": "北京理工大学",
        "department": "机电学院·兵器飞航系",
        "discipline": "兵器科学与技术",
        "listing": "https://smen.bit.edu.cn/szdw/szml/wrfhgcx/qb01/",
        "max_pages": 1,
    },
    {
        "key": "bit_weapon_control",
        "code": "0826",
        "institution": "北京理工大学",
        "department": "机电学院·兵器控制系",
        "discipline": "兵器科学与技术",
        "listing": "https://smen.bit.edu.cn/szdw/szml/jdxtgcx/qb02/",
        "max_pages": 1,
    },
    {
        "key": "bit_weapon_mechanics",
        "code": "0826",
        "institution": "北京理工大学",
        "department": "机电学院·兵器力学系",
        "discipline": "兵器科学与技术",
        "listing": "https://smen.bit.edu.cn/szdw/szml/lxgcx/qb03/",
        "max_pages": 1,
    },
    {
        "key": "bit_weapon_energy",
        "code": "0826",
        "institution": "北京理工大学",
        "department": "机电学院·兵器能源系",
        "discipline": "兵器科学与技术",
        "listing": "https://smen.bit.edu.cn/szdw/szml/nyydlgcx/qb04/",
        "max_pages": 1,
    },
    {
        "key": "xatu_weapon_professors",
        "code": "0826",
        "institution": "西安工业大学",
        "department": "兵器科学与技术学院·二三级教授",
        "discipline": "兵器科学与技术",
        "listing": "https://bqxy.xatu.edu.cn/szdw/esjjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xatu_weapon_supervisors",
        "code": "0826",
        "institution": "西安工业大学",
        "department": "兵器科学与技术学院·硕士博士导师",
        "discipline": "兵器科学与技术",
        "listing": "https://bqxy.xatu.edu.cn/szdw/ssbsds.htm",
        "max_pages": 1,
    },
)

BIT_CARD_LIST = "div.sub_031b ul"
# 卡片链接的末级目录是该教师所属的职称分组（qb01 / fgjzc01 / zgjzc01 …），
# 不是固定的「全部」目录，因此两级目录都放宽为字母数字。
BIT_PERSON_HREF = re.compile(
    r"^https://smen\.bit\.edu\.cn/szdw/szml/[a-z0-9]+/[a-z0-9]+/[0-9a-f]{32}\.htm$"
)
XATU_LIST = "ul.list-teacher"
XATU_PERSON_HREF = re.compile(r"^https://bqxy\.xatu\.edu\.cn/info/10\d\d/\d+\.htm$")

_LATIN = re.compile(r"[A-Za-z]")
_RANK_IN_NAME = re.compile(r"教授|讲师|研究员|高工|院士|博士后|导师")
_NAV_NOISE = frozenset({"首页", "上页", "下页", "尾页", "全部", "正高级职称", "副高级职称"})

SOURCE_KIND_BIT = "学院师资队伍·师资名录（按系）"
SOURCE_KIND_XATU = "学院师资队伍"

EXPECTED = {
    "bit_weapon_flight": 29,
    "bit_weapon_control": 29,
    "bit_weapon_mechanics": 35,
    "bit_weapon_energy": 31,
    "xatu_weapon_professors": 8,
    "xatu_weapon_supervisors": 7,
}


def _norm(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _note(department: str) -> str:
    return (
        "学院「师资队伍」名录按兵器系/导师组公布"
        f"（{department}）。名录只列姓名（北理工卡片另列职称），未列个人研究方向，"
        "故方向字段为「方向待补」，职称只写进来源说明、不作为研究方向。"
        "导师资格与招生专业以当年招生公告为准。"
    )


def _bit_parse(soup: BeautifulSoup, url: str, spec: dict):
    rows, skipped, duplicates = [], [], []
    seen: set[str] = set()
    entries = 0
    for group in soup.select(BIT_CARD_LIST):
        for item in group.select("li"):
            entries += 1
            anchor = item.select_one("a[href]")
            if anchor is None:
                raise ValueError(f"兵器系卡片缺少个人页链接：{url}")
            homepage = urljoin(url, (anchor.get("href") or "").strip())
            if not BIT_PERSON_HREF.fullmatch(homepage):
                raise ValueError(f"兵器系卡片链接不是个人详情页：{homepage!r}（{url}）")
            title = anchor.select_one("div.title")
            if title is None:
                raise ValueError(f"兵器系卡片缺少姓名节点 div.title：{url}")
            name = _norm(title.get_text(" ", strip=True))
            if not name:
                raise ValueError(f"兵器系卡片姓名为空：{url}")
            if _LATIN.search(name):
                skipped.append(name)
                continue
            if name in _NAV_NOISE:
                raise ValueError(f"兵器系卡片出现导航词：{name!r}（{url}）")
            if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
                raise ValueError(f"无法识别为姓名的卡片标题：{name!r}（{url}）")
            if name in seen:
                duplicates.append(name)
                continue
            seen.add(name)
            rows.append(roster_row(
                name, spec["institution"], spec["department"], spec["code"],
                NO_DIRECTION, homepage, url, SOURCE_KIND_BIT,
                _note(spec["department"]),
            ))
    return rows, entries, skipped, duplicates


def _xatu_parse(soup: BeautifulSoup, url: str, spec: dict):
    rows, skipped, duplicates = [], [], []
    seen: set[str] = set()
    holder = soup.select_one(XATU_LIST)
    if holder is None:
        raise ValueError(f"兵器学院名录缺少 ul.list-teacher 容器：{url}")
    entries = holder.select("li")
    for item in entries:
        anchor = item.select_one("a[href]")
        if anchor is None:
            raise ValueError(f"兵器学院名录条目缺少个人页链接：{url}")
        homepage = urljoin(url, (anchor.get("href") or "").strip())
        if not XATU_PERSON_HREF.fullmatch(homepage):
            raise ValueError(f"兵器学院名录链接不是个人详情页：{homepage!r}（{url}）")
        name = _norm(anchor.get_text(" ", strip=True))
        if not name:
            raise ValueError(f"兵器学院名录姓名为空：{url}")
        if _LATIN.search(name):
            skipped.append(name)
            continue
        if name in _NAV_NOISE:
            raise ValueError(f"兵器学院名录出现导航词：{name!r}（{url}）")
        if not NAME_RE.fullmatch(name) or _RANK_IN_NAME.search(name):
            raise ValueError(f"无法识别为姓名的条目：{name!r}（{url}）")
        if name in seen:
            duplicates.append(name)
            continue
        seen.add(name)
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, homepage, url, SOURCE_KIND_XATU,
            _note(spec["department"]),
        ))
    return rows, len(entries), skipped, duplicates


def parse_with_stats(html: str, url: str, spec: dict) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    if "smen.bit.edu.cn" in spec["listing"]:
        rows, entries, skipped, duplicates = _bit_parse(soup, url, spec)
    elif "bqxy.xatu.edu.cn" in spec["listing"]:
        rows, entries, skipped, duplicates = _xatu_parse(soup, url, spec)
    else:  # pragma: no cover - 防御：来源模块只服务这两套站点
        raise ValueError(f"未登记的名录站点：{url}")

    accounted = len(rows) + len(skipped) + len(duplicates)
    if entries != accounted:
        raise ValueError(
            f"兵器名录解析不完整：容器内 {entries} 个条目，解析 {len(rows)} 条、"
            f"非中文姓名跳过 {len(skipped)} 条、重复 {len(duplicates)} 条（{url}）"
        )
    expected = EXPECTED.get(spec["key"])
    if expected is not None and len(rows) != expected:
        raise ValueError(
            f"兵器名录人数与登记值不符：期望 {expected}，实际 {len(rows)}（{url}）"
        )
    return rows, {
        "entries": entries,
        "skipped_non_cjk": skipped,
        "skipped_duplicate": duplicates,
    }


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse one 北理工兵器系 / 西安工业大学兵器学院 roster page."""
    return parse_with_stats(html, url, spec)[0]
