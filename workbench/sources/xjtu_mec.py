"""西安交通大学机械工程学院 教师名录（0802 机械工程）.

学院官网「师资队伍 → 教师名录」（``/szdw/jsml.htm``）本身**不列任何教师**：它只是
一个栏目页，列出学院 **11 个研究所/中心**各自的子名录页。真正的名单在子页上，由
服务端直接渲染（WebPlus 静态页，普通 GET 即可拿全，不依赖脚本或接口）::

    div.nyrCon
      div.box.jszhy                      ← 名录容器
        dl
          dd
            ul.flex-left
              <li><a href="https://gr.xjtu.edu.cn/en/web/hrcao"
                      title="曹宏瑞">曹宏瑞</a></li>
              <li><a href="#">          title="聂祥樊（双聘）">聂祥樊（双聘）</a></li>
              …
        div.pb_sys_common                ← 分页条（首页 上页 1 2 下页 尾页）

因此本模块为**每个研究所在册一份 SPECS 条目、共用同一个 parse**（与
``whu_hydropower.py`` 的多条目共用解析一致）。11 个研究所合起来就是学院公布的
整份教师名录，所以这个来源覆盖的是**整个学院**，不是某一个系。

分页（本模块最需要说清的一点）
------------------------------

只有两个研究所的名录超过一页，页面自己的分页条写着「1 2」两个页码，也就是**共 2 页**
（其余 9 个研究所的分页条是「1」，即单页）。WebPlus 的这个分页是**静态文件分页**：

* 第 1 页 = ``/szdw/jsml/<slug>.htm``
* 第 2 页 = ``/szdw/jsml/<slug>/1.htm``   ← 路径下标比页码**小 1**
* （``<slug>/0.htm`` 实测 404，``<slug>/2.htm`` 也 404，``?page=2`` 会被忽略并返回第 1 页，
  都验证过）

采集器只支持从 1 开始的 ``{page}`` 占位符，用它无法同时表示「基准页」与「基准页/1」，
所以这两页被**分别声明成两个条目**（``_p1`` 与 ``_p2``），各自是单次请求
（``max_pages: 1``，listing 里没有占位符）。两份名单的人不重合，合起来才是该研究所的
完整名录；这一点在真机上用两个页面的人数之和验证过（机器人所 40+6、先进制造所 40+37）。

实录（2026-10-15 快照）
-----------------------

11 个研究所 + 2 个第二页共 13 页、**330 条、325 个不同姓名**（各所条数）：

* 国际机械中心 11
* 航空发动机研究所 35
* 航天制造与信息工程研究所 23
* 机器人与智能系统研究所 40 + 6
* 设计科学与基础部件研究所 29
* 医工交叉研究所 11
* 先进制造技术研究所 40 + 37
* 精密工程研究所 39
* 装备智能诊断与控制研究所 27
* 新能源装备与质量工程研究所 15
* 工业产品工程研究所 17

页面上方/侧栏的「专职科研人员 →研究员/副研究员」与「实验技术人员 →正高级/副高级/
中级/初级」以及「博士后」是每个研究所名下的**另一批子页**，实测均为空壳或只是基准页的
子集（航空发动机所：研究员 1 人、副研究员 4 人，5 人全部已在该所基准名录里；六个研究所的
实验技术子页全部 0 人，仅先进制造所有 1 位副高级实验师 ``张会杰`` 不在基准名录里，属已知
缺口）。因此不为其单独建条目——收录一个解析结果为空或纯子集的来源只会制造"已覆盖"的假象。

口径说明
--------

* **名录不列职称，也不列个人研究方向**，所以每一行的 ``direction`` 一律是
  :data:`NO_DIRECTION`（``方向待补``）。学院另有「杰出人才」栏目给部分人标头衔，
  但那是另一份名单，它与名录的重合度无法核实，不作合并；职称也绝不写进方向字段
  （项目红线 2）。
* **双聘教师保留**：5 位教师的锚文本带「（双聘）」后缀（何卫锋、聂祥樊、吴云、吴子祥、
  周留成），姓名取后缀之前的汉字串，并在备注里写明「页面标注：双聘」。这与
  ``tsinghua_me.py`` 排除双聘教授的做法不同——清华把双聘放在**另一个栏目**里，
  而这里双聘者就出现在研究所的在册名录内，属于学院自己公布的该所名录。
* **重名处理**：5 个姓名出现在两个研究所的名录里：``李兵``（航空发动机所/精密工程所）、
  ``王晶``（机器人所/先进制造所）两人的个人主页地址不同（``/en/web/bli`` 与
  ``/en/web/lb``；``/en/web/wangpele666`` 与一个 ``/info/`` 个人页），说明学院内确实存在
  重名；另外 3 个（``李敏``、``毛红威``、``马壮``）两处都指向不区分个人的
  ``gr.xjtu.edu.cn/en/home`` 或 ``#``，页面没有任何可区分字段。本模块对这三种情况一律
  **各所保留一行、各引各自的名录页**，不合并、也不猜谁是谁：合并等于替页面断言同人，
  删一条则等于凭空丢掉一个可能是真人的条目。合计 330 行 / 325 个不同姓名，差额即这 5 行。
* ``department`` 取研究所名（页面自己的分组），没落到笼统的学院名；11 个研究所都是
  科研/教学单位，不含党委、工会、办公室一类非教学单位（合同第 5 条）——学院把行政机构
  另挂在「学院概况 → 行政机构」下，本来源不涉及。
* ``homepage`` 取人名锚点的 href：指向个人主页的（``gr.xjtu.edu.cn/<id>``、
  ``faculty.xjtu.edu.cn/<id>``、学院 ``/info/`` 个人页）原样保留并把
  ``;jsessionid=…`` 这类会话参数去掉；指向 ``http://gr.xjtu.edu.cn/en/home`` 这个
  不区分个人的通用入口、或 ``#`` 的，回落到名录页本身——把 100 多人指到同一个"研究
  主页入口"会被下游 ``--enrich`` 读成同一个人的资料。
* 联系方式（项目红线 1）：名录页本身只有页脚的学院邮箱与座机，快照落盘前已按仓库
  规则脱敏为「联系方式已隐去」，本模块从不读取任何联系方式字段。
* 与学院自报口径的差别：学院「师资概况」自报专业技术队伍 358 人（专任教师 213、
  专职科研 54、博士后 49、实验技术 42）。研究所名录合计 330 条，与这组数字**不是同一
  口径**（名录不标岗位、也没有把博士后单列），因此**不能**把这 330 条读成"213 名专任
  教师"或"全院 358 人"。本来源只表示：学院按研究所公布的在册名录里有这些人。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# 「师资队伍 → 教师名录」下每个研究所一个子名录页；两个分页研究所的第二页是
# ``<slug>/1.htm``（路径下标比页码小 1，见模块文档）。
BASE = "https://mec.xjtu.edu.cn/szdw/jsml/"

SPECS = (
    {
        "key": "xjtu_mec_international_center",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "国际机械中心",
        "discipline": "机械工程",
        "listing": BASE + "gjjxzx.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_aero_engine",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "航空发动机研究所",
        "discipline": "机械工程",
        "listing": BASE + "hkfdjyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_space_manufacturing",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "航天制造与信息工程研究所",
        "discipline": "机械工程",
        "listing": BASE + "htzzyxxgcyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_robotics_p1",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "机器人与智能系统研究所",
        "discipline": "机械工程",
        # 分页条「1 2」：第 1 页就是基准页。
        "listing": BASE + "jqryznxtyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_robotics_p2",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "机器人与智能系统研究所",
        "discipline": "机械工程",
        # 分页条第 2 页 = 基准页下的 1.htm。
        "listing": BASE + "jqryznxtyjs/1.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_design_science",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "设计科学与基础部件研究所",
        "discipline": "机械工程",
        "listing": BASE + "sjkxyjcbjyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_biomedical_cross",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "医工交叉研究所",
        "discipline": "机械工程",
        "listing": BASE + "ygjcyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_advanced_manufacturing_p1",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "先进制造技术研究所",
        "discipline": "机械工程",
        # 分页条「1 2」：第 1 页就是基准页。
        "listing": BASE + "xjzzjsyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_advanced_manufacturing_p2",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "先进制造技术研究所",
        "discipline": "机械工程",
        # 分页条第 2 页 = 基准页下的 1.htm。
        "listing": BASE + "xjzzjsyjs/1.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_precision_engineering",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "精密工程研究所",
        "discipline": "机械工程",
        "listing": BASE + "jmgcyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_equipment_diagnostics",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "装备智能诊断与控制研究所",
        "discipline": "机械工程",
        "listing": BASE + "zbznzdykzyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_new_energy_equipment",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "新能源装备与质量工程研究所",
        "discipline": "机械工程",
        "listing": BASE + "xnyzbyzlgcyjs.htm",
        "max_pages": 1,
    },
    {
        "key": "xjtu_mec_industrial_product",
        "code": "0802",
        "institution": "西安交通大学",
        "department": "工业产品工程研究所",
        "discipline": "机械工程",
        "listing": BASE + "gycpgcyjs.htm",
        "max_pages": 1,
    },
)

# 名录容器：只有 div.jszhy 里是研究所的在册名单，页头页脚与左侧栏目导航都在它外面。
ROOT_BOX = "div.jszhy"
# 人名的锚点 href 若是这个"通用研究主页入口"，它不区分个人，不能当个人主页用。
GENERIC_GR_HOME = re.compile(r"^https?://gr\.xjtu\.edu\.cn/(?:en|zh)?/?home/?$", re.I)
# 会话参数只是访问痕迹，进 URL 会让同一人变出多个主页地址。
JSESSIONID = re.compile(r";jsessionid=[0-9A-Za-z]+", re.I)
# 双聘/兼职之类**页面自己标注**的身份后缀，如「何卫锋（双聘）」；只当作备注，不进姓名。
STATUS_SUFFIX = re.compile(r"[（(]([^（）()]{1,8})[）)]$")
# 职称词：``教授`` 只有两个字，**能**通过 NAME_RE，因此必须在姓名阶段就挡掉。
RANK_WORD = re.compile(r"教授|讲师|研究员|博士后|正高级|副高级|中级|初级|院士|工程师|"
                       r"实验师|助教|导师")
# 单位与栏目词：``中心`` 之类的两字块同样能通过 NAME_RE，必须挡掉。
UNIT_WORD = re.compile(r"学院|研究所|中心|实验室|学系|系|办公室|教研室|党委|工会|"
                       r"团队|基地|名录|名单|教师|师资")
# 分页条与导航文字不是人名（两字块如「首页」「下页」也能通过 NAME_RE）。
NAV_NOISE = re.compile(r"^(首页|上页|下页|尾页|末页|前一页|后一页|返回|更多|登录|"
                       r"英文|搜索|分享|打印)$")


def _squash(text: str) -> str:
    """去掉**所有**空白，含全角空格 U+3000 与 ``&nbsp;``；必须先做再校验姓名。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def _person(text: str) -> tuple[str, str]:
    """把锚文本变成 (姓名, 页面标注的身份后缀)；不合格返回 ``("", "")``。"""
    raw = _squash(text)
    if not raw:
        return "", ""
    status = ""
    match = STATUS_SUFFIX.search(raw)
    if match:
        status = _squash(match.group(1))
        raw = raw[: match.start()]
    if not NAME_RE.fullmatch(raw):
        return "", ""
    if RANK_WORD.search(raw) or UNIT_WORD.search(raw) or NAV_NOISE.fullmatch(raw):
        return "", ""
    return raw, status


def _homepage(anchor, url: str) -> str:
    """个人主页：指向个人时用原链接，指向通用入口或 ``#`` 时回落到名录页。"""
    href = JSESSIONID.sub("", (anchor.get("href") or "").strip())
    if href in ("", "#") or href.startswith("javascript"):
        return url
    if GENERIC_GR_HOME.match(href):
        return url
    return urljoin(url, href)


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    for box in soup.select(ROOT_BOX):
        # 逐层按文档顺序走：div.jszhy → dl → (dt 标题 / dd 名单)，分页条 div 在这一层
        # 之外，不会被当成人名列表；这样也不会因嵌套元素而重置所名。
        for block in box.find_all("dl"):
            unit = spec["department"]
            for part in block.find_all(True, recursive=False):
                if part.name == "dt":
                    heading = _squash(part.get_text(" ", strip=True))
                    if heading:
                        unit = heading
                    continue
                if part.name != "dd":
                    continue
                for anchor in part.find_all("a"):
                    name, status = _person(anchor.get_text(" ", strip=True)
                                           or anchor.get("title") or "")
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    detail = "；".join(x for x in (
                        f"所属：{unit}",
                        f"页面标注：{status}" if status else "",
                    ) if x)
                    note = (f"西安交通大学机械工程学院「师资队伍 → 教师名录」按研究所公布"
                            f"在册教师名单（{detail}）；名录不列职称，也不列个人研究方向，"
                            f"故方向留待补。名录页把学院 11 个研究所各列为一份子名录，"
                            f"其中机器人与智能系统研究所、先进制造技术研究所各分 2 页，"
                            f"本来源逐所（逐页）收录，不代表学院自报的「专任教师」人数。"
                            f"导师资格与招生专业以当年招生公告为准。")
                    rows.append(roster_row(
                        name, spec["institution"], unit, spec["code"],
                        NO_DIRECTION, _homepage(anchor, url), url,
                        "学院教师名录（按研究所）", note,
                    ))
    return rows
