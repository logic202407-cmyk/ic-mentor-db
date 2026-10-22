"""四川大学水利水电学院「学者风采」师资名录（0815 水利工程）。

学院把在岗教师按单位拆成多份**服务端直接渲染**的静态 ``.htm`` 名录，路径统一为
``/szdw/xzfc/<单位>.htm``，普通 GET 就能拿到完整名单，不依赖脚本、接口或分页：

* 水利水电工程系                  ``/szdw/xzfc/slsdgcx.htm``         24 人
* 水文与水资源工程系              ``/szdw/xzfc/swyszygcx.htm``       13 人
* 山区河流保护与治理全国重点实验室 ``/szdw/xzfc/sqhlbhyzlqgzdsys.htm`` 66 人

三份名录的结构完全一致：``div.szlist`` 内先给一个职称分组标题，再跟一组卡片::

    <div class="szlist">
      <div class="bt"><p>教授（正高）</p><span>姓名按照拼音首字母排序</span></div>
      <ul class="flex">
        <li><a href="../../info/1028/1273.htm">
              <div class="scale">…头像…</div>
              <div class="con"><h3 style="text-align:center">陈建康</h3></div>
        </a></li>
        …

姓名只出现在卡片 ``h3`` 里，与职称分组标题分处不同节点，不存在「曹德平研究员」这种
姓名—职称拼接；即便如此仍按项目红线先剥一次职称后缀再用 ``NAME_RE`` 校验，双重保险。
``div.szlist`` 之外的 ``li``（顶部导航、左侧栏、相关新闻）一律不进入解析，避免把
2-8 个汉字的导航词当人名——本页侧栏恰好有「水利水电工程系」这类 7 字词条。

口径说明：

* **只收 0815 的三个二级学科对口单位**：水利水电工程系（081504 水利水电工程）、
  水文与水资源工程系（081501 水文学及水资源）、山区河流保护与治理全国重点实验室
  （081502 水力学及河流动力学）。学院里另外三个系分属别的一级学科，故不建来源：
  能源与动力工程系归 0807 动力工程及工程热物理、农业水利工程系归 0828 农业工程
  （农业水土工程）、岩土与地下工程系归 0814 土木工程（岩土工程）。
* 水利水电工程实验中心的页面 ``div.szlist`` 为空、不列任何姓名，因此不为它建条目——
  收录一个解析结果恒为空的来源只会制造“已覆盖”的假象。
* 名录只按职称分组，不写研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`，
  绝不拿职称顶替方向。
* 页面页脚带学院邮箱与联系电话，落快照前已按项目规则整体替换为「联系方式已隐去」；
  解析器从不读取任何联系方式字段。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "https://cwrh.scu.edu.cn"
_SZDW = f"{_BASE}/szdw/xzfc"

SPECS = (
    {
        "key": "scu_water_hydropower",
        "code": "0815",
        "institution": "四川大学",
        "department": "水利水电工程系",
        "discipline": "水利工程",
        "listing": f"{_SZDW}/slsdgcx.htm",
        "max_pages": 1,
    },
    {
        "key": "scu_water_hydrology",
        "code": "0815",
        "institution": "四川大学",
        "department": "水文与水资源工程系",
        "discipline": "水利工程",
        "listing": f"{_SZDW}/swyszygcx.htm",
        "max_pages": 1,
    },
    {
        "key": "scu_water_mountain_river_lab",
        "code": "0815",
        "institution": "四川大学",
        "department": "山区河流保护与治理全国重点实验室",
        "discipline": "水利工程",
        "listing": f"{_SZDW}/sqhlbhyzlqgzdsys.htm",
        "max_pages": 1,
    },
)

# 真正的人员容器：只有 div.szlist 内的卡片是教师名录，其余 ul/li 都是导航与新闻。
ROOT_SELECTOR = "div.szlist"
GROUP_SELECTOR = "div.bt"
PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
# 卡片文字里可能拼着的职称后缀，长的放前面，避免「副研究员」被「研究员」半截匹配。
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|正高工|副高工|研究员|教授|"
    r"副教授|讲师|高工|院士)+$"
)
# 非教学单位（合同第 5 条）。本院三份名录的单位名都不会命中，保留作为防御。
_ADMIN = re.compile(r"党委|党支部|工会|离退休|办公室|机关|行政|人事|财务|教务")
# 职称只是职称，绝不允许整段跑进研究方向（合同红线 2）。
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def clean_name(text: str) -> str:
    """从卡片文字里取姓名：压掉空白、剥掉结尾职称，再交给 ``NAME_RE`` 校验。"""
    raw = re.sub(r"[\s\u3000\xa0]+", "", text or "")
    stripped = TITLE_SUFFIX.sub("", raw)
    return stripped if NAME_RE.fullmatch(stripped) else ""


def _rank_of(group) -> str:
    """职称分组标题里的职称（``教授（正高）``），去空白与“姓名按照…”提示。"""
    text = re.sub(r"[\s\u3000\xa0]+", "", group.get_text(" ", strip=True))
    return re.split(r"姓名", text, maxsplit=1)[0]


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    root = soup.select_one(ROOT_SELECTOR)
    rows: list[dict] = []
    if root is None or _ADMIN.search(spec["department"]):
        return rows

    seen: set[str] = set()
    unit = spec["department"]
    for group in root.select(GROUP_SELECTOR):
        rank = _rank_of(group)
        # 该分组标题之后、下一个分组标题之前的兄弟节点才是本职称的卡片。
        for holder in group.find_next_siblings():
            if "bt" in (holder.get("class") or []):
                break
            for item in holder.select("li"):
                anchor = item.find("a", href=PERSON_HREF)
                heading = item.find("h3")
                if anchor is None or heading is None:
                    continue
                name = clean_name(heading.get_text(" ", strip=True))
                if not name or name in seen:
                    continue
                seen.add(name)
                note = (f"四川大学水利水电学院「师资队伍 → 学者风采 → {unit}」"
                        f"按职称分组列出（本条目所在分组：{rank}）；"
                        f"名录未列个人研究方向。本来源覆盖与 0815 水利工程二级学科"
                        f"对应的三个单位，不代表学院全部人员（能源与动力工程、"
                        f"农业水利工程、岩土与地下工程三系及实验中心未计入）；"
                        f"导师资格与招生专业以当年招生公告为准。")
                rows.append(roster_row(
                    name, spec["institution"], unit, spec["code"],
                    NO_DIRECTION, urljoin(url, anchor["href"]), url,
                    "学院学者风采（按职称）", note,
                ))
    return rows
