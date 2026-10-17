"""中国刑事警察学院 研究生导师名录（0838 公安技术）.

学校官网「师资队伍 → 研究生导师」把全校导师按**教学单位**分组公布：每个单位一个
``h3.flex`` 标题，紧随其后是 ``ul.flex`` 名单，名单里每个人的 ``<a>`` **没有 href**
（只有 ``title``），因此这些记录没有个人主页可取，``homepage`` 回落到名录页 URL。

本模块只收录与 **0838 公安技术**对应的四个技术类教学单位：

* 刑事科学技术学院（法庭科学学院）—— 痕迹、理化、文件检验、法医学等
* 公安信息技术与情报学院 —— 网络安全与执法、公安视听技术、数据警务等
* 警犬技术学院（公安部沈阳警犬基地）—— 警犬技术
* 公安基础教研部 —— 公安技术基础与方法

**刻意排除**「马克思主义学院」「法律教研部」「公共基础教研部」——它们是通识与
法学教学单位，不属 0838；也排除「侦查与反恐怖学院」「经济犯罪侦查学院」
「禁毒与治安学院」——这三个是**公安学（0306）**方向的侦查与治安专业院系，
把它们的师资并进 0838 等于把另一个一级学科的人划过来，会造成学科归属错误。
排除不是遗漏，是有意的口径选择，本模块文档与每条记录的备注都写明覆盖范围。

名录只给姓名与所属教学单位，**没有研究方向、没有职称**，故 ``direction`` 一律为
:data:`NO_DIRECTION`；页面本身也不含邮箱与电话（实测 0/0，项目红线 1）。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "cipuc_grad_supervisors",
    "code": "0838",
    "institution": "中国刑事警察学院",
    "department": "研究生导师（公安技术相关教学单位）",
    "discipline": "公安技术",
    # 师资队伍 → 研究生导师。单页静态名录，无分页。
    "listing": "https://www.cipuc.edu.cn/szdw/yjsds.htm",
    "max_pages": 1,
},)

# 名录容器：div.zjjs 是「专家教授」页，div.zjjs.zjjs2 是「研究生导师」页；
# 两页结构一致，这里按 class 兼容取值。
ROOT_SELECTORS = ("div.zjjs.zjjs2", "div.zjjs")
GROUP_HEADING = "h3"
LIST_BOX = "ul"

# 属于 0838 公安技术的教学单位（白名单，默认拒绝——新增栏目不会悄悄混进来）。
IN_SCOPE = (
    "刑事科学技术学院",
    "公安信息技术与情报学院",
    "警犬技术学院",
    "公安基础教研部",
)
# 明确排除的两类：通识/法学单位，以及属公安学（0306）的侦查与治安院系。
OUT_OF_SCOPE = (
    "马克思主义学院",
    "法律教研部",
    "公共基础教研部",
    "侦查与反恐怖学院",
    "经济犯罪侦查学院",
    "禁毒与治安学院",
)
# 导航用词，避免被当成姓名。
NAVWORD = re.compile(r"师资队伍|师资概况|优秀团队|专家教授|教学名师|研究生导师|学校概况|"
                     r"首页|学院|部门|概况|团队|教授|名师|导师")


def _compact(node) -> str:
    """取文本并去掉所有空白，含全角空格与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    root = None
    for selector in ROOT_SELECTORS:
        root = soup.select_one(selector)
        if root is not None:
            break
    if root is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    unit = ""
    for child in root.find_all(recursive=False):
        if child.name == GROUP_HEADING:
            text = _compact(child)
            if text:
                unit = text
            continue
        if child.name != LIST_BOX:
            continue
        if not any(token in unit for token in IN_SCOPE):
            # Not a 0838 unit (either out of scope explicitly, or a heading we do
            # not recognise — default deny so a new column cannot leak in silently).
            continue
        if any(token in unit for token in OUT_OF_SCOPE):
            continue
        for anchor in child.find_all(["a", "span", "li"]):
            name = _compact(anchor)
            if not NAME_RE.fullmatch(name) or name in seen or NAVWORD.search(name):
                continue
            seen.add(name)
            note = (f"学校「师资队伍 → 研究生导师」按教学单位公布（所属：{unit}）；"
                    f"名录只列姓名与教学单位，未列职称与个人研究方向。"
                    f"本来源收录与公安技术对应的技术类教学单位，"
                    f"不含侦查、治安等公安学方向院系，也不含通识与法学教学单位；"
                    f"导师资格与招生方向以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, url, url, "学校研究生导师名录", note,
            ))
    return rows
