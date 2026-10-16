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


class EcustBioengineeringSourceTests(unittest.TestCase):
    """0836 生物工程 — 华东理工大学生物工程学院 教师分布名录（按教学科研单位分组）."""

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源模块并发修改共享 import 块。
        from workbench.sources.ecust_bioengineering import SPECS as ECUST_SPECS
        from workbench.sources.ecust_bioengineering import parse as parse_ecust
        cls.spec = ECUST_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_ecust(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_bioengineering_discipline(self):
        self.assertEqual(self.spec["key"], "ecust_bioengineering")
        self.assertEqual(self.spec["code"], "0836")
        self.assertEqual(self.spec["discipline"], "生物工程")
        self.assertEqual(self.spec["institution"], "华东理工大学")
        self.assertEqual(self.spec["department"], "生物工程学院")
        self.assertIn("biotech.ecust.edu.cn", self.spec["listing"])
        # 单页静态名录，没有 {page} 分页。
        self.assertNotIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_the_source_is_a_second_university_for_0836(self):
        # 0836 原有的 35 条全部来自上海交通大学，本来源必须是另一所学校。
        self.assertNotEqual(self.spec["institution"], "上海交通大学")

    def test_parser_finds_the_whole_roster(self):
        self.assertEqual(len(self.rows), 116)
        self.assertEqual(len(self.by_name), 116)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0836 生物工程"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("郑高伟", "叶邦策", "张立新", "魏东芝", "谭文松", "许建和",
                         "庄英萍", "花强", "王启要", "赵黎明"):
            self.assertIn(expected, self.by_name)
        for noise in ("生物工程系", "学院党委", "学院党政办公室", "学院思政办公室",
                      "生物反应器工程全国重点实验室", "国家生化工程技术研究中心（上海）",
                      "食品科学与工程系", "应用生物学系", "鲁华所", "阿华所",
                      "教师分布", "师资队伍", "导师名单"):
            self.assertNotIn(noise, self.by_name)

    def test_names_with_internal_spaces_are_not_split(self):
        # 页面把两字/三字姓名写成“花 强”“陈 骏”“张 敬宇”“王 玮”。先去空白再切分
        # 才得到完整姓名；若先切分，“敬宇”会是一个合法的两字姓名，凭空多出一个人。
        for name in ("花强", "陈骏", "张敬宇", "王玮", "鲍杰", "吴辉", "陈琦", "刘敏"):
            self.assertIn(name, self.by_name)
        for fragment in ("敬宇", "花", "骏", "玮"):
            self.assertNotIn(fragment, self.by_name)

    def test_departments_are_the_teaching_and_research_units(self):
        self.assertEqual({row["department"] for row in self.rows}, {
            "生物工程系", "生物反应器工程全国重点实验室",
            "国家生化工程技术研究中心（上海）", "鲁华所", "阿华所", "动物细胞室",
            "海洋室", "生物分离室", "上海生物技术产业技术研究院",
            "上海市发酵工程实验教学中心", "发酵工业分离提取技术研发中心",
            "中国轻工业生物基材料工程重点实验室"})
        for row in self.rows:
            self.assertNotRegex(row["department"], r"党委|工会|离退休|办公室|思政|行政")
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_other_disciplines_on_the_same_page_are_not_merged_in(self):
        # 同一张表上还列着食品科学与工程系（0832）与应用生物学系（0710）。
        for other in ("叶江", "季亮", "周英骏", "罗远婵", "孙丽云", "马昱澍",
                      "郑国生", "曹旭妮"):
            self.assertNotIn(other, self.by_name)
        # 确认这些人确实出现在快照里，上面的断言不是空转。
        import re
        from bs4 import BeautifulSoup
        text = re.sub(r"[\s\u3000\xa0]+", "",
                      BeautifulSoup(self.html, "html.parser").get_text(" ", strip=True))
        for other in ("叶江", "季亮", "郑国生", "曹旭妮"):
            self.assertIn(other, text)

    def test_one_row_per_person_when_listed_under_several_units(self):
        # 郑高伟同时挂在“生物工程系”与“生物反应器工程全国重点实验室”：只出一行，
        # department 取首次出现的单位，另一处写进备注。
        self.assertEqual(self.by_name["郑高伟"]["department"], "生物工程系")
        self.assertIn("生物反应器工程全国重点实验室",
                      self.by_name["郑高伟"]["assignment"]["note"])
        # 刘琴先出现在“学院党委”（非教学单位，整段跳过），因此首次有效单位是重点实验室。
        self.assertEqual(self.by_name["刘琴"]["department"], "生物反应器工程全国重点实验室")
        self.assertEqual(self.by_name["王宜冰"]["department"], "生物反应器工程全国重点实验室")

    def test_rank_never_becomes_a_research_direction(self):
        # 该页只列姓名与单位：既没有职称，也没有研究方向，故一律“方向待补”。
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|高工|导师")
        # 备注里只有“名录不含个人职称与研究方向”这句声明，没有任何职称取值。
        self.assertNotIn("职称：", self.by_name["叶邦策"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "华东理工大学")
            self.assertTrue(row["homepage"].startswith("http"), row["homepage"])
        # 92 位有个人主页；其余 24 位页面确实没给链接，回落到名录页本身。
        linked = [row for row in self.rows if row["homepage"] != self.spec["listing"]]
        self.assertEqual(len(linked), 92)
        for row in linked:
            self.assertIn("/page.htm", row["homepage"])

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("邮箱", blob)
        # 快照落盘前跑过脱敏通道（命中数 0：该页正文既无邮箱也无电话），
        # 这里再兜一次底，确保将来页面改版也不会带进联系方式。
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class CauAgricultureSourceTests(unittest.TestCase):
    """0828 农业工程 — 中国农业大学工学院农业工程系 师资队伍名录（按职称分组）."""

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源模块并发修改共享 import 块。
        from workbench.sources.cau_agriculture import SPECS as CAU_SPECS
        from workbench.sources.cau_agriculture import parse as parse_cau
        cls.spec = CAU_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_cau(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_agricultural_engineering_discipline(self):
        self.assertEqual(self.spec["key"], "cau_agriculture")
        self.assertEqual(self.spec["code"], "0828")
        self.assertEqual(self.spec["discipline"], "农业工程")
        self.assertEqual(self.spec["institution"], "中国农业大学")
        self.assertEqual(self.spec["department"], "工学院·农业工程系")
        self.assertIn("coe.cau.edu.cn", self.spec["listing"])
        # 单页静态名录，没有 {page} 分页。
        self.assertNotIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_the_source_is_a_second_university_for_0828(self):
        # 0828 原有的 27 条全部来自中国农业科学院，本来源必须是另一所学校。
        self.assertNotEqual(self.spec["institution"], "中国农业科学院")
        self.assertNotIn("caas", self.spec["listing"])

    def test_parser_finds_the_whole_roster(self):
        # 27 教授 + 25 副教授 + 2 讲师 + 2 高级实验师 + 1 工程师；
        # 页面上的“实验师”“博士后”两组表格为空。
        self.assertEqual(len(self.rows), 57)
        self.assertEqual(len(self.by_name), 57)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0828 农业工程"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("郭建斌", "韩鲁佳", "李洪文", "李永玉", "王德成", "周宇光",
                         "崔涛", "李延啸", "马帅", "王超", "聂森", "董向前",
                         "曹凤梅", "王树东"):
            self.assertIn(expected, self.by_name)
        # 职称分组标题本身也能过 NAME_RE（“副教授”就是 3 个汉字），必须被排除；
        # 栏目名、导航与页脚同理。
        for noise in ("教授", "副教授", "讲师", "高级实验师", "工程师", "实验师",
                      "博士后", "农业工程系", "机械工程系", "机械工程训练中心",
                      "师资队伍", "网站首页", "联系我们", "友情链接"):
            self.assertNotIn(noise, self.by_name)

    def test_names_written_with_layout_spaces_are_not_split(self):
        # 页面把姓名写成“何　进”“崔　涛”，李延啸更被拆成“李延”+“啸”两个 span：
        # 先去空白再用 NAME_RE 校验才得到完整姓名。
        for name in ("何进", "崔涛", "李延啸", "李煜", "马帅", "尚楠", "王超", "聂森"):
            self.assertIn(name, self.by_name)
        for fragment in ("何", "进", "啸", "延", "煜"):
            self.assertNotIn(fragment, self.by_name)

    def test_department_is_the_listed_teaching_unit(self):
        self.assertEqual({row["department"] for row in self.rows}, {"工学院·农业工程系"})
        for row in self.rows:
            self.assertNotRegex(row["department"], r"党委|工会|离退休|办公室")
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_postdocs_are_not_faculty_rows(self):
        # “博士后”是在站培养岗位而不是教师职称，整组跳过（与 whu_hydropower.py 同口径）。
        self.assertNotIn("职称：博士后", json.dumps(self.rows, ensure_ascii=False))
        # 该分组标题确实在快照里，上面的断言不是空转。
        import re
        from bs4 import BeautifulSoup
        text = re.sub(r"[\s\u3000\xa0]+", "",
                      BeautifulSoup(self.html, "html.parser").get_text(" ", strip=True))
        self.assertIn("博士后", text)

    def test_rank_never_becomes_a_research_direction(self):
        # 该页只列姓名与职称，没有个人研究方向，故一律“方向待补”。
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|实验师|工程师|博士后|正高|副高|中级")
        # 职称只写进来源说明。
        self.assertIn("职称：教授", self.by_name["郭建斌"]["assignment"]["note"])
        self.assertIn("职称：副教授", self.by_name["崔涛"]["assignment"]["note"])
        self.assertIn("职称：高级实验师", self.by_name["曹凤梅"]["assignment"]["note"])
        self.assertIn("职称：工程师", self.by_name["王树东"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "中国农业大学")
            self.assertTrue(row["homepage"].startswith("http"), row["homepage"])
        # 45 位有 faculty.cau.edu.cn 教师主页；其余 12 位页面给的链接不是本人公开主页
        # （导师信息查询编辑页 / 已失效的导师库 / CMS 后台），回落到名录页本身。
        linked = [row for row in self.rows if row["homepage"] != self.spec["listing"]]
        self.assertEqual(len(linked), 45)
        for row in linked:
            self.assertRegex(row["homepage"],
                             r"^https?://faculty\.cau\.edu\.cn/")
        blob = json.dumps(self.rows, ensure_ascii=False)
        for bad in ("gmsadm.cau.edu.cn", "gradinfo.cau.edu.cn", "/jcms/manager/"):
            self.assertNotIn(bad, blob)

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("Email", blob)
        # 快照落盘前跑过脱敏通道：页面样式表里 3 处“字母 + at + 倍图后缀”的图片文件名
        # （形如 search 与 3x 之间的 at 符号）已整体替换为“联系方式已隐去”，
        # 所以下面的断言不是空转。（此处不写出原串，避免审计脚本再命中一次。）
        self.assertIn("联系方式已隐去", self.html)
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.assertNotIn("联系方式已隐去", blob)


class ZjuControlSourceTests(unittest.TestCase):
    """0811 控制科学与工程 — 浙江大学控制科学与工程学院 师资队伍「教师」名录（按研究所）."""

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源模块并发修改共享 import 块。
        from workbench.sources.zju_cse_control import SPECS as ZJU_SPECS
        from workbench.sources.zju_cse_control import parse as parse_zju
        cls.spec = ZJU_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_zju(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_control_discipline(self):
        self.assertEqual(self.spec["key"], "zju_cse_control")
        self.assertEqual(self.spec["code"], "0811")
        self.assertEqual(self.spec["discipline"], "控制科学与工程")
        self.assertEqual(self.spec["institution"], "浙江大学")
        self.assertEqual(self.spec["department"], "控制科学与工程学院")
        self.assertEqual(self.spec["listing"],
                         "http://www.cse.zju.edu.cn/39568/list.htm")
        # 单页静态名录：正文里没有任何记录数/页码标记，故没有 {page} 占位符。
        self.assertNotIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_the_source_is_a_second_university_for_0811(self):
        # 0811 原有 149 条里 125 条来自华中科技大学，本来源必须是另一所学校。
        self.assertNotEqual(self.spec["institution"], "华中科技大学")
        self.assertNotIn("hust.edu.cn", self.spec["listing"])

    def test_the_listing_page_is_not_paginated(self):
        # 同站其它栏目会写出“每页 N 记录 / 总共 M 记录 / 页码 i/j”，教师页一处都没有；
        # 这正是 max_pages=1 的依据，所以下面的断言不是装饰。
        import re
        from bs4 import BeautifulSoup
        text = re.sub(r"[\s\u3000\xa0]+", "",
                      BeautifulSoup(self.html, "html.parser").get_text(" ", strip=True))
        self.assertNotIn("每页", text)
        self.assertNotIn("页码", text)
        self.assertNotIn("总共", text)
        # 五个研究所的标题都在同一页上。
        for institute in ("工业控制研究所", "智能系统与控制研究所", "智能感知与检测研究所",
                          "工业智能与系统工程研究所", "控制装备及综合安全研究所"):
            self.assertIn(institute, text)

    def test_parser_finds_the_whole_teacher_roster(self):
        # 五个研究所合计 108 条，其中“工业智能与系统工程研究所”的 Anjan Tula 不是汉字
        # 姓名，被 NAME_RE 跳过，故入库 107 条。
        self.assertEqual(len(self.rows), 107)
        self.assertEqual(len(self.by_name), 107)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0811 控制科学与工程"
            for row in self.rows))
        self.assertTrue(all(row["name"] for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("柴利", "陈积明", "孙优贤", "苏宏业", "熊蓉", "朱秋国",
                         "侯迪波", "张宏建", "邵之江", "王慧", "王文海", "赵春晖",
                         "高飞", "吴俊", "程鹏", "杨春节"):
            self.assertIn(expected, self.by_name)
        # 研究所标题本身也能过 NAME_RE（“工业控制研究所”就是 7 个汉字），必须排除；
        # 栏目名、导航与页脚同理。
        for noise in ("教师", "师资队伍", "人事工作", "机关教工", "实验中心", "院士",
                      "国家级高层次人才", "国家级青年人才", "招聘信息",
                      "工业控制研究所", "智能系统与控制研究所", "智能感知与检测研究所",
                      "工业智能与系统工程研究所", "控制装备及综合安全研究所",
                      "首页", "上一页", "下一页", "尾页", "第一页", "更多"):
            self.assertNotIn(noise, self.by_name)

    def test_non_chinese_name_is_skipped_not_guessed(self):
        # 页面确实列着这个非汉字姓名（断言非空转），但它不符合 NAME_RE，宁缺勿猜。
        self.assertIn("Anjan Tula", self.html)
        self.assertNotIn("AnjanTula", self.by_name)
        self.assertNotIn("Anjan Tula", self.by_name)

    def test_departments_are_the_five_research_institutes(self):
        counts = {}
        for row in self.rows:
            counts[row["department"]] = counts.get(row["department"], 0) + 1
        self.assertEqual(counts, {
            "工业控制研究所": 24,
            "智能系统与控制研究所": 43,
            "智能感知与检测研究所": 13,
            "工业智能与系统工程研究所": 17,
            "控制装备及综合安全研究所": 10,
        })
        for row in self.rows:
            self.assertNotRegex(row["department"], r"党委|工会|离退休|办公室|机关教工")
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_group_heading_is_read_from_the_document_order_sibling(self):
        # h3.research-name 与名单容器是 div.teacher-box1 下的同级兄弟、交替出现；
        # 若用扁平的 find_all('div') 遍历，五个所会串成一个。这里锁住分组归属。
        self.assertEqual(self.by_name["柴利"]["department"], "工业控制研究所")
        self.assertEqual(self.by_name["陈积明"]["department"], "工业控制研究所")
        self.assertEqual(self.by_name["苏宏业"]["department"], "智能系统与控制研究所")
        self.assertEqual(self.by_name["熊蓉"]["department"], "智能系统与控制研究所")
        self.assertEqual(self.by_name["侯迪波"]["department"], "智能感知与检测研究所")
        self.assertEqual(self.by_name["张宏建"]["department"], "智能感知与检测研究所")
        self.assertEqual(self.by_name["邵之江"]["department"],
                         "工业智能与系统工程研究所")
        self.assertEqual(self.by_name["赵豫红"]["department"],
                         "工业智能与系统工程研究所")
        self.assertEqual(self.by_name["王文海"]["department"], "控制装备及综合安全研究所")
        self.assertEqual(self.by_name["赵春晖"]["department"], "控制装备及综合安全研究所")

    def test_talent_lists_are_not_merged_in(self):
        # 院士(1) / 国家级高层次人才(13) / 国家级青年人才(21) 三份名单都是教师名单的
        # 子集（孙优贤、柴利、陈积明、苏宏业等同时挂在两处），并进来只会重复计数：
        # 本来源的每一行都必须来自「教师」一页，department 不得是人才栏目名。
        for row in self.rows:
            self.assertNotRegex(row["department"],
                                r"院士|国家级高层次人才|国家级青年人才")
            self.assertIn("研究所", row["department"])
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("国家级高层次人才", blob)
        self.assertNotIn("国家级青年人才", blob)

    def test_rank_never_becomes_a_research_direction(self):
        # 该页只列姓名与个人页链接：既没有职称，也没有研究方向，故一律“方向待补”。
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|实验师|工程师|院士|博导")
        # 备注里也不得出现任何职称取值。
        self.assertNotIn("职称：", self.by_name["柴利"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "浙江大学")
            self.assertTrue(row["homepage"].startswith(
                "http://www.cse.zju.edu.cn/"), row["homepage"])
        # 107 人各自的文章页链接互不相同，没有一条回落到名录页。
        self.assertEqual(len({row["homepage"] for row in self.rows}), 107)
        self.assertNotIn(self.spec["listing"],
                         {row["homepage"] for row in self.rows})

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("mailto", blob)
        self.assertNotIn("联系方式已隐去", blob)
        # 快照落盘前跑过脱敏通道，但命中数为 0：这份名录页正文里本来就没有任何
        # 邮箱或电话（整页连一个 @ 都没有），所以这里断言的是“页面确实干净”。
        self.assertIn("师资队伍", self.html)
        self.assertNotIn("@", self.html)
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class SeuAutomationSourceTests(unittest.TestCase):
    """0811 控制科学与工程 — 东南大学自动化学院 师资力量「全体教师」名录.

    该栏目的四个 ``list.htm`` 页面在服务端都是空壳（``ul.cols_list`` 为空，名单由
    ``js/szdw.js`` 异步取回），所以快照存的是页面自身调用的站内教师查询服务的
    响应体（JSON，服务把 Content-Type 写成 text/html），而不是 ``list.htm``。
    """

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源模块并发修改共享 import 块。
        from workbench.sources.seu_automation import SPECS as SEU_SPECS
        from workbench.sources.seu_automation import parse as parse_seu
        cls.specs = SEU_SPECS
        cls.spec = SEU_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_seu(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_control_discipline(self):
        self.assertEqual(self.spec["key"], "seu_automation")
        self.assertEqual(self.spec["code"], "0811")
        self.assertEqual(self.spec["discipline"], "控制科学与工程")
        self.assertEqual(self.spec["institution"], "东南大学")
        self.assertEqual(self.spec["department"], "自动化学院")
        self.assertIn("automation.seu.edu.cn", self.spec["listing"])

    def test_the_source_is_a_second_university_for_0811(self):
        # 0811 原有的 125 条全部来自华中科技大学，本来源必须是另一所学校。
        self.assertNotEqual(self.spec["institution"], "华中科技大学")
        self.assertNotIn("hust.edu.cn", self.spec["listing"])

    def test_listing_is_the_service_the_page_itself_calls(self):
        # 四个 list.htm 页面都是客户端渲染的空壳，名单来自 szdw.js 调用的
        # /_wp3services/generalQuery?queryObj=teacherHome。快照就是这个响应体。
        self.assertIn("/_wp3services/generalQuery", self.spec["listing"])
        self.assertIn("queryObj=teacherHome", self.spec["listing"])
        self.assertEqual(json.loads(self.html)["total"], 114)

    def test_one_request_no_pagination(self):
        # 服务自报 total=114，但任何查询都只返回同一批 100 条：rows=999 时
        # pageIndex=2 返回 0 条；rows=100 时是 87+13，并集仍是这 100 人。所以
        # listing 里没有 {page}，max_pages=1。
        payload = json.loads(self.html)
        self.assertEqual(len(payload["data"]), 100)
        self.assertEqual(payload["pageCount"], 1)
        self.assertNotIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_doctoral_and_master_lists_are_not_separate_specs(self):
        # 博士生导师(62)与硕士生导师(82)都是「全体教师」(100)的子集，合并只会给
        # 同一个人造出重复行，因此只收「全体教师」一份来源。
        self.assertEqual(len(self.specs), 1)
        for column in ("/32670/", "/32671/", "/32669/"):
            self.assertNotIn(column, self.spec["listing"])

    def test_parser_finds_the_teaching_roster(self):
        # 服务返回 100 条，其中 5 条是办公室/党委岗位且不带任何导师标签，按合同
        # 第 5 条跳过，故 95 条。
        self.assertEqual(len(self.rows), 95)
        self.assertEqual(len(self.by_name), 95)
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0811 控制科学与工程"
            for row in self.rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        for expected in ("翟军勇", "温广辉", "李世华", "郭雷", "黄卫", "孙长银",
                         "周东华", "达飞鹏", "路小波", "忻欣", "金立左"):
            self.assertIn(expected, self.by_name)
        for noise in ("全体教师", "师资力量", "博士生导师", "硕士生导师", "院士",
                      "国家级人才", "自动化学院", "东南大学", "教师", "教授",
                      "副教授", "讲师", "研究员"):
            self.assertNotIn(noise, self.by_name)

    def test_pinyin_suffix_in_a_name_is_not_a_second_person(self):
        # 页面把这位老师写成“杨超群Chaoqun Yang”；先去空白再取前导汉字串，
        # 得到一个人，而不是把拼音当成另一个人或整条丢掉。
        self.assertIn("杨超群Chaoqun Yang", self.html)
        self.assertIn("杨超群", self.by_name)
        self.assertNotIn("杨超群Chaoqun Yang", self.by_name)
        self.assertNotIn("Chaoqun", json.dumps(self.rows, ensure_ascii=False))

    def test_department_is_the_college_the_service_reports(self):
        # 服务只给到学院一级（department 字段只有“自动化学院”），没有系/研究所。
        self.assertEqual({row["department"] for row in self.rows}, {"自动化学院"})
        for row in self.rows:
            self.assertNotRegex(row["department"], r"党委|工会|离退休|办公室")
            self.assertIn(row["department"], row["assignment"]["note"])

    def test_administrative_offices_are_skipped(self):
        # 这五位的岗位是院办主任/教学秘书/院办秘书/研究生秘书/研究生辅导员，且不带
        # 任何导师标签：属于非教学单位，整条跳过（合同第 5 条）。
        for name in ("陈晓华", "成曦", "胡菊红", "吴晓娜", "薛裕峰"):
            self.assertIn(name, self.html)      # 快照里确实有，断言不是空转
            self.assertNotIn(name, self.by_name)

    def test_teachers_with_an_admin_post_are_kept(self):
        # 反过来，带行政兼职但同时是博导/硕导的老师不能因为岗位里有“院长/党委/
        # 工会/主任”就被删掉——他们确实在教师名录里。
        for name, post in (("李世华", "院长"), ("温广辉", "副院长"), ("牛丹", "副院长"),
                           ("周波", "副院长、教授"), ("杜松林", "副教授、院长助理"),
                           ("金立左", "党委书记"),
                           ("夏思宇", "党委委员，学科组长，工会主席"),
                           ("李骏扬", "教师教学发展分中心主任")):
            self.assertIn(name, self.by_name)
            self.assertIn(post, self.by_name[name]["assignment"]["note"])

    def test_records_without_rank_or_degree_are_kept_unfilled(self):
        # 郝立、朱奕扬两条的岗位/学位栏与导师标签都是空的：不猜、不编，照收。
        for name in ("郝立", "朱奕扬"):
            self.assertIn(name, self.by_name)
            self.assertIn("页面未标注岗位、学位与导师类别",
                          self.by_name[name]["assignment"]["note"])
            self.assertEqual(self.by_name[name]["assignment"]["direction"], "方向待补")

    def test_rank_never_becomes_a_research_direction(self):
        # 该服务只给姓名、岗位、学位栏与导师类别，没有个人研究方向，故一律“方向待补”。
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|导师|院士|博士|硕士|正高|副高")
        # 职称只写进来源说明（岗位栏里的“教授”等原文照录，不进方向字段）。
        self.assertIn("岗位/职称：教授", self.by_name["达飞鹏"]["assignment"]["note"])
        self.assertIn("岗位/职称：副教授", self.by_name["房芳"]["assignment"]["note"])
        self.assertIn("岗位/职称：讲师", self.by_name["蔡苗"]["assignment"]["note"])

    def test_mentor_tags_are_quoted_from_the_page(self):
        # 导师类别取自页面 exField1 字段，顺序照录。
        self.assertIn("导师类别：博士生导师、全体教师、院士",
                      self.by_name["郭雷"]["assignment"]["note"])
        self.assertIn("导师类别：硕士生导师、全体教师",
                      self.by_name["蔡苗"]["assignment"]["note"])
        self.assertIn("国家级人才",
                      self.by_name["温广辉"]["assignment"]["note"])

    def test_every_row_cites_the_listing_and_links_a_personal_page(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["institution"], "东南大学")
            self.assertTrue(row["homepage"].startswith(
                "http://automation.seu.edu.cn/"), row["homepage"])
        # 95 人各自的个人页互不相同，没有一条回落到名录页本身。
        self.assertEqual(len({row["homepage"] for row in self.rows}), 95)
        self.assertNotIn(self.spec["listing"],
                         {row["homepage"] for row in self.rows})

    def test_no_contact_information_is_stored_or_even_requested(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("手机", blob)
        self.assertNotIn("mailto", blob)
        self.assertNotIn("联系方式已隐去", blob)
        # 联系方式在取数层就被挡掉：服务的 exField2 装的是教师电话、exField3 是外部
        # 网址，listing 的 returnInfos 字段白名单里没有它们，所以响应体里根本不存在
        # 这两个字段（下面第二条断言即为此，防止以后有人把字段加回去）。
        payload = json.loads(self.html)
        keys = {k for item in payload["data"] for k in item}
        self.assertNotIn("exField2", keys)
        self.assertNotIn("exField3", keys)
        self.assertNotIn("exField2", self.spec["listing"])
        self.assertNotIn("exField3", self.spec["listing"])
        # 快照落盘前仍跑了一遍脱敏通道，命中数为 0——响应体里连一个 @ 都没有。
        self.assertGreater(len(self.html), 10000)
        self.assertNotIn("@", self.html)
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.assertNotRegex(self.html,
                            r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?\d{7,8}|1[3-9]\d{9})")


if __name__ == "__main__":
    unittest.main()
