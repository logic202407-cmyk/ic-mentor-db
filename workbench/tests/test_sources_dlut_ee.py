"""大连理工大学 电气工程学院 教师名录（0808 电气工程）离线检查.

只读 ``workbench/tests/fixtures/dlut_ee.html``，不联网：学院改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录页共 57 张教师卡片（正高级 18 / 副高级 23 / 中级 11 / 博士后 5），解析出 50 条；
  另 7 条**在册但没有个人主页**（5 条锚点是 ``#``、2 条连锚点都没有），显式跳过并
  计数，不给它们编造主页、也不回落到名录页；容器守卫要求 57 = 50 + 7；
* 姓名是真人、不带职称，也不是导航；卡片里被注释掉的职称块、四个职称分组标题都不得
  混进姓名；
* ``homepage`` 必须是 ``faculty.dlut.edu.cn/<账号>/zh_CN/…`` 的个人主页，50 个人
  50 个不同地址，且不等于名录页本身；
* ``direction`` 一律 ``方向待补``——职称分组只写进 note，不写进方向字段；学院另一张
  「师资队伍」概况页按研究方向分组，本来源不采其分组；
* 行里没有邮箱、电话；快照落盘前已脱敏（"没有残留" + "至少发生过一次替换"，
  不硬编码占位符出现次数）；
* 容器内条目数与「解析数 + 跳过数」对不上时必须抛错（红线 4）。
"""

import collections
import json
import pathlib
import re
import unittest

from workbench.sources.dlut_ee import (
    EXPECTED_BY_GROUP,
    EXPECTED_ROSTER,
    PUBLISHED_ENTRIES,
    SKIPPED_NON_CJK,
    SKIPPED_NO_HOMEPAGE,
    SPECS,
    parse,
    parse_with_skips,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
LISTING = "https://ee.dlut.edu.cn/szdw/jsml.htm"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|讲师|研究员|高工|院士|博士后|助教|工程师|实验师|导师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
# 个人主页：站点自己会写出连续两个斜杠，两种都算。
PERSON_PAGE = re.compile(r"^https?://faculty\.dlut\.edu\.cn/{1,2}[0-9A-Za-z_]+/zh_CN/")
# note 里的职称分组，用来核对分组没有被写进方向字段。
GROUP_IN_NOTE = re.compile(r"本条目所在分组：([^）]+)）")

# 页面上的栏目/导航词与分组标题：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "学院概况", "师资队伍", "教师名录", "科学研究", "人才培养", "招生就业",
    "党群工作", "合作交流", "办事指南", "导师信息", "教学名师", "科研团队",
    "电气工程", "实验教学", "正高级", "副高级", "中级", "博士后",
)

# 卡片容器开标签：注入用（每张卡片的第一个 class 都是 team-block）。
CARD_OPEN = '<div class="team-block '


def _card(name: str, href: str) -> str:
    """拼一张教师卡片，用来模拟页面结构变化。"""
    return (
        '<div class="team-block col-lg-3-faculty-2 col-md-3 col-sm-12">'
        '<div class="inner-box">'
        f'<a href="{href}" target="_blank">'
        '<div class="image"><img alt="" src="../jspic/x.png"/></div>'
        f'<div class="lower-content"><h3 style="text-align:center">{name}</h3></div>'
        "</a></div></div>\n"
    )


class DlutEeSourceTests(unittest.TestCase):
    """0808 电气工程 — 大连理工大学电气工程学院教师名录."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / "dlut_ee.html").read_text(encoding="utf-8")
        cls.rows, cls.skipped = parse_with_skips(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]
        cls.groups = collections.Counter(
            match.group(1)
            for row in cls.rows
            for match in [GROUP_IN_NOTE.search(row["assignment"]["note"])]
            if match
        )

    def test_spec_targets_the_electrical_discipline(self):
        spec = self.spec
        self.assertEqual(spec["key"], "dlut_ee")
        self.assertEqual(spec["code"], "0808")
        self.assertEqual(spec["discipline"], "电气工程")
        self.assertEqual(spec["institution"], "大连理工大学")
        self.assertEqual(spec["department"], "电气工程学院")
        self.assertEqual(spec["listing"], LISTING)
        # 单页名录：一页一个 key，listing 里没有分页占位符
        self.assertEqual(spec["max_pages"], 1)
        self.assertNotIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_roster_on_the_single_page(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 50)
        # 页面自报的卡片数 = 解析数 + 跳过数（红线 4 的守卫口径）
        self.assertEqual(PUBLISHED_ENTRIES, 57)
        self.assertEqual(len(self.rows) + len(self.skipped), PUBLISHED_ENTRIES)
        self.assertEqual(PUBLISHED_ENTRIES, self.html.count(CARD_OPEN))

    def test_rank_groups_are_recorded_without_leaking_into_direction(self):
        # 四个职称分组标题都在页面上；入库行按组分布与实录一致
        for group in EXPECTED_BY_GROUP:
            self.assertIn(group, self.html)
        # 分组只出现在 note 里，方向字段对每组都是「方向待补」
        self.assertEqual({group: self.groups.get(group, 0) for group in EXPECTED_BY_GROUP},
                         EXPECTED_BY_GROUP)
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertRegex(row["assignment"]["note"], GROUP_IN_NOTE)

    def test_the_seven_cards_without_a_page_are_skipped_and_counted(self):
        # 没有个人主页的在册教师：跳过并登记，原因只有一类
        self.assertEqual(len(self.skipped), 7)
        self.assertEqual({item["reason"] for item in self.skipped}, {"no_homepage"})
        self.assertEqual({item["name"] for item in self.skipped},
                         set(SKIPPED_NO_HOMEPAGE))
        # 它们既不在结果里，也没有被指到名录页本身
        for skipped in SKIPPED_NO_HOMEPAGE:
            self.assertNotIn(skipped, self.names)
        self.assertNotIn(LISTING, {row["homepage"] for row in self.rows})
        # 本次没有拉丁字母姓名，登记表为空
        self.assertEqual(SKIPPED_NON_CJK, ())

    def test_roster_is_deduplicated(self):
        self.assertEqual(len(set(self.names)), 50)
        keys = {(row["institution"], row["department"], row["name"]) for row in self.rows}
        self.assertEqual(len(keys), 50)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的 h3）
        for expected in ("董恩源", "段雄英", "李卫星", "袁铁江", "孙长海", "巴宇",
                         "张颖杰", "晁璞璞", "严梓铭", "彭琦琳"):
            self.assertIn(expected, self.names)
        # 栏目/导航/职称分组标题/被注释掉的职称块都不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            self.assertNotEqual(row["homepage"], LISTING)
        self.assertEqual(len({row["homepage"] for row in self.rows}), 50)
        # assignment.url 必须是名录页本身（单页来源）
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], LISTING)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0808 电气工程")
            self.assertEqual(row["assignment"]["subject"], "080800 电气工程")
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

    def test_snapshot_is_scrubbed(self):
        self.assertIsNone(EMAIL.search(self.html), "快照里仍有邮箱")
        self.assertIsNone(PHONE.search(self.html), "快照里仍有电话")
        # 至少发生过一次替换；不写死次数，避免以后补一处脱敏就把测试改红。
        self.assertGreaterEqual(self.html.count("联系方式已隐去"), 1)
        # 脱敏没有破坏名录：快照仍能解析出全部 50 人
        self.assertEqual(len(parse(self.html, LISTING, self.spec)), 50)

    def test_rank_suffix_is_stripped_before_validation(self):
        # 红线 1：拼接式姓名先剥后置职称再校验；剥完必须仍能入库
        broken = self.html.replace(
            CARD_OPEN,
            _card("张三教授", "https://faculty.dlut.edu.cn//zhangsan/zh_CN/index.htm")
            + CARD_OPEN,
            1,
        )
        rows = parse(broken, LISTING, self.spec)
        self.assertEqual(len(rows), 51)
        names = [row["name"] for row in rows]
        self.assertIn("张三", names)
        self.assertNotIn("张三教授", names)

    def test_non_cjk_name_is_skipped_and_counted(self):
        # 红线 1：非中文姓名显式跳过并计数，不做音译/截断；守卫仍要配平
        broken = self.html.replace(
            CARD_OPEN,
            _card("John Smith", "https://faculty.dlut.edu.cn//jsmith/zh_CN/index.htm")
            + CARD_OPEN,
            1,
        )
        rows, skipped = parse_with_skips(broken, LISTING, self.spec)
        self.assertEqual(len(rows), 50)
        self.assertEqual([item["name"] for item in skipped if item["reason"] == "non_cjk"],
                         ["John Smith"])
        self.assertEqual(len(rows) + len(skipped), PUBLISHED_ENTRIES + 1)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：往人员容器里塞一个过不了 NAME_RE、也没登记跳过的条目，解析器必须抛错
        # 提醒更新解析器，而不是悄悄少收人。
        broken = self.html.replace(
            CARD_OPEN,
            _card("张三（兼职）", "https://faculty.dlut.edu.cn//zs/zh_CN/index.htm")
            + CARD_OPEN,
            1,
        )
        with self.assertRaises(ValueError):
            parse(broken, LISTING, self.spec)

    def test_unexpected_link_shape_breaks_the_parser(self):
        # 链接形态变了宁可停下，也不要把栏目页当个人主页写进 homepage
        broken = self.html.replace(
            CARD_OPEN, _card("李四", "szdw/other.htm") + CARD_OPEN, 1)
        with self.assertRaises(ValueError):
            parse(broken, LISTING, self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空，也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>教师名录 电气工程学院 董恩源 教授</body></html>",
                  LISTING, self.spec),
            [],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
