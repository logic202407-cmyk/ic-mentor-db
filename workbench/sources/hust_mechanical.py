"""华中科技大学机械科学与工程学院 师资队伍「教师名录（全体）」名录（0802 机械工程）。

学院官网「师资队伍 → 教师名录 → 全体」是一张服务端渲染的静态页：``div.js_menu``
里先是一排拼音首字母锚点（``ol > li > a``，``#A``…``#Z``），随后按字母分成 24 组
（A/E/I/K/N/O 六组为空），每组::

    <div class="munu_js" id="C">
      <h6>C</h6>                                  ← 拼音首字母
      <div class="js_bt">
        <ul>
          <li><a href="../../../info/1142/1334.htm" target="_blank">陈文斌（双聘）</a></li>
          …
        </ul>
      </div>
    </div>

也就是说名单完全在 HTML 里，普通 GET 就能拿到，不需要执行脚本、也没有 JSON 接口。
字母分组只是检索用的索引，不是院系，所以本模块**不用字母当院系**，而是读每人链接里
的栏目编号 ``/info/<栏目编号>/<文章编号>.htm``。

栏目编号 → 单位名不是猜的：学院另有一页「单位列表」
（``szdw/jsml/dwlb.htm``），它把 10 个教研单位各做成一张独立名录页。本模块逐页
取回这 10 页，与其栏目编号做过**集合相等**核对（``1142`` 智能制造装备与技术全国
重点实验室 65 人、``1143`` 制造装备数字化国家工程研究中心 24 人、``1144`` 国家企业
信息化支撑软件工程技术研究中心 22 人、``1145`` 国家数控系统工程技术研究中心 23 人、
``1146`` 工艺装备及自动化系 10 人、``1147`` 机械设计与汽车工程系 15 人、``1148``
机械电子信息工程系 26 人、``1149`` 仪器科学与技术系 19 人、``1150`` 流体动力控制
工程系 17 人、``1151`` 工业及制造系统工程系 10 人），因此这里的映射是站点自证的。
映射表里没有的栏目编号一律回落到学院名，不会瞎猜一个单位。

**为什么只挂「全体」这一页，而不按 10 个单位各建一个 SPECS 条目**：这 10 个单位的
名录页彼此**有重名**——李培根、沈卫明、高亮、刘琼、饶运清、管在林、邓超、朱海平、
邱浩波、张超勇、李新宇 11 位同时挂在「工业及制造系统工程系」和「制造装备数字化
国家工程研究中心」名下，逐单位建条目会让这 11 位各出两行（采集器的去重键含院系，
跨条目无法合并），正是本项目反复避免的"同一个人多条记录"。「全体」页由学院自己
给每人**只归一处**（上列 11 位都归在 ``1143``），既保留单位归属又保证一人一行：
本页 232 条链接对应 232 个人，页内无重名。

**分页**：``max_pages=1``，``listing`` 里没有 ``{page}`` 占位符。依据是页面自身
没有任何「每页 N 记录 / 总共 M 记录 / 页码 i/j」标记（同站文章列表页会写出这三种，
本页一处都没有，``div`` 上也没有 ``wp_paging``/``listcon`` 之类的分页容器），
24 个字母组的 232 条链接全部在同一次响应里。10 个单位页同样各自单页
（``div.fy`` 的分页块只有"1"，首页/上页/下页/尾页四个按钮全部是 ``p_fun_d`` 禁用态、
没有 href），所以「全体」页也不是被截断的前 N 条。

**姓名口径**：页面上 8 位把兼职身份写在姓名后面，形如 ``陈文斌（双聘）``。``（双聘）``
是聘任状态而不是姓名的一部分，本模块去掉这个尾缀再校验姓名，并把「页面标注（双聘）」
写进备注——不丢人，也不把括号当姓名。去掉尾缀后页内仍无重名。

**研究方向**：名录页只列姓名与个人页链接，**不列职称，也不列研究方向**，所以每一条
的方向都是 :data:`NO_DIRECTION`（项目红线 2：不猜方向、不拿职称顶替）。个人页
``homepage`` 逐条记录，采集器的 ``--enrich`` 环节可以据此再读个人页上的研究方向。

**刻意不合并的相邻栏目**（避免给同一个人造出重复行）：

* 「院士风采」是教师名录的子集（熊有伦、丁汉、李培根、周济、尤政等都在本页里）。
* 「研究生导师」（148 人）与教师名录重叠 145 人；它是另一种切法，不合并。
* 「兼职教师」页是名誉教授／顾问教授／客座教授／企业兼职教授，多为非汉字姓名且
  本身不是本院专任教师。
* 「实验工程人员」页是"工作人员及职责"的叙述段落（并逐段带邮箱），不是一人一行的
  名录，故不建来源、也不读取其中的任何联系方式。
* 「博士后」（40 人）是在站培养岗位而不是教师职称，与 ``whu_hydropower.py``／
  ``hust.py`` 同一口径不计入。
* 「离退休人员」「人才招聘」不在教学科研人员范围内。

**本来源的缺口（如实记录）**：① 只覆盖机械科学与工程学院的教师名录，不代表华中
科技大学 0802 学科的全部师资（其他院系/中心的机械工程导师不在本页）；②「研究生
导师」页上有 3 位（教师名录未收）不在本来源里，为了不给同一人制造重复行、也不为
个别姓名另建来源，这 3 位没有单独补录；③ 名录不含研究方向，232 位方向一律待补；
④ 不读取任何联系方式（项目红线 1），页面本身也不列联系方式，只有页脚一处学院
总机与学院邮箱，解析器根本不碰页脚。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "hust_mechanical",
    "code": "0802",
    "institution": "华中科技大学",
    "department": "机械科学与工程学院",
    "discipline": "机械工程",
    # 师资队伍 → 教师名录 → 全体。单页静态名录，无分页（依据见模块 docstring）。
    "listing": "https://mse.hust.edu.cn/szdw/jsml/jsml/qb.htm",
    "max_pages": 1,
},)

# 名录页链接里的栏目编号 → 教研单位。已与学院「单位列表」的 10 张单位页做过集合相等
# 核对（见 docstring）；映射表里没有的编号回落到学院名，绝不推测。
COLUMN_UNIT = {
    "1142": "智能制造装备与技术全国重点实验室",
    "1143": "制造装备数字化国家工程研究中心",
    "1144": "国家企业信息化支撑软件工程技术研究中心",
    "1145": "国家数控系统工程技术研究中心",
    "1146": "工艺装备及自动化系",
    "1147": "机械设计与汽车工程系",
    "1148": "机械电子信息工程系",
    "1149": "仪器科学与技术系",
    "1150": "流体动力控制工程系",
    "1151": "工业及制造系统工程系",
}
COLUMN_RE = re.compile(r"/info/(\d+)/")
# 姓名尾缀的聘任状态标记：「双聘」是状态，不是姓名。全角/半角括号都见过。
JOINT_MARK = re.compile(r"[（(]\s*双聘\s*[）)]\s*$")
# 只有 div.js_menu 内的 div.js_bt 才是名单；其余列表是导航与字母索引。
ROOT_BOX = "div.js_menu"
GROUP_BOX = "munu_js"
LIST_BOX = "js_bt"
# 能通过 NAME_RE 但其实是栏目/单位/导航的串（防御用；本页实测 0 命中）。
NAV_NOISE = re.compile(r"^(首页|上页|下页|尾页|末页|返回|更多|全部|教师名录|师资队伍|"
                       r"单位列表|学院概况|学院简介|现任领导|国家平台|教研单位|职能科室|"
                       r"科学研究|人才培养|社会服务|国际交流|校友专栏|常用下载|"
                       r"院士风采|研究生导师|兼职教师|实验工程人员|博士后|离退休人员|"
                       r"人才招聘|系|中心|研究所|实验室|学院)$")


def _squash(text: str) -> str:
    """取文本并去掉**所有**空白，含全角空格 U+3000 与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _split_person(raw: str) -> tuple[str, bool]:
    """把 ``陈文斌（双聘）`` 拆成 (``陈文斌``, True)；没有尾缀时原样返回。"""
    joint = bool(JOINT_MARK.search(raw))
    return JOINT_MARK.sub("", raw), joint


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = soup.select_one(ROOT_BOX)
    if root is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for group in root.find_all("div", class_=GROUP_BOX):
        for anchor in group.select(f"div.{LIST_BOX} ul li a"):
            raw = _squash(anchor.get_text(" ", strip=True))
            name, joint = _split_person(raw)
            if not name or not NAME_RE.fullmatch(name) or NAV_NOISE.fullmatch(name):
                # 拼音字母、导航文字与非汉字姓名都不猜。
                continue
            if name in seen:
                continue
            seen.add(name)
            href = (anchor.get("href") or "").strip()
            homepage = url if href in ("", "#") or href.startswith("javascript") \
                else urljoin(url, href)
            column = COLUMN_RE.search(href)
            unit = COLUMN_UNIT.get(column.group(1), "") if column else ""
            unit = unit or spec["department"]
            detail = "，页面在姓名后标注「（双聘）」" if joint else ""
            note = (f"华中科技大学机械科学与工程学院「师资队伍 → 教师名录（全体）」"
                    f"按姓名拼音首字母列出，页面把此人归在「{unit}」"
                    f"（单位取自名录页个人链接的栏目编号，已与学院「单位列表」的 10 张"
                    f"单位名录页逐一核对）{detail}；"
                    f"名录页只列姓名与个人页链接，不列职称与研究方向，方向待补。"
                    f"本来源只含该学院教师名录，不含研究生导师名单、兼职教师、"
                    f"实验工程人员、博士后与离退休人员，故不代表全院或全校人员；"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, homepage, url, "学院教师名录（全体）", note,
            ))
    return rows
