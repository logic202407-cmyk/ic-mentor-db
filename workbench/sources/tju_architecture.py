"""天津大学 建筑学院 建筑学系 师资名录（0813 建筑学）.

天大建筑学院「人才培养 → 师资队伍」按头衔分若干静态页，本轮收录**能找到静态名录的三类**：

* 教授（第 1、2 页）  ``/rcpy/szdw/jzxx/js1/1.htm``、``/js1/2.htm``
* 英才教授            ``/rcpy/szdw/jzxx/ycjs.htm``
* 讲席教授            ``/rcpy/szdw/jzxx/jxjs.htm``

**未覆盖的部分要写明**：副教授、讲师等类别在站内没有找到可用的静态名录页（父页
``jzxx.htm`` 是「建筑学系」正文页，不含分类入口），因此本轮**只收上述三类**。
这会让本学科的高职称人数偏多、低职称偏少——属于**已知缺口**，不是"该院只有这些人"。

口径说明：

* ``department`` 记为「建筑学系（教授/英才教授/讲席教授）」：把收录范围写进院系字段，
  这样在界面上不会把"三类"误读成"全系"。
* 名录不列研究方向，故 ``direction`` 一律 :data:`NO_DIRECTION`。
* 页面不含邮箱与电话（项目红线 1，实测见快照）。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

_BASE = "http://arch.tju.edu.cn/rcpy/szdw/jzxx"

SPECS = (
    {
        "key": "tju_arch_professor",
        "code": "0813",
        "institution": "天津大学",
        "department": "建筑学系（教授，第 1 页）",
        "discipline": "建筑学",
        "listing": f"{_BASE}/js1/1.htm",
        "max_pages": 1,
    },
    {
        "key": "tju_arch_professor_p2",
        "code": "0813",
        "institution": "天津大学",
        "department": "建筑学系（教授，第 2 页）",
        "discipline": "建筑学",
        "listing": f"{_BASE}/js1/2.htm",
        "max_pages": 1,
    },
    {
        "key": "tju_arch_talent",
        "code": "0813",
        "institution": "天津大学",
        "department": "建筑学系（英才教授）",
        "discipline": "建筑学",
        "listing": f"{_BASE}/ycjs.htm",
        "max_pages": 1,
    },
    {
        "key": "tju_arch_chair",
        "code": "0813",
        "institution": "天津大学",
        "department": "建筑学系（讲席教授）",
        "discipline": "建筑学",
        "listing": f"{_BASE}/jxjs.htm",
        "max_pages": 1,
    },
)

PERSON_HREF = re.compile(r"/info/\d+/\d+\.htm")
TITLE_SUFFIX = re.compile(
    r"(?:正高级工程师|高级工程师|副研究员|助理研究员|正高工|副高工|研究员|教授|"
    r"副教授|讲师|高工|院士)+$"
)
_ADMIN = re.compile(r"党委|工会|离退休|办公室|机关|行政")
_RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")


def clean_title(text: str) -> str:
    raw = re.sub(r"[\s\u3000\xa0]+", "", text)
    stripped = TITLE_SUFFIX.sub("", raw)
    return stripped if NAME_RE.fullmatch(stripped) else ""


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    rows: list[dict] = []
    seen: set[str] = set()
    if _ADMIN.search(spec["department"]):
        return []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        if not PERSON_HREF.search(href):
            continue
        name = clean_title(anchor.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        note = (f"天津大学建筑学院建筑学系「师资队伍 → {spec['department']}」名单；"
                f"**本轮只收教授、英才教授、讲席教授三类**——副教授/讲师在站内未找到"
                f"可用的静态名录页，属已知缺口，不代表该系只有这些人；"
                f"名录未列研究方向，导师资格以当年招生公告为准。")
        direction = NO_DIRECTION
        if _RANK.search(direction):  # pragma: no cover - 防御
            direction = NO_DIRECTION
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            direction, urljoin(url, href), url, "学院师资队伍（按头衔）", note,
        ))
    return rows
