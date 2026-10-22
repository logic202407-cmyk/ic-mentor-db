"""北京航空航天大学 宇航学院 航天飞行器技术系 教师名录（0825 航空宇航科学与技术）离线检查.

只读 ``workbench/tests/fixtures/buaa_astro_p1.html`` … ``_p4.html``，不联网：学校站点
改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录共 4 页、39 人，逐页人数 12/12/12/3；页面按「一页一个 key」登记（分页目录名
  是倒序的：第 2 页在 ``/3.htm``），4 个 key 对应 4 个不同的入口；
* 姓名是真人、不带职称，也不是导航（筛选器、栏目名、分页都不得混进来）；
* ``homepage`` 必须是指向个人详情页的 ``/info/1011/<id>.htm``，不能回落成名录页，
  且 39 个人 39 个不同的详情页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话，4 份快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 非中文姓名显式跳过并计数，容器内条目数与解析结果不一致时必须抛错（红线 4）；
* 名录只覆盖航天飞行器技术系，不代表宇航学院全部教师；本来源不是力学/航空宇航
  合设学院，不存在 0801 教师被整体并入 0825 的弱归属。
"""

import json
import pathlib
import re
import unittest

from workbench.sources.buaa_astro import (
    EXPECTED_PER_PAGE,
    EXPECTED_ROSTER,
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
PERSON_PAGE = re.compile(r"^https://www\.sa\.buaa\.edu\.cn/info/\d+/\d+\.htm$")

LISTINGS = (
    "https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx.htm",
    "https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/3.htm",
    "https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/2.htm",
    "https://www.sa.buaa.edu.cn/szdw/jsfc/htfxqjsx/1.htm",
)

# 页面自己的栏目名/导航词/职称词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "学院概况", "师资队伍", "教师风采", "师资简介", "导航", "筛选查询",
    "站内搜索", "职称/职位", "教授", "副教授", "讲师", "研究员", "博导", "硕导",
    "上页", "下页", "尾页", "第一页", "版权所有", "联系方式", "航天飞行器技术系",
)

# 快照里 p1 的第一张卡片；注入测试条目时插在它前面。
FIRST_CARD = '<li id="line_u15_0">'


def _card(name, href="../../info/1011/9999.htm", rank="教授/博导"):
    """Return a synthetic roster card with the same markup as the live page."""
    return (
        f'<li id="line_u15_99">'
        f'<a href="{href}" title="{name}">'
        f'<p class="mingzi">{name}</p>'
        f'<p class="zhicheng" style="color:#999;"><span>职称/职位：{rank}</span></p>'
        f"</a></li>\n"
    )


class BuaaAstroSourceTests(unittest.TestCase):
    """0825 航空宇航科学与技术 — 北京航空航天大学宇航学院航天飞行器技术系."""

    @classmethod
    def setUpClass(cls):
        cls.specs = SPECS
        cls.pages = []
        cls.rows = []
        for spec in SPECS:
            html = (FIXTURES / f"{spec['key']}.html").read_text(encoding="utf-8")
            cls.pages.append((spec["key"], spec["listing"], html))
            cls.rows.extend(parse(html, spec["listing"], spec))
        cls.names = [row["name"] for row in cls.rows]

    def test_specs_cover_four_pages_of_one_department(self):
        self.assertEqual(len(SPECS), 4)
        self.assertEqual(tuple(spec["key"] for spec in SPECS),
                         ("buaa_astro_p1", "buaa_astro_p2",
                          "buaa_astro_p3", "buaa_astro_p4"))
        # 分页目录名倒序：第 2 页是 /3.htm，第 4 页是 /1.htm；一页一个 key。
        self.assertEqual(tuple(spec["listing"] for spec in SPECS), LISTINGS)
        self.assertEqual(len(set(LISTINGS)), 4)
        for spec in SPECS:
            self.assertEqual(spec["code"], "0825")
            self.assertEqual(spec["discipline"], "航空宇航科学与技术")
            self.assertEqual(spec["institution"], "北京航空航天大学")
            self.assertEqual(spec["department"], "宇航学院·航天飞行器技术系")
            self.assertEqual(spec["max_pages"], 1)
            # 不能用 {page} 模板去猜倒序目录名
            self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_roster_across_pages(self):
        self.assertEqual(EXPECTED_PER_PAGE, (12, 12, 12, 3))
        self.assertEqual(EXPECTED_ROSTER, 39)
        counts = tuple(len(parse(html, url, spec))
                       for spec, (_, url, html) in zip(SPECS, self.pages))
        self.assertEqual(counts, EXPECTED_PER_PAGE)
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 39)
        self.assertEqual(sum(EXPECTED_PER_PAGE), EXPECTED_ROSTER)

    def test_roster_is_deduplicated(self):
        # 同一个人不能因跨页/重复出现而在库里变成多条
        self.assertEqual(len(set(self.names)), 39)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), 39)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的 p.mingzi）
        for expected in ("孟庆春", "陈万春", "徐明", "桂海潮", "师鹏",
                         "王晓慧", "王林娟", "游晖", "王新升", "程浩"):
            self.assertIn(expected, self.names)
        # 导航/栏目/筛选器/职称不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)
        # 职称词不能以任何形式出现在姓名里
        for name in self.names:
            for word in ("教授", "研究员", "讲师", "博导", "硕导"):
                self.assertNotIn(word, name)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 39 个人指到同一份名单
            self.assertNotIn(row["homepage"], LISTINGS)
        self.assertEqual(len({row["homepage"] for row in self.rows}), 39)
        # assignment.url 必须是该行所在的具体分页，而不是笼统的栏目
        page_urls = {url for _, url, _ in self.pages}
        for row in self.rows:
            self.assertIn(row["assignment"]["url"], page_urls)
        # 四页各解析各的，四个来源 URL 都要出现（不是全指向第一页）
        self.assertEqual({row["assignment"]["url"] for row in self.rows},
                         set(LISTINGS))

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0825 航空宇航科学与技术")
            self.assertEqual(row["assignment"]["subject"],
                             "082500 航空宇航科学与技术")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["assignment"]["source_kind"],
                             "学院师资队伍·教师风采")
            # 职称只出现在 note 的说明里，不能出现在方向字段
            self.assertIsNone(TITLE.search(row["assignment"]["direction"]))

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
        for key, url, html in self.pages:
            self.assertIsNone(EMAIL.search(html), f"快照里仍有邮箱：{key}")
            self.assertIsNone(PHONE.search(html), f"快照里仍有电话：{key}")
            replaced += html.count("联系方式已隐去")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(replaced, 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 39 人
        self.assertEqual(len(self.rows), 39)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员容器里塞一个过不了
        # NAME_RE、也没登记跳过的条目，解析器必须抛错提醒更新解析器，而不是悄悄少收人。
        html = self.pages[0][2]
        self.assertIn(FIRST_CARD, html)
        broken = html.replace(FIRST_CARD, _card("张三（兼职）") + FIRST_CARD, 1)
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][1], SPECS[0])

    def test_non_cjk_name_is_skipped_and_counted(self):
        # 非中文姓名不音译、不截断：显式跳过，容器守卫按「条目数 = 解析数 + 跳过数」核对。
        html = self.pages[0][2]
        broken = html.replace(FIRST_CARD, _card("John Smith") + FIRST_CARD, 1)
        rows = parse(broken, self.pages[0][1], SPECS[0])
        self.assertEqual(len(rows), 12)  # 12 个中文姓名，1 个拉丁字母姓名被跳过
        self.assertNotIn("JohnSmith", [row["name"] for row in rows])
        # 两个外籍姓名也照样跳过并计数，不会让容器守卫误判
        broken2 = html.replace(FIRST_CARD,
                               _card("John Smith") + _card("Jane Doe") + FIRST_CARD, 1)
        self.assertEqual(len(parse(broken2, self.pages[0][1], SPECS[0])), 12)

    def test_title_suffix_is_stripped_from_names(self):
        # 红线 1：如果锚文本/姓名是「姓名+职称」拼接，剥掉后缀后必须通过 NAME_RE。
        html = self.pages[0][2]
        broken = html.replace(FIRST_CARD, _card("李四副教授") + FIRST_CARD, 1)
        rows = parse(broken, self.pages[0][1], SPECS[0])
        names = [row["name"] for row in rows]
        self.assertEqual(len(rows), 13)
        self.assertIn("李四", names)
        for name in names:
            self.assertIsNone(TITLE.search(name))

    def test_duplicate_name_on_one_page_breaks_the_guard(self):
        html = self.pages[0][2]
        broken = html.replace(FIRST_CARD, _card("孟庆春") + FIRST_CARD, 1)
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][1], SPECS[0])

    def test_link_that_is_not_a_personal_page_breaks(self):
        # 红线 5：详情页链接不能回落成名录页/栏目页。
        html = self.pages[0][2]
        broken = html.replace(
            FIRST_CARD, _card("王五", href="../../szdw/jsfc/htfxqjsx.htm") + FIRST_CARD, 1)
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][1], SPECS[0])

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>师资队伍 教师风采 航天飞行器技术系 孟庆春 教授</body></html>",
                  LISTINGS[0], SPECS[0]),
            [],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
