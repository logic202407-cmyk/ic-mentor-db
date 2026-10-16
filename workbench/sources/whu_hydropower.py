"""武汉大学水利水电学院水力发电工程系在岗教师名录（0815 水利工程）。

水利水电学院把在岗教师按 **系** 分成六份名录（智慧水利系、水力发电工程系、
水文水资源系、河流工程系、水利工程系、水利水电工程实验中心），每份名录是一个
静态 ``.htm`` 页，服务端直接渲染出全部教师——普通 GET 就能拿到完整名单，不依赖
任何脚本或接口。本模块读取其中的 ``水力发电工程系``：它是六份名录里人数最多、
且每个人名字都是汉字的一份（六系合计约 200 人，其余五系的页面结构与这里完全
一致，可以由各自的来源模块分别收录）。

页面结构（``div.home_pro_right`` 内，文档顺序自洽）::

    <p class="title05"><b>水力发电工程系</b></p>     ← 系名（院系）
    <p class="title04"><b>教授</b></p>               ← 职称分组标题
    <ul class="am-avg-lg-10 am-thumbnails empty teacher">
      <li><a href="../../info/1087/4516.htm">
        <div class="sheet">…头像…</div>
        <h2>常晓林</h2>                              ← 姓名
        <p>职称：教授，博士生导师</p>                  ← 职称
        <p>邮箱：changxl@whu.edu.cn</p>              ← 联系方式，从不读取
        <p>研究方向：高坝结构安全，…</p>               ← 研究方向（页面自身标注）
      </a></li>
      …

本模块因此可以给出比纯名录更完整的条目：姓名、职称、系，以及**页面自己写明的**
研究方向。研究方向的取值只来自 ``研究方向：`` 这一段，绝不会拿职称去填；某位
教师没有写研究方向时留 :data:`NO_DIRECTION`。``邮箱：`` 那一段整个跳过，并且
写入备注与方向的字符串还会再过滤一次邮箱/电话样式，确保结果里不可能出现联系方式
（项目红线 1）。

两条口径说明：

* ``博士后`` 是在站培养岗位而不是教师职称，与 ``hust.py`` 保持一致不计入教师名录，
  故 ``ul.teacher`` 在 ``博士后`` 分组下整体跳过。
* 非汉字姓名（如 ``KIM Jong Suk``）会被 ``NAME_RE`` 拒绝，因此不会出现在结果里；
  本页 48 条恰好全部是汉字姓名，不受影响。

本模块收录水利水电学院在岗教师名录的**五个系级页面**（智慧水利系、水力发电工程系、
水文水资源系、河流工程系、水利工程系），每个页面一个 ``SPECS`` 条目、共用同一个
``parse``，因为五页结构完全一致。

学院导航里还有第六项「水利水电工程实验中心」，但它的页面**不列教师**：``title04``
标题是实验室名（农田水利与水环境实验室、水工结构实验室……），页面上 ``ul.teacher``
为 0 个，没有任何姓名。因此不为其建来源条目——收录一个解析结果恒为空的来源只会
制造"已覆盖"的假象。仍**不含**在站博士后与行政人员，所以不代表学院全部人员；
这一点在每条记录的备注里也写明，避免被读成全院名单。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = (
    {
        "key": "whu_hydropower",
        "code": "0815",
        "institution": "武汉大学",
        "department": "水力发电工程系",
        "discipline": "水利工程",
        # 师资队伍 → 在岗教师 → 各系。六份名录结构完全一致。
        "listing": "https://swrh.whu.edu.cn/szdw/zgjs/slfdgcx1.htm",
        "max_pages": 1,
    },
    {
        "key": "whu_smart_water",
        "code": "0815",
        "institution": "武汉大学",
        "department": "智慧水利系",
        "discipline": "水利工程",
        "listing": "https://swrh.whu.edu.cn/szdw/zgjs/zhslx.htm",
        "max_pages": 1,
    },
    {
        "key": "whu_hydrology",
        "code": "0815",
        "institution": "武汉大学",
        "department": "水文水资源系",
        "discipline": "水利工程",
        "listing": "https://swrh.whu.edu.cn/szdw/zgjs/swszyx.htm",
        "max_pages": 1,
    },
    {
        "key": "whu_river_engineering",
        "code": "0815",
        "institution": "武汉大学",
        "department": "河流工程系",
        "discipline": "水利工程",
        "listing": "https://swrh.whu.edu.cn/szdw/zgjs/hlgcx1.htm",
        "max_pages": 1,
    },
    {
        "key": "whu_hydraulic_engineering",
        "code": "0815",
        "institution": "武汉大学",
        "department": "水利工程系",
        "discipline": "水利工程",
        "listing": "https://swrh.whu.edu.cn/szdw/zgjs/slgcx.htm",
        "max_pages": 1,
    },
)

# 在站博士后是培养岗位，不是教师职称，整组不计入（与 hust.py 同一口径）。
NON_FACULTY_RANK = re.compile(r"博士后")
# 非教学单位（合同第 5 条）。本页的系名不会命中，保留作为防御。
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|工会|离退休|办公室|机关|人事|财务|教务|"
                                 r"学生工作|行政|校友|后勤")
# 职称只是职称，绝不允许整段跑进研究方向（合同红线 2）。
RANK_WORD = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
# 兜底：即使上游页面把联系方式塞进职称或研究方向段里，也不会写进行。
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?\d{7,8}|1[3-9]\d{9})")
_CONTACT_LABEL_RE = re.compile(r"邮箱|邮件|电话|手机|E-?mail", re.I)


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格（“陈　华”）与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def _clean(value: str) -> str:
    """去掉尾随的联系方式栏与任何邮箱/电话样式，再收紧两端标点。"""
    value = _CONTACT_LABEL_RE.split(value, maxsplit=1)[0]
    value = _EMAIL_RE.sub("", value)
    value = _PHONE_RE.sub("", value)
    return value.strip("，,；;、 ")


def _field(items, label: str) -> str:
    """在 ``<p>标签：值</p>`` 列表里取 ``label`` 之后的值，取不到返回空串。"""
    for node in items:
        text = _compact(node)
        if text.startswith(label):
            return _clean(text[len(label):].lstrip("：:"))
    return ""


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    root = soup.select_one("div.home_pro_right") or soup

    rows: list[dict] = []
    seen: set[str] = set()
    unit = spec["department"]
    rank = ""
    for node in root.find_all(["p", "ul"]):
        classes = node.get("class") or []
        if node.name == "p" and "title05" in classes:
            unit = _compact(node) or unit
            continue
        if node.name == "p" and "title04" in classes:
            rank = _compact(node)
            continue
        # 只有 div.home_pro_right 里的 ul.teacher 是教师名录，其余列表是导航。
        if node.name != "ul" or "teacher" not in classes:
            continue
        if NON_FACULTY_RANK.search(rank) or ADMINISTRATIVE_UNIT.search(unit):
            continue
        for li in node.find_all("li"):
            anchor = li.find("a")
            heading = li.find("h2")
            if anchor is None or heading is None:
                continue
            name = _compact(heading)
            if not NAME_RE.fullmatch(name) or name in seen:
                continue
            seen.add(name)
            paragraphs = li.find_all("p")
            title = _field(paragraphs, "职称")
            direction = _field(paragraphs, "研究方向")
            if not direction or RANK_WORD.search(direction):
                # 页面没有写方向，或者写出来的其实是职称：都不猜。
                direction = NO_DIRECTION
            href = (anchor.get("href") or "").strip()
            homepage = url if href in ("", "#") or href.startswith("javascript") \
                else urljoin(url, href)
            detail = "；".join(x for x in (
                unit,
                f"职称分组：{rank}" if rank else "",
                f"职称：{title}" if title else "",
            ) if x)
            note = (f"武汉大学水利水电学院在岗教师名录按系与职称分组列出（{detail}）；"
                    f"研究方向一栏取自名录页面自身标注。"
                    f"本来源覆盖学院在岗教师名录的六个系级页面，"
                    f"仍不代表学院全部人员（如博士后与行政人员未收录）；"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                direction, homepage, url, "学院在岗教师名录", note,
            ))
    return rows
