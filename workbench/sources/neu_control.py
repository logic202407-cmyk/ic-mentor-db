"""东北大学信息科学与工程学院 教师名录（0811 控制科学与工程）.

学院「师资队伍 → 教师名录 → 按部门」页把在岗教师按 **研究所** 分组，每个研究所一个
``h3.sublist_title`` 标题，标题本身是指向该所独立名录页的链接::

    <h3 class="sublist_title"><a href="/znjsyyyyjs/list.htm">智能技术与应用研究所</a></h3>

因此本模块按**研究所**各建一个 ``SPECS`` 条目（共用同一个 ``parse``），而不是只挂
总览页：每条记录因此能带上「这个人属于哪个研究所」，院系字段不再是笼统的学院名。
总览页 101 位、23 个研究所，各单位之间没有重名（实测重叠 0）。

口径说明：

* 名录页只给姓名与所属研究所，**不写研究方向**，故方向一律 :data:`NO_DIRECTION`；
  研究所名只作为院系与备注，绝不进入方向字段（项目红线 2）。
* 不读取任何联系方式字段（项目红线 1）。
* 学院还有「按职称」的三份名录（教授／副教授／讲师）。它们与「按部门」是**同一批人
  的两种切法**，合并会产生重复条目，故不并入。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "http://www.ise.neu.edu.cn"

# 学院「教师名录 → 按部门」下的各研究所名录页。总览页：
# http://www.ise.neu.edu.cn/js/list.htm （101 位，23 个研究所）
_INSTITUTES = (
    ("智能技术与应用研究所", "znjsyyyyjs"),
    ("智能系统研究所", "znxtyjs"),
    ("智能控制与安全研究所", "znkzyaqyjs"),
    ("工业智能与优化研究所", "gyrgznyyhyjs"),
    ("无人系统自主控制研究所", "wrxtzzkzyjs"),
    ("智能感知与机器人研究所", "zngzyjqryjs"),
    ("信息物理系统控制与安全性研究所", "xxwlxtkzyaqxyjs"),
    ("图像识别与机器智能研究所", "txsbyjqznyjs"),
    ("机器学习与智能决策研究所", "jqxxyznjcyjs"),
    ("数据智能与系统工程研究所", "sjznyxtgcyjs"),
    ("深度学习与先进智能决策研究所", "sdxxyxjznjcyjs"),
    ("流程工业综合自动化国家重点实验室", "6043"),
    ("电气自动化研究所", "dqzdhyjs"),
)

SPECS = tuple({
    "key": f"neu_{slug}",
    "code": "0811",
    "institution": "东北大学",
    "department": name,
    "discipline": "控制科学与工程",
    "listing": f"{_BASE}/{slug}/list.htm",
    "max_pages": 1,
} for name, slug in _INSTITUTES)

# 名录容器；只有它内部才是教师，导航与页脚都在它外面。
ROOT_BOX = "div.container_right"
# 人员详情页链接形如 /2022/0708/c1415a216438/page.htm —— 指向文章而非另一个列表。
PERSON_HREF = re.compile(r"/\d{4}/\d{4}/c\d+a\d+/page\.htm")


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = soup.select_one(ROOT_BOX) or soup.body or soup
    unit = spec["department"]
    rows: list[dict] = []
    seen: set[str] = set()
    for anchor in root.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = _compact(anchor)
        if not NAME_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        homepage = urljoin(url, href)
        note = (f"学院教师名录「按部门」下的研究所名录页（所属：{unit}）；"
                f"名录只列姓名与所属研究所，未列个人研究方向。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], unit, spec["code"],
            NO_DIRECTION, homepage, url, "学院教师名录（按部门）", note,
        ))
    return rows
