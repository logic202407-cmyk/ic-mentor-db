"""华南理工大学 食品科学与工程学院 教授 师资名录（0832 食品科学与工程）离线检查.

只读 ``workbench/tests/fixtures/scut_food.html`` 与 ``scut_food_p2.html`` / ``_p3.html``，
不联网：学校站点改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录共 48 条（每页 16 条 × 3 页），48 个互不相同的姓名与 48 个不同的个人详情页；
* 姓名是真人、不带职称（「教授」是页面栏目名，不是人名），也不是导航/页脚；
* ``homepage`` 必须是指向个人详情页的
  ``https://www2.scut.edu.cn/sp/<年>/<月日>/c39841a<id>/page.htm``，不能回落成名录页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话，3 份快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 容器内条目数与解析结果不一致时必须抛错（红线 4 的「核对恰好 N 人」）；
* 拉丁字母姓名显式跳过、不音译不截断；「姓名+职称」拼接形式剥后缀后可正常收录。
"""

import json
import pathlib
import re
import unittest

from workbench.sources.scut_food import (
    EXPECTED_PER_PAGE,
    EXPECTED_ROSTER,
    PUBLISHED_ENTRIES,
    PUBLISHED_PER_PAGE,
    SKIPPED_NON_CJK,
    SPECS,
    parse,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(
    r"^https://www2\.scut\.edu\.cn/sp/\d{4}/\d{4}/c39841a\d+/page\.htm$")

# 页面自己的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "学院概况", "师资队伍", "教师风采", "教授", "副教授", "研究员",
    "下一页", "尾页", "友情链接", "书记院长信箱", "食品科学与工程系",
    "食品质量与安全系", "食品营养与健康系",
)

# 本模块只新增一所学校，按「机构-院系-姓名」合并，因此新增行数 = 本模块解析行数。
BASELINE_TOTAL = 83          # 0832 现状：中国农业科学院 59 + 上海交通大学 24
BASELINE_TOP = 59            # 中国农业科学院
BASELINE_TOP_SHARE = 59 / 83  # 71.1%，超过 60% 的集中度上限
# 任务书按 80 条口径计（59/80=73.8%），两种口径下补后结论一致。
TASK_BASELINE_TOTAL = 80


class ScutFoodSourceTests(unittest.TestCase):
    """0832 食品科学与工程 — 华南理工大学食品科学与工程学院 教授."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.pages = []
        cls.rows = []
        for page in range(1, cls.spec["max_pages"] + 1):
            name = ("scut_food.html" if page == 1 else f"scut_food_p{page}.html")
            html = (FIXTURES / name).read_text(encoding="utf-8")
            url = cls.spec["listing"].format(page=page)
            cls.pages.append((url, html))
            cls.rows.extend(parse(html, url, cls.spec))
        cls.names = [row["name"] for row in cls.rows]

    def test_spec_targets_the_food_discipline(self):
        spec = self.spec
        self.assertEqual(spec["key"], "scut_food")
        self.assertEqual(spec["code"], "0832")
        self.assertEqual(spec["discipline"], "食品科学与工程")
        self.assertEqual(spec["institution"], "华南理工大学")
        self.assertEqual(spec["department"], "食品科学与工程学院")
        self.assertEqual(spec["listing"],
                         "https://www2.scut.edu.cn/sp/js_39841/list{page}.htm")
        # 教授名录共 3 页（页面自报「每页 16 记录 / 总共 48 记录」）
        self.assertEqual(spec["max_pages"], 3)
        self.assertIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_roster_across_pages(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 48)
        counts = tuple(len(parse(html, url, self.spec)) for url, html in self.pages)
        self.assertEqual(counts, EXPECTED_PER_PAGE)
        self.assertEqual(counts, (16, 16, 16))
        # 页面自报 48 条 = 解析出的 48 条 + 跳过的非汉字姓名（本批为 0）
        self.assertEqual(PUBLISHED_ENTRIES, 48)
        self.assertEqual(PUBLISHED_PER_PAGE, 16)
        self.assertEqual(len(self.rows) + len(SKIPPED_NON_CJK), PUBLISHED_ENTRIES)

    def test_roster_is_deduplicated(self):
        self.assertEqual(len(set(self.names)), 48)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), 48)
        self.assertEqual(len({row["homepage"] for row in self.rows}), 48)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的姓名锚点）
        for expected in ("成军虎", "陈玲", "赵谋明", "曾新安", "杨晓泉",
                         "孙为正", "宗敏华", "魏东"):
            self.assertIn(expected, self.names)
        # 导航/栏目/页脚不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)
        # 拉丁字母姓名不在 NAME_RE 范围内，已登记跳过，不能出现在结果里
        for skipped in SKIPPED_NON_CJK:
            self.assertNotIn(skipped, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 48 个人指到同一份名单
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertNotIn("list", row["homepage"].rsplit("/", 1)[-1])
        # assignment.url 必须是该行所在的具体分页，而不是笼统的栏目
        page_urls = {url for url, _ in self.pages}
        for row in self.rows:
            self.assertIn(row["assignment"]["url"], page_urls)
        self.assertEqual(len(page_urls), 3)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0832 食品科学与工程")
            self.assertEqual(row["assignment"]["subject"], "083200 食品科学与工程")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("联系方式已隐去", blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        for row in self.rows:
            self.assertNotRegex(row["assignment"]["note"], EMAIL)
            self.assertNotRegex(row["assignment"]["note"], PHONE)

    def test_snapshots_are_scrubbed(self):
        replaced = 0
        for url, html in self.pages:
            self.assertIsNone(EMAIL.search(html), f"快照里仍有邮箱：{url}")
            self.assertIsNone(PHONE.search(html), f"快照里仍有电话：{url}")
            replaced += html.count("联系方式已隐去")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(replaced, 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 48 人
        self.assertEqual(len(self.rows), 48)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员容器里塞一个过不了
        # NAME_RE、也没登记跳过的条目，解析器必须抛错提醒更新解析器，而不是悄悄少收人。
        marker = '<div class="teacher-item">'
        self.assertEqual(self.pages[0][1].count(marker), 16)
        broken = self.pages[0][1].replace(
            marker,
            '<div class="teacher-item"><div class="teacher-name">'
            '<a href="/sp/2026/0101/c39841a999999/page.htm">张三（兼职）</a>'
            '</div></div>\n' + marker,
            1,
        )
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][0], self.spec)

    def test_latin_name_is_skipped_not_transliterated(self):
        # 红线 1：非中文姓名不音译、不截断，显式跳过并计数；容器核对仍应通过
        # （17 个条目 = 16 条解析 + 1 条跳过），返回的仍是原来的 16 人。
        marker = '<div class="teacher-item">'
        page = self.pages[0][1].replace(
            marker,
            '<div class="teacher-item"><div class="teacher-name">'
            '<a href="/sp/2026/0101/c39841a999998/page.htm">John Smith</a>'
            '</div></div>\n' + marker,
            1,
        )
        rows = parse(page, self.pages[0][0], self.spec)
        self.assertEqual(len(rows), 16)
        names = {row["name"] for row in rows}
        for fake in ("JohnSmith", "John", "Smith"):
            self.assertNotIn(fake, names)

    def test_title_suffix_is_stripped_before_validation(self):
        # 红线 1：「姓名+职称」拼接形式剥掉后缀后应能正常收录，且不把职称带进姓名。
        marker = '<div class="teacher-item">'
        page = self.pages[0][1].replace(
            marker,
            '<div class="teacher-item"><div class="teacher-name">'
            '<a href="/sp/2026/0101/c39841a999997/page.htm">李四教授</a>'
            '</div></div>\n' + marker,
            1,
        )
        rows = parse(page, self.pages[0][0], self.spec)
        self.assertEqual(len(rows), 17)
        names = {row["name"] for row in rows}
        self.assertIn("李四", names)
        self.assertNotIn("李四教授", names)

    def test_missing_detail_link_breaks_the_guard(self):
        # 姓名锚点必须指向个人详情页；指回栏目页说明结构变了，不能当成人名收下。
        marker = '<div class="teacher-item">'
        page = self.pages[0][1].replace(
            marker,
            '<div class="teacher-item"><div class="teacher-name">'
            '<a href="/sp/js_39841/list.htm">王五</a></div></div>\n' + marker,
            1,
        )
        with self.assertRaises(ValueError):
            parse(page, self.pages[0][0], self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>师资队伍 教师风采 教授 成军虎 陈玲</body></html>",
                  self.spec["listing"].format(page=1), self.spec),
            [],
        )

    def test_adding_this_source_brings_the_top_share_below_the_cap(self):
        # 0832 现状：中国农业科学院 59/83 = 71.1%，超过 60% 的集中度上限。
        self.assertGreater(BASELINE_TOP_SHARE, 0.6)
        added = len(self.rows)
        total = BASELINE_TOTAL + added
        top = max(BASELINE_TOP, added)
        self.assertLess(top / total, 0.6)
        # 补后：中国农业科学院 59/131=45.0%，华南理工大学 48/131=36.6%。
        self.assertAlmostEqual(59 / total, 0.4504, places=4)
        self.assertAlmostEqual(added / total, 0.3664, places=4)
        # 任务书按 80 条口径计，结论一致（59/128=46.1%、48/128=37.5%）。
        self.assertLess(max(BASELINE_TOP, added) / (TASK_BASELINE_TOTAL + added), 0.6)
        # 新增学校不得自己变成新的独大：48 < 现有最大机构 59。
        self.assertLess(added, BASELINE_TOP)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
