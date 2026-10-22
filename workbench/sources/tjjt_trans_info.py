"""同济大学 交通运输工程学院「交通信息与控制系」师资名录（0823 交通运输工程）.

入口是学院「师资队伍 → 教师名录」的静态页::

    https://tjjt.tongji.edu.cn/szdw1/jsml.htm

该页把学院五个系／中心**一次性服务端渲染**在同一张静态 HTML 上，不依赖脚本、接口或
翻页（``div#content`` 下恰好 5 组 ``h4`` 系名 + 5 个 ``div.xilie`` 人员格）::

    div#content
      h4                              ← 系名，例如「交通信息与控制系」
      div.xilie                       ← 一个系一个人员格
        div.xilie_xm > a[href]        ← 一个教师一个条目，href 指向个人详情页

实测 2026-10-22 五组条目数：交通设施系 63、交通运输规划与管理系 55、交通信息与控制系 35、
车辆与载运系 23、磁浮交通工程技术研究中心 21，合计 197 条（其中「交通设施系」有 1 位
外文姓名 Mohsen Alae，按红线 1 显式跳过、不音译不截断，故该系可入库 62 人）。

为什么只收「交通信息与控制系」这一个系
--------------------------------------

0823 交通运输工程现为 60 条 / 2 所，上海海事大学一家 48 条（80.0%），已远超 60% 的
集中度上限。净新增人数 N 既不能太小（压不下上海海事），也不能太大（同济会变成新的
独大），求解如下（新增若全给同一所学校）：

* 把上海海事大学压到 60% 以下：48/(60+N) < 60%  ⇒  N ≥ 21（本批 N 的**下界**）；
* 同济自己不能超过 60%：N/(60+N) < 60%  ⇒  N ≤ 89（本批 N 的**上界**，很宽松）；
* 但项目另有一条更严的口径：新校人数不得高于现有主导校（否则只是把「一家独大」从
  上海海事平移到同济）——同济 N 人与上海海事 48 人相比，要求 N ≤ 48。上一轮 0839 把
  东南大学四个系 74 人全并进来，74/(34+74) = 68.5% 仍然不达标，就是踩了这条线。

所以本批的窗口是 **21 ≤ N ≤ 48**：N ≥ 21 才压得下上海海事，N ≤ 48 才不会自己变成新的
独大（N = 48 时同济 48/108 = 44.4%，与上海海事打平，仍在上限内）。

五个系／中心全部属于 0823（交通信息工程及控制、交通运输规划与管理、道路与铁道工程、
载运工具运用工程等二级学科），但没有切法能既 ≥21 又 ≤48 且不硬拆：取 63 或 55 都越过
上界，取 63+55 更不行。因此本模块**只收交通信息与控制系**（082302 交通信息工程及控制
方向）35 人：上海海事大学 48/95 = 50.5%、同济 35/95 = 36.8%，两校都在 60% 以下。
其余四个系／中心同属 0823，**留作各自独立的来源模块**（不是遗漏），本模块文档与每条
备注都写明覆盖范围；后续补进来时同样受上面那条上界约束。

口径说明
--------

* ``department`` 记为「交通运输工程学院·交通信息与控制系」：既有学院，也有页面自己的
  系名，不含党委／工会／办公室一类行政机构。
* 名录只按系公布，不列个人研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`，
  绝不拿职称顶替方向（红线 2）。
* ``homepage`` 取 ``div.xilie_xm`` 内锚的 href，指向个人详情页 ``/info/2996/<id>.htm``
  （2996 是本系在学院站内的栏目号），不是名录页本身（红线 5）。
* 名录页模板**不含任何邮箱与电话**（实测全文「电话」「邮箱」「@」各 0 处），因此名录页
  快照无需脱敏；个人详情页模板则带「邮箱：…」，本模块从不读取详情页，只取其 URL，
  并在测试里用一份**已脱敏**的详情页快照证明：详情页里的联系方式既不进快照也不进行。
* 姓名节点是纯姓名；仍按红线 1 剥一次职称后缀并用 ``NAME_RE`` 全匹配，双重保险。
  外文姓名、带不可剥后缀的条目一律**显式跳过并计数**，用
  「容器条目数 = 解析数 + 跳过数」硬核对（见 :func:`parse_with_stats`）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://tjjt.tongji.edu.cn/szdw1/jsml.htm"

SPECS = ({
    "key": "tjjt_trans_info",
    "code": "0823",
    "institution": "同济大学",
    "department": "交通运输工程学院·交通信息与控制系",
    "discipline": "交通运输工程",
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：系名在 ``h4``，人员格是它紧邻的 ``div.xilie``；容器外的导航、页头、
# 页脚、以及**其他四个系**的人员格一律不进入解析。
CONTENT = "div#content"
SECTION = "h4"
CONTAINER = "div.xilie"
ENTRY = "div.xilie_xm"

# 本来源只收这一个系。
TARGET_UNIT = "交通信息与控制系"

# 页面上的五个系／中心，只用于错误信息里提示"结构变了没有"。
UNITS = ("交通设施系", "交通运输规划与管理系", "交通信息与控制系",
         "车辆与载运系", "磁浮交通工程技术研究中心")

# 本系在页面上的条目数（逐个数自页面自身的人员格）。
EXPECTED_ROSTER = 35

# 红线 1 的兜底：万一姓名节点是「姓名+职称」拼接，先剥后缀再交给 NAME_RE 全匹配。
# 长词优先，否则「副研究员」会被「研究员」剥成「副」。
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|研究员|副教授|教授|讲师|高工|院士)+$"
)


def _norm(text: str) -> str:
    """压掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _unit_box(soup):
    """按容器自己的系名找到目标系的 ``div.xilie``；找不到返回 None。"""
    content = soup.select_one(CONTENT)
    if content is None:
        return None
    for heading in content.select(SECTION):
        if _norm(heading.get_text(" ", strip=True)) != TARGET_UNIT:
            continue
        box = heading.find_next_sibling("div", class_="xilie")
        if box is not None:
            return box
    return None


def clean_name(text: str) -> str:
    """剥掉可能粘在姓名后面的职称；剥完不是合法姓名则返回空串。"""
    stripped = TITLE_SUFFIX.sub("", _norm(text))
    return stripped if NAME_RE.fullmatch(stripped) else ""


def _note() -> str:
    return ("学院「师资队伍 → 教师名录」按系公布的在册教师；名录未列个人研究方向，"
            "故方向字段为「方向待补」，不拿职称顶替方向。本来源只覆盖交通信息与控制系，"
            "学院另四个系／中心（交通设施系、交通运输规划与管理系、车辆与载运系、"
            "磁浮交通工程技术研究中心）同属 0823，另建来源，不在本条范围内；"
            "导师资格与招生专业以当年招生公告为准。")


def parse_with_stats(html: str, url: str, spec: dict) -> tuple[list[dict], list[str]]:
    """解析一个名录页，返回 (行, 被显式跳过的条目原文)。

    跳过的条目单独返回而不是静默丢弃：外文姓名（不音译、不截断）、无法剥净职称的
    拼接串、同名重复，都进 ``skipped``；随后用「容器条目数 = 解析数 + 跳过数」核对，
    对不上就抛错，交给契约测试暴露结构变化。
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    box = _unit_box(soup)
    if box is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return [], []

    entries = box.select(ENTRY)
    rows: list[dict] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for item in entries:
        anchor = item.select_one("a[href]")
        if anchor is None:
            # 结构残缺的条目不计入任何桶，直接让下面的守恒核对报错。
            continue
        raw = item.get_text(" ", strip=True)
        name = clean_name(raw)
        if not name or name in seen:
            skipped.append(_norm(raw))
            continue
        seen.add(name)
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, urljoin(url, anchor["href"]), url,
            "学院师资队伍·教师名录（按系）", _note(),
        ))

    # 红线 4 + 红线 1：容器内条目 = 解析数 + 跳过数，差一个就说明有人被静默丢掉了。
    if len(rows) + len(skipped) != len(entries):
        raise ValueError(
            f"{TARGET_UNIT} 名录解析不完整：容器内 {len(entries)} 个条目，解析出 "
            f"{len(rows)} 人 + 跳过 {len(skipped)} 条 = {len(rows) + len(skipped)}，对不上。"
            f"请检查 {url} 的页面结构（系名是否仍为 {UNITS}）。")
    return rows, skipped


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse the 同济大学交通运输工程学院 交通信息与控制系 roster page."""
    return parse_with_stats(html, url, spec)[0]
