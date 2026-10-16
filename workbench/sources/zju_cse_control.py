"""浙江大学控制科学与工程学院 教师名录（0811 控制科学与工程）.

学院官网「人事工作 → 师资队伍」下有六个栏目：院士、国家级高层次人才、
国家级青年人才、教师、机关教工、实验中心。其中 **教师** 一页
(``/39568/list.htm``) 是全院教学科研岗最完整的一份名单：它把五个研究所的
在册教师一次性全部渲染在同一张静态页上，普通 GET 即可拿到，不依赖任何脚本
或接口::

    <div class="con1r tea-con">
      <div class="teacher-box1">
        <h3 class="research-name">工业控制研究所</h3>      ← 研究所标题
        <div frag="窗口40" portletmode="simpleNews">
          <div id="wp_news_w40">
            <ul class="teacher-list">
              <li class="teacher-item">
                <a href="/2022/0706/c72508a2660272/page.htm">柴利</a>   ← 姓名
              </li>
              …
            </ul>
          </div>
        </div>
        <h3 class="research-name">智能系统与控制研究所</h3>  ← 下一个研究所
        <div frag="窗口41" …> … </div>
        …

**布局要点**：``h3.research-name`` 与装着名单的 ``div`` 是 ``div.teacher-box1``
下的**同级兄弟**、按文档顺序交替出现。因此本模块只遍历 ``div.teacher-box1`` 的
**直接子元素**，遇到 ``h3`` 就更新所名、遇到 ``div`` 才取名单；若改用扁平的
``find_all('div')`` 遍历，研究所标题会被内层容器覆盖，五个所会串成一个。

五个研究所与 CMS 栏目号一一对应（正文链接形如 ``/c<栏目号>a<文章号>/page.htm``）：
工业控制研究所 72508（24 人）、智能系统与控制研究所 72509（43 人）、
智能感知与检测研究所 72510（13 人）、工业智能与系统工程研究所 72511（18 人，
含一位非汉字姓名 ``Anjan Tula``）、控制装备及综合安全研究所 72521（10 人），
合计 108 条，全部都在这一页上。

**分页判定**：本页正文里**没有任何**记录数/页码标记——同站其它栏目都会写出
“每页 N 记录 / 总共 M 记录 / 页码 i/j”（如国家级青年人才页写作“每页14记录 /
总共21记录 / 页码1/2”），本页一处都没有；另外 ``list2.htm`` 与 ``list3.htm``
返回的是同一份聚合内容（同样五个所、同样 108 条），说明该页不是分页列表。
故 ``max_pages`` 取 1，``listing`` 里也不放 ``{page}`` 占位符。

**口径说明**：

* 只收 **教师** 一页。院士（1 人）、国家级高层次人才（13 人）、国家级青年人才
  （21 人）三份名单都是教师名单的**子集**（例如孙优贤、柴利、陈积明、苏宏业等
  同时出现在两处），把它们并进同一套 ``SPECS`` 只会给同一个人产出多行；因此
  本来源不含这三页。
* ``机关教工``（17 人）是行政岗位，属合同第 5 条要跳过的非教学单位，不收录。
* ``实验中心``（7 人，实验师/高级工程师序列）用的是另一套模板（``div.con1rmr``
  卡片），且与教师名单不重叠；本轮不含该页，故本来源**不代表学院全部人员**。
* 名字里的空白（含全角空格）在校验前全部剔除；非汉字姓名（``Anjan Tula``）
  不符合 ``NAME_RE``，宁缺勿猜，直接跳过 → 实际入库 107 条。
* 该页只给姓名与个人页链接，**不写职称、不写研究方向**，故方向一律为
  :data:`NO_DIRECTION`；研究所名写进 ``department`` 与备注，绝不进入方向字段。
* 页面本身没有任何联系方式，且本模块只读 ``<a>`` 的文本与 href；``mailto:`` /
  ``tel:`` 链接一律丢弃，不会成为 ``homepage``。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "zju_cse_control",
    "code": "0811",
    "institution": "浙江大学",
    "department": "控制科学与工程学院",
    "discipline": "控制科学与工程",
    # 人事工作 → 师资队伍 → 教师；五个研究所的全部在册教师都在这一页，无分页。
    "listing": "http://www.cse.zju.edu.cn/39568/list.htm",
    "max_pages": 1,
},)

# 名录容器：只有它里面是教师名单，导航与页脚都在它外面。
ROSTER_BOX = "div.teacher-box1"
# 研究所标题；它与名单容器在 ROSTER_BOX 下同级交替出现。
GROUP_HEAD = "h3"
GROUP_HEAD_CLASS = "research-name"
# 名单：ul.teacher-list > li.teacher-item > a（锚文本即姓名）。
LIST_ITEM = "ul.teacher-list li.teacher-item"
# 非教学单位（合同第 5 条）。本页五个研究所都不会命中，保留作为防御。
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|工会|离退休|办公室|机关|人事|财务|教务|"
                                 r"学生工作|行政|校友|后勤")
# 导航文字而不是姓名。
NAV_NOISE = re.compile(r"^(首页|上一页|下一页|尾页|末页|第一页|返回|更多|教师|"
                       r"师资队伍|教师名录|实验中心|机关教工|院士|"
                       r"国家级高层次人才|国家级青年人才)$")
# 绝不允许成为 homepage 的联系方式协议。
CONTACT_SCHEME = re.compile(r"^(mailto|tel|fax|sms):", re.I)


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格（“张 三”）与 ``&nbsp;``。

    必须先去空白再做任何切分，否则“张 三”会被拆成两个人。
    """
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def _homepage(anchor, url: str) -> str:
    """个人页链接；``mailto:``/``tel:`` 以及非 http(s) 一律回落到名录页。"""
    href = (anchor.get("href") or "").strip()
    if not href or href == "#" or href.startswith("javascript") or CONTACT_SCHEME.match(href):
        return url
    absolute = urljoin(url, href)
    return absolute if urlparse(absolute).scheme in ("http", "https") else url


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    box = soup.select_one(ROSTER_BOX)
    if box is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    institute = ""
    # 只遍历名录容器的直接子元素，保持文档顺序：研究所标题给下一份名单定组。
    for child in box.find_all(recursive=False):
        if child.name == GROUP_HEAD and GROUP_HEAD_CLASS in (child.get("class") or []):
            text = _compact(child)
            if text:
                institute = text
            continue
        for item in child.select(LIST_ITEM):
            anchor = item.find("a")
            if anchor is None:
                continue
            name = _compact(anchor)
            if not NAME_RE.fullmatch(name) or NAV_NOISE.fullmatch(name) or name in seen:
                continue
            unit = institute or spec["department"]
            if ADMINISTRATIVE_UNIT.search(unit):
                continue
            seen.add(name)
            note = ("浙江大学控制科学与工程学院「师资队伍 → 教师」按研究所公布"
                    f"（研究所：{unit}）；名录只列姓名与个人页链接，"
                    f"不含个人职称与研究方向。本来源覆盖该页五个研究所的全部在册教师，"
                    f"不含机关教工、实验中心与原列于院士/国家级人才栏目的名单；"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, _homepage(anchor, url), url,
                "学院师资名录（按研究所）", note,
            ))
    return rows
