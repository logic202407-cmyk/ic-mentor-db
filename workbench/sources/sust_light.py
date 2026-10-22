"""陕西科技大学 轻工科学与工程学院 皮革工程系 师资名录（0822 轻工技术与工程）.

入口是学院官网「师资队伍 → 各系师资 → 皮革工程系」::

    https://qg.sust.edu.cn/szdw2/gxsz/pggcx.htm

页面由服务端直接渲染（博达/WebPlus 静态页，普通 GET 即可拿全，不依赖脚本或接口），
人员容器结构稳定::

    div.list_bssds                      ← 名录容器（全页唯一）
      div.list_bssds_div01              ← 一个职称分组（教授 / 副教授 / 讲师，共 3 组）
        div.list_bssds_div > dd > p     ← 分组标题，例如「教授」
        div.list_bssds_name > ul > li > a[href]
                                        ← 人名锚点，href 指向个人详情页 /info/<栏>/<id>.htm

实测 2026-10-22：**21 人 = 教授 9 + 副教授 10 + 讲师 2**，单页列完，无分页。

为什么限定到「皮革工程系」而不是整个学院
----------------------------------------

学院「各系师资」共 6 个系：皮革工程系、造纸工程系、非织造材料与工程系、柔性电子学系、
新能源与生物质材料系、新媒体技术系。与 0822 轻工技术与工程对口的只有前两个：

* **皮革工程系** 对应 0822 下设的 **082204 皮革化学与工程**，是本校轻工技术与工程的
  主干方向，也是本次收录的来源（``pggcx.htm``）。
* **造纸工程系**（``zzgcx.htm``）对应 **082201 制浆造纸工程**，同样属于 0822，实测 28 人；
  本次**有意不并进来**：0822 现有 19 条里浙江科技大学占 15 条（78.9%），再加 21 人后
  陕西科技大学 21/(19+21)=52.5%；若同时加造纸系的 28 人，合计 49 人会把陕西科技大学
  推到 49/(19+49)=72.1%，反而**超过 60% 的集中度上限**。造纸系留作独立的后续来源，
  单独成模块即可继续压低集中度，不需要改本模块。
* 其余 4 个系不属 0822，不收录：非织造材料与工程系属 0821 纺织科学与工程；柔性电子学系、
  新能源与生物质材料系、新媒体技术系是学院的自设/交叉方向。

为什么必须限定人员容器（红线 4）
---------------------------------

**只按 href 抓 ``/info/\\d+/\\d+\\.htm`` 会多出一条**：页头的「意见（监督）邮箱」也指向
``/info/1198/13874.htm``，全页这样的锚点有 **22** 个，而真正的教师只有 **21** 个。
限定 ``div.list_bssds`` 后锚点数正好 21，且解析结果必须与容器内锚点数逐一对上
（少一个就抛错），避免结构变化时静默少收人。

口径说明
--------

* 名录按**职称分组**公布，不列个人研究方向，因此每行 ``direction`` 一律
  :data:`NO_DIRECTION`（``方向待补``）；职称只写进来源说明，绝不当作方向（红线 2）。
* 姓名锚点本身不含职称（页面 ``title`` 与锚文本都是纯姓名）；解析仍按红线 1 做后缀剥离
  并用 ``NAME_RE`` 全匹配兜底。
* 联系方式（红线 3）：名录页页脚有一处学院座机（``联系电话：`` 后 11 位区号号码），
  落盘快照前已替换为「联系方式已隐去」；本模块只读 ``div.list_bssds`` 内的人名与 href，
  从不读取任何联系方式字段。
* ``department`` 记为「轻工科学与工程学院·皮革工程系」：既有学院，也有页面自己的分组名；
  两者都是教学科研单位，不含党委/工会/办公室一类行政机构（契约第 5 条）。
* ``homepage`` 取人名锚点的 href（``/info/1808/<id>.htm`` 等个人详情页，实测每页标题形如
  「高党鸽-轻工科学与工程学院」），不是名录页本身。
* 导师资格与招生专业以当年招生公告为准；本来源只表示学院按系公布的在册教师名录里有这些人。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

LISTING = "https://qg.sust.edu.cn/szdw2/gxsz/pggcx.htm"

SPECS = ({
    "key": "sust_light",
    "code": "0822",
    "institution": "陕西科技大学",
    "department": "轻工科学与工程学院·皮革工程系",
    "discipline": "轻工技术与工程",
    "listing": LISTING,
    "max_pages": 1,
},)

# 人员容器：全页唯一的 div.list_bssds；容器外的人名锚点（页头「意见（监督）邮箱」）一律不算。
CONTAINER = "div.list_bssds"
GROUP = "div.list_bssds_div01"
NAME_BOX = "div.list_bssds_name"
ROSTER = f"{CONTAINER} {NAME_BOX} ul li a[href]"

# 页面自己的分组标题。只认这几个；认不出来说明结构变了，不再往下猜。
RANKS = ("教授", "副教授", "讲师", "助理教授", "研究员", "副研究员", "助教", "院士")

# 红线 1 的兜底：万一锚文本是「姓名+职称」拼接，剥掉后缀再校验。长词优先，
# 否则「副研究员」会被「研究员」剥成「副」。
_TITLE_SUFFIX = re.compile(r"(?:副教授|助理教授|副研究员|研究员|博士后|教授|讲师|院士|高工)$")

# 实测：2026-10-22 该容器内恰好 21 人（9 + 10 + 2）。
EXPECTED_ROSTER = 21


def _norm(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def parse(html: str, url: str, spec: dict) -> list[dict]:
    """Parse the SUST 皮革工程系 directory page into roster rows."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()

    box = soup.select_one(CONTAINER)
    if box is None:
        # 结构变了就明确返回空，交给契约测试暴露，而不是把整页文本当人名。
        return []

    anchors = box.select(ROSTER)
    rows: list[dict] = []
    seen: set[str] = set()
    for group in box.select(GROUP):
        heading = group.select_one("div.list_bssds_div dd p")
        rank = _norm(heading.get_text(" ", strip=True)) if heading else ""
        if rank not in RANKS:
            # 分组标题都认不出来，说明容器结构与快照不一致；不静默当成 0 人。
            continue
        for anchor in group.select(f"{NAME_BOX} ul li a[href]"):
            name = _norm(anchor.get_text(" ", strip=True))
            name = _TITLE_SUFFIX.sub("", name)
            if not NAME_RE.fullmatch(name) or name in seen:
                continue
            seen.add(name)
            note = (f"学院「师资队伍 → 各系师资 → 皮革工程系」名录按职称分组公布"
                    f"（本条目所在分组：{rank}）；名录未列个人研究方向，故方向字段为“方向待补”，"
                    f"职称只写入来源说明、不作为研究方向。"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], spec["department"], spec["code"],
                NO_DIRECTION, urljoin(url, anchor["href"]), url,
                "学院各系师资名录", note,
            ))

    # 红线 4：核对「容器内恰好 N 人」——容器里有锚点却没解析成人名，说明有人被漏掉。
    if len(rows) != len(anchors):
        raise ValueError(
            f"皮革工程系名录解析不完整：容器内 {len(anchors)} 个条目，只解析出 {len(rows)} 条"
            f"（重名或非人名条目）。请检查 {url} 的页面结构。")
    return rows
