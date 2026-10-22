"""大连理工大学 能源与动力学院 教师列表（0807 动力工程及工程热物理）.

入口不在学院自己的站点上（``energy.dlut.edu.cn`` 对外部请求一律 403），而在**学校
教师主页系统的「单位列表」**里：``faculty.dlut.edu.cn`` 的
``xyjslb.jsp?urltype=tsites.CollegeTeacherList&id=1154``。这个平台按院系组织全校
教师主页，``id=1154`` 就是「能源与动力学院」，服务端直接渲染，普通 GET 即可拿全，
不依赖脚本或接口::

    div.jsy                                ← 教师列表容器
      div.jctc
        ul.flex
          li                               ← 一位教师 = 一条名录条目
            a[href=faculty.dlut.edu.cn/<账号>/zh_CN/index.htm]   ← 个人主页
              div.con
                h3  姓名
                p   单位：能源与动力学院
                p   职称：教授
                h4  「个人主页」字样（同一张卡片上的文字，不是姓名）

分页
----

列表**每页 12 人**，页数由 ``totalpage`` 参数决定，页码由 ``PAGENUM`` 决定：第 1 页
= ``PAGENUM=1``（= 不带参数时的默认页）。本模块把页面模板声明成 ``{page}`` +
``max_pages`` 12，由采集器逐页走完；最后一页（``PAGENUM=12``）只剩 1 人，
``PAGENUM=13`` 返回 0 条，说明 12 页就是全部。页码是**正序**的（第 1 页是最前面的一批
人，不是末页），与 `xjtu_mec.py` 里那种「默认页其实是末页」的站点不同。

名录口径
--------

* 列表给的是**学院**一级（每条卡片的「单位」都写「能源与动力学院」），``department``
  就取这个页面自己的单位名，不虚构更细的系所。
* 列表给「姓名 / 单位 / 职称」三样，**不列个人研究方向**，所以每一行的 ``direction``
  一律是 :data:`NO_DIRECTION`（``方向待补``）；职称只写进 ``note``，绝不写进方向字段
  （项目红线 2）。132 条的职称分布是 教授 54、副教授 50、助理研究员 11、助理教授 5、
  高级工程师 4、研究员 3、工程师 1、副研究馆员 1、讲师 1；另有 **2 条卡片的职称行是
  空的**（页面就没写，``<p></p>``），这两条的 note 记「未标注」——不替页面补职称。
* 每条卡片的「个人主页」都指向 ``faculty.dlut.edu.cn/<账号>/zh_CN/index.htm`` 形式的
  **个人详情页**（少数教师只有英文页 ``/<账号>/en/index.htm``，同样是只属于一个人的
  详情页），``homepage`` 用它；名录页本身从不作为 ``homepage``。133 条卡片全部带主页，
  没有需要跳过的主页缺口。
* 容器守卫：「容器内条目数 = 解析数 + 跳过数」，对不上即抛错（项目红线 4）。拉丁字母
  姓名不在 :data:`NAME_RE` 范围内，显式跳过并登记（``non_cjk``），不做音译/截断
  （项目红线 1）；本次快照没有拉丁字母姓名，故该登记表为空。
* **同院同名**：第 1 页有两条「鲍民乐」，职称不同（副教授 / 助理研究员）、个人主页
  也不同，页面上没有任何字段能把它们并成一个人。项目的合并键是
  「机构 + 院系 + 姓名」，同院同名只能留一条，所以保留页面顺序里的第一条、把第二条
  登记成 ``duplicate`` 跳过，并在报告里写清 133 = 132 + 1。这不是"去重掉一个人"的
  判断，而是数据模型装不下两条同名记录的已知缺口。
* 联系方式（项目红线 3）：12 页快照实测**一个邮箱、一个电话号码都没有**（卡片只有
  姓名 / 单位 / 职称，页脚也没有联系方式栏目），本模块从不读取任何联系方式字段。
* 口径提醒：这是教师主页系统里的**院系列表**，不是研究生导师名单，也不区分专任/科研/
  实验技术岗位，故不能读成「学院博导人数」；导师资格与招生专业以当年招生公告为准。

学科归属
--------

大连理工大学能源与动力学院是 0807 动力工程及工程热物理的建制学院（学院的一级学科
即 0807，含工程热物理、热能工程、动力机械及工程、流体机械及工程、制冷及低温工程
等方向）；该校的汽车工程系（``id=1210``）、力学与航空航天学院（``id=1209``）在教师
主页系统里是**分开的单位**，不在 ``id=1154`` 的列表里，因此这个列表不会把 0802 力学、
0802 机械或 0825 航空宇航的教师算进来。这一点是本来源能整院归入 0807 的前提，也是
它与 `single_institution_disciplines.py` 里那种「学院合设多学科需整体拒绝」的区别。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# 学校教师主页系统「单位列表 → 能源与动力学院」。``totalpage`` 是页数（实测 12 页），
# ``PAGENUM`` 是页码；``id=1154`` 在平台上是「能源与动力学院」。
LISTING = (
    "https://faculty.dlut.edu.cn/xyjslb.jsp?totalpage=12&PAGENUM={page}"
    "&urltype=tsites.CollegeTeacherList&wbtreeid=1003&st=0&id=1154&lang=zh_CN"
)

SPECS = ({
    "key": "dlut_energy",
    "code": "0807",
    "institution": "大连理工大学",
    "department": "能源与动力学院",
    "discipline": "动力工程及工程热物理",
    "listing": LISTING,
    "max_pages": 12,
},)

# 教师列表容器：导航、页脚、页头都在 div.jsy 外面，不会被当成人名。
ROOT_SELECTOR = "div.jsy"
# 容器里一位教师一个 li；``ul.flex`` 是卡片列表本身。
ITEM_SELECTOR = "ul.flex > li"
# 个人详情页形态（``faculty.dlut.edu.cn/<账号>/zh_CN/index.htm``）。多数账号是中文页，
# 少数教师只有英文页（实测一位蒙古族姓名的教师指向 ``/<账号>/en/index.htm``），
# 两种都算个人详情页——它仍然只属于一个人，不是名录页。
PERSONAL_PAGE = re.compile(
    r"^https?://faculty\.dlut\.edu\.cn/{1,2}[0-9A-Za-z_.-]+/(?:zh_CN|zh_TW|en)/index\.htm$",
    re.I)
# 卡片里的姓名在 h3；去掉零宽字符与全部空白后再校验。
_BLANK = re.compile(r"[\s\u3000\xa0\u200b\u200c\u200d\ufeff]+")
# 拼接式姓名（「张三教授」）先剥后置职称再校验；单独一个职称词则原样交给 NAME_RE 拒绝。
_RANK_SUFFIX = re.compile(
    r"(?:长聘教授|助理教授|副教授|教授|副研究员|研究员|高级工程师|工程师|"
    r"高级实验师|实验师|讲师|助教|院士|博导|硕导)+$"
)
# 拉丁字母姓名不在 NAME_RE 范围内：显式跳过并登记，不做音译/截断。
_NON_CJK = re.compile(r"[A-Za-z]")
# 卡片上的「单位：…」「职称：…」两行。
_UNIT_LINE = re.compile(r"^单位[：:]\s*(.+)$")
_RANK_LINE = re.compile(r"^职称[：:]\s*(.+)$")
# 没有个人主页的锚点形态。
_EMPTY_HREF = frozenset({"", "#"})

# 实录（2026-10-23 快照）：12 页、133 条卡片；133 = 132 条入库 + 1 条同院同名跳过。
# 133 条全部带个人主页，没有拉丁字母姓名，所以跳过项只有「同名」一类。
EXPECTED_PAGES = 12
PUBLISHED_ENTRIES = 133
EXPECTED_ROSTER = 132
# 每页入库条数：第 1 页 12 条卡片里有 1 条同院同名被跳过，末页只剩 1 人。
EXPECTED_PER_PAGE = (11, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 1)
SKIPPED_NON_CJK: tuple[str, ...] = ()
# 同院同名的两条记录：页面顺序里的第二条被登记跳过（合并键装不下同院同名）。
SKIPPED_DUPLICATE = ("鲍民乐",)

_NOTE = (
    "大连理工大学教师主页系统「单位列表 → 能源与动力学院」按院系公布的教师列表"
    "（学校教师主页系统将该院与汽车工程系、力学与航空航天学院分开列示；"
    "页面标注职称：{rank}）；列表只给姓名、单位与职称，不列个人研究方向，故方向留待补"
    "——职称是岗位等级，不是研究方向。本来源不代表学院专任教师总数，"
    "导师资格与招生专业以当年招生公告为准。"
)


def _name(text: str) -> str:
    """把卡片里的姓名文字变成裸姓名；带职称后缀的先剥后缀。"""
    raw = _BLANK.sub("", text or "")
    if not raw:
        return ""
    stripped = _RANK_SUFFIX.sub("", raw)
    return stripped or raw


def _facts(item) -> tuple[str, str]:
    """从卡片的 ``p`` 行里取 (单位, 职称)；没有就返回空串。"""
    unit = rank = ""
    for para in item.find_all("p"):
        line = _BLANK.sub("", para.get_text(" ", strip=True))
        match = _UNIT_LINE.match(line)
        if match:
            unit = match.group(1)
            continue
        match = _RANK_LINE.match(line)
        if match:
            rank = match.group(1)
    # 「职称：教授个人主页」这类同一行还有卡片文字，只取职称词本身。
    rank = re.split(r"个人主页|单位[：:]", rank, maxsplit=1)[0]
    unit = re.split(r"职称[：:]|个人主页", unit, maxsplit=1)[0]
    return _BLANK.sub("", unit), _BLANK.sub("", rank)


def parse_with_skips(html: str, url: str, spec: dict) -> tuple[list[dict], list[dict]]:
    """解析一页列表，返回 (rows, skipped)。

    ``skipped`` 的每一项是 ``{"name": ..., "reason": ...}``，只登记**在册但无法入库**
    的条目（非中文姓名、没有个人主页、同页重名），供调用方与容器守卫核对。
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    skipped: list[dict] = []
    seen: set[str] = set()
    entries = 0
    for root in soup.select(ROOT_SELECTOR):
        for item in root.select(ITEM_SELECTOR):
            entries += 1
            holder = item.find("h3")
            raw = holder.get_text(" ", strip=True) if holder is not None else ""
            name = _name(raw)
            if not name:
                raise ValueError(f"教师列表条目没有姓名文字：{raw!r}")
            if not NAME_RE.fullmatch(name):
                if _NON_CJK.search(name):
                    # 登记时保留页面原样（含空格），便于人工核对；不做音译/截断。
                    skipped.append({"name": re.sub(r"\s+", " ", raw).strip(),
                                    "reason": "non_cjk"})
                    continue
                raise ValueError(f"教师列表条目姓名无法校验：{name!r}")

            anchor = item.find("a", href=True)
            href = (anchor.get("href") or "").strip() if anchor is not None else ""
            if href in _EMPTY_HREF:
                skipped.append({"name": name, "reason": "no_homepage"})
                continue
            if not PERSONAL_PAGE.match(href):
                # 链接形态变了：宁可让采集停下来，也不要把导航或栏目页当个人主页。
                raise ValueError(f"教师列表条目的链接不是个人主页：{name!r} → {href!r}")
            if name in seen:
                skipped.append({"name": name, "reason": "duplicate"})
                continue
            seen.add(name)

            unit, rank = _facts(item)
            rows.append(roster_row(
                name, spec["institution"], unit or spec["department"], spec["code"],
                NO_DIRECTION, href, url, "学校教师主页·单位列表",
                _NOTE.format(rank=rank or "未标注"),
            ))

    if entries != len(rows) + len(skipped):
        raise ValueError(
            f"教师列表容器内 {entries} 条，解析 {len(rows)} 条 + 跳过 {len(skipped)} 条，对不上"
        )
    return rows, skipped


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """返回一页列表里的教师行（跳过项只计数，不进返回值）。"""
    rows, _ = parse_with_skips(html, url, spec)
    return rows
