"""同济大学软件学院 教师名录（0835 软件工程）.

学院官网「师资队伍 → 教师名录（按职称）」是一张静态页，把在岗教师按职称分组，
每组一个 ``div.lanmu_nr`` 容器，容器内的 ``a`` 就是教师姓名并指向本人主页::

    教授
    <div class="lanmu_nr">
      <a href="...">周兴铭</a>
      <a href="...">赵生捷</a>
      …
    </div>
    兼职教授
    <div class="lanmu_nr"> … </div>

因此本模块按文档顺序把「职称标题 → 该组名单」配起来：解析出的每一条都以职称
分组作为 ``department``（例如「教授」「副教授」「讲师」），因为这一页本身只按
职称组织，学院并未给出教研室归属。

三条口径说明：

* 名录里有个别非汉字姓名（如 ``Gonzalo R Arce``）不符合 ``NAME_RE``，会被跳过；
  这类姓名无法可靠核对身份，宁缺勿猜。
* 页面不列个人研究方向，故方向一律为 :data:`NO_DIRECTION`；职称写进
  ``department`` 与备注，绝不进入方向字段（项目红线 2）。
* 不读取任何联系方式字段（项目红线 1）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "tongji_software",
    "code": "0835",
    "institution": "同济大学",
    "department": "软件学院",
    "discipline": "软件工程",
    # 师资队伍 → 教师名录（按职称）。静态页，无分页。
    "listing": "https://sse.tongji.edu.cn/szdw/jsml_azc_.htm",
    "max_pages": 1,
},)

# 名录容器；它内部是「职称标题 div.lanmu_bt」与「该组名单 div.lanmu_nr」交替出现。
ROOT_BOX = "div.right-nr"
HEAD_BOX = "lanmu_bt"
GROUP_BOX = "lanmu_nr"


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = soup.select_one(ROOT_BOX)
    if root is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    group = spec["department"]
    # 只遍历名录容器的直接子元素，保持文档顺序：标题给下一组名单定组。
    for child in root.find_all("div", recursive=False):
        classes = child.get("class") or []
        if HEAD_BOX in classes:
            text = _compact(child)
            if text:
                group = text
            continue
        if GROUP_BOX not in classes:
            continue
        for anchor in child.select("a[href]"):
            name = _compact(anchor)
            if not NAME_RE.fullmatch(name) or name in seen:
                continue
            seen.add(name)
            href = (anchor.get("href") or "").strip()
            homepage = url if href in ("", "#") or href.startswith("javascript") \
                else urljoin(url, href)
            note = (f"学院师资队伍「教师名录（按职称）」按职称分组列出"
                    f"（职称分组：{group}）；名录未列个人研究方向。"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], group, spec["code"],
                NO_DIRECTION, homepage, url, "学院教师名录（按职称）", note,
            ))
    return rows
