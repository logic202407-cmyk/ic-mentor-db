"""西安建筑科技大学 城乡规划学系 师资名录（0833 城乡规划学）离线检查.

只读 ``workbench/tests/fixtures/xauat_up_1.html`` … ``xauat_up_6.html``，
不联网：学校站点改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 该系名录共 63 个条目，六页分别 12 / 3 / 12 / 12 / 12 / 12；
* 本模块只收教学科研岗 59 人（教授/副教授/准聘副教授/讲师），
  4 名工程师系列显式排除，不静默丢人；
* 59 个互不相同的姓名与 59 个不同的个人详情页；
* 姓名是真人、不带职称，也不是导航/页脚；
* ``homepage`` 必须指向个人详情页（学院个人页或教师个人主页），不能回落成名录页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话，6 份快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 容器内条目数与解析结果不一致时必须抛错（红线 4 的「核对恰好 N 人」）；
* 拉丁字母姓名显式跳过、不音译不截断；「姓名+职称」拼接形式剥后缀后可正常收录。
"""

import json
import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.sources.xauat_urban_planning import (
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
    r"^(?:https://arch\.xauat\.edu\.cn/info/1401/\d+\.htm|"
    r"https://faculty\.xauat\.edu\.cn/[A-Za-z0-9_.-]+/zh_CN/index\.htm)$"
)

# 页面自己的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "师资队伍", "城乡规划学系", "建筑学院", "教授", "副教授", "讲师",
    "下一页", "尾页", "教师主页", "知名校友", "诚聘英才",
)

# 工程师系列（工程/实验技术岗）：本模块按教学科研岗收录，显式排除这 4 人。
SUPPORT_NAMES = ("杨鑫", "周在辉", "王相东", "李萌")

EXPECTED_ROWS = 59
EXPECTED_ENTRIES = 63
EXPECTED_PER_PAGE_ROWS = (12, 3, 8, 12, 12, 12)
EXPECTED_PER_PAGE_ENTRIES = (12, 3, 12, 12, 12, 12)

# 0833 现状：同济大学 62 + 清华大学 1 = 63；同济占 98.4%。
BASELINE_TOTAL = 63
BASELINE_TOP = 62
BASELINE_TOP_SHARE = 62 / 63


class XauatUrbanPlanningSourceTests(unittest.TestCase):
    """0833 城乡规划学 — 西安建筑科技大学建筑学院城乡规划学系."""

    @classmethod
    def setUpClass(cls):
        cls.pages = []
        cls.rows = []
        cls.per_page_rows = []
        cls.per_page_entries = []
        for spec in SPECS:
            html = (FIXTURES / f"{spec['key']}.html").read_text(encoding="utf-8")
            url = spec["listing"]
            cls.pages.append((url, html))
            parsed = parse(html, url, spec)
            cls.per_page_rows.append(len(parsed))
            cls.per_page_entries.append(
                len(BeautifulSoup(html, "html.parser").select(
                    "div.lists div.list a.item[href]"))
            )
            cls.rows.extend(parsed)
        cls.names = [row["name"] for row in cls.rows]

    def test_specs_target_the_urban_planning_discipline(self):
        self.assertEqual(len(SPECS), 6)
        base = "https://arch.xauat.edu.cn/rw/szdw/cxghxx"
        expected = [
            f"{base}.htm",
            f"{base}/1.htm",
            f"{base}/2.htm",
            f"{base}/3.htm",
            f"{base}/4.htm",
            f"{base}/5.htm",
        ]
        self.assertEqual([spec["listing"] for spec in SPECS], expected)
        for index, spec in enumerate(SPECS, 1):
            with self.subTest(key=spec["key"]):
                self.assertEqual(spec["key"], f"xauat_up_{index}")
                self.assertEqual(spec["code"], "0833")
                self.assertEqual(spec["discipline"], "城乡规划学")
                self.assertEqual(spec["institution"], "西安建筑科技大学")
                self.assertEqual(spec["department"], "建筑学院 城乡规划学系")
                self.assertEqual(spec["max_pages"], 1)
                self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_teaching_roster(self):
        self.assertEqual(tuple(self.per_page_entries), EXPECTED_PER_PAGE_ENTRIES)
        self.assertEqual(sum(self.per_page_entries), EXPECTED_ENTRIES)
        self.assertEqual(tuple(self.per_page_rows), EXPECTED_PER_PAGE_ROWS)
        self.assertEqual(len(self.rows), EXPECTED_ROWS)
        self.assertEqual(len(self.rows), 59)
        # 63 个条目 = 59 条解析 + 0 个非中文姓名 + 4 个工程师系列范围排除
        self.assertEqual(
            len(self.rows) + len(SKIPPED_NON_CJK) + len(SUPPORT_NAMES),
            EXPECTED_ENTRIES,
        )
        self.assertEqual(len(SKIPPED_NON_CJK), 0)

    def test_roster_is_deduplicated(self):
        self.assertEqual(len(set(self.names)), EXPECTED_ROWS)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), EXPECTED_ROWS)
        self.assertEqual(len({row["homepage"] for row in self.rows}), EXPECTED_ROWS)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的姓名卡片）
        for expected in ("雷振东", "黄明华", "张沛", "蒋希冀",
                         "张洁璐", "张峰", "徐岚", "王新文"):
            self.assertIn(expected, self.names)
        # 导航/栏目/页脚不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)
        # 工程师系列按范围排除，不能出现在结果里
        for support in SUPPORT_NAMES:
            self.assertNotIn(support, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        page_urls = {url for url, _ in self.pages}
        self.assertEqual(len(page_urls), 6)
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 59 个人指到同一份名单
            self.assertNotEqual(row["homepage"], row["assignment"]["url"])
            self.assertNotIn("/list", row["homepage"])
            # assignment.url 必须是该行所在的具体分页，而不是笼统的栏目
            self.assertIn(row["assignment"]["url"], page_urls)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0833 城乡规划学")
            self.assertEqual(row["assignment"]["subject"], "083300 城乡规划学")
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
            # 页脚座机/传真在数字中间带空格，PHONE 正则匹配不到；按标签再核一次。
            self.assertNotRegex(html, r"(?:电话|传真)[：:]\s*\d")
            replaced += html.count("联系方式已隐去")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(replaced, 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 59 人
        self.assertEqual(len(self.rows), EXPECTED_ROWS)

    def test_engineer_series_is_excluded_by_scope(self):
        # 第 3 页（/2.htm）12 个条目里有 4 名工程师，教学科研岗只有 8 人。
        self.assertEqual(len(parse(*self._page(2))), 8)
        names = {row["name"] for row in parse(*self._page(2))}
        for support in SUPPORT_NAMES:
            self.assertNotIn(support, names)
        self.assertEqual(len(names), 8)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员容器里塞一个过不了
        # NAME_RE、也没登记跳过的条目，解析器必须抛错提醒更新解析器，而不是悄悄少收人。
        page = self._inject(
            self.pages[0][1],
            '<a class="item" href="https://arch.xauat.edu.cn/info/1401/999999.htm">'
            '<div class="mz">下一页</div><div class="yx">教授</div></a>',
        )
        with self.assertRaises(ValueError):
            parse(page, self.pages[0][0], SPECS[0])

    def test_latin_name_is_skipped_not_transliterated(self):
        # 红线 1：非中文姓名不音译、不截断，显式跳过并计数；容器核对仍应通过
        # （13 个条目 = 12 条解析 + 1 条跳过），返回的仍是原来的 12 人。
        page = self._inject(
            self.pages[0][1],
            '<a class="item" href="https://arch.xauat.edu.cn/info/1401/999998.htm">'
            '<div class="mz">John Smith</div><div class="yx">教授</div></a>',
        )
        rows = parse(page, self.pages[0][0], SPECS[0])
        self.assertEqual(len(rows), 12)
        names = {row["name"] for row in rows}
        for fake in ("JohnSmith", "John", "Smith"):
            self.assertNotIn(fake, names)

    def test_title_suffix_is_stripped_before_validation(self):
        # 红线 1：「姓名+职称」拼接形式剥掉后缀后应能正常收录，且不把职称带进姓名。
        page = self._inject(
            self.pages[0][1],
            '<a class="item" href="https://arch.xauat.edu.cn/info/1401/999997.htm">'
            '<div class="mz">李四教授</div><div class="yx">教授</div></a>',
        )
        rows = parse(page, self.pages[0][0], SPECS[0])
        self.assertEqual(len(rows), 13)
        names = {row["name"] for row in rows}
        self.assertIn("李四", names)
        self.assertNotIn("李四教授", names)

    def test_unknown_rank_breaks_the_guard(self):
        # 职称字段出现未登记的系列时抛错，不能因为不认识就静默丢掉这个人。
        page = self._inject(
            self.pages[0][1],
            '<a class="item" href="https://arch.xauat.edu.cn/info/1401/999996.htm">'
            '<div class="mz">王五</div><div class="yx">高级实验师</div></a>',
        )
        with self.assertRaises(ValueError):
            parse(page, self.pages[0][0], SPECS[0])

    def test_missing_detail_link_breaks_the_guard(self):
        # 姓名锚点必须指向个人详情页；指回栏目页说明结构变了，不能当成人名收下。
        html = self.pages[0][1].replace(
            "../../info/1401/26301.htm", "cxghxx.htm", 1)
        self.assertNotEqual(html, self.pages[0][1])
        with self.assertRaises(ValueError):
            parse(html, self.pages[0][0], SPECS[0])

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>师资队伍 城乡规划学系 雷振东 黄明华</body></html>",
                  SPECS[0]["listing"], SPECS[0]),
            [],
        )

    def test_adding_this_source_brings_the_top_share_below_the_cap(self):
        # 0833 现状：同济大学 62/63 = 98.4%，超过 60% 的集中度上限。
        self.assertGreater(BASELINE_TOP_SHARE, 0.6)
        added = len(self.rows)
        total = BASELINE_TOTAL + added
        top = max(BASELINE_TOP, added)
        self.assertLess(top / total, 0.6)
        # 补后：同济大学 62/122 = 50.8%，西安建筑科技大学 59/122 = 48.4%。
        self.assertAlmostEqual(62 / total, 0.5082, places=4)
        self.assertAlmostEqual(added / total, 0.4836, places=4)
        # 任务区间：至少 41、至多 62；新学校不得自己变成新的独大机构。
        self.assertGreaterEqual(added, 41)
        self.assertLessEqual(added, 62)
        self.assertLess(added, BASELINE_TOP)

    def _page(self, index):
        return self.pages[index][1], self.pages[index][0], SPECS[index]

    def _inject(self, html, fragment):
        marker = '<div class="list style">'
        self.assertEqual(html.count(marker), 1)
        return html.replace(marker, marker + fragment, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
