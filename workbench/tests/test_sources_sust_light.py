"""陕西科技大学 轻工科学与工程学院 皮革工程系（0822 轻工技术与工程）离线检查.

只读 ``workbench/tests/fixtures/sust_light.html``，不联网：学校站点改版不应把这里的
断言变红。

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录条数（容器内恰好 21 人：教授 9 / 副教授 10 / 讲师 2）；
* 姓名是真人、不带职称，也不是导航（页头「意见（监督）邮箱」不得混进来）；
* ``homepage`` 必须是指向个人详情页的 ``/info/<栏>/<id>.htm``，不能回落成名录页；
* ``direction`` 一律 ``方向待补``，职称只写在 note 里；
* 行里没有邮箱、电话，快照落盘前已脱敏；
* 容器内条目数与解析结果不一致时必须抛错（红线 4 的「核对恰好 N 人」）。
"""

import json
import pathlib
import re
import unittest

from workbench.sources.sust_light import EXPECTED_ROSTER, SPECS, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(r"^https://qg\.sust\.edu\.cn/info/\d+/\d+\.htm$")

# 页头的「意见（监督）邮箱」也指向 /info/1198/13874.htm：只按 href 抓就会把它当成人。
MAILBOX_PAGE = "https://qg.sust.edu.cn/info/1198/13874.htm"

# 名录里三个职称分组各自的人数，逐个数自页面自身的分组标题。
GROUPS = {"教授": 9, "副教授": 10, "讲师": 2}


class SustLightSourceTests(unittest.TestCase):
    """0822 轻工技术与工程 — 陕西科技大学轻工科学与工程学院·皮革工程系在册教师."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]

    def test_spec_targets_the_light_industry_discipline(self):
        self.assertEqual(self.spec["key"], "sust_light")
        self.assertEqual(self.spec["code"], "0822")
        self.assertEqual(self.spec["discipline"], "轻工技术与工程")
        self.assertEqual(self.spec["institution"], "陕西科技大学")
        self.assertEqual(self.spec["department"], "轻工科学与工程学院·皮革工程系")
        self.assertEqual(self.spec["listing"], "https://qg.sust.edu.cn/szdw2/gxsz/pggcx.htm")
        # 单页列完，不能靠翻页补人
        self.assertEqual(self.spec["max_pages"], 1)
        self.assertNotIn("{page}", self.spec["listing"])

    def test_parser_finds_the_whole_roster(self):
        self.assertEqual(len(self.rows), 21)
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        # 21 个不同姓名，没有一条被重复收进来
        self.assertEqual(len(set(self.names)), 21)
        for row in self.rows:
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0822 轻工技术与工程")
            self.assertEqual(row["assignment"]["subject"], "082200 轻工技术与工程")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "陕西科技大学")

    def test_roster_matches_the_pages_own_rank_groups(self):
        # 页面自己的三个分组标题各多少人，解析结果就该有多少人——不是"整页文本里
        # 有多少个汉字串"。
        for rank, expected in GROUPS.items():
            note_count = sum(
                1 for row in self.rows
                if f"本条目所在分组：{rank}" in row["assignment"]["note"])
            self.assertEqual(note_count, expected, f"{rank} 分组人数不对")
        self.assertEqual(sum(GROUPS.values()), 21)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的锚文本）
        for expected in ("高党鸽", "吕斌", "王学川", "官小玉", "吕游", "周庆芳"):
            self.assertIn(expected, self.names)
        # 导航/表头/页脚不是人名
        for noise in ("意见（监督）邮箱", "师资队伍", "各系师资", "皮革工程系",
                      "教授", "副教授", "讲师", "学院简介", "机构设置"):
            self.assertNotIn(noise, self.names)
        # 页头那个邮箱链接指向的地址不能成为任何人的 homepage
        self.assertNotIn(MAILBOX_PAGE, [row["homepage"] for row in self.rows])

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 21 个人指到同一份名单
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
        self.assertEqual(len({row["homepage"] for row in self.rows}), 21)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])

    def test_rank_is_recorded_in_the_note_not_the_direction(self):
        for row in self.rows:
            note = row["assignment"]["note"]
            self.assertTrue(any(f"本条目所在分组：{rank}" in note for rank in GROUPS))
            self.assertNotRegex(note, EMAIL)
            self.assertNotRegex(note, PHONE)

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("联系方式已隐去", blob)
        # 不在此写出具体号码：测试文件本身也不该成为联系方式的发布渠道。
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))

    def test_snapshot_is_scrubbed(self):
        self.assertIsNone(EMAIL.search(self.html), "快照里仍有邮箱")
        self.assertIsNone(PHONE.search(self.html), "快照里仍有电话")
        # 页脚原本有一处学院座机，已替换为占位符
        self.assertEqual(self.html.count("联系方式已隐去"), 1)
        # 脱敏没有破坏名录：快照仍能解析出 21 人
        self.assertEqual(len(self.rows), 21)

    def test_container_entry_that_is_not_a_person_breaks_the_guard(self):
        # 红线 4：容器内条目数与解析出的人数必须对得上。往人员容器里塞一个带后缀、
        # 过不了 NAME_RE 的条目（学院真实存在的「（双聘）」写法），解析器必须抛错
        # 提醒更新解析器，而不是悄悄少收一个人。
        marker = "</ul><script>_showDynClickBatch"
        self.assertIn(marker, self.html)
        broken = self.html.replace(
            marker,
            '<li><a href="/info/1808/99999.htm">张三（双聘）</a></li>'
            "</ul><script>_showDynClickBatch",
            1,
        )
        with self.assertRaises(ValueError):
            parse(broken, self.spec["listing"], self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(parse("<html><body>皮革工程系 教授 高党鸽</body></html>",
                              self.spec["listing"], self.spec), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
