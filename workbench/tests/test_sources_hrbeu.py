"""0827 核科学与技术 — 哈尔滨工程大学 核科学与技术学院 教师介绍。

独立测试文件：只覆盖 ``workbench.sources.hrbeu_nuclear``，不改
``test_engineering_sources.py``。全部断言读离线快照，不碰网络。
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import unittest

from workbench.collect_thin_discipline_depth import NAME_RE, NO_DIRECTION
from workbench.sources.hrbeu_nuclear import SPECS, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

TITLE_IN_NAME = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
PERSON_HREF = re.compile(
    r"^(?:https?://cnst\.hrbeu\.edu\.cn/info/\d+/\d+\.htm"
    r"|https?://faculty\.hrbeu\.edu\.cn/[A-Za-z0-9_])"
)


class HrbeuNuclearSourceTests(unittest.TestCase):
    """哈尔滨工程大学核科学与技术学院「师资队伍 → 教师介绍」两个系的完整名单."""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.fixture = FIXTURES / f"{cls.spec['key']}.html"
        cls.html = cls.fixture.read_text(encoding="utf-8")
        cls.rows = parse(cls.html, cls.spec["listing"], cls.spec)

    def test_single_spec_targets_the_nuclear_discipline(self):
        self.assertEqual(len(SPECS), 1)
        spec = SPECS[0]
        self.assertEqual(spec["key"], "hrbeu_nuclear")
        self.assertEqual(spec["code"], "0827")
        self.assertEqual(spec["discipline"], "核科学与技术")
        self.assertEqual(spec["institution"], "哈尔滨工程大学")
        self.assertIn("核科学与技术学院", spec["department"])
        self.assertEqual(spec["max_pages"], 1)
        self.assertEqual(spec["listing"], "https://cnst.hrbeu.edu.cn/szdw/jsjs.htm")

    def test_exactly_the_two_department_containers(self):
        # 整页 9 个容器共 120 人；解析器只取两个「系」，必须恰好 12 + 13 = 25。
        self.assertEqual(len(self.rows), 25)
        self.assertEqual(len({row["name"] for row in self.rows}), 25)
        per_department = collections.Counter(row["department"] for row in self.rows)
        self.assertEqual(per_department["核科学与技术学院·核技术系"], 12)
        self.assertEqual(per_department["核科学与技术学院·核化工系"], 13)

    def test_other_containers_and_navigation_are_not_people(self):
        names = {row["name"] for row in self.rows}
        # 其他容器的真实教师（核动力仿真技术研究中心/核动力装置研究所）不应入库。
        for outside in ("夏庚磊", "彭敏俊", "孙中宁", "阎昌琪", "丁铭"):
            self.assertNotIn(outside, names)
        # 机构名与栏目名不是人名。
        for heading in ("核技术系", "核化工系", "核动力仿真技术研究中心",
                        "核动力装置研究所", "实验中心", "综合办", "科技办",
                        "人才培养办", "师资队伍", "教师介绍"):
            self.assertNotIn(heading, names)

    def test_names_carry_no_title(self):
        for row in self.rows:
            name = row["name"]
            self.assertIsNotNone(NAME_RE.fullmatch(name), name)
            self.assertIsNone(TITLE_IN_NAME.search(name), name)

    def test_title_suffix_is_stripped_before_validation(self):
        # 页面若有「张三教授」「李四 副教授」这种拼接形式，必须剥后缀再入库。
        html = """<div class="newlist1"><h2>核技术系</h2><ul class="list">
        <li><a href="https://cnst.hrbeu.edu.cn/info/1055/1.htm">
            <h3 class="l1 txt1">张三教授</h3></a></li>
        <li><a href="https://cnst.hrbeu.edu.cn/info/1055/2.htm">
            <h3 class="l1 txt1">李四 副教授</h3></a></li>
        <li><a href="https://cnst.hrbeu.edu.cn/info/1055/3.htm">
            <h3 class="l1 txt1">王五研究员</h3></a></li>
        </ul></div>"""
        rows = parse(html, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["张三", "李四", "王五"])

    def test_only_the_two_named_units_are_parsed(self):
        # 即使同一页有行政办公室/研究所容器，也只认 UNITS 里的两个系。
        html = """<div class="newlist1"><h2>综合办</h2><ul class="list">
        <li><a href="https://cnst.hrbeu.edu.cn/info/1062/1.htm">
            <h3 class="l1 txt1">赵六</h3></a></li></ul></div>
        <div class="newlist1"><h2>核技术系</h2><ul class="list">
        <li><a href="https://cnst.hrbeu.edu.cn/info/1055/2.htm">
            <h3 class="l1 txt1">钱七</h3></a></li></ul></div>"""
        rows = parse(html, self.spec["listing"], self.spec)
        self.assertEqual([row["name"] for row in rows], ["钱七"])

    def test_every_row_links_a_person_detail_page(self):
        for row in self.rows:
            self.assertRegex(row["homepage"], PERSON_HREF)
            self.assertNotEqual(row["homepage"], self.spec["listing"])
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])

    def test_points_at_another_university_than_the_dominant_one(self):
        # 0827 现由上海交通大学主导；本模块必须来自另一所学校。
        self.assertNotEqual(self.spec["institution"], "上海交通大学")
        self.assertEqual({row["institution"] for row in self.rows}, {"哈尔滨工程大学"})

    def test_direction_is_never_invented(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], NO_DIRECTION)

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        match = PHONE.search(blob)
        self.assertIsNone(match, match)

    def test_fixture_is_redacted(self):
        self.assertIn("联系方式已隐去", self.html)
        self.assertIsNone(EMAIL.search(self.html))
        match = PHONE.search(self.html)
        self.assertIsNone(match, match)

    def test_fixture_keeps_the_whole_page(self):
        # 快照保留整页（含未入库的研究中心），证明 25 人是“限定容器”而非页面缺人。
        self.assertIn("核动力仿真技术研究中心", self.html)


if __name__ == "__main__":
    unittest.main()
