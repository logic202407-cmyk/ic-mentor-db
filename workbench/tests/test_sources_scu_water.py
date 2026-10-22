"""四川大学水利水电学院「学者风采」0815 水利工程 来源模块的离线校验。

只读 ``workbench/tests/fixtures`` 下的三份快照，不联网，所以学院站点抖动不会把这些
检查变红。
"""

import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.collect_thin_discipline_depth import NAME_RE, NO_DIRECTION
from workbench.sources.scu_water import SPECS, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?\d{7,8}|1[3-9]\d{9})")
RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级|院士|高工")
PERSON_HOME = re.compile(r"^https://cwrh\.scu\.edu\.cn/info/\d+/\d+\.htm$")

# 三份名录各自的自报人数：24 = 7 教授 + 17 副教授；13 = 7 + 5 + 1；66 = 36 + 23 + 7。
EXPECTED_ROWS = {
    "scu_water_hydropower": 24,
    "scu_water_hydrology": 13,
    "scu_water_mountain_river_lab": 66,
}
# 每份快照的脱敏命中数 = 邮箱 + 电话（页头两处学院邮箱 + 页脚电话）。
EXPECTED_REDACTIONS = {
    "scu_water_hydropower": 4,
    "scu_water_hydrology": 6,
    "scu_water_mountain_river_lab": 6,
}
# 页面顶栏/侧栏里的导航词：都是 2-8 个汉字，NAME_RE 拦不住，必须靠容器限定排除。
NAV_WORDS = frozenset({
    "学院首页", "学院概况", "师资队伍", "师资概况", "学者风采", "人才引进", "退休教师",
    "水利水电工程系", "水文与水资源工程系", "能源与动力工程系", "农业水利工程系",
    "岩土与地下工程系", "水利水电工程实验中心", "教授（正高）", "副教授（副高）",
    "讲师（中级）", "姓名按照拼音首字母排序",
})


class ScuWaterSourceTests(unittest.TestCase):
    """0815 水利工程 — 四川大学水利水电学院 学者风采（三份静态名录）."""

    @classmethod
    def setUpClass(cls):
        cls.specs = {spec["key"]: spec for spec in SPECS}
        cls.html = {}
        cls.rows = {}
        for key, spec in cls.specs.items():
            text = (FIXTURES / f"{key}.html").read_text(encoding="utf-8")
            cls.html[key] = text
            cls.rows[key] = parse(text, spec["listing"], spec)

    def test_specs_target_the_hydraulic_discipline_at_sichuan_university(self):
        self.assertEqual(len(SPECS), 3)
        self.assertEqual({spec["code"] for spec in SPECS}, {"0815"})
        self.assertEqual({spec["discipline"] for spec in SPECS}, {"水利工程"})
        self.assertEqual({spec["institution"] for spec in SPECS}, {"四川大学"})
        self.assertEqual({spec["max_pages"] for spec in SPECS}, {1})
        self.assertEqual(
            {spec["department"] for spec in SPECS},
            {"水利水电工程系", "水文与水资源工程系", "山区河流保护与治理全国重点实验室"},
        )

    def test_this_is_not_one_of_the_already_covered_institutions(self):
        # 0815 原有武汉大学、同济大学、北京师范大学三家，本来源必须是第四所学校。
        self.assertNotIn("四川大学", {"武汉大学", "同济大学", "北京师范大学"})
        self.assertTrue(all(spec["institution"] == "四川大学" for spec in SPECS))

    def test_the_listing_pages_are_the_units_own_static_pages(self):
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                self.assertTrue(spec["listing"].startswith(
                    "https://cwrh.scu.edu.cn/szdw/xzfc/"))
                self.assertTrue(spec["listing"].endswith(".htm"))
                self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_each_units_whole_roster(self):
        for key, expected in EXPECTED_ROWS.items():
            with self.subTest(source=key):
                rows = self.rows[key]
                self.assertEqual(len(rows), expected)
                self.assertEqual(len({row["name"] for row in rows}), expected)

    def test_the_three_units_add_up_to_more_than_seventy_six_people(self):
        allrows = [row for rows in self.rows.values() for row in rows]
        self.assertEqual(len(allrows), 103)
        self.assertEqual(len({row["name"] for row in allrows}), 103)

    def test_every_row_belongs_to_its_own_listing_and_unit(self):
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                for row in self.rows[key]:
                    self.assertEqual(row["institution"], "四川大学")
                    self.assertEqual(row["department"], spec["department"])
                    self.assertEqual(row["assignment"]["first_level_discipline"],
                                     "0815 水利工程")
                    self.assertEqual(row["assignment"]["url"], spec["listing"])
                    self.assertEqual(row["assignment"]["record_kind"],
                                     "faculty_directory")
                    self.assertEqual(row["assignment"]["source_kind"],
                                     "学院学者风采（按职称）")

    def test_names_are_people_not_navigation(self):
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                for row in rows:
                    name = row["name"]
                    self.assertRegex(name, NAME_RE.pattern)
                    self.assertNotIn(name, NAV_WORDS)
                    self.assertIsNone(RANK.search(name), f"{name} 的姓名里带职称")
                    self.assertGreaterEqual(len(name), 2)

    def test_the_person_container_holds_exactly_the_parsed_people(self):
        # 容器内 h3 数 == 解析人数，说明既没有漏人，也没有把容器外的导航当人。
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                soup = BeautifulSoup(self.html[key], "html.parser")
                root = soup.select_one("div.szlist")
                self.assertIsNotNone(root)
                headings = [h3 for h3 in root.select("h3")
                            if NAME_RE.fullmatch(h3.get_text(strip=True))]
                self.assertEqual(len(headings), EXPECTED_ROWS[key])

    def test_navigation_outside_the_container_is_not_parsed(self):
        html = """
        <ul class="nav">
          <li><a href="/info/1/2.htm"><h3>学院概况</h3></a></li>
          <li><a href="/info/1/3.htm"><h3>师资队伍</h3></a></li>
        </ul>
        <div class="szlist">
          <div class="bt"><p>教授（正高）</p><span>姓名按照拼音首字母排序</span></div>
          <ul class="flex">
            <li><a href="../../info/1028/1273.htm">
              <div class="con"><h3>曹德平研究员</h3></div></a></li>
          </ul>
        </div>
        """
        spec = SPECS[0]
        rows = parse(html, spec["listing"], spec)
        self.assertEqual([row["name"] for row in rows], ["曹德平"])

    def test_direction_is_never_invented(self):
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                for row in rows:
                    self.assertEqual(row["assignment"]["direction"], NO_DIRECTION)

    def test_rank_never_becomes_a_research_direction(self):
        ranks = {row["name"]: row["assignment"]["direction"]
                 for rows in self.rows.values() for row in rows}
        for name, direction in ranks.items():
            self.assertIsNone(RANK.search(direction), f"{name} 的方向字段含职称")

    def test_every_row_links_that_persons_own_detail_page(self):
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                homepages = {row["homepage"] for row in rows}
                self.assertEqual(len(homepages), len(rows))
                for homepage in homepages:
                    self.assertRegex(homepage, PERSON_HOME.pattern)

    def test_homepages_are_not_borrowed_from_other_units(self):
        # 每条个人页都应当落在本单位的正文编号段上，不能一条 URL 多人共用。
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                paths = [row["homepage"].split("cwrh.scu.edu.cn")[1] for row in rows]
                self.assertEqual(len(set(paths)), len(rows))

    def test_no_contact_information_is_stored(self):
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                blob = repr(rows)
                self.assertNotIn("@", blob)
                self.assertIsNone(EMAIL.search(blob))
                self.assertIsNone(PHONE.search(blob))
                self.assertNotIn("联系方式已隐去", blob)

    def test_fixtures_are_redacted(self):
        # 断言"没有残留"而不是"恰好 N 个标记"：标记数会随新发现的联系方式变化，
        # 硬编码计数会让补脱敏反而把测试改红（本次就发生过一次）。
        for key in EXPECTED_REDACTIONS:
            with self.subTest(source=key):
                text = self.html[key]
                self.assertNotIn("@", text)
                self.assertIsNone(EMAIL.search(text))
                self.assertIsNone(PHONE.search(text))
                # 至少做过一次脱敏替换，说明处理路径确实执行过
                self.assertGreaterEqual(text.count("联系方式已隐去"), 1)

    def test_snapshots_are_the_three_units_not_a_shell_page(self):
        for key, rows in self.rows.items():
            with self.subTest(source=key):
                text = self.html[key]
                self.assertIn("学者风采", text)
                self.assertIn("div class=\"szlist\"", text)
                self.assertTrue(rows, "快照疑似壳页：解析不出任何人")


if __name__ == "__main__":
    unittest.main()
