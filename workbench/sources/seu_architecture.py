"""东南大学建筑学院 建筑系 师资力量名录（0813 建筑学）.

学院官网的“师资力量”栏目按系所分栏，建筑系的名单挂在 ``/16781/`` 下，是静态
HTML：每页 16 人，页面自称“总共 45 记录 / 页码 1 / 3”，分页地址就是
``list1.htm``、``list2.htm``、``list3.htm``（``list1.htm`` 与 ``list.htm``
同内容），因此正好可以用 ``{page}`` 模板走完三页。

卡片结构（同一页内自洽，不依赖任何外部信息）::

    <div class="col_news_list listcon">
      <div class="news n1">
        <a href="https://arch.seu.edu.cn/wjg/main.htm" target="_blank">
          <div class="con_t">
            <div class="news_title">王建国</div>      ← 姓名
            <div class="news_text">教授</div>         ← 职称
          </div>
          <div class="news_con">…头像…<div class="news-email"></div></div>
        </a>
      </div>
      …

* 只在 ``div.col_news_list.listcon`` 这个名录容器里取人。页面其余部分（导航、
  页脚、相关学科单位）也有大量 ``a``，但它们不在该容器内，不会被读成姓名。
* ``div.news-email`` 字段**从不读取**——项目不保存任何联系方式（页面页脚里
  确实有学院邮箱与电话，一行都不会进入结果）。
* 名录只给姓名与职称，没有个人研究方向；因此方向一律留
  :data:`NO_DIRECTION`，职称只写进来源说明，绝不当作方向。
* 每人卡片上的 ``a[href]`` 指向本人在 ``arch.seu.edu.cn`` 的个人主页
  （``main.htm`` / ``main.psp``），作为 ``homepage``；取不到时回落到名录页。
* 学院另有“城市规划系”（0833 城乡规划学）与“景观学系”（0834 风景园林学）
  的名单，它们属于另外两个一级学科，**不并入** 0813，故本模块只收建筑系。
  建筑历史与理论研究所、建筑技术与科学研究所、基础教学部同样是 0813 的
  教学科研单位，但各自挂在不同的栏目地址上，一个 ``SPECS`` 只能有一个
  ``listing`` 模板，故本来源只覆盖建筑系；如需并集需再加来源。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "seu_architecture",
    "code": "0813",
    "institution": "东南大学",
    "department": "建筑系",
    "discipline": "建筑学",
    # 建筑学院 → 师资力量 → 建筑系；每页 16 人，页码 1 / 3（总共 45 记录）。
    "listing": "https://arch.seu.edu.cn/16781/list{page}.htm",
    "max_pages": 3,
},)

# 名录容器：只有它内部才是教师卡片，导航与页脚都在它外面。
ROSTER_BOX = "div.col_news_list.listcon"
# 卡片内各字段（news-email 有意不列出：联系方式不采集）。
NAME_FIELD = "div.news_title"
RANK_FIELD = "div.news_text"


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格与 ``&nbsp;``，便于 NAME_RE 校验。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    box = soup.select_one(ROSTER_BOX)
    if box is None:
        return []

    rows: list[dict] = []
    for card in box.select("div.news"):
        anchor = card.find("a", href=True)
        name_el = card.select_one(NAME_FIELD)
        if anchor is None or name_el is None:
            continue
        name = _compact(name_el)
        if not NAME_RE.fullmatch(name):
            continue
        rank_el = card.select_one(RANK_FIELD)
        rank = _compact(rank_el) if rank_el is not None else ""
        href = (anchor.get("href") or "").strip()
        homepage = url if href in ("", "#") or href.startswith("javascript") \
            else urljoin(url, href)
        note = (f"学院师资力量栏目按系所公布（{spec['department']}"
                f"{'，职称：' + rank if rank else ''}）；名录未列个人研究方向。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, homepage, url, "学院师资名录（建筑系）", note,
        ))
    return rows
