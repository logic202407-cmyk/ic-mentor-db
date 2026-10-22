"""上海理工大学 健康科学与工程学院 生物医学工程学科导师名录（0831 生物医学工程）离线检查.

只读 ``workbench/tests/fixtures/usst_bme.html`` 与 ``usst_bme_p2.html`` … ``_p7.html``，
不联网：学校站点改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录共 93 条、解析出 92 条（1 位外籍导师姓名为拉丁字母，不在 ``NAME_RE`` 范围内，
  已登记跳过，不做音译/截断），逐页人数与页面自报的「每页 14 条 / 共 93 条」对得上；
* 姓名是真人、不带职称，也不是导航（分页、面包屑、栏目名都不得混进来）；
* ``homepage`` 必须是指向个人详情页的 ``/<年>/<月日>/c<栏>a<id>/page.htm``，不能回落成
  名录页，且 92 个人 92 个不同的详情页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话，7 份快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 容器内条目数与解析结果不一致时必须抛错（红线 4 的「核对恰好 N 人」）。
"""

import json
import pathlib
import re
import unittest

from workbench.sources.usst_bme import (
    EXPECTED_PER_PAGE,
    EXPECTED_ROSTER,
    PUBLISHED_ENTRIES,
    SKIPPED_NON_CJK,
    SPECS,
    parse,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(r"^https://jiankang\.usst\.edu\.cn/\d{4}/\d{4}/c\d+a\d+/page\.htm$")

# 页面自己的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "学院概况", "师资队伍", "导师信息", "教师名录", "生物医学工程",
    "食品科学与工程", "生物工程", "联合培养单位", "联系我们", "版权所有",
    "上一页", "下一页", "尾页", "第一页", "学科专业", "个人简介", "研究方向",
)


class UsstBmeSourceTests(unittest.TestCase):
    """0831 生物医学工程 — 上海理工大学健康科学与工程学院生物医学工程学科导师."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.pages = []
        cls.rows = []
        for page in range(1, cls.spec["max_pages"] + 1):
            name = ("usst_bme.html" if page == 1 else f"usst_bme_p{page}.html")
            html = (FIXTURES / name).read_text(encoding="utf-8")
            url = cls.spec["listing"].format(page=page)
            cls.pages.append((url, html))
            cls.rows.extend(parse(html, url, cls.spec))
        cls.names = [row["name"] for row in cls.rows]

    def test_spec_targets_the_bme_discipline(self):
        spec = self.spec
        self.assertEqual(spec["key"], "usst_bme")
        self.assertEqual(spec["code"], "0831")
        self.assertEqual(spec["discipline"], "生物医学工程")
        self.assertEqual(spec["institution"], "上海理工大学")
        self.assertEqual(spec["department"], "健康科学与工程学院")
        self.assertEqual(spec["listing"],
                         "https://jiankang.usst.edu.cn/18088/list{page}.htm")
        # 名录共 7 页（页面自报 93 条、每页 14 条）
        self.assertEqual(spec["max_pages"], 7)
        self.assertIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_roster_across_pages(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 92)
        # 逐页人数 = 每页 14 条（第 2 页含 1 位外籍导师被登记跳过，故 13）
        counts = []
        for page, (url, html) in enumerate(self.pages, start=1):
            counts.append(len(parse(html, url, self.spec)))
        self.assertEqual(tuple(counts), EXPECTED_PER_PAGE)
        # 页面自报 93 条：93 = 92 条入库 + 1 条登记跳过的拉丁字母姓名
        self.assertEqual(PUBLISHED_ENTRIES, 93)
        self.assertEqual(len(self.rows) + len(SKIPPED_NON_CJK), PUBLISHED_ENTRIES)

    def test_roster_is_deduplicated(self):
        # 同一个人不能因跨页/重复出现而在库里变成多条
        self.assertEqual(len(set(self.names)), 92)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), 92)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的锚文本）
        for expected in ("柏杨", "常兆华", "喻洪流", "宋成利", "刘宝林",
                         "胥义", "孟巧玲", "李清都"):
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
            # 不能回落到名录页本身：那会把 92 个人指到同一份名单
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertNotIn("list", row["homepage"].rsplit("/", 1)[-1])
        self.assertEqual(len({row["homepage"] for row in self.rows}), 92)
        # assignment.url 必须是该行所在的具体分页，而不是笼统的栏目
        page_urls = {url for url, _ in self.pages}
        for row in self.rows:
            self.assertIn(row["assignment"]["url"], page_urls)
        self.assertEqual(len(page_urls), 7)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0831 生物医学工程")
            self.assertEqual(row["assignment"]["subject"], "083100 生物医学工程")
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
        # 脱敏没有破坏名录：快照仍能解析出全部 92 人
        self.assertEqual(len(self.rows), 92)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员容器里塞一个过不了
        # NAME_RE、也没登记跳过的条目，解析器必须抛错提醒更新解析器，而不是悄悄少收人。
        marker = '<li class="news n14"'
        self.assertIn(marker, self.pages[0][1])
        broken = self.pages[0][1].replace(
            marker,
            '<li class="news n99" img-src="">'
            '<a class="news_wz" href="/2026/0101/c18088a1/page.htm">'
            '<div class="news_title">张三（兼职）</div></a></li>\n' + marker,
            1,
        )
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][0], self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>导师信息 生物医学工程 柏杨 教授</body></html>",
                  self.spec["listing"].format(page=1), self.spec),
            [],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
