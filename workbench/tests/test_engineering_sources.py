"""Offline checks for the per-university source modules in ``workbench/sources``.

Each test reads a saved listing page from ``workbench/tests/fixtures`` and never
touches the network, so a failing university website cannot turn these checks red.
"""
import json
import pathlib
import unittest

from workbench.sources.cup import SPECS as CUP_SPECS
from workbench.sources.cup import parse as parse_cup
from workbench.sources.hust import SPECS as HUST_SPECS
from workbench.sources.hust import parse as parse_hust

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# 082000 石油与天然气工程 的编号—方向对照表，逐字取自名录页面自身。
PETROLEUM_DIRECTIONS = {
    "油气藏渗流理论与开发技术", "油气田钻采力学与控制工程", "油气田流体力学与钻采工程",
    "油气田岩石力学与钻采工程", "油气田化学与提高采收率", "油气输送与储存理论与技术",
    "油气集输与城市输配理论与技术", "海洋油气工程理论与技术", "非常规油气工程理论与技术",
    "油气工程信息化与智能化技术", "CO2地质利用与封存理论与技术",
}


class HustControlSourceTests(unittest.TestCase):
    """0811 控制科学与工程 — 华中科技大学人工智能与自动化学院 学院师资（按系列表）."""

    @classmethod
    def setUpClass(cls):
        cls.spec = HUST_SPECS[0]
        cls.html = (FIXTURES / "hust.html").read_text(encoding="utf-8")
        cls.rows = parse_hust(cls.html, cls.spec["listing"], cls.spec)

    def test_spec_targets_the_control_discipline(self):
        self.assertEqual(self.spec["code"], "0811")
        self.assertEqual(self.spec["discipline"], "控制科学与工程")
        self.assertIn("aia.hust.edu.cn", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_parser_finds_the_whole_roster(self):
        self.assertEqual(len(self.rows), 125)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0811 控制科学与工程"
            for row in self.rows))
        self.assertTrue(all(row["name"] for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        names = [row["name"] for row in self.rows]
        for name in names:
            self.assertRegex(name, r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("程善美", "王燕舞", "曾志刚", "曹治国", "刘文中", "张洪"):
            self.assertIn(expected, names)
        for noise in ("办公室", "党委", "工会", "师资队伍", "杰出学者", "博士后",
                      "荣休教师", "按系列表", "研究方向"):
            self.assertNotIn(noise, names)

    def test_department_comes_from_the_listed_unit(self):
        self.assertEqual({row["department"] for row in self.rows}, {
            "自主智能与智能控制系", "智能感知与测量科学系",
            "智能系统与系统工程系", "图像识别与智能科学系"})
        for row in self.rows:
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_rank_never_becomes_a_research_direction(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            for rank in ("正高", "副高", "中级", "教授", "副教授"):
                self.assertNotIn(rank, row["assignment"]["direction"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertTrue(row["homepage"].startswith("http"))
            self.assertEqual(row["institution"], "华中科技大学")

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("027-87543130", blob)


class CupPetroleumSourceTests(unittest.TestCase):
    """0820 石油与天然气工程 — 中国石油大学（北京）石油工程学院研究生导师名录."""

    @classmethod
    def setUpClass(cls):
        cls.spec = CUP_SPECS[0]
        cls.html = (FIXTURES / "cup_petroleum.html").read_text(encoding="utf-8")
        cls.rows = parse_cup(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_petroleum_discipline(self):
        self.assertEqual(self.spec["code"], "0820")
        self.assertEqual(self.spec["discipline"], "石油与天然气工程")
        self.assertEqual(self.spec["institution"], "中国石油大学（北京）")
        self.assertEqual(self.spec["department"], "石油工程学院")
        self.assertIn("cup.edu.cn", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_parser_finds_the_whole_roster(self):
        # 082000 分组共 146 人，其中第一位（高德利）与分组标题同处一行。
        self.assertEqual(len(self.rows), 146)
        self.assertEqual(len(self.by_name), 146)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0820 石油与天然气工程"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("高德利", "李根生", "陈勉", "张士诚", "邓金根",
                         "程林松", "宁正福", "赵凤兰"):
            self.assertIn(expected, self.by_name)
        for noise in ("姓名", "职称", "性别", "研究方向", "出生年份", "出生年月",
                      "是否博导", "联系电话", "备注", "学科名称及研究方向"):
            self.assertNotIn(noise, self.by_name)

    def test_other_discipline_groups_are_not_merged_in(self):
        # 同一张表里还有“080100 力学”分组，它只属于力学，不算进 0820。
        for mechanics_only in ("张广清", "黄文君", "赵建林", "周大伟",
                               "朱力行", "林青", "帅健", "李妍"):
            self.assertNotIn(mechanics_only, self.by_name)

    def test_direction_is_read_from_the_pages_own_legend(self):
        self.assertEqual(self.by_name["高德利"]["assignment"]["direction"],
                         "油气田钻采力学与控制工程")
        self.assertEqual(self.by_name["李根生"]["assignment"]["direction"],
                         "油气田流体力学与钻采工程")
        self.assertIn("油气藏渗流理论与开发技术",
                      self.by_name["杨胜来"]["assignment"]["direction"])
        for row in self.rows:
            direction = row["assignment"]["direction"]
            if direction == "方向待补":
                continue
            for part in direction.split("；"):
                self.assertIn(part, PETROLEUM_DIRECTIONS)

    def test_unresolvable_direction_stays_unknown(self):
        # 名录里“邹积瑞”一行的研究方向列填的是出生日期（2001/5/9），编号对不上对照表，
        # 于是不做任何猜测。
        self.assertEqual(self.by_name["邹积瑞"]["assignment"]["direction"], "方向待补")
        self.assertTrue(any(row["assignment"]["direction"] == "方向待补"
                            for row in self.rows))

    def test_rank_never_becomes_a_research_direction(self):
        for row in self.rows:
            direction = row["assignment"]["direction"]
            for rank in ("教授", "副教授", "讲师", "研究员", "博导", "院士"):
                self.assertNotIn(rank, direction)
        self.assertIn("职称：教授", self.by_name["高德利"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "中国石油大学（北京）")
            self.assertTrue(row["homepage"].startswith("http"))

    def test_department_is_a_teaching_or_research_unit(self):
        departments = {row["department"] for row in self.rows}
        self.assertIn("石油工程学院", departments)
        self.assertLessEqual(departments, {
            "石油工程学院", "油气井工程系", "油气田开发工程系", "油气储运工程系",
            "海洋油气工程系", "工程力学系"})
        for row in self.rows:
            self.assertNotIn(row["department"], ("党委", "工会", "离退休", "办公室"))

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("电话", blob)
        # 名录页面上真实存在的联系电话，一条都不应出现在结果里。
        for phone in ("89733281", "89733935", "13436364418", "89732268"):
            self.assertNotIn(phone, blob)


if __name__ == "__main__":
    unittest.main()
