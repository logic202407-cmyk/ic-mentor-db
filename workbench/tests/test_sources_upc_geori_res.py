"""中国石油大学（华东）资源系 师资名录（0818 地质资源与地质工程）离线检查.

只读 ``workbench/tests/fixtures/upc_geori_res.html``，不联网：学校站点改版不应把这里
的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 资源系分区共 57 个姓名格：53 位教师 + 3 位在站博士后 + 1 位无个人详情页的工程师，
  解析结果 53 条（「姓名格数 = 解析数 + 博士后数 + 跳过数」的硬核对，57 = 53+3+1）；
* 只收资源系：地质系、地球物理系、测井系与交叉学科中心的人不得混进来；
* 在站博士后是培养岗位而不是教师职称，与 ``whu_hydropower.py`` / ``hust.py``
  同口径不计入师资行，但必须被计数（不能静默丢掉）；
* 姓名是真人、不带职称，也不是导航/栏目名；
* ``homepage`` 必须是指向个人详情页的
  ``http://geori.upc.edu.cn/<年>/<月日>/c<栏目号>a<文章号>/page.htm``，不能回落成名录页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话；快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 分区内出现无法识别为姓名的条目、链接不是个人详情页、同一分区重复收录时必须抛错；
* 拉丁字母姓名显式跳过、不音译不截断；「姓名+职称」拼接形式剥后缀后可正常收录；
* 补后集中度回到 60% 以下，且新增学校不超过现有最大机构。
"""

import json
import pathlib
import re
import unittest

from workbench.sources.upc_geori_res import (
    EXPECTED_POSTDOCS,
    EXPECTED_ROSTER,
    NON_FACULTY_RANK,
    PUBLISHED_NAME_CELLS,
    SECTION,
    SKIPPED_NON_CJK,
    SPECS,
    parse,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "upc_geori_res.html"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(
    r"^http://geori\.upc\.edu\.cn/\d{4}/\d{4}/c\d+a\d+/page\.htm$")

# 页面上的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "学院首页", "师资队伍", "学院概况", "学院介绍", "资源系", "地质系",
    "地球物理系", "测井系", "博士后", "高层次人才", "专家学者", "教授", "副教授",
    "讲师", "研究生导师", "人才培养", "学科建设", "联系我们",
)

# 资源系里的教师（逐个核对过快照里的姓名锚点）：教授、副教授、讲师、高工各取几位。
RESOURCE_PEOPLE = ("郝芳", "林承焰", "田辉", "张立强", "李俊乾", "王齐鸣", "任怀强")
# 其他分区的人：不得出现在本模块结果里。
OTHER_SECTIONS = ("周瑶琪", "印兴耀", "唐晓明", "刘可禹")
# 资源系里的在站博士后：单独计数后排除，不是教师行。
POSTDOC_NAMES = ("苟启洋", "许艳华", "李君健")

# 0818 现状：中南大学 83 + 中国科学院大学 21 = 104，中南大学占 79.8%。
BASELINE_TOTAL = 104
BASELINE_TOP = 83
BASELINE_SECOND = 21

# 与快照同构的最小页面：一张表、三个【系】分区，用来做红线守卫的注入测试。
MINI = """<html><body><div class="wp_articlecontent"><table>
<tr><td colspan="4">【地质系】</td></tr>
<tr><td><a href="/2018/0526/c10381a152099/page.htm">周瑶琪（教授）</a></td></tr>
<tr><td colspan="4">【资源系】</td></tr>
{body}
<tr><td colspan="4">【地球物理系】</td></tr>
<tr><td><a href="/2018/0526/c10381a152010/page.htm">印兴耀（教授）</a></td></tr>
</table></div></body></html>"""


def _mini(body: str) -> str:
    return MINI.format(body=body)


class UpcGeoriResSourceTests(unittest.TestCase):
    """0818 地质资源与地质工程 — 中国石油大学（华东）地球科学与技术学院·资源系."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = FIXTURE.read_text(encoding="utf-8")
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]

    def test_spec_targets_the_georesource_discipline(self):
        spec = self.spec
        self.assertEqual(spec["key"], "upc_geori_res")
        self.assertEqual(spec["code"], "0818")
        self.assertEqual(spec["discipline"], "地质资源与地质工程")
        self.assertEqual(spec["institution"], "中国石油大学（华东）")
        self.assertEqual(spec["department"], "地球科学与技术学院·资源系")
        self.assertEqual(spec["listing"],
                         "https://geori.upc.edu.cn/10927/list.htm")
        # 单页名录：list2/list3 只是同一版式的空栏目尾页，不再有系名录。
        self.assertEqual(spec["max_pages"], 1)
        self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_resource_section(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 53)
        # 红线 4：资源系 57 个姓名格 = 53 位教师 + 3 位在站博士后 + 1 位无个人页的工程师。
        self.assertEqual(PUBLISHED_NAME_CELLS, 57)
        self.assertEqual(EXPECTED_POSTDOCS, 3)
        self.assertEqual(PUBLISHED_NAME_CELLS,
                         len(self.rows) + EXPECTED_POSTDOCS + 1)
        # 快照里确实只有一个资源系分区标题。
        self.assertEqual(self.html.count(SECTION), 1)

    def test_ranks_of_the_collected_teachers(self):
        # 53 = 教授 20 + 副教授 25 + 副研究员 1 + 高级工程师 1 + 讲师 6。
        ranks = {}
        for row in self.rows:
            match = re.search(r"页面标注「([^」]+)」", row["assignment"]["note"])
            self.assertIsNotNone(match, row["assignment"]["note"])
            rank = match.group(1)
            ranks[rank] = ranks.get(rank, 0) + 1
        self.assertEqual(ranks, {"教授": 20, "副教授": 25, "副研究员": 1,
                                 "高级工程师": 1, "讲师": 6})
        for rank in ranks:
            self.assertNotIn(rank, NON_FACULTY_RANK)

    def test_postdocs_are_counted_but_not_teachers(self):
        # 在站博士后：不计入师资行，但也不能被静默丢掉（核对见上一个用例）。
        for name in POSTDOC_NAMES:
            self.assertNotIn(name, self.names)
        # 注入一位博士后：解析结果不变，计数核对仍应通过。
        page = _mini('<tr><td><a href="/2026/0101/c10382a999994/page.htm">'
                     '张三（教授）</a></td>'
                     '<td><a href="/2026/0101/c10382a999993/page.htm">'
                     '王六（博士后）</a></td></tr>')
        rows = parse(page, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["张三"])

    def test_only_the_resource_section_is_collected(self):
        for name in RESOURCE_PEOPLE:
            self.assertIn(name, self.names)
        # 其他系/中心的人不能被算进资源系（否则等于把整个学院收进 0818）。
        for name in OTHER_SECTIONS:
            self.assertNotIn(name, self.names)

    def test_roster_is_deduplicated(self):
        self.assertEqual(len(set(self.names)), 53)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), 53)
        self.assertEqual(len({row["homepage"] for row in self.rows}), 53)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)
        # 拉丁字母姓名不在 NAME_RE 范围内，已登记跳过，不能出现在结果里。
        for skipped in SKIPPED_NON_CJK:
            self.assertNotIn(skipped, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 53 个人指到同一份名单。
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertNotIn("/10927/", row["homepage"])
            # assignment.url 必须记名录页（该行唯一的分页/栏目）。
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0818 地质资源与地质工程")
            self.assertEqual(row["assignment"]["subject"],
                             "081800 地质资源与地质工程")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            # 职称写进 note、不写进 direction（红线 2）。
            self.assertRegex(row["assignment"]["note"], r"页面标注「[^」]+」")

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("联系方式已隐去", blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        for row in self.rows:
            self.assertNotRegex(row["assignment"]["note"], EMAIL)
            self.assertNotRegex(row["assignment"]["note"], PHONE)

    def test_snapshot_is_scrubbed(self):
        self.assertIsNone(EMAIL.search(self.html), "快照里仍有邮箱")
        self.assertIsNone(PHONE.search(self.html), "快照里仍有电话")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(self.html.count("联系方式已隐去"), 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 53 人。
        self.assertEqual(len(self.rows), 53)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        self.assertEqual(
            parse("<html><body>师资队伍 资源系 郝芳 林承焰 田辉</body></html>",
                  self.spec["listing"], self.spec),
            [],
        )

    def test_missing_section_yields_nothing(self):
        # 没有【资源系】分区时宁可返回空，也不能把相邻分区的人当成本分区。
        page = _mini('<tr><td><a href="/2026/0101/c10382a999999/page.htm">张三（教授）</a>'
                     '</td></tr>').replace("<tr><td colspan=\"4\">【资源系】</td></tr>", "")
        self.assertEqual(parse(page, self.spec["listing"], self.spec), [])

    def test_latin_name_is_skipped_not_transliterated(self):
        # 红线 1：非中文姓名不音译、不截断，显式跳过并计数；容器核对仍应通过
        # （2 个姓名格 = 1 条解析 + 1 条跳过）。
        page = _mini('<tr><td><a href="/2026/0101/c10382a999998/page.htm">'
                     '张三（教授）</a></td>'
                     '<td><a href="/2026/0101/c10382a999997/page.htm">'
                     'John Smith（教授）</a></td></tr>')
        rows = parse(page, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["张三"])
        for fake in ("JohnSmith", "John", "Smith"):
            self.assertNotIn(fake, {row["name"] for row in rows})

    def test_title_suffix_is_stripped_before_validation(self):
        # 红线 1：「姓名+职称」拼接形式剥掉后缀后应能正常收录，且不把职称带进姓名。
        page = _mini('<tr><td><a href="/2026/0101/c10382a999996/page.htm">'
                     '王五教授</a></td></tr>')
        rows = parse(page, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["王五"])
        self.assertNotIn("王五教授", {row["name"] for row in rows})

    def test_text_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：分区里出现「研究方向：……」这种非姓名条目，必须抛错提醒更新解析器，
        # 而不是悄悄当成一个人收下或静默丢掉。
        page = _mini('<tr><td><a href="/2026/0101/c10382a999995/page.htm">'
                     '研究方向：油气成藏</a></td></tr>')
        with self.assertRaises(ValueError):
            parse(page, self.spec["listing"], self.spec)

    def test_link_that_is_not_a_detail_page_breaks_the_guard(self):
        # 链接指回栏目页说明结构变了，不能当成人名收下（红线 5）。
        page = _mini('<tr><td><a href="/10927/list.htm">赵六（教授）</a></td></tr>')
        with self.assertRaises(ValueError):
            parse(page, self.spec["listing"], self.spec)

    def test_duplicate_person_in_the_section_breaks_the_guard(self):
        page = _mini('<tr><td><a href="/2026/0101/c10382a999994/page.htm">张三（教授）</a>'
                     '</td><td><a href="/2026/0101/c10382a999994/page.htm">张三（教授）</a>'
                     '</td></tr>')
        with self.assertRaises(ValueError):
            parse(page, self.spec["listing"], self.spec)

    def test_adding_this_source_brings_the_top_share_below_the_cap(self):
        # 0818 现状：中南大学 83/104 = 79.8%，超过 60% 的集中度上限。
        self.assertGreater(BASELINE_TOP / BASELINE_TOTAL, 0.6)
        self.assertEqual(BASELINE_TOP + BASELINE_SECOND, BASELINE_TOTAL)
        added = len(self.rows)
        total = BASELINE_TOTAL + added
        # 下限：要能把最大机构压到 60% 以下；上限：新增学校不得超过现有最大机构。
        self.assertGreaterEqual(added, 35)
        self.assertLess(added, BASELINE_TOP)
        self.assertLess(max(BASELINE_TOP, added) / total, 0.6)
        # 补后：中南大学 83/157 = 52.9%，中国石油大学（华东）53/157 = 33.8%。
        self.assertEqual(total, 157)
        self.assertAlmostEqual(BASELINE_TOP / total, 0.528662, places=6)
        self.assertAlmostEqual(added / total, 0.337580, places=6)
        # 中国科学院大学 21/157 = 13.4%，仍然是最小的一所。
        self.assertAlmostEqual(BASELINE_SECOND / total, 0.133758, places=6)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
