"""中国石油大学（华东）石油工程学院 教师名录（0820 石油与天然气工程）.

本模块补上的正是 0820 这个一级学科此前完全缺失的一半：库里 164 条全部来自
中国石油大学（**北京**），跨校比较无从谈起。同一学科的两所学校各有一个石油工程学院，
这里接入华东（青岛）那一所。

来源页面与取数方式
------------------
学院官网「师资队伍 → 教师名录」（``/jsml_20276/list.htm``）**不是服务端渲染的名单**：
页面 HTML 里没有任何教师姓名，能匹配姓名的链接全是导航（现任领导、党建工作、常用下载…）。
名单由模板脚本在浏览器里渲染，真正的数据是学院自己发布的静态数据文件::

    /_upload/tpl/07/a3/1955/template1955/js/json.js
    var jsonBox = [ { "name": "步玉环", "add": "<个人主页>", "szm": "B",
                      "dep": "油气井工程研究所",
                      'tutor': '硕士生导师/博士生导师', 'professor': '正高' }, … ]

该文件后缀是 ``.js``，内容却是**数据**而非代码：键名有的带引号有的不带、字符串单双
引号混用、还带尾随逗号，``json.loads`` 直接失败，所以这里逐条取它自己的六个字段
（``name`` / ``add`` / ``szm`` / ``dep`` / ``tutor`` / ``professor``），不做 JSON 反序列化。
页面把 ``jsonBox`` 整份读进前端，按「系所 / 姓名首字母 / 导师类别」过滤显示，
所以一次请求就能拿到完整名单。

分页口径：该栏目**没有分页**——页面里没有 WebPlus 的 ``wp_paging`` / ``paging_content``
标记，也没有「每页 N 记录 / 总共 M 记录 / 页码 i/j / 下一页 / 尾页」任何一项
（这三句 WebPlus 自报文案在本页连一处都不存在，同站其它栏目才有）。实测数据文件
自报 ``jsonBox`` 共 **221** 条，本模块三次重取该文件均为同一批 221 人（逐名比对一致），
故 ``max_pages=1``、``listing`` 里不放 ``{page}`` 占位符。

``parse`` 的两条取数路径（同一条规则：只读学院自己发布的东西）::

* 页内已有 ``jsonBox`` 时直接用它——采集快照 ``tests/fixtures/upc_petroleum.html``
  就是把该数据文件**就地内联**在页面加载它的位置，因此契约测试完全离线；
* 页内没有（真实抓取时页面是空壳）才去取同一份数据文件，地址从页面自己的
  ``<script src=…json.js>`` 读出，读不到时回落到常量 :data:`DATA_FILE`。

覆盖范围
--------
数据文件自带 ``dep`` 字段，正好是学院的 6 个研究所与 2 个中心，221 人全部落在其中::

    油气藏工程研究所 54、油气田化学研究所 53、油气井工程研究所 34、
    油气开采工程研究所 23、海洋油气与水合物研究所 22、智能油气田研究所 19、
    实验教学中心 12、公共测试中心 4

也就是说 221 人覆盖学院**全部 8 个教学科研单位**，而不是只抓了某一个系。这比多数
来源更完整，但仍**不等于全院花名册**：在站博士后（``/bsh/list.htm``）与行政人员不
在教师名录里。学院「师资概况」自报教职工 217 人（教授 70、副教授 82），而本名录
221 条里含 38 位兼职教授与 1 位外院教师，两个口径不能直接相减对齐。每条记录的备注
都写明了这一点。

刻意不合并的名单
----------------
* **高层次人才**（``/gccrc_20275/list.htm``）是一张按人才称号分组的**静态表格**
  （22 组、113 人次、56 人）。实测其 56 人里 49 人已出现在本教师名录中（其中 6 人
  是人才表格自己标注的双聘院士），剩下 7 人（王德民、高德利、李根生、程远方、管志川、
  蒋达清、刘锋报）多为双聘院士与不在名录的教师。把两张表合并只会给同一批人造出
  重复行，因此不建条目。
* **师资概况**（``/szgk/list.htm``）与师资队伍栏目（``/szdw_20262/list.htm``）返回的是
  同一页内容（学院简介与教职工人数，两份快照逐字节相同），**不列任何教师**，不建条目。
* **博士后**栏目是在站培养岗位而不是教师职称，与 ``hust.py`` / ``whu_hydropower.py``
  同一口径，不收录。

字段口径
--------
* 姓名的括注是页面自己的标注（``(兼职)`` 38 条、``(院士)`` 1 条、``（外院）`` 1 条），
  **不是姓名的一部分**：先剥掉括注再校验姓名，括注写进备注，避免把 ``李阳(兼职)``
  这种串当成姓名，也避免这 40 条被 2–8 汉字校验整体丢掉。剥掉后 221 个姓名互不重复。
* 页面**不列个人研究方向**，所以每一条的方向都是 :data:`NO_DIRECTION`；
  ``professor``（正高/副高/中级）与 ``tutor``（硕导/博导）只是职称与导师类别，
  一律只写进备注，绝不进入方向字段（项目红线 2）。
* ``homepage`` 只用页面给的 ``add`` 链接，且**必须是 ``pe.upc.edu.cn`` 同站地址**才采用；
  其余（含 43 位没有主页的）回落到 ``listing``。数据文件本身实测不含邮箱与电话
  （``json.js`` 内 ``@`` 出现 0 次），模块也只读上述六项；写入备注的字段另有一道
  邮箱兜底过滤（项目红线 1）。
* ``department`` 取页面自己的 ``dep``（研究所/中心），且与 :data:`UNITS` 白名单**逐字**
  匹配——白名单默认拒绝，将来页面新增党委/工会/办公室一类单位不会漏进来；取不到时
  回落到 ``spec["department"]``。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_engineering_scale import fetch
from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://pe.upc.edu.cn/jsml_20276/list.htm"
# 站点自己的教师名录数据文件；页面模板 <script> 引用的正是这一个。
DATA_FILE = ("https://pe.upc.edu.cn/_upload/tpl/07/a3/1955/"
             "template1955/js/json.js")

SPECS = ({
    "key": "upc_petroleum",
    "code": "0820",
    "institution": "中国石油大学（华东）",
    "department": "石油工程学院",
    "discipline": "石油与天然气工程",
    # 师资队伍 → 教师名录。单页：全站该栏目没有 wp_paging 标记，也没有任何
    # 「每页/总共/页码」文案；名单一次由数据文件的 jsonBox 给出（实测 221 条，
    # 三次重取逐名一致）。
    "listing": LISTING,
    "max_pages": 1,
},)

# 数据文件自带的 8 个机构名，逐字抄录（``海洋油气与水合物研究所`` 是 11 字，容易漏
# 掉中间的「水」）：与数据文件逐字相等才采用，默认拒绝——这样将来页面新增党委/工会/
# 办公室一类单位不会漏进来，写错单位名也只会回落到学院名而不会写出错误院系。
UNITS = (
    "油气井工程研究所", "油气开采工程研究所", "油气藏工程研究所", "油气田化学研究所",
    "海洋油气与水合物研究所", "智能油气田研究所", "实验教学中心", "公共测试中心",
)
# 非教学单位（合同第 5 条）。当前数据不含，保留作为防御。
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|工会|离退休|办公室|机关|人事|财务|教务|"
                                 r"学生工作|行政|校友|后勤|招聘")
# 姓名后面的页面标注，如 李阳(兼职) / 陈掌星(院士) / 赵健（外院）。
ANNOTATION = re.compile(r"[（(]([^）)]{1,4})[）)]")
# 数据文件里的记录外壳与 ``var jsonBox =`` 赋值（用于从整页里切出数据段）。
BOX_RE = re.compile(r"jsonBox\s*=\s*\[")
RECORD_RE = re.compile(r"\{([^{}]*)\}", re.S)
# 逐字段取值：键的引号可有可无、字符串单双引号混用，所以按字段名精确匹配。
FIELD_RE = re.compile(
    r"""["']?(name|add|szm|dep|tutor|professor)["']?\s*:\s*(["'])(.*?)\2""", re.S)
# 兜底：即使上游把联系方式塞进数据文件，也不会写进行（项目红线 1）。
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 姓名里不可能出现的词（防止把「张教授」这类串当成姓名）。
NAME_NOISE = re.compile(r"教授|讲师|研究员|导师|院士|博士|硕士|老师|学院|研究所|中心|"
                        r"办公室|党委|工会|教师|名录|名单")


def _squash(value) -> str:
    """去掉**所有**空白，含全角空格 U+3000 与 ``&nbsp;``。

    必须先合并再校验姓名：``张 三``（中间是半角或全角空格）会被 ``NAME_RE`` 当成
    长度 3 的串而漏过，或按空格切成两个人。
    """
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))


def _clean(value) -> str:
    """取字段值，并做最后的联系方式兜底过滤。"""
    return EMAIL_RE.sub("", _squash(value)).strip()


def _person(raw_name: str) -> tuple[str, str]:
    """返回 ``(姓名, 页面标注)``；姓名不合格时姓名返回空串。"""
    text = _squash(raw_name)
    if not text:
        return "", ""
    marks = [match.group(1) for match in ANNOTATION.finditer(text)]
    name = ANNOTATION.sub("", text)
    if not NAME_RE.fullmatch(name) or NAME_NOISE.search(name):
        return "", ""
    return name, "、".join(marks)


def _feed_source(soup: BeautifulSoup, url: str) -> str:
    """数据文件地址：优先用页面自己引用的那个 ``*json*.js``。"""
    for script in soup.find_all("script", src=True):
        src = _squash(script.get("src"))
        if src.endswith(".js") and "json" in src.rsplit("/", 1)[-1].lower():
            return urljoin(url, src)
    return DATA_FILE


def _records(feed: str) -> list[dict]:
    """把 ``var jsonBox = [ … ]`` 里的记录逐条取成 dict。"""
    text = feed or ""
    marker = BOX_RE.search(text)
    if marker:
        text = text[marker.end() - 1:]
    records: list[dict] = []
    for block in RECORD_RE.findall(text):
        item = {key: value.strip() for key, _quote, value in FIELD_RE.findall(block)}
        if item:
            records.append(item)
    return records


def _looks_like_feed(code: str) -> bool:
    """页内脚本是不是那份数据。

    页面自己的渲染脚本里有 12 处 ``jsonBox`` 引用（``$.each(jsonBox, …)``、
    ``jsonBox[j].dep`` …），只按这个词判断会错把渲染脚本当数据、解析出 0 条，
    因此还要求脚本里真的有 ``name: …`` 记录。
    """
    return "jsonBox" in code and any(
        "name" in item for item in _records(code))


def _feed_text(html: str, url: str) -> str:
    """取出教师名录数据段：页内内联的 ``jsonBox``，否则读站点自己的数据文件。"""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        if script.get("src"):
            continue
        code = script.string or script.get_text() or ""
        if _looks_like_feed(code):
            return code
    if _looks_like_feed(html):
        return html  # 直接拿到了数据文件本体
    return fetch(_feed_source(soup, url))


def _homepage(raw: str, url: str) -> str:
    """个人主页：只采用石油工程学院同站地址，其余回落到名录页。"""
    href = _squash(raw)
    if not href.startswith("http") or "pe.upc.edu.cn" not in href:
        return url
    return href


def _note(unit: str, tutor: str, rank: str, marks: str) -> str:
    detail = "；".join(part for part in (
        f"所属单位：{unit}",
        f"职称：{rank}" if rank else "",
        f"导师类别：{tutor}" if tutor else "",
        f"名录标注：{marks}" if marks else "",
    ) if part)
    return (f"中国石油大学（华东）石油工程学院「师资队伍 → 教师名录」按研究所/中心列出"
            f"（{detail}）；名录不列个人研究方向，方向待补。"
            f"该名录覆盖学院全部 6 个研究所与 2 个中心共 221 人，"
            f"但不含在站博士后与行政人员，不代表学院全部人员。"
            f"导师资格与招生专业以当年招生公告为准。")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    records = _records(_feed_text(html, url))
    rows: list[dict] = []
    seen: set[str] = set()
    for item in records:
        name, marks = _person(item.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        unit = _clean(item.get("dep"))
        if unit not in UNITS or ADMINISTRATIVE_UNIT.search(unit):
            unit = spec["department"]
        rows.append(roster_row(
            name, spec["institution"], unit, spec["code"],
            NO_DIRECTION, _homepage(item.get("add", ""), url), url,
            "学院教师名录（按研究所/中心）",
            _note(unit, _clean(item.get("tutor")), _clean(item.get("professor")), marks),
        ))
    return rows
