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
from workbench.sources.whu_hydropower import SPECS as WHU_HYDROPOWER_SPECS
from workbench.sources.whu_hydropower import parse as parse_whu_hydropower

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# 082000 石油与天然气工程 的编号—方向对照表，逐字取自名录页面自身。
PETROLEUM_DIRECTIONS = {
    "油气藏渗流理论与开发技术", "油气田钻采力学与控制工程", "油气田流体力学与钻采工程",
    "油气田岩石力学与钻采工程", "油气田化学与提高采收率", "油气输送与储存理论与技术",
    "油气集输与城市输配理论与技术", "海洋油气工程理论与技术", "非常规油气工程理论与技术",
    "油气工程信息化与智能化技术", "CO2地质利用与封存理论与技术",
}

# 武汉大学水力发电工程系名录里“博士后”分组的 9 位在站人员：是培养岗位，不是教师。
POSTDOC_NAMES = frozenset({
    "匡智浩", "李凯", "梅江洲", "吴婷", "熊峻巍", "袁晶晶", "张仁君", "周海孝", "朱洪泽",
})


class HustControlSourceTests(unittest.TestCase):
    """0811 控制科学与工程 — 华中科技大学人工智能与自动化学院 学院师资（按系列表）."""

    @classmethod
    def setUpClass(cls):
        cls.spec = HUST_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
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


class SourceModuleContractTests(unittest.TestCase):
    """Every source module must satisfy the shared contract and ship a fixture."""

    def test_every_source_has_a_fixture_named_after_its_key(self):
        from workbench.collect_engineering_scale import discover_sources
        for key, spec in discover_sources().items():
            with self.subTest(source=key):
                fixture = FIXTURES / f"{key}.html"
                self.assertTrue(fixture.is_file(), f"缺少快照 {key}.html")

    def test_every_parser_satisfies_the_red_lines(self):
        import re
        from workbench.collect_engineering_scale import discover_sources
        from workbench.collect_thin_discipline_depth import NO_DIRECTION

        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        rank = re.compile(r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
        admin = re.compile(r"党委|工会|离退休|办公室")

        for key, spec in discover_sources().items():
            with self.subTest(source=key):
                html = (FIXTURES / f"{key}.html").read_text(encoding="utf-8", errors="replace")
                rows = spec["parser"](html, spec["listing"], spec)
                self.assertTrue(rows, "解析器没有解析出任何人")
                for row in rows:
                    self.assertNotRegex(repr(row), email)
                    # A 职称 is a rank, never a direction.
                    direction = row["assignment"]["direction"]
                    if direction != NO_DIRECTION:
                        self.assertIsNone(rank.search(direction),
                                          f"{row['name']} 的方向字段含职称")
                    self.assertTrue(row["assignment"]["url"], "条目缺少来源链接")
                    self.assertIsNone(admin.search(row["department"]),
                                      f"{row['name']} 的院系是行政单位")
                    self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")


class WhuHydropowerSourceTests(unittest.TestCase):
    """0815 水利工程 — 武汉大学水利水电学院水力发电工程系 在岗教师名录."""

    @classmethod
    def setUpClass(cls):
        cls.spec = WHU_HYDROPOWER_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_whu_hydropower(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_hydraulic_discipline(self):
        self.assertEqual(self.spec["key"], "whu_hydropower")
        self.assertEqual(self.spec["code"], "0815")
        self.assertEqual(self.spec["discipline"], "水利工程")
        self.assertEqual(self.spec["institution"], "武汉大学")
        self.assertEqual(self.spec["department"], "水力发电工程系")
        self.assertIn("swrh.whu.edu.cn", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_parser_finds_the_whole_roster(self):
        # 名录共 48 条：22 教授 + 15 副教授 + 1 副研究员 + 1 高级工程师 + 9 博士后。
        # 博士后是在站培养岗位而不是教师职称，与 hust.py 同口径不计入，故教师 39 人。
        self.assertEqual(len(self.rows), 39)
        self.assertEqual(len(self.by_name), 39)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0815 水利工程"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("常晓林", "陈益峰", "卢文波", "周伟", "伍鹤皋",
                         "李进平", "曹生荣", "赵志高"):
            self.assertIn(expected, self.by_name)
        for noise in ("在岗教师", "水力发电工程系", "教授", "副教授", "副研究员",
                      "研究方向", "职称", "邮箱", "荣休教职工", "师资队伍"):
            self.assertNotIn(noise, self.by_name)

    def test_postdocs_are_not_faculty_rows(self):
        # 页面把 9 位博士后放在同一套 ul.teacher 结构下，但整组跳过。
        self.assertEqual({row["name"] for row in self.rows} & POSTDOC_NAMES, set())

    def test_direction_is_read_from_the_pages_own_field(self):
        self.assertEqual(self.by_name["常晓林"]["assignment"]["direction"],
                         "高坝结构安全，高坝复杂坝基稳定，高混凝土坝温控防裂，水工结构数值模拟")
        self.assertEqual(self.by_name["赖旭"]["assignment"]["direction"], "水电站过渡过程")
        self.assertEqual(self.by_name["陈益峰"]["assignment"]["direction"][:10],
                         "多孔裂隙介质复杂渗流")
        # 本页每位教师都写了自己的研究方向，所以没有一条是“方向待补”。
        self.assertTrue(all(row["assignment"]["direction"] != "方向待补"
                            for row in self.rows))

    def test_rank_never_becomes_a_research_direction(self):
        for row in self.rows:
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|博士后|正高|副高|中级")
        self.assertIn("职称：教授，博士生导师", self.by_name["常晓林"]["assignment"]["note"])
        self.assertIn("职称分组：副教授", self.by_name["李进平"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "武汉大学")
            self.assertEqual(row["department"], "水力发电工程系")
            self.assertTrue(row["homepage"].startswith("https://swrh.whu.edu.cn/info/"))

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        # 名录页面上真实存在的联系方式一律不得进入结果（不在此处写出具体地址，
        # 以免测试文件本身成为地址的发布渠道）。
        self.assertNotIn("Email", blob)
        self.assertNotIn("Tel", blob)


class SeuArchitectureSourceTests(unittest.TestCase):
    """0813 建筑学 — 东南大学建筑学院建筑系 师资力量名录（每页 16 条，共 3 页）."""

    @classmethod
    def setUpClass(cls):
        # Imported here so this class does not touch the shared import block that
        # other source modules are edited into concurrently.
        from workbench.sources.seu_architecture import SPECS as SEU_SPECS
        from workbench.sources.seu_architecture import parse as parse_seu
        cls.spec = SEU_SPECS[0]
        cls.page_one = "https://arch.seu.edu.cn/16781/list1.htm"
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_seu(cls.html, cls.page_one, cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_architecture_discipline(self):
        self.assertEqual(self.spec["key"], "seu_architecture")
        self.assertEqual(self.spec["code"], "0813")
        self.assertEqual(self.spec["discipline"], "建筑学")
        self.assertEqual(self.spec["institution"], "东南大学")
        self.assertEqual(self.spec["department"], "建筑系")
        self.assertIn("arch.seu.edu.cn", self.spec["listing"])
        self.assertIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 3)
        # 快照就是分页的第 1 页：页面自称“每页 16 记录 / 总共 45 记录 / 页码 1 / 3”。
        # 原文用 &nbsp; 分隔数字与单位，所以断言去空白后的纯文本。
        import re
        from bs4 import BeautifulSoup
        text = re.sub(r"[\s\u3000\xa0]+", "",
                      BeautifulSoup(self.html, "html.parser").get_text(" ", strip=True))
        self.assertIn("每页16记录", text)
        self.assertIn("总共45记录", text)
        self.assertIn("页码1/3", text)

    def test_parser_finds_the_first_page_of_the_roster(self):
        self.assertEqual(len(self.rows), 16)
        self.assertEqual(len(self.by_name), 16)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0813 建筑学"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("王建国", "韩冬青", "张彤", "冷嘉伟", "周颖", "李飚",
                         "史永高", "鲍莉", "杨靖"):
            self.assertIn(expected, self.by_name)
        for noise in ("师资力量", "建筑系", "建筑学院", "教授", "研究员", "首页",
                      "更多", "关闭", "东南大学", "相关学科单位", "数字中大院",
                      "通知公告", "建筑学院综合管理入口", "东南大学建筑研究所"):
            self.assertNotIn(noise, self.by_name)

    def test_department_is_the_listed_teaching_unit(self):
        self.assertEqual({row["department"] for row in self.rows}, {"建筑系"})
        for row in self.rows:
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_rank_never_becomes_a_research_direction(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|高工|导师")
        # 职称只写进来源说明。
        self.assertIn("职称：教授", self.by_name["王建国"]["assignment"]["note"])
        self.assertIn("职称：研究员", self.by_name["杨靖"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.page_one)
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "东南大学")
            self.assertTrue(row["homepage"].startswith("https://arch.seu.edu.cn/"),
                            row["homepage"])

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("电话", blob)
        # 快照页脚确实带着学院联系方式（按仓库惯例已隐去字面值），卡片里也每张都有
        # news-email 字段；这些触点一条都不许进结果。
        self.assertIn("联系方式已隐去", self.html)
        self.assertIn("025-83792223", self.html)  # 页脚电话，用于验证下面的断言非空转
        self.assertNotIn("联系方式已隐去", blob)
        self.assertNotIn("025-83792223", blob)


if __name__ == "__main__":
    unittest.main()
