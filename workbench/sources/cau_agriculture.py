"""中国农业大学工学院农业工程系师资队伍名录（0828 农业工程）。

工学院官网的“师资队伍”栏目按系分栏，农业工程系的名单挂在 ``col28301``：这是
服务端渲染的静态 HTML，一页列全，没有分页、没有接口，普通 GET 就能拿到完整
名单。页面按 **职称** 分组（教授 / 副教授 / 讲师 / 高级实验师 / 工程师 /
实验师 / 博士后），每组一张姓名表格，每个姓名格子里是本人的
``faculty.cau.edu.cn`` 教师主页链接。

页面结构（全部在 ``div.info-main.listinfo`` 内容容器内，文档顺序自洽）::

    <div class="info-main listinfo">
      <p><strong><span>农业工程系</span></strong></p>        ← 栏目名
      <p><strong><span>教  授</span></strong></p>            ← 职称分组标题
      <table><tr>
        <td><p><a href="https://faculty.cau.edu.cn/gjb"><span>郭建斌</span></a></p></td>
        …
      </table>
      <p><strong><span>副教授</span></strong></p>
      …

三处页面怪癖都已在 :func:`parse` 里处理：

* 姓名与职称里的空格是排版用的 ``&nbsp;`` 和全角空格（``何&nbsp;进``、
  ``教&nbsp;&nbsp;授``），有的姓名还被拆进多个 ``<span>``
  （``李延`` + ``啸``）。因此取值一律用 ``"".join(stripped_strings)`` 再删掉
  所有空白，``NAME_RE`` 才能校验通过。
* 职称标题自己占一张表格，格子文本（``副教授``、``高级实验师``）同样能过
  ``NAME_RE``。所以只认「格子文本与格内某个 ``a`` 的文本完全相同」的格子：
  标题表格里没有任何 ``a``，自然被排除，不会解析出名为“副教授”的人。
* 姓名格子里其余的 ``a`` 是头像与图标链接，文本为空，按上面这条规则必然落选。

研究方向：本页**不写**任何研究方向，方向一律留 :data:`NO_DIRECTION`
（“方向待补”）；职称只写进来源说明，绝不当作研究方向（合同红线 2）。

个人主页：只采用 ``faculty.cau.edu.cn`` 上的教师主页。名录里还有三类链接都不是
教师本人的公开学术主页，一律回落为名录页 URL——``gmsadm.cau.edu.cn/dsxxgl/
dsxxwh/edit_dszszgtg``（标题“导师信息查询编辑页面”，是后台维护页）、
``gradinfo.cau.edu.cn/portaltutor/...``（已无法连接）、``/jcms/manager/...``
（CMS 后台地址，实测 404）。全系 57 人中 45 人有 ``faculty.cau.edu.cn`` 主页，
其余 12 人的 ``homepage`` 回落为名录页 URL。

收录边界：本来源只覆盖工学院农业工程系。中国农业大学的 0828 农业工程还分布在
信息与电气工程学院、水利与土木工程学院等单位，各自名录的地址与结构不同，需要
各自的来源模块，因此本来源**不代表中国农业大学 0828 农业工程的全部师资**。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

SPECS = ({
    "key": "cau_agriculture",
    "code": "0828",
    "institution": "中国农业大学",
    "department": "工学院·农业工程系",
    "discipline": "农业工程",
    # 工学院 → 师资队伍 → 农业工程系。单页列全，无分页参数。
    # （同一栏目的 col28302 是机械工程系，属 0802 机械工程，不在本来源范围内。）
    "listing": "https://coe.cau.edu.cn/col/col28301/index.html",
    "max_pages": 1,
},)

# 只有这个容器里才是师资名录；导航、页脚、友情链接都在它外面。
ROSTER_BOX = "div.info-main.listinfo"
# 页面上的职称分组标题（去掉排版空白后的字面值）。标题可能被拆进多个 <strong>，
# 但外层 <p> 的文本是完整的，所以按 <p> 的整段文本判定。
RANK_LABELS = frozenset({
    "教授", "副教授", "讲师", "高级实验师", "实验师",
    "工程师", "高级工程师", "研究员", "副研究员", "博士后", "助教",
})
# 在站博士后是培养岗位而不是教师职称，整组不计入（与 whu_hydropower.py / hust.py 同口径）。
NON_FACULTY_RANK = frozenset({"博士后"})
# 教师本人的公开主页：只有 faculty.cau.edu.cn 上的个人页算数。
PERSONAL_PAGE = re.compile(r"^https?://faculty\.cau\.edu\.cn/", re.I)


def _compact(node) -> str:
    """取文本并删掉所有空白，含全角空格与 ``&nbsp;``（“何　进”“教　　授”）。"""
    return re.sub(r"[\s\u3000\xa0]+", "", "".join(node.stripped_strings))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    box = soup.select_one(ROSTER_BOX)
    if box is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    rank = ""
    for node in box.find_all(["p", "table"]):
        if node.name == "p":
            text = _compact(node)
            if text in RANK_LABELS:
                rank = text
            continue
        # 博士后分组整表跳过；其余分组都是教学科研或实验技术岗位。
        if rank in NON_FACULTY_RANK:
            continue
        for cell in node.find_all(["td", "th"]):
            name = _compact(cell)
            if name in RANK_LABELS or not NAME_RE.fullmatch(name) or name in seen:
                continue
            # 只有“格子文本 == 格内某个链接的文本”才算教师条目：
            # 头像/图标链接文本为空，职称标题表格里没有链接，两者都会被排除。
            anchor = next((a for a in cell.find_all("a", href=True)
                           if _compact(a) == name), None)
            if anchor is None:
                continue
            seen.add(name)
            href = (anchor.get("href") or "").strip()
            homepage = href if PERSONAL_PAGE.match(href) else url
            note = (f"中国农业大学工学院官网“师资队伍”栏目按系与职称公布"
                    f"（{spec['department']}"
                    f"{'，职称：' + rank if rank else ''}）；该名录不含个人研究方向。"
                    f"本来源只覆盖工学院农业工程系，中国农业大学 0828 农业工程还分布在"
                    f"其他学院，故不代表全校该学科的全部师资；"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], spec["department"], spec["code"],
                NO_DIRECTION, homepage, url, "学院师资队伍名录（农业工程系）", note,
            ))
    return rows
