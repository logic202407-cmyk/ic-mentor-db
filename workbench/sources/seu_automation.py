"""东南大学自动化学院 师资力量「全体教师」名录（0811 控制科学与工程）。

学院官网的师资栏目有四个候选地址——师资力量 ``/szdw_32667/list.htm``、全体教师
``/32668/list.htm``、博士生导师 ``/32670/list.htm``、硕士生导师
``/32671/list.htm``——它们**都不是**服务端渲染的名单。四个页面在服务端返回的是
同一个空壳：``div.col_news_con > div.col_news_list.listcon`` 里放着一个
``div.loading`` 加载图、一个**空的** ``ul.cols_list`` 和一个空的 ``#wp_paging``；
普通 GET 拿到的 HTML 里一个教师姓名都没有（页面上能匹配姓名的 ``a`` 全部是导航
菜单）。名单由页面引用的模板脚本
``/_upload/tpl/0a/4c/2636/template2636/js/szdw.js`` 在浏览器里异步取回：

* 该脚本向本站教师查询服务 ``/_wp3services/generalQuery?queryObj=teacherHome``
  发请求，参数为 ``siteId=338``、``pageIndex=1``、``rows=999``、
  ``conditions=[{"field":"published","value":"1","judge":"="}]``、
  ``orders=[{"field":"letter","type":"asc"}]``，以及 ``returnInfos``——**字段白名单**；
* ``returnInfos`` 决定服务返回哪些字段。本模块只申请
  ``title / post / degree / exField1 / cnUrl / department`` 六个字段。
  站点的 ``exField2`` 字段装的是**教师电话**、``exField3`` 是外部网址，两者
  **一律不申请**，因此联系方式根本不会出现在响应体里（项目红线 1 在取数层就成立，
  而不是靠事后过滤）；
* 该服务的响应体是 JSON，但 ``Content-Type`` 写的是 ``text/html``。本模块因此用
  ``json.loads`` 解析响应文本，而不是 ``BeautifulSoup``。

记录数（决定 ``max_pages``）：服务自报 ``total=114``，但**任何查询都只返回 100
条**，且这 100 条是稳定的同一批人。实测：``rows=999`` 时 ``pageIndex=2`` 返回 0 条；
``rows=100`` 时分为 2 页（87+13=100）；``rows=50`` 时分为 3 页（46+41+13=100）；
换排序（letter 升/降、cnUrl、columnId、title、post）与换切片（exField1 的
全体教师/院士/国家级人才/博士生导师/硕士生导师、post 的各个取值）得到的人都只是
这 100 人的子集，没有新面孔。也就是说站点自己的「全体教师」页（脚本同样一次请求
``rows=999``）渲染出来的也只有这 100 人，另外 14 条只计入 ``total``、取不到。因此
本来源是**单次请求**：``max_pages=1``，``listing`` 里没有 ``{page}`` 占位符。

口径说明：

* 只收「全体教师」这一份。博士生导师（62 人）与硕士生导师（82 人）都是这 100 人的
  子集，把三份合并只会给同一个人造出重复行。
* 岗位是行政办公室岗位、且不带任何导师标签的 5 人（院办主任、本科教学秘书、
  院办秘书、研究生秘书、研究生辅导员）整条跳过——合同第 5 条要求跳过非教学单位。
  带行政兼职但同时是博导/硕导的（院长、副院长、党委书记、学科组长等）保留，
  因为他们确实在教师名录里。
* 名录**不含个人研究方向**，所以每一条的 ``direction`` 一律是
  :data:`NO_DIRECTION`；``post`` / ``degree`` / 导师类别只写进备注，绝不当作方向
  （项目红线 2）。每个人的 ``cnUrl``（形如
  ``http://automation.seu.edu.cn/zjy/list.htm``）作为 ``homepage``，供采集器的
  ``--enrich`` 环节后续读取其个人页上的研究方向。
* 页面把 ``杨超群`` 写成 ``杨超群Chaoqun Yang``；本模块取前导汉字串作为姓名，
  其余是拼音注记。非汉字姓名（若以后出现）会被 ``NAME_RE`` 拒绝而跳过。
* 服务只给到学院一级（``department`` 字段只有 ``自动化学院``），没有系/研究所，
  所以所有条目的 ``department`` 都是学院名，**不代表**学院里某个具体的系。
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from ..collect_thin_discipline_depth import NAME_RE, NO_DIRECTION, roster_row

# 学院官网「师资力量 → 全体教师」页面脚本调用的站内教师查询服务。
SERVICE = "https://automation.seu.edu.cn/_wp3services/generalQuery"
# 字段白名单：只申请姓名/岗位/学位栏/导师类别/个人页/院系。
# exField2（电话）与 exField3（外部网址）有意不申请——不申请就不会返回。
RETURN_FIELDS = ("title", "post", "degree", "exField1", "cnUrl", "department")

LISTING = SERVICE + "?" + urlencode({
    "queryObj": "teacherHome",
    "siteId": 338,
    "pageIndex": 1,
    "rows": 999,
    "conditions": json.dumps([{"field": "published", "value": "1", "judge": "="}]),
    "orders": json.dumps([{"field": "letter", "type": "asc"}]),
    "returnInfos": json.dumps([{"field": f, "name": f} for f in RETURN_FIELDS]),
    "articleType": 1,
    "level": 1,
})

SPECS = ({
    "key": "seu_automation",
    "code": "0811",
    "institution": "东南大学",
    "department": "自动化学院",
    "discipline": "控制科学与工程",
    # 单次请求：服务把整份名录一次返回，实测再翻页也取不到第 101 人。
    "listing": LISTING,
    "max_pages": 1,
},)

# 非教学单位的岗位（合同第 5 条）：只有同时不带导师标签时才整条跳过。
ADMIN_ROLE = re.compile(r"秘书|辅导员|主任|党委|工会|财务|人事|教务|行政|离退休|"
                        r"办公室|院办|后勤|招聘")
# 导师标签：带这些标签的人即使在行政岗位上也是教师，保留。
MENTOR_TAG = re.compile(r"博士生导师|硕士生导师")
# 姓名里不可能出现的词（防止把「张三教授」这类串当成姓名）。
NAME_NOISE = re.compile(r"教授|讲师|研究员|导师|院士|博士|硕士|老师|学院|系|中心|"
                        r"办公室|党委|工会|教师|名录|名单")


def _squash(text) -> str:
    """取文本并去掉**所有**空白，含全角空格 U+3000 与 ``&nbsp;``。"""
    return re.sub(r"[\s\u3000\xa0]+", "", str(text or ""))


def _payload(text: str):
    """把响应文本解析成 JSON；采集器会用自动探测的编码解码响应体，因此容错。"""
    if not text:
        return None
    candidates = [text]
    try:
        # 探测成 latin-1 之类的单字节编码时，按原字节复原再解一次。
        candidates.append(text.encode("latin-1").decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _tags(raw) -> list[str]:
    """``exField1`` 是逗号分隔的导师类别标签（可能含空项与重复项）。"""
    out: list[str] = []
    for part in re.split(r"[,，、;；]", str(raw or "")):
        tag = _squash(part)
        if tag and tag not in out:
            out.append(tag)
    return out


def _person_name(raw) -> str:
    """姓名：先去空白再校验；``杨超群Chaoqun Yang`` 这类写法取前导汉字串。"""
    name = _squash(raw)
    if not name:
        return ""
    if not NAME_RE.fullmatch(name):
        lead = re.match(r"^[\u4e00-\u9fff·]{2,8}", name)
        name = lead.group(0) if lead else ""
    if not name or not NAME_RE.fullmatch(name) or NAME_NOISE.search(name):
        return ""
    return name


def _is_administrative(post: str, tags: list[str]) -> bool:
    """岗位是办公室/党委/工会/秘书/辅导员一类，且本人没有任何导师标签。"""
    if any(MENTOR_TAG.search(tag) for tag in tags):
        return False
    return bool(ADMIN_ROLE.search(post))


def parse(html: str, url: str, spec: dict) -> list[dict]:
    payload = _payload(html)
    if payload is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        name = _person_name(item.get("title"))
        if not name or name in seen:
            continue
        post = _squash(item.get("post"))
        tags = _tags(item.get("exField1"))
        if _is_administrative(post, tags):
            continue
        seen.add(name)
        degree = _squash(item.get("degree"))
        department = _squash(item.get("department")) or spec["department"]
        href = str(item.get("cnUrl") or "").strip()
        homepage = url if href in ("", "#") or href.startswith("javascript") else href
        detail = "；".join(x for x in (
            f"岗位/职称：{post}" if post else "",
            f"页面标注：{degree}" if degree else "",
            f"导师类别：{'、'.join(tags)}" if tags else "",
        ) if x)
        note = (f"东南大学自动化学院「师资力量 → 全体教师」名录由页面脚本向站内教师"
                f"查询服务取数（{detail or '页面未标注岗位、学位与导师类别'}）；"
                f"名录不列个人研究方向，方向留待补；该服务自报 114 条、实际可取出的"
                f"为 100 条，故本来源不代表学院全部人员。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], department, spec["code"],
            NO_DIRECTION, homepage, url, "学院师资力量·全体教师名录（站内教师查询服务）",
            note,
        ))
    return rows
