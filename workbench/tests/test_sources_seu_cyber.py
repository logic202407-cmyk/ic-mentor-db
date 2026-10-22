"""东南大学网络空间安全学院 网络安全系 0839 网络空间安全 来源模块的离线校验。

只读 ``workbench/tests/fixtures/seu_cyber.html`` 这一份快照，不联网，所以学院站点抖动
不会把这些检查变红。
"""

import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.collect_thin_discipline_depth import NAME_RE, NO_DIRECTION
from workbench.sources.seu_cyber import SPECS, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 红线 3 的完整口径：11 位手机、带区号座机（``025-52091393``）、括号区号 + 空格
# （``(029) 88201234``）。只查前两种就会漏掉第三种。
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
RANK = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级|院士|高工")
ADMIN = re.compile(r"党委|党支部|工会|离退休|办公室|机关|行政")

# 个人主页的三种形态：个人栏目、个人资料文章、教师自己填的外部站点。
PERSON_COLUMN = re.compile(r"^https://cyber\.seu\.edu\.cn/[a-z0-9_]+/list\.(?:htm|psp)$")
PERSON_ARTICLE = re.compile(r"^https://cyber\.seu\.edu\.cn/\d{4}/\d{4}/c\d+a\d+/page\.htm$")
EXTERNAL_PERSONAL = re.compile(r"^https://fei-tong\.github\.io/$")

# 快照自报人数：网络安全系容器内 34 条 = 29 名专任教师 + 5 名「（博后）」在站博士后。
EXPECTED_ROWS = 29
EXPECTED_POSTDOCS = 5

# 页面顶栏/侧栏里的导航词：都是 2-8 个汉字，NAME_RE 拦不住，必须靠容器限定排除。
NAV_WORDS = frozenset({
    "学院首页", "学院概况", "师资队伍", "师资力量", "高层次人才", "教职员工", "各系教师",
    "网络安全系", "智能安全系", "信息安全系", "密码科学与技术系", "科学研究", "研究方向",
    "联系我们", "按拼音排序",
})


def _fixture() -> str:
    return (FIXTURES / f"{SPECS[0]['key']}.html").read_text(encoding="utf-8")


class SeuCyberSourceTests(unittest.TestCase):
    """0839 网络空间安全 — 东南大学网络空间安全学院 网络安全系 各系教师名录."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = _fixture()
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_cyberspace_security_discipline(self):
        self.assertEqual(len(SPECS), 1)
        self.assertEqual(self.spec["key"], "seu_cyber")
        self.assertEqual(self.spec["code"], "0839")
        self.assertEqual(self.spec["discipline"], "网络空间安全")
        self.assertEqual(self.spec["institution"], "东南大学")
        self.assertEqual(self.spec["department"], "网络空间安全学院·网络安全系")
        self.assertEqual(self.spec["max_pages"], 1)

    def test_this_is_not_one_of_the_already_covered_institutions(self):
        # 0839 原有中国科学技术大学、中国科学院大学、上海交通大学三家；本来源必须是第四所。
        covered = {"中国科学技术大学", "中国科学院大学", "上海交通大学"}
        self.assertNotIn(self.spec["institution"], covered)
        self.assertTrue(all(row["institution"] == "东南大学" for row in self.rows))

    def test_listing_is_one_static_page_without_pagination(self):
        self.assertEqual(self.spec["listing"], "https://cyber.seu.edu.cn/gxjs/list.htm")
        self.assertNotIn("{page}", self.spec["listing"])
        # 页面里没有 list2.htm/…/list11.htm 这类分页兄弟页，四个系一次列完。
        self.assertIsNone(re.search(r"/gxjs/list\d+\.htm", self.html))

    def test_parser_finds_the_whole_department_roster(self):
        self.assertEqual(len(self.rows), EXPECTED_ROWS)
        self.assertEqual(len({row["name"] for row in self.rows}), EXPECTED_ROWS)

    def test_the_person_container_holds_exactly_the_parsed_people(self):
        # 容器内 34 条 = 29 名教师 + 5 名在站博士后；差一条就说明漏人或把导航当人名。
        soup = BeautifulSoup(self.html, "html.parser")
        box = next(
            b for b in soup.select("div.sz_box")
            if b.select_one("div.sz_tit")
            and b.select_one("div.sz_tit").get_text(strip=True) == "网络安全系"
        )
        entries = box.select("ul.sz_list li")
        self.assertEqual(len(entries), EXPECTED_ROWS + EXPECTED_POSTDOCS)
        names = [li.select_one("div.news_title").get_text(strip=True) for li in entries]
        postdocs = [n for n in names if "博后" in n]
        self.assertEqual(len(postdocs), EXPECTED_POSTDOCS)
        self.assertEqual(len(self.rows) + len(postdocs), len(entries))

    def test_only_the_target_department_is_parsed(self):
        # 同一页上还有智能安全系、信息安全系、密码科学与技术系，本模块不并进来。
        soup = BeautifulSoup(self.html, "html.parser")
        titles = [b.select_one("div.sz_tit").get_text(strip=True)
                  for b in soup.select("div.sz_box") if b.select_one("div.sz_tit")]
        self.assertIn("网络安全系", titles)
        others = [t for t in titles if t != "网络安全系"]
        self.assertTrue(others, "快照里应当还有别的系，否则这条测试没有意义")
        everyone = {li.select_one("div.news_title").get_text(strip=True)
                    for b in soup.select("div.sz_box") for li in b.select("ul.sz_list li")}
        for row in self.rows:
            self.assertIn(row["name"], everyone)
        # 只属于别系、不在网络安全系里的人一条都不该出现。
        only_elsewhere = everyone - {
            li.select_one("div.news_title").get_text(strip=True)
            for b in soup.select("div.sz_box")
            if b.select_one("div.sz_tit")
            and b.select_one("div.sz_tit").get_text(strip=True) == "网络安全系"
            for li in b.select("ul.sz_list li")
        }
        self.assertTrue(only_elsewhere)
        self.assertEqual(only_elsewhere & set(self.by_name), set())

    def test_postdocs_are_not_faculty_rows(self):
        soup = BeautifulSoup(self.html, "html.parser")
        postdocs = {li.select_one("div.news_title").get_text(strip=True)
                    for li in soup.select("ul.sz_list li")
                    if "博后" in li.select_one("div.news_title").get_text(strip=True)}
        self.assertEqual(len(postdocs), EXPECTED_POSTDOCS)
        for marked in postdocs:
            bare = re.sub(r"[（(].*$", "", marked)
            self.assertNotIn(bare, self.by_name, f"{marked} 是在站博士后，不该成为师资行")

    def test_names_are_people_not_navigation(self):
        for row in self.rows:
            name = row["name"]
            self.assertRegex(name, NAME_RE.pattern)
            self.assertNotIn(name, NAV_WORDS)
            self.assertIsNone(RANK.search(name), f"{name} 的姓名里带职称")
            self.assertNotRegex(name, r"[（(）)]", f"{name} 的姓名里还有注记括号")
            self.assertGreaterEqual(len(name), 2)

    def test_direction_is_never_invented(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], NO_DIRECTION)
            self.assertIsNone(RANK.search(row["assignment"]["direction"]))

    def test_department_is_a_teaching_unit(self):
        for row in self.rows:
            self.assertEqual(row["department"], "网络空间安全学院·网络安全系")
            self.assertIsNone(ADMIN.search(row["department"]))

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        homepages = set()
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertIn("0839 网络空间安全", row["assignment"]["first_level_discipline"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            homepage = row["homepage"]
            self.assertNotEqual(homepage, self.spec["listing"])
            self.assertTrue(
                PERSON_COLUMN.match(homepage)
                or PERSON_ARTICLE.match(homepage)
                or EXTERNAL_PERSONAL.match(homepage),
                f"{row['name']} 的 homepage 不是个人详情页：{homepage}",
            )
            homepages.add(homepage)
        # 一人一页，不能一条 URL 多人共用。
        self.assertEqual(len(homepages), len(self.rows))

    def test_no_contact_information_is_stored(self):
        blob = repr(self.rows)
        self.assertNotIn("@", blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        # 行里不该出现脱敏标记：标记只属于快照，不属于发布数据。
        self.assertNotIn("联系方式已隐去", blob)

    def test_fixture_is_redacted(self):
        # 断言"没有残留"而不是"恰好 N 个标记"：标记数会随新发现的联系方式变化，
        # 硬编码计数会让补脱敏反而把测试改红。
        text = self.html
        self.assertNotIn("@", text)
        self.assertIsNone(EMAIL.search(text))
        self.assertIsNone(PHONE.search(text))
        # 至少做过一次脱敏替换，说明处理路径确实执行过。
        self.assertGreaterEqual(text.count("联系方式已隐去"), 1)

    def test_snapshot_is_the_department_page_not_a_shell(self):
        self.assertIn("各系教师", self.html)
        self.assertIn('div class="sz_box"', self.html)
        self.assertTrue(self.rows, "快照疑似壳页：解析不出任何人")

    def test_a_name_with_a_title_suffix_is_peeled_not_kept(self):
        html = """
        <div class="sz_box">
          <div class="sz_tt"><div class="sz_tit">网络安全系</div>（按拼音排序）</div>
          <ul class="sz_list">
            <li><a class="news_link" href="/abc/list.htm"><div class="news_title">曹德平研究员</div></a></li>
            <li><a class="news_link" href="/def/list.htm"><div class="news_title">张静（Jing Zhang）</div></a></li>
          </ul>
        </div>
        """
        rows = parse(html, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["曹德平", "张静"])

    def test_navigation_outside_the_container_is_not_parsed(self):
        html = """
        <ul class="nav">
          <li><a href="/info/1/2.htm"><div class="news_title">学院概况</div></a></li>
          <li><a href="/info/1/3.htm"><div class="news_title">师资队伍</div></a></li>
        </ul>
        <div class="sz_box">
          <div class="sz_tt"><div class="sz_tit">网络安全系</div>（按拼音排序）</div>
          <ul class="sz_list">
            <li><a class="news_link" href="/ch/list.psp"><div class="news_title">陈浩</div></a></li>
            <li><a class="news_link" href="/czh/list.htm"><div class="news_title">陈子涵（博后）</div></a></li>
          </ul>
        </div>
        """
        rows = parse(html, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["陈浩"])

    def test_a_missing_department_box_yields_no_rows(self):
        html = '<div class="sz_box"><div class="sz_tit">智能安全系</div>' \
               '<ul class="sz_list"><li><a class="news_link" href="/bl/list.psp">' \
               '<div class="news_title">白离</div></a></li></ul></div>'
        self.assertEqual(parse(html, self.spec["listing"], self.spec), [])

    def test_the_source_is_a_meaningful_dilution_of_the_dominant_institution(self):
        # 0839 现状：34 条，中国科学技术大学 29 条。补 29 人后中科大 29/63 = 46.0%，
        # 东南大学 29/63 = 46.0%，两家都在 60% 以下。
        before_total, dominant = 34, 29
        after_total = before_total + EXPECTED_ROWS
        self.assertLess(dominant / after_total, 0.6)
        self.assertLess(EXPECTED_ROWS / after_total, 0.6)
        self.assertGreaterEqual(EXPECTED_ROWS, 15)


if __name__ == "__main__":
    unittest.main()
