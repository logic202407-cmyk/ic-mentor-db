"""大连理工大学 能源与动力学院 教师列表（0807 动力工程及工程热物理）离线检查.

只读 ``workbench/tests/fixtures/dlut_energy.html`` 与 ``dlut_energy_p2.html`` … ``_p12.html``，
不联网：教师主页系统改版不应把这里的断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 列表共 12 页、133 条卡片，解析出 132 条；133 = 132 + 1 条**同院同名**（第 1 页两位
  「鲍民乐」，职称不同、个人主页也不同，合并键「机构 + 院系 + 姓名」装不下两条），
  第二条显式登记跳过；容器守卫要求「卡片数 = 解析数 + 跳过数」；
* 姓名是真人、不带职称，也不是导航（单位列表、教师索引、职称分组、页码都不得混进来）；
* ``homepage`` 必须是 ``faculty.dlut.edu.cn/<账号>/zh_CN|en/index.htm`` 的个人详情页，
  不能回落成名录页；132 个人 132 个不同地址；
* ``direction`` 一律 ``方向待补``——卡片上的职称只写进 note，不作为研究方向；有 2 张卡片
  页面自己没写职称，note 记「未标注」，不替页面补；
* 行里没有邮箱、电话；12 份快照实测 0 命中，落盘前后都做过残留自检（"没有残留" +
  "脱敏器至少替换过一次"，不硬编码占位符出现次数）；
* 容器内条目数与「解析数 + 跳过数」对不上时必须抛错（红线 4）。
"""

import collections
import json
import pathlib
import re
import unittest

from workbench.sources import dlut_energy
from workbench.sources.dlut_energy import (
    EXPECTED_PAGES,
    EXPECTED_PER_PAGE,
    EXPECTED_ROSTER,
    PUBLISHED_ENTRIES,
    SKIPPED_DUPLICATE,
    SKIPPED_NON_CJK,
    SPECS,
    parse,
    parse_with_skips,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|讲师|研究员|高工|院士|博士后|助教|工程师|实验师|导师")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
# 个人详情页：多数是中文页，少数教师只有英文页（实测一位蒙古族姓名的教师）。
PERSON_PAGE = re.compile(
    r"^https?://faculty\.dlut\.edu\.cn/{1,2}[0-9A-Za-z_.-]+/(?:zh_CN|zh_TW|en)/index\.htm$"
)
# note 里的职称标注，用来核对职称只落在 note、没有写进方向字段。
RANK_IN_NOTE = re.compile(r"页面标注职称：([^）]+)）")

# 列表页上的栏目名/导航词/职称词：2–8 个汉字，姓名正则拦不住，必须确认没有混进名录。
NAV_WORDS = (
    "首页", "网站首页", "单位列表", "教师索引", "杰出人才", "个人主页",
    "团队主页", "科研团队", "教学团队", "自建团队", "机构主页", "科研机构",
    "教学机构", "团队检索", "机构检索", "能源与动力学院", "教授", "副教授",
    "助理研究员", "职称", "单位", "上一页", "下一页", "尾页", "版权所有",
)

# 卡片容器开标签：注入用（每张教师的第一个标签都是这个 li）。
CARD_OPEN = '<li data-aos="fade-up">'
CONTACT_PLACEHOLDER = "联系方式已隐去"


def scrub_contacts(text: str) -> tuple[str, int]:
    """落盘前用的脱敏器；返回 (文本, 替换次数)。与其它来源同一套规则。"""
    hits = 0
    for pattern in (EMAIL, PHONE):
        text, count = pattern.subn(CONTACT_PLACEHOLDER, text)
        hits += count
    return text, hits


def _card(name: str, href: str) -> str:
    """拼一张教师卡片，用来模拟页面结构变化。"""
    return (
        CARD_OPEN + "\n"
        f'<a href="{href}" target=_blank class="wl">\n'
        '<div class="pis"><div class="scale"><div class="imged"></div></div></div>\n'
        '<div class="con">\n'
        f"<h3>{name}</h3>\n"
        "<p>单位：能源与动力学院</p>\n"
        "<p>职称：教授</p>\n"
        '<h4 class="flex"><span class="flex">个人主页'
        '<img src="images/r-xq1.png" alt=""></span></h4>\n'
        "</div>\n</a>\n</li>\n"
    )


class DlutEnergySourceTests(unittest.TestCase):
    """0807 动力工程及工程热物理 — 大连理工大学能源与动力学院."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.pages = []
        cls.rows = []
        cls.skips = []
        for page in range(1, cls.spec["max_pages"] + 1):
            name = ("dlut_energy.html" if page == 1 else f"dlut_energy_p{page}.html")
            html = (FIXTURES / name).read_text(encoding="utf-8")
            url = cls.spec["listing"].format(page=page)
            rows, skipped = parse_with_skips(html, url, cls.spec)
            cls.pages.append((url, html))
            cls.rows.extend(rows)
            cls.skips.extend(skipped)
        cls.names = [row["name"] for row in cls.rows]
        cls.ranks = collections.Counter(
            match.group(1)
            for row in cls.rows
            for match in [RANK_IN_NOTE.search(row["assignment"]["note"])]
            if match
        )

    def test_spec_targets_the_energy_discipline(self):
        spec = self.spec
        self.assertEqual(spec["key"], "dlut_energy")
        self.assertEqual(spec["code"], "0807")
        self.assertEqual(spec["discipline"], "动力工程及工程热物理")
        self.assertEqual(spec["institution"], "大连理工大学")
        self.assertEqual(spec["department"], "能源与动力学院")
        self.assertIn("tsites.CollegeTeacherList", spec["listing"])
        self.assertIn("id=1154", spec["listing"])
        # 列表共 12 页（末页 1 人，第 13 页 0 条），分页靠 {page} 占位符
        self.assertEqual(spec["max_pages"], EXPECTED_PAGES)
        self.assertEqual(spec["max_pages"], 12)
        self.assertIn("{page}", spec["listing"])

    def test_parser_finds_the_whole_roster_across_pages(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 132)
        counts = tuple(len(parse(html, url, self.spec)) for url, html in self.pages)
        self.assertEqual(counts, EXPECTED_PER_PAGE)
        self.assertEqual(sum(counts), 132)
        # 页面自报 133 张卡片：133 = 132 条入库 + 1 条同院同名跳过
        self.assertEqual(PUBLISHED_ENTRIES, 133)
        self.assertEqual(len(self.rows) + len(self.skips), PUBLISHED_ENTRIES)
        # 每页卡片数 = 该页解析数 + 该页跳过数（红线 4 的守卫口径）。
        # 只有第 1 页有跳过（1 条同院同名），其余 11 页卡片数 = 解析数。
        for index, ((url, html), parsed_count) in enumerate(zip(self.pages, counts)):
            expected_cards = parsed_count + (1 if index == 0 else 0)
            self.assertEqual(html.count(CARD_OPEN), expected_cards, url)

    def test_roster_is_deduplicated(self):
        # 同一个人不能因跨页/重复出现而在库里变成多条
        self.assertEqual(len(set(self.names)), 132)
        keys = {(row["institution"], row["department"], row["name"])
                for row in self.rows}
        self.assertEqual(len(keys), 132)
        self.assertEqual({row["department"] for row in self.rows}, {"能源与动力学院"})

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的 h3）
        for expected in ("白敏丽", "鲍民乐", "常亚超", "董东升", "东明", "冯立岩",
                         "贺缨", "蒋兰兰", "宋永臣", "沈胜强", "唐大伟", "解茂昭",
                         "左建国"):
            self.assertIn(expected, self.names)
        # 导航/栏目/职称/单位名不是人名
        for noise in NAV_WORDS:
            self.assertNotIn(noise, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 132 个人指到同一份名单
            self.assertNotIn("xyjslb.jsp", row["homepage"])
            self.assertNotIn("list.htm", row["homepage"])
        self.assertEqual(len({row["homepage"] for row in self.rows}), 132)
        # assignment.url 必须是该行所在的具体分页，而不是笼统的栏目
        page_urls = {url for url, _ in self.pages}
        for row in self.rows:
            self.assertIn(row["assignment"]["url"], page_urls)
        self.assertEqual(len(page_urls), 12)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0807 动力工程及工程热物理")
            self.assertEqual(row["assignment"]["subject"],
                             "080700 动力工程及工程热物理")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")

    def test_rank_is_written_into_the_note_not_the_direction(self):
        # 卡片上的职称只进 note；方向字段对每一行都是「方向待补」
        self.assertGreaterEqual(len(self.ranks), 3)
        for rank in ("教授", "副教授", "助理研究员"):
            self.assertIn(rank, self.ranks)
        for row in self.rows:
            self.assertRegex(row["assignment"]["note"], RANK_IN_NOTE)
            self.assertEqual(row["assignment"]["direction"], "方向待补")

    def test_cards_without_a_published_rank_are_marked_unknown(self):
        # 有 2 张卡片的职称行页面自己就是空的（<p></p>）：note 记「未标注」，
        # 不替页面编一个职称，也不让空值变成方向。
        blank = [row for row in self.rows if "未标注" in row["assignment"]["note"]]
        self.assertEqual(len(blank), 2)
        self.assertEqual({row["name"] for row in blank}, {"汪婷婷", "张野"})
        for row in blank:
            self.assertEqual(row["assignment"]["direction"], "方向待补")

    def test_same_department_namesake_is_collapsed_and_counted(self):
        # 第 1 页有两位「鲍民乐」（职称不同、个人主页也不同），合并键只能留一条
        page1 = self.pages[0][1]
        self.assertEqual(page1.count(">鲍民乐<"), 2)
        duplicates = [item for item in self.skips if item["reason"] == "duplicate"]
        self.assertEqual([item["name"] for item in duplicates], list(SKIPPED_DUPLICATE))
        self.assertEqual(self.names.count("鲍民乐"), 1)
        # 跳过的不是"查无此人"：两条卡片各自都有个人主页
        self.assertEqual(page1.count("baominle"), 2)
        # 本次没有拉丁字母姓名
        self.assertEqual(SKIPPED_NON_CJK, ())
        self.assertEqual({item["reason"] for item in self.skips}, {"duplicate"})

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn(CONTACT_PLACEHOLDER, blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        for row in self.rows:
            self.assertNotRegex(row["assignment"]["note"], EMAIL)
            self.assertNotRegex(row["assignment"]["note"], PHONE)

    def test_snapshots_have_no_contact_residue(self):
        replaced = 0
        for url, html in self.pages:
            self.assertIsNone(EMAIL.search(html), f"快照里仍有邮箱：{url}")
            self.assertIsNone(PHONE.search(html), f"快照里仍有电话：{url}")
            self.assertNotIn("@", html, f"快照里仍有联系方式的痕迹：{url}")
            replaced += html.count(CONTACT_PLACEHOLDER)
        # 这 12 页本身**不含任何联系方式字段**（实测 0 命中），所以落盘时的替换次数是 0；
        # 「至少替换过一次」由下一个用例对脱敏器本身自检，而不是硬编码占位符出现次数。
        self.assertEqual(replaced, 0)
        # 脱敏没有破坏名录：快照仍能解析出全部 132 人
        self.assertEqual(len(self.rows), 132)

    def test_scrubber_is_not_a_noop(self):
        # 用运行期拼出的形状串自检脱敏器：源码里不出现完整的邮箱/号码样例。
        at = chr(64)
        sample = (
            f"<p>u{at}host.tld</p>"
            f"<p>{'-'.join(('0' + '10', '0' * 8))}</p>"
        )
        cleaned, hits = scrub_contacts(sample)
        self.assertGreaterEqual(hits, 1)
        self.assertIsNone(EMAIL.search(cleaned))
        self.assertIsNone(PHONE.search(cleaned))
        self.assertIn(CONTACT_PLACEHOLDER, cleaned)

    def test_source_module_carries_no_contact_sample(self):
        # 项目红线 3：源码与注释里不写完整电话号码或邮箱样例
        source = pathlib.Path(dlut_energy.__file__).read_text(encoding="utf-8")
        self.assertNotIn("@", source)
        self.assertIsNone(EMAIL.search(source))
        self.assertIsNone(PHONE.search(source))

    def test_rank_suffix_is_stripped_before_validation(self):
        # 红线 1：拼接式姓名先剥后置职称再校验；剥完必须仍能入库
        broken = self.pages[0][1].replace(
            CARD_OPEN,
            _card("张三教授",
                  "http://faculty.dlut.edu.cn/zhangsan/zh_CN/index.htm") + CARD_OPEN,
            1,
        )
        rows, skipped = parse_with_skips(broken, self.pages[0][0], self.spec)
        names = [row["name"] for row in rows]
        self.assertIn("张三", names)
        self.assertNotIn("张三教授", names)
        self.assertEqual(len(rows), 12)
        self.assertEqual(len(rows) + len(skipped), 13)

    def test_non_cjk_name_is_skipped_and_counted(self):
        # 红线 1：非中文姓名显式跳过并计数，不做音译/截断；守卫仍要配平
        broken = self.pages[0][1].replace(
            CARD_OPEN,
            _card("John Smith",
                  "http://faculty.dlut.edu.cn/jsmith/zh_CN/index.htm") + CARD_OPEN,
            1,
        )
        rows, skipped = parse_with_skips(broken, self.pages[0][0], self.spec)
        self.assertEqual(len(rows), 11)
        self.assertEqual(
            [item["name"] for item in skipped if item["reason"] == "non_cjk"],
            ["John Smith"],
        )
        self.assertEqual(len(rows) + len(skipped), 13)

    def test_entry_without_a_personal_page_is_skipped_and_counted(self):
        # 没有个人主页的在册条目：跳过并登记，不编造主页、也不回落到名录页
        broken = self.pages[0][1].replace(
            CARD_OPEN, _card("李四", "#") + CARD_OPEN, 1)
        rows, skipped = parse_with_skips(broken, self.pages[0][0], self.spec)
        self.assertEqual(len(rows), 11)
        self.assertEqual(
            [item["name"] for item in skipped if item["reason"] == "no_homepage"],
            ["李四"],
        )
        self.assertEqual(len(rows) + len(skipped), 13)
        self.assertNotIn("#", {row["homepage"] for row in rows})

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：往人员容器里塞一个过不了 NAME_RE、也没登记跳过的条目，解析器必须抛错
        # 提醒更新解析器，而不是悄悄少收人。
        broken = self.pages[0][1].replace(
            CARD_OPEN,
            _card("张三（兼职）",
                  "http://faculty.dlut.edu.cn/zs/zh_CN/index.htm") + CARD_OPEN,
            1,
        )
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][0], self.spec)

    def test_unexpected_link_shape_breaks_the_parser(self):
        # 链接形态变了宁可停下，也不要把栏目页当个人主页写进 homepage
        broken = self.pages[0][1].replace(
            CARD_OPEN, _card("李四", "szdw/other.htm") + CARD_OPEN, 1)
        with self.assertRaises(ValueError):
            parse(broken, self.pages[0][0], self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(
            parse("<html><body>单位列表 能源与动力学院 白敏丽 教授</body></html>",
                  self.spec["listing"].format(page=1), self.spec),
            [],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
