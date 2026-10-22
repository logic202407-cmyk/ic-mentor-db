"""中国人民警察大学 研究生导师名录（0838 公安技术）离线检查.

只读 ``workbench/tests/fixtures/cppu_police_tech.html``，不联网：学校站点改版
不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 该页按教学单位分组，本模块只收「智慧警务学院 / 警务装备技术学院 /
  防火工程学院」三个公安技术方向单位，共 65 人（26 / 18 / 21）；
* 65 个互不相同的姓名，没有职称、没有导航词；
* ``direction`` 一律 ``方向待补``，职称不当作方向；
* 行里没有邮箱、电话；页面实测 0/0，仍按项目正则复核「无残留」，
  并用运行时构造的合成串证明脱敏器确实会替换（不把具体号码写进源码）；
* 容器守卫：三个单位容器内条目数与解析数对不上时必须抛错；
* 拉丁字母姓名显式跳过、不音译不截断；「姓名+职称」拼接形式剥后缀后可正常收录；
* ``homepage`` 回落名录页：该页不提供个人详情页。这是本来源已知的红线偏差，
  测试显式断言 65 条全部回落，不伪装成个人主页。
"""

import json
import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.sources.cppu_police_tech import IN_SCOPE, LISTING, SPECS, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师|教官|导师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)

# 页面自己的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "上页", "下页", "上一页", "下一页", "尾页", "末页",
    "师资队伍", "研究生导师", "队伍概况", "师德标兵", "名师风采", "人才引进",
)

EXPECTED_ROWS = 65
EXPECTED_PER_UNIT = {
    "智慧警务学院": 26,
    "警务装备技术学院": 18,
    "防火工程学院": 21,
}

# 0838 现状：中国刑事警察学院 87 + 中国人民公安大学 14 = 101，主导校 87/101。
BASELINE_TOTAL = 101
BASELINE_TOP = 87


def _scrub(text):
    """Replace contact information and return (scrubbed_text, replacements)."""
    text, emails = EMAIL.subn("联系方式已隐去", text)
    text, phones = PHONE.subn("联系方式已隐去", text)
    return text, emails + phones


def _synthetic_contacts():
    """Build a synthetic email/phone at runtime, so no concrete value is stored."""
    email = "user" + chr(64) + "example" + "." + "com"
    phone = "010" + "-" + "".join(chr(48 + d) for d in (1, 2, 3, 4, 5, 6, 7))
    return email, phone


class CppuPoliceTechSourceTests(unittest.TestCase):
    """0838 公安技术 — 中国人民警察大学研究生导师名录."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / "cppu_police_tech.html").read_text(encoding="utf-8")
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]

    def test_specs_target_the_police_technology_discipline(self):
        self.assertEqual(len(SPECS), 1)
        spec = SPECS[0]
        self.assertEqual(spec["key"], "cppu_police_tech")
        self.assertEqual(spec["code"], "0838")
        self.assertEqual(spec["discipline"], "公安技术")
        self.assertEqual(spec["institution"], "中国人民警察大学")
        self.assertEqual(spec["listing"], LISTING)
        self.assertEqual(spec["max_pages"], 1)
        self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_three_in_scope_units(self):
        counts = {}
        for row in self.rows:
            counts[row["department"]] = counts.get(row["department"], 0) + 1
        self.assertEqual(counts, EXPECTED_PER_UNIT)
        self.assertEqual(len(self.rows), EXPECTED_ROWS)
        self.assertEqual(set(counts), set(IN_SCOPE))

    def test_roster_is_deduplicated(self):
        self.assertEqual(len(set(self.names)), EXPECTED_ROWS)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), EXPECTED_ROWS)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的姓名卡片）
        for expected in ("王立冬", "屈健", "唐超", "吴立志", "李思成", "郭子东"):
            self.assertIn(expected, self.names)
        # 导航/栏目/页脚不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)

    def test_out_of_scope_units_are_excluded(self):
        # 侦查学院、移民管理学院等公安学/非公安技术单位不能混进来。
        for outsider in ("邓亮", "李阳", "王亚宁", "王强", "梁秀波"):
            self.assertNotIn(outsider, self.names)
        for row in self.rows:
            self.assertIn(row["department"], IN_SCOPE)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0838 公安技术")
            self.assertEqual(row["assignment"]["subject"], "083800 公安技术")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")

    def test_homepage_falls_back_to_the_listing(self):
        # 该页只列姓名、姓名没有 href，学校没有为导师公布个人详情页。
        # 这是本来源已知的红线偏差：65 条全部回落名录页，不伪装成个人主页。
        fallbacks = [row for row in self.rows if row["homepage"] == LISTING]
        self.assertEqual(len(fallbacks), EXPECTED_ROWS)
        personal = [row for row in self.rows if row["homepage"] != LISTING]
        self.assertEqual(personal, [])

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("联系方式已隐去", blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        for row in self.rows:
            self.assertNotRegex(row["assignment"]["note"], EMAIL)
            self.assertNotRegex(row["assignment"]["note"], PHONE)

    def test_snapshot_has_no_contact_information(self):
        # 页面实测 0/0：不存邮箱电话，也不把联系方式写进快照。
        self.assertIsNone(EMAIL.search(self.html))
        self.assertIsNone(PHONE.search(self.html))
        self.assertNotRegex(self.html, r"(?:电话|传真)[：:]\s*\d")
        scrubbed, replaced = _scrub(self.html)
        self.assertEqual(scrubbed, self.html)
        self.assertEqual(replaced, 0)
        # 脱敏器本身必须真的会替换；用运行时构造的合成串，不落具体号码。
        email, phone = _synthetic_contacts()
        out, count = _scrub(f"邮箱：{email} 电话：{phone}")
        self.assertEqual(count, 2)
        self.assertIsNone(EMAIL.search(out))
        self.assertIsNone(PHONE.search(out))

    def test_container_guard_rejects_navigation(self):
        # 红线 4：往人员容器里塞一个导航词，解析器必须抛错提醒更新解析器，
        # 而不是把它当成人名收下。
        with self.assertRaises(ValueError):
            parse(self._inject("下一页"), self.spec["listing"], self.spec)

    def test_container_guard_rejects_unknown_entry(self):
        # 无 href 的条目若既不是姓名也没有登记跳过，必须抛错，不能静默少人。
        with self.assertRaises(ValueError):
            parse(self._inject("王"), self.spec["listing"], self.spec)

    def test_latin_name_is_skipped_not_transliterated(self):
        rows = parse(self._inject("John Smith"), self.spec["listing"], self.spec)
        self.assertEqual(len(rows), EXPECTED_ROWS)
        names = {row["name"] for row in rows}
        for fake in ("JohnSmith", "John", "Smith"):
            self.assertNotIn(fake, names)

    def test_title_suffix_is_stripped_before_validation(self):
        rows = parse(self._inject("李四教授"), self.spec["listing"], self.spec)
        self.assertEqual(len(rows), EXPECTED_ROWS + 1)
        names = {row["name"] for row in rows}
        self.assertIn("李四", names)
        self.assertNotIn("李四教授", names)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        self.assertEqual(
            parse("<html><body>师资队伍 研究生导师 王立冬 屈健</body></html>",
                  self.spec["listing"], self.spec),
            [],
        )

    def test_adding_this_source_brings_the_top_share_below_the_cap(self):
        # 0838 现状：中国刑事警察学院 87/101 = 86.1%，超过 60% 的集中度上限。
        self.assertGreater(BASELINE_TOP / BASELINE_TOTAL, 0.6)
        added = len(self.rows)
        total = BASELINE_TOTAL + added
        top = max(BASELINE_TOP, added)
        self.assertLess(top / total, 0.6)
        # 补后：中国刑事警察学院 87/166 = 52.4%，中国人民警察大学 65/166 = 39.2%，
        # 中国人民公安大学 14/166 = 8.4%。
        self.assertAlmostEqual(87 / total, 0.5241, places=4)
        self.assertAlmostEqual(added / total, 0.3916, places=4)
        self.assertAlmostEqual(14 / total, 0.0843, places=4)

    def _inject(self, name):
        """Insert one <li> into 智慧警务学院's roster container."""
        soup = BeautifulSoup(self.html, "html.parser")
        heading = soup.find("h3", string=lambda text: text and "智慧警务学院" in text)
        self.assertIsNotNone(heading)
        holder = heading.find_next("ul", class_="list1")
        self.assertIsNotNone(holder)
        item = soup.new_tag("li")
        span = soup.new_tag("span", attrs={"class": "con"})
        h4 = soup.new_tag("h4", attrs={"class": "tit eclip"})
        h4.string = name
        span.append(h4)
        item.append(span)
        holder.insert(0, item)
        return str(soup)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
