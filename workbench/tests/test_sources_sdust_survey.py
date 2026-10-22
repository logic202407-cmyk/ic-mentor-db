"""山东科技大学 测绘与空间信息学院「师资总览」离线检查（0816 测绘科学与技术）.

只读 ``workbench/tests/fixtures/sdust_survey.html``，不联网：学校站点改版不应把
这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 该页七个单元共 109 个条目，四个教学系 88 人（测绘工程系 29、地理信息科学系 19、
  遥感科学与技术系 20、海洋测绘系 20）；
* 综合办公室 6、学生工作办公室 9、实验中心 6 共 21 条按非教学单位范围排除，
  不静默丢人：88 + 21 = 109 必须守恒；
* 88 个互不相同的姓名与 88 个互不相同的个人详情页，全部指向教学栏目（1186–1197）；
* 姓名是真人、不带职称、不带页面标记符 ``*``，也不是导航/页脚；
* ``direction`` 一律「方向待补」，职称只写在 note 里，不作为研究方向；
* 行里没有邮箱、电话；名录快照落盘前已脱敏（「没有残留」+「至少发生过一次替换」，
  不硬编码占位符出现次数——后续再补一处脱敏不应该把测试改红）；
* 容器内条目数与解析结果不一致时必须抛错（红线 4 的「核对恰好 N 人」）；
* 拉丁字母姓名显式跳过、不音译不截断；「姓名+职称」拼接形式剥后缀后可正常收录。

补入量算术：0816 现状 126 条 / 2 所，武汉大学 114 条（90.48%）。唯一判据是
``max(原主导, N) / (原总数 + N) < 60%``，故 N ≥ 65 即达标（另一侧 N ≤ 188）。
本来源 88 条：补后总量 214，武汉大学 114/214 = 53.27%、山东科技大学 88/214 =
41.12%，最大机构 53.27% < 60%。
"""

import json
import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.sources.sdust_survey import (
    EXPECTED_ENTRIES,
    EXPECTED_ROWS,
    LISTING,
    SKIPPED_NON_CJK,
    SPECS,
    parse,
    parse_with_stats,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教|工程师|导师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(r"^https://gc\.sdust\.edu\.cn/info/(\d+)/\d+\.htm$")

# 非教学栏目：综合办公室 1083、学生工作办公室 1084、实验中心 1085。
NON_TEACHING_CATEGORIES = {"1083", "1084", "1085"}
TEACHING_CATEGORIES = {str(n) for n in range(1186, 1198)}

# 页面自己的栏目名/导航词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "师资队伍", "师资总览", "教师名录", "下一页", "尾页", "查看更多",
    "测绘工程系", "地理信息科学系", "遥感科学与技术系", "海洋测绘系",
)

# 页面上按非教学单位列出的真人：按范围排除，不能出现在结果里。
SUPPORT_NAMES = (
    "范俊峰", "刘峰", "杨丽", "于焕菊", "孙志勇", "王喜芹",   # 综合办公室
    "刘凤英", "赵会兴", "李万武", "张灵先", "李婷", "杨安秀",  # 实验中心
)

EXPECTED_UNITS = (
    "综合办公室", "学生工作办公室", "实验中心", "测绘工程系",
    "地理信息科学系", "遥感科学与技术系", "海洋测绘系",
)
TEACHING_UNITS = ("测绘工程系", "地理信息科学系", "遥感科学与技术系", "海洋测绘系")
EXPECTED_PER_UNIT = {
    "测绘与空间信息学院·测绘工程系": 29,
    "测绘与空间信息学院·地理信息科学系": 19,
    "测绘与空间信息学院·遥感科学与技术系": 20,
    "测绘与空间信息学院·海洋测绘系": 20,
}
EXPECTED_EXCLUDED = {"综合办公室": 6, "学生工作办公室": 9, "实验中心": 6}

# 0816 现状：武汉大学 114 + 中国科学院大学 12 = 126；武汉大学占 90.48%。
BASELINE_TOTAL = 126
BASELINE_TOP = 114
BASELINE_TOP_SHARE = 114 / 126


class SdustSurveySourceTests(unittest.TestCase):
    """0816 测绘科学与技术 — 山东科技大学测绘与空间信息学院."""

    @classmethod
    def setUpClass(cls):
        cls.html = (FIXTURES / "sdust_survey.html").read_text(encoding="utf-8")
        cls.url = SPECS[0]["listing"]
        cls.rows, cls.stats = parse_with_stats(cls.html, cls.url, SPECS[0])
        cls.names = [row["name"] for row in cls.rows]

    def test_specs_target_the_surveying_discipline(self):
        self.assertEqual(len(SPECS), 1)
        spec = SPECS[0]
        self.assertEqual(spec["key"], "sdust_survey")
        self.assertEqual(spec["code"], "0816")
        self.assertEqual(spec["institution"], "山东科技大学")
        self.assertEqual(spec["department"], "测绘与空间信息学院")
        self.assertEqual(spec["discipline"], "测绘科学与技术")
        self.assertEqual(spec["listing"], LISTING)
        self.assertEqual(spec["max_pages"], 1)
        self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_teaching_roster(self):
        self.assertEqual(len(self.rows), EXPECTED_ROWS)
        self.assertEqual(EXPECTED_ROWS, 88)
        self.assertEqual(self.stats["entries"], EXPECTED_ENTRIES)
        self.assertEqual(EXPECTED_ENTRIES, 109)
        # 109 个条目 = 88 条解析 + 0 个非中文姓名 + 21 条非教学单位范围排除
        self.assertEqual(self.stats["excluded"], EXPECTED_EXCLUDED)
        self.assertEqual(
            len(self.rows) + len(self.stats["skipped_non_cjk"])
            + sum(self.stats["excluded"].values()),
            self.stats["entries"],
        )
        self.assertEqual(self.stats["skipped_non_cjk"], [])
        self.assertEqual(len(SKIPPED_NON_CJK), 0)
        self.assertEqual(tuple(self.stats["units"]), EXPECTED_UNITS)

    def test_each_department_is_fully_counted(self):
        counts = {}
        for row in self.rows:
            counts[row["department"]] = counts.get(row["department"], 0) + 1
        self.assertEqual(counts, EXPECTED_PER_UNIT)
        self.assertEqual(sum(counts.values()), EXPECTED_ROWS)
        # 四个系各自是「学院·系」，不含综合办公室/学生工作办公室/实验中心
        for department in counts:
            self.assertTrue(department.startswith("测绘与空间信息学院·"))

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
            # 页面标记符（* / ＊）不是姓名的一部分
            self.assertNotIn("*", name)
            self.assertNotIn("＊", name)
        # 页面上的真人（逐个核对过快照里的姓名卡片，四个系各取几人）
        for expected in ("靳奉祥", "涂锐", "郭金运", "艾波", "黄珏",
                         "赵丰", "彭东东", "张燕"):
            self.assertIn(expected, self.names)
        # 带 * 标记的条目剥掉标记后是能收录的真人
        for marked in ("龚晓东", "郑玉新", "孔巧丽", "洪菊"):
            self.assertIn(marked, self.names)
        # 导航/栏目词不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)
        # 非教学单位人员按范围排除，不能出现在结果里
        for support in SUPPORT_NAMES:
            self.assertNotIn(support, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            match = PERSON_PAGE.fullmatch(row["homepage"])
            self.assertIsNotNone(match, row["homepage"])
            self.assertNotIn(match.group(1), NON_TEACHING_CATEGORIES)
            self.assertIn(match.group(1), TEACHING_CATEGORIES)
            # 不能回落到名录页本身：那会把 88 个人指到同一份名单
            self.assertNotEqual(row["homepage"], row["assignment"]["url"])
            self.assertNotIn("/szdw/", row["homepage"])
            # assignment.url 必须是该行所在的师资总览页
            self.assertEqual(row["assignment"]["url"], self.url)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0816 测绘科学与技术")
            self.assertEqual(row["assignment"]["subject"], "081600 测绘科学与技术")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["assignment"]["source_kind"],
                             "学院师资队伍（师资总览）")
            # 职称只进 note，不能变成方向
            self.assertIn("职称：", row["assignment"]["note"])

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
        self.assertNotRegex(self.html, r"(?:电话|传真)[：:]\s*\d")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(self.html.count("联系方式已隐去"), 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 88 人
        self.assertEqual(len(parse(self.html, self.url, SPECS[0])), EXPECTED_ROWS)

    def test_star_marker_is_stripped_not_kept(self):
        # 页面有 13 个姓名带 *，剥掉标记后仍是同一个人；不能把 * 带进姓名。
        stars = [a.get_text() for a in BeautifulSoup(self.html, "html.parser").select(
            "div.teacher_list a[href]") if re.sub(r"\s+", "", a.get_text()).endswith("*")]
        self.assertEqual(len(stars), 13)
        self.assertIn("龚晓东", self.names)
        self.assertNotIn("龚晓东*", self.names)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员格塞一个过不了
        # NAME_RE 的导航词，解析器必须抛错，而不是悄悄当成第 89 个人。
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            self._item("下一页", "1186", "999999"),
        ])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_latin_name_is_skipped_not_transliterated(self):
        # 红线 1：非中文姓名不音译、不截断，显式跳过并计数；容器核对仍应通过。
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            self._item("John Smith", "1186", "999998"),
        ])
        rows, stats = parse_with_stats(page, self.url, SPECS[0])
        self.assertEqual([row["name"] for row in rows], ["靳奉祥"])
        self.assertEqual(stats["skipped_non_cjk"], ["JohnSmith"])
        self.assertEqual(stats["entries"], 2)

    def test_title_suffix_is_stripped_before_validation(self):
        # 红线 1：「姓名+职称」拼接形式剥掉后缀后应能正常收录，且不把职称带进姓名。
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            self._item("李四教授", "1186", "999997"),
        ])
        names = {row["name"] for row in parse(page, self.url, SPECS[0])}
        self.assertEqual(names, {"靳奉祥", "李四"})
        self.assertNotIn("李四教授", names)

    def test_missing_detail_link_breaks_the_guard(self):
        # 姓名条目必须指向个人详情页；指回栏目页说明结构变了，不能当成人名收下。
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            '<li><a href="../szdw/szzl.htm">王五</a></li>',
        ])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_non_person_entry_without_link_breaks_the_guard(self):
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            "<li>王五</li>",
        ])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_admin_category_link_breaks_the_guard(self):
        # 教学系的人员格里出现综合办公室的个人页，说明结构错位，不能当教学岗收下。
        page = self._mini([
            self._item("靳奉祥", "1186", "6891"),
            self._item("范俊峰", "1083", "5953"),
        ])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_unknown_unit_breaks_the_guard(self):
        page = self._mini([self._item("靳奉祥", "1186", "6891")],
                          unit="党委", units=["党委"])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_missing_teaching_department_breaks_the_guard(self):
        # 四个系必须都在；只剩非教学单位时不能返回 0 行假装名录是空的。
        page = self._mini([self._item("靳奉祥", "1186", "6891")],
                          unit="实验中心", units=["实验中心"])
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_empty_roster_breaks_the_guard(self):
        # 人员格全空（改版成前端渲染）时抛错，交给契约测试暴露，而不是静默 0 行。
        with self.assertRaises(ValueError):
            parse(self._mini([]), self.url, SPECS[0])

    def test_entry_outside_a_rank_heading_breaks_the_guard(self):
        # 教学系的人员格必须落在已知职称分组下；没有分组说明页面结构变了。
        page = self._mini([self._item("靳奉祥", "1186", "6891")], rank="")
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_person_grid_nested_in_a_wrapper_breaks_the_guard(self):
        # 人员格不再是单元块的直接子节点时，按直接子节点遍历会漏人：必须抛错。
        item = self._item("靳奉祥", "1186", "6891")
        blocks = []
        for unit in TEACHING_UNITS:
            body = (f'<div class="teacher_list"><ul>{item}</ul></div>'
                    if unit == "测绘工程系"
                    else '<div class="wrap"><div class="teacher_list"><ul></ul>'
                         "</div></div>")
            blocks.append(
                '<div class="teacher_item">'
                f'<div class="tit"><p>{unit}</p></div>'
                f'<h2 class="teacher_zitem">教授</h2>{body}</div>'
            )
        page = ('<html><body><div class="teacher_zhpgae">'
                + "".join(blocks) + "</div></body></html>")
        with self.assertRaises(ValueError):
            parse(page, self.url, SPECS[0])

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>师资总览 测绘工程系 靳奉祥 郭金运</body></html>",
                  self.url, SPECS[0]),
            [],
        )

    def test_adding_this_source_brings_the_top_share_below_the_cap(self):
        # 0816 现状：武汉大学 114/126 = 90.48%，超过 60% 的集中度上限。
        self.assertAlmostEqual(BASELINE_TOP_SHARE, 0.9048, places=4)
        self.assertGreater(BASELINE_TOP_SHARE, 0.6)
        added = len(self.rows)
        total = BASELINE_TOTAL + added
        top = max(BASELINE_TOP, added)
        self.assertLess(top / total, 0.6)
        # 补后：武汉大学 114/214 = 53.27%，山东科技大学 88/214 = 41.12%。
        self.assertAlmostEqual(BASELINE_TOP / total, 0.5327, places=4)
        self.assertAlmostEqual(added / total, 0.4112, places=4)
        # 唯一判据是「压到 60% 以下」，下界 N ≥ 65；本来源 88 条已越过下界。
        self.assertGreaterEqual(added, 65)
        # 另一侧：自己不得变成新的独大（N ≤ 188）。
        self.assertLess(added / total, 0.6)

    # --- helpers -------------------------------------------------------

    def _mini(self, items, unit="测绘工程系", rank="教授", units=None):
        """拼一张最小「师资总览」：四个教学系默认都在，``items`` 放进 ``unit``。

        缺系的场景由 ``units`` 显式指定，以便单独验证「四个系必须都在」的守卫。
        """
        if units is None:
            units = TEACHING_UNITS
        heading = f'<h2 class="teacher_zitem">{rank}</h2>' if rank else ""
        blocks = []
        for name in units:
            body = "".join(items) if name == unit else ""
            blocks.append(
                '<div class="teacher_item">'
                f'<div class="tit"><p>{name}</p></div>{heading}'
                f'<div class="teacher_list"><ul>{body}</ul></div>'
                "</div>"
            )
        return ('<html><body><div class="teacher_zhpgae">'
                + "".join(blocks) + "</div></body></html>")

    @staticmethod
    def _item(name, category, page_id):
        return (f'<li><a href="../info/{category}/{page_id}.htm" '
                f'target="_blank">{name}</a></li>')


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
