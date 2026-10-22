"""同济大学 交通运输工程学院「交通信息与控制系」师资名录（0823 交通运输工程）离线检查.

只读两份快照，不联网：学校站点改版不应把这里的断言变红。

* ``fixtures/tjjt_trans_info.html``        —— 学院「师资队伍 → 教师名录」名录页
* ``fixtures/tjjt_trans_info_person.html`` —— 本系第一位教师的个人详情页（已脱敏）

这个文件是**独立**的，不并入 ``test_engineering_sources.py``（那份是全库契约测试）。
这里盯的是本来源自己的取数事实与项目红线：

* 名录页一页列完学院五个系／中心共 197 条，本来源**只收交通信息与控制系 35 人**
  （0823 的集中度上限决定的，见模块文档的算式）；
* 姓名是真人、不带职称，也不是导航；外文姓名显式跳过并计数；
* ``homepage`` 必须是指向个人详情页的 ``/info/2996/<id>.htm``（本系栏目号），
  不能回落成名录页，也不能借用别的系的栏目号；
* ``direction`` 一律 ``方向待补``；
* 行里没有邮箱、电话；名录页模板本身不含联系方式，个人详情页快照里的邮箱已脱敏。
"""

import json
import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.sources.tjjt_trans_info import (
    EXPECTED_ROSTER,
    SPECS,
    TARGET_UNIT,
    UNITS,
    parse,
    parse_with_stats,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
TITLE = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|助教")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_PAGE = re.compile(r"^https://tjjt\.tongji\.edu\.cn/info/2996/\d+\.htm$")

# 名录页整页的条目数（逐个数自页面自身的五个人员格：63 + 55 + 35 + 23 + 21）。
PAGE_ENTRIES = 197

# 其他四个系／中心的真人：同属 0823，但不属于本来源，绝不能出现在结果里。
OTHER_UNITS_PEOPLE = ("蔡武强",  # 交通设施系
                      "白玉",    # 交通运输规划与管理系
                      "陆正刚",  # 车辆与载运系
                      "曾国锋")  # 磁浮交通工程技术研究中心


class TjjtTransportInfoSourceTests(unittest.TestCase):
    """0823 交通运输工程 — 同济大学交通运输工程学院·交通信息与控制系在册教师."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.person_html = (FIXTURES / f"{cls.spec['key']}_person.html").read_text(encoding="utf-8")
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]

    def _inject(self, fragment):
        """把额外条目塞进目标系的人员格，用于核对跳过／报错逻辑。"""
        marker = f"<h4>{TARGET_UNIT}</h4>"
        self.assertIn(marker, self.html)
        start = self.html.index(marker)
        opening = '<div class="xilie">'
        cut = self.html.index(opening, start) + len(opening)
        return self.html[:cut] + fragment + self.html[cut:]

    @staticmethod
    def _target_block(html):
        """从整页 HTML 里切出目标系那一段（到下一个 h4 为止），独立数条目。"""
        start = html.index(f"<h4>{TARGET_UNIT}</h4>")
        nxt = html.find("<h4>", start + 1)
        return html[start:nxt if nxt != -1 else len(html)]

    def test_spec_targets_the_transport_discipline(self):
        self.assertEqual(self.spec["key"], "tjjt_trans_info")
        self.assertEqual(self.spec["code"], "0823")
        self.assertEqual(self.spec["discipline"], "交通运输工程")
        self.assertEqual(self.spec["institution"], "同济大学")
        self.assertEqual(self.spec["department"], "交通运输工程学院·交通信息与控制系")
        self.assertEqual(self.spec["listing"], "https://tjjt.tongji.edu.cn/szdw1/jsml.htm")
        # 单页列完，不能靠翻页补人
        self.assertEqual(self.spec["max_pages"], 1)
        self.assertNotIn("{page}", self.spec["listing"])

    def test_parser_finds_the_whole_roster(self):
        self.assertEqual(len(self.rows), EXPECTED_ROSTER)
        self.assertEqual(len(self.rows), 35)
        # 35 个不同姓名，没有一条被重复收进来
        self.assertEqual(len(set(self.names)), 35)
        for row in self.rows:
            self.assertEqual(row["institution"], "同济大学")
            self.assertEqual(row["assignment"]["first_level_discipline"],
                             "0823 交通运输工程")
            self.assertEqual(row["assignment"]["subject"], "082300 交通运输工程")
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertIn("教师名录", row["assignment"]["source_kind"])

    def test_only_one_unit_of_the_five_is_collected(self):
        # 名录页一页列出五个系／中心共 197 条，本来源只收其中一个系（集中度上限所致）。
        self.assertEqual(self.html.count('<div class="xilie_xm">'), PAGE_ENTRIES)
        self.assertEqual(self.html.count('<div class="xilie">'), len(UNITS))
        self.assertEqual(len(self.rows), 35)
        self.assertEqual(len(UNITS), 5)
        # 别的系的真人不能混进来
        for name in OTHER_UNITS_PEOPLE:
            self.assertNotIn(name, self.names)
        # 每行备注都写明覆盖范围，避免被当成全学院名录
        for row in self.rows:
            note = row["assignment"]["note"]
            self.assertIn(TARGET_UNIT, note)
            for unit in UNITS:
                self.assertIn(unit, note)

    def test_names_are_people_and_not_navigation(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            self.assertIsNone(TITLE.search(name), f"姓名含职称：{name!r}")
        # 页面上的真人（逐个核对过快照里的锚文本）
        for expected in ("安琨", "曾小清", "常云涛", "马万经", "唐克双", "朱宏"):
            self.assertIn(expected, self.names)
        # 导航／系名／栏目名不是人名
        for noise in UNITS + ("师资队伍", "教师名录", "师资概况", "名师采风", "首页",
                              "当前位置", "交通学院"):
            self.assertNotIn(noise, self.names)

    def test_every_row_links_a_personal_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_PAGE.pattern)
            # 不能回落到名录页本身：那会把 35 个人指到同一份名单
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
        self.assertEqual(len({row["homepage"] for row in self.rows}), 35)

    def test_homepages_are_not_borrowed_from_other_units(self):
        # 其他四个系的个人页在 /2863/ /2901/ /2943/ /3062/ 栏目下；本来源只许出现 /2996/。
        for row in self.rows:
            self.assertIn("/info/2996/", row["homepage"])
        self.assertEqual(self.html.count("../info/2996/"), 35)

    def test_direction_is_always_unknown(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertEqual(row["assignment"]["degree_level"], "")
            self.assertIsNone(row["assignment"]["year"])

    def test_rank_is_recorded_in_the_note_not_the_direction(self):
        for row in self.rows:
            note = row["assignment"]["note"]
            self.assertNotRegex(note, EMAIL)
            self.assertNotRegex(note, PHONE)
            self.assertIsNone(TITLE.search(row["assignment"]["direction"]))

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("联系方式已隐去", blob)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))

    def test_snapshots_are_redacted(self):
        # 名录页模板本身不含联系方式（实测「电话」「邮箱」「@」各 0 处），故无需替换；
        # 个人详情页模板带「邮箱：…」，落盘前已替换为「联系方式已隐去」。
        self.assertIsNone(EMAIL.search(self.html), "名录页快照里仍有邮箱")
        self.assertIsNone(PHONE.search(self.html), "名录页快照里仍有电话")
        self.assertNotIn("@", self.html)
        self.assertIsNone(EMAIL.search(self.person_html), "个人页快照里仍有邮箱")
        self.assertIsNone(PHONE.search(self.person_html), "个人页快照里仍有电话")
        self.assertNotIn("@", self.person_html)
        # 无残留 + 至少替换过一次（不硬编码替换处数，避免补脱敏反而把测试改红）
        self.assertGreaterEqual(self.person_html.count("联系方式已隐去"), 1)
        # 脱敏没有毁掉这一页：它仍是那位教师的详情页
        title = BeautifulSoup(self.person_html, "html.parser").title
        self.assertIsNotNone(title)
        self.assertIn("安琨", title.get_text(strip=True))

    def test_the_person_page_snapshot_yields_no_rows(self):
        # 解析器限定在目标系的人员容器内：把个人详情页整页喂进去必须返回空，
        # 而不是把页面正文里的汉字串或「邮箱：…」当成人名/方向。
        self.assertEqual(parse(self.person_html, self.spec["listing"], self.spec), [])

    def test_skipped_entries_are_counted_not_dropped(self):
        # 红线 1：非中文姓名不音译、不截断，显式跳过并计数；容器条目数 = 解析数 + 跳过数。
        rows, skipped = parse_with_stats(self.html, self.spec["listing"], self.spec)
        entries = self._target_block(self.html).count('<div class="xilie_xm">')
        self.assertEqual(entries, 35)
        self.assertEqual(len(rows), 35)
        self.assertEqual(skipped, [])
        self.assertEqual(len(rows) + len(skipped), entries)

    def test_foreign_name_in_the_container_is_skipped_and_counted(self):
        broken = self._inject('<div class="xilie_xm"><a href="../info/2996/99999.htm">'
                              "John Smith</a></div>")
        rows, skipped = parse_with_stats(broken, self.spec["listing"], self.spec)
        entries = self._target_block(broken).count('<div class="xilie_xm">')
        self.assertEqual(entries, 36)
        self.assertEqual(len(rows), 35, "外文姓名不能变成本系教师，也不能截断成中文名")
        self.assertEqual(skipped, ["JohnSmith"])
        self.assertEqual(len(rows) + len(skipped), entries)

    def test_concatenated_rank_is_stripped_from_the_name(self):
        # 红线 1：姓名与职称拼在一起时先剥后缀（本页没有这种写法，属于防御）。
        broken = self._inject('<div class="xilie_xm"><a href="../info/2996/99998.htm">'
                              "张三教授</a></div>")
        rows, skipped = parse_with_stats(broken, self.spec["listing"], self.spec)
        self.assertEqual(skipped, [])
        self.assertEqual(len(rows), 36)
        names = [row["name"] for row in rows]
        self.assertIn("张三", names)
        self.assertNotIn("张三教授", names)

    def test_entry_without_a_link_breaks_the_guard(self):
        # 红线 4：容器条目数与解析数对不上时必须抛错，不能悄悄少收一个人。
        broken = self._inject('<div class="xilie_xm">李四</div>')
        with self.assertRaises(ValueError):
            parse(broken, self.spec["listing"], self.spec)

    def test_missing_container_yields_nothing_instead_of_page_text(self):
        # 结构不匹配时宁可返回空（让契约测试报缺快照/缺人），也不要把整页汉字串当人名。
        self.assertEqual(parse("<html><body>交通信息与控制系 安琨 教授</body></html>",
                               self.spec["listing"], self.spec), [])
        # 目标系名改了也要返回空，而不是退化成收别的系
        renamed = self.html.replace(f"<h4>{TARGET_UNIT}</h4>", "<h4>交通信息系</h4>", 1)
        self.assertEqual(parse(renamed, self.spec["listing"], self.spec), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
