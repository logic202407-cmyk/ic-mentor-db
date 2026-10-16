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
        # 不在此处写出具体号码：测试文件本身也不应成为联系方式的发布渠道。
        # 改为断言"任何电话形状都不在结果里"，覆盖面比点名一个号码更宽。
        self.assertNotRegex(blob,
                            r"(?<![0-9A-Za-z])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8})(?![0-9A-Za-z])")


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
        # 名录页面上真实存在的联系电话，一条都不应出现在结果里。不写出具体号码
        # （测试文件本身也不该成为发布渠道），改为断言任何电话形状都不出现——
        # 覆盖 8 位分机、带区号座机与 11 位手机三种写法。
        self.assertNotRegex(blob,
                            r"(?<![0-9A-Za-z])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8})(?![0-9A-Za-z])")


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
        # 快照页脚确实带着学院联系方式，卡片里也每张都有 news-email 字段；这些触点
        # 一条都不许进结果。快照本身在落盘时已整体脱敏：邮箱与电话都替换为
        # 「联系方式已隐去」，因此这里断言的是"快照里已无字面联系方式"，而不是
        # 去断言某个具体号码仍然存在——写出具体号码等于把它再发布一次。
        self.assertIn("联系方式已隐去", self.html)
        self.assertNotRegex(self.html,
                            r"(?<![0-9A-Za-z])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8})(?![0-9A-Za-z])")
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.assertNotIn("联系方式已隐去", blob)


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


class UpcPetroleumSourceTests(unittest.TestCase):
    """0820 石油与天然气工程 — 中国石油大学（华东）石油工程学院 教师名录.

    该学院的「教师名录」页（``/jsml_20276/list.htm``）服务端返回的 HTML 里没有任何
    教师姓名（能匹配姓名的全是导航），真实名单由页面加载的一个数据文件
    ``/_upload/tpl/07/a3/1955/template1955/js/json.js`` 提供——后缀是 .js，内容却是
    ``var jsonBox = [ … ]`` 数据。快照 ``upc_petroleum.html`` 是**整页快照**，采集时把
    那份数据文件就地内联在页面加载它的位置，因此本类完全离线，并且同时锁住两件事：
    解析结果正确，以及「页内没有数据时模块会去读页面自己引用的那份数据文件」。
    """

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源并发修改共享 import 块。
        from workbench.sources.upc_petroleum import SPECS as UPC_SPECS
        from workbench.sources.upc_petroleum import parse as parse_upc
        cls.spec = UPC_SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows = parse_upc(cls.html, cls.spec["listing"], cls.spec)
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_spec_targets_the_petroleum_discipline(self):
        self.assertEqual(self.spec["key"], "upc_petroleum")
        self.assertEqual(self.spec["code"], "0820")
        self.assertEqual(self.spec["discipline"], "石油与天然气工程")
        self.assertEqual(self.spec["institution"], "中国石油大学（华东）")
        self.assertEqual(self.spec["department"], "石油工程学院")
        # 条目引用的是人看的那个栏目页；页面本身没有分页（没有 wp_paging 标记，
        # 也没有「每页/总共/页码」文案），名单一次由数据文件的 jsonBox 给出。
        self.assertEqual(self.spec["listing"],
                         "https://pe.upc.edu.cn/jsml_20276/list.htm")
        self.assertNotIn("{page}", self.spec["listing"])
        self.assertEqual(self.spec["max_pages"], 1)

    def test_this_is_a_second_university_for_0820(self):
        # 0811 之外，0820 原有 164 条全部来自中国石油大学（北京）。
        self.assertNotEqual(self.spec["institution"], "中国石油大学（北京）")

    def test_parser_finds_the_whole_roster(self):
        self.assertEqual(len(self.rows), 221)
        self.assertEqual(len(self.by_name), 221, "姓名应互不重复")
        self.assertTrue(all(
            row["assignment"]["first_level_discipline"] == "0820 石油与天然气工程"
            for row in self.rows))

    def test_parenthetical_labels_are_stripped_not_dropped(self):
        # 40 条写成「姓名（兼职）」「姓名（院士）」「姓名（外院）」。若先做 2-8 汉字
        # 校验再剥括注，这 40 条会被整体丢弃——这里锁住「剥掉且不丢人」。
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
            self.assertNotIn("（", row["name"])
            self.assertNotIn("(", row["name"])
        labelled = [r for r in self.rows if "名录标注" in r["assignment"]["note"]]
        self.assertGreaterEqual(len(labelled), 30,
                                "带括注的条目应保留下来，并把标注写进备注")

    def test_departments_are_research_units_not_administration(self):
        units = {row["department"] for row in self.rows}
        self.assertGreaterEqual(len(units), 6)
        for unit in units:
            self.assertNotRegex(unit, r"党委|工会|离退休|办公室|机关|行政")

    def test_direction_is_never_invented(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")

    def test_every_row_cites_the_source_file(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertTrue(row["assignment"]["note"])

    def test_homepages_are_per_person_or_the_listing(self):
        real = [r for r in self.rows if r["homepage"] != self.spec["listing"]]
        self.assertGreaterEqual(len(real), 170)
        for row in real:
            # 列表里有一条给的是 http:// 而非 https://（同一站点同一路径），
            # 因此只校验主机名，不强制协议。
            self.assertTrue(
                row["homepage"].startswith(("https://pe.upc.edu.cn/", "http://pe.upc.edu.cn/")),
                f"{row['name']} 的主页不在学院域名下：{row['homepage']}")

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("Email", blob)
        self.assertNotIn("Tel", blob)

    def test_fixture_is_redacted(self):
        self.assertNotRegex(self.html,
                            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.assertNotRegex(self.html,
                            r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?\d{7,8}|1[3-9]\d{9})")

    def test_the_json_payload_is_javascript_not_strict_json(self):
        # 这条锁住模块文档里写明的坑：该文件键名可不带引号、字符串单双引号混用、
        # 还有尾随逗号，json.loads 会失败，必须先规范化。
        self.assertIn("jsonBox", self.html)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.html[self.html.index("["):self.html.rindex("]") + 1])

    def test_the_whole_college_is_covered_not_one_institute(self):
        # 这份名录自带 dep 字段，221 人分布在学院全部 6 个研究所与 2 个中心；
        # 逐单位锁住人数，避免「只解析出某一个系」被当成全院覆盖。
        counts = {}
        for row in self.rows:
            counts[row["department"]] = counts.get(row["department"], 0) + 1
        self.assertEqual(counts, {
            "油气藏工程研究所": 54, "油气田化学研究所": 53, "油气井工程研究所": 34,
            "油气开采工程研究所": 23, "海洋油气与水合物研究所": 22,
            "智能油气田研究所": 19, "实验教学中心": 12, "公共测试中心": 4,
        })
        # 院系名一律取自数据文件的 dep，没有一条回落到笼统的学院名。
        self.assertNotIn("石油工程学院", counts)

    def test_shell_page_falls_back_to_the_data_file_the_page_loads(self):
        # 真实抓取时页面是空壳：页内没有 jsonBox 数据，模块必须去读页面自己引用的
        # 那个数据文件（而不是随便哪个 .js，也不是解析出一份空名单）。
        import re as _re

        from workbench.sources.upc_petroleum import DATA_FILE, _feed_source
        from bs4 import BeautifulSoup

        shell = _re.sub(r"<script>\s*var jsonBox.*?</script>", "", self.html, flags=_re.S)
        self.assertNotIn("var jsonBox", shell)
        # 渲染脚本仍然提到 jsonBox（12 处），所以「页内出现 jsonBox」绝不能当作拿到数据。
        self.assertIn("jsonBox", shell)
        self.assertEqual(_feed_source(BeautifulSoup(shell, "html.parser"),
                                      self.spec["listing"]), DATA_FILE)
        self.assertIn("json.js", DATA_FILE)


class SwpuNepuPetroleumSourceTests(unittest.TestCase):
    """0820 石油与天然气工程 — 西南石油大学石油与天然气工程学院 与
    东北石油大学石油工程学院 的教师名录（两个学校、共十个单位页，一个模块）。

    0820 原有 164 条全部来自中国石油大学（北京），跨校比较无从谈起。本来源一次接入
    两所石油主干高校的**院级**名录：西南石油大学石工院「师资队伍 → 教师名录」下的
    五个教学/实验单位（271 人），东北石油大学石工院「师资队伍 → 学院教师名录」下的
    五个系/中心/研究所（102 人）。两页都不列研究方向，故全部为「方向待补」。
    """

    # 每个单位页在快照里的人数（页面姓名数；东北石油大学油气田开发工程系页面上
    # 有 33 个姓名，其中 LuJing 是拼音写法，不符合 NAME_RE，故收录 32）。
    EXPECTED = {
        "swpu_petroleum_engineering": 184,
        "swpu_oil_gas_storage": 31,
        "swpu_offshore_petroleum": 18,
        "swpu_fluid_thermal": 11,
        "swpu_petroleum_lab": 27,
        "nepu_reservoir_engineering": 32,
        "nepu_well_engineering": 22,
        "nepu_oil_gas_storage": 22,
        "nepu_petroleum_lab": 14,
        "nepu_eor_institute": 12,
    }

    @classmethod
    def setUpClass(cls):
        # 就地导入，避免与其他来源并发修改共享 import 块。
        from workbench.sources.swpu_nepu_petroleum import SPECS as PETROLEUM_SPECS
        from workbench.sources.swpu_nepu_petroleum import parse as parse_petroleum
        cls.specs = {spec["key"]: spec for spec in PETROLEUM_SPECS}
        cls.html = {}
        cls.parsed = {}
        for key, spec in cls.specs.items():
            text = (FIXTURES / f"{key}.html").read_text(encoding="utf-8")
            cls.html[key] = text
            cls.parsed[key] = parse_petroleum(text, spec["listing"], spec)
        cls.all_rows = [row for rows in cls.parsed.values() for row in rows]

    def test_every_spec_targets_the_petroleum_discipline(self):
        self.assertEqual(set(self.specs), set(self.EXPECTED))
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                self.assertEqual(spec["code"], "0820")
                self.assertEqual(spec["discipline"], "石油与天然气工程")
                self.assertIn(spec["institution"], ("西南石油大学", "东北石油大学"))
                # 两份名录都不分页：没有 {page} 占位符，max_pages 为 1。
                self.assertNotIn("{page}", spec["listing"])
                self.assertEqual(spec["max_pages"], 1)
                self.assertTrue(spec["listing"].startswith("http"))

    def test_this_adds_two_more_universities_for_0820(self):
        schools = {spec["institution"] for spec in self.specs.values()}
        self.assertEqual(schools, {"西南石油大学", "东北石油大学"})
        self.assertNotIn("中国石油大学（北京）", schools)
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                if spec["institution"] == "西南石油大学":
                    self.assertIn("swpu.edu.cn", spec["listing"])
                else:
                    self.assertIn("sygcxy.nepu.edu.cn", spec["listing"])

    def test_parser_finds_each_units_whole_roster(self):
        counts = {key: len(rows) for key, rows in self.parsed.items()}
        self.assertEqual(counts, self.EXPECTED)
        self.assertEqual(len(self.all_rows), 373)
        for key, rows in self.parsed.items():
            with self.subTest(source=key):
                self.assertEqual(len({row["name"] for row in rows}), len(rows),
                                 "同一单位页内的姓名不应重复")
                self.assertTrue(all(
                    row["assignment"]["first_level_discipline"] == "0820 石油与天然气工程"
                    for row in rows))

    def test_names_are_people_and_not_navigation(self):
        for row in self.all_rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        names = {row["name"] for row in self.all_rows}
        for expected in ("白杨", "郭建春", "赵金洲", "李长俊", "曹晓春",
                         "柏明星", "成庆林", "曹广胜", "皮彦夫"):
            self.assertIn(expected, names)
        for noise in ("师资队伍", "教师名录", "杰出师资", "荣休教师", "资料下载",
                      "石油工程教研室", "油气井工程系", "教授", "副教授", "讲师",
                      "实验中心", "提高采收率研究所", "学生工作组", "管理团队",
                      "学工团队", "首页", "联系方式"):
            self.assertNotIn(noise, names)

    def test_full_width_spaces_are_stripped_before_the_name_check(self):
        # 东北石油大学把「李　玮」「索　彧」排成三格宽（全角空格 U+3000）。
        by_name = {row["name"]: row for row in self.parsed["nepu_well_engineering"]}
        for name in ("李玮", "索彧", "范森", "张军", "赵欢"):
            self.assertIn(name, by_name)
        self.assertIn("索\u3000彧", self.html["nepu_well_engineering"])
        self.assertNotIn("\u3000", "".join(by_name))

    def test_non_chinese_names_are_skipped_not_guessed(self):
        # 油气田开发工程系列表里有一位写成拼音「Lu Jing」：NAME_RE 不接受，
        # 宁缺勿猜，故该页收录 32 人而不是 33 人。
        page = self.html["nepu_reservoir_engineering"]
        self.assertIn("Lu Jing", page)
        self.assertEqual(len(self.parsed["nepu_reservoir_engineering"]), 32)
        self.assertNotIn("Lu Jing",
                         {row["name"] for row in self.parsed["nepu_reservoir_engineering"]})

    def test_the_two_zhang_tao_are_kept_apart(self):
        # 同名不同人：西南石油大学石油工程教研室的张涛（副教授）与流体与热工教研室的
        # 张涛（教授）职称与个人页都不同，两条都保留，各自引用自己的名录页。
        rows = self.parsed["swpu_petroleum_engineering"] + self.parsed["swpu_fluid_thermal"]
        tao = [row for row in rows if row["name"] == "张涛"]
        self.assertEqual(len(tao), 2)
        self.assertEqual({row["department"] for row in tao},
                         {"石油工程教研室", "流体与热工教研室"})
        self.assertEqual({row["homepage"] for row in tao}, {
            "http://www.swpu.edu.cn/sgy/szdw/jsml/sugc/fjs/zt.htm",
            "http://www.swpu.edu.cn/sgy/szdw/jsml/ltrg/js/zhangtao.htm",
        })

    def test_departments_are_teaching_units_not_administration(self):
        units = {row["department"] for row in self.all_rows}
        self.assertEqual(units, {
            "石油工程教研室", "油气储运工程教研室", "海洋油气工程教研室",
            "流体与热工教研室", "石油工程实验中心",
            "油气田开发工程系", "油气井工程系", "油气储运工程系",
            "实验中心", "提高采收率研究所"})
        for unit in units:
            self.assertNotRegex(unit, r"党委|工会|离退休|办公室|学工|管理团队|招聘")

    def test_direction_is_never_invented_and_rank_stays_out_of_it(self):
        for row in self.all_rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")
            self.assertNotRegex(row["assignment"]["direction"],
                                r"教授|副教授|讲师|研究员|实验师|导师|正高|副高|中级")
        # 职称写进备注：两校的组标题都照录。
        note = {}
        for rows in self.parsed.values():
            for row in rows:
                note.setdefault(row["name"], []).append(row["assignment"]["note"])
        self.assertIn("职称分组：教授", note["柏明星"][0])
        self.assertIn("职称分组：特任副教授", note["房雨佳"][0])
        self.assertIn("职称分组：正高级实验师", note["王其军"][0])
        self.assertIn("职称分组：高级实验师", note["陈迟"][0])
        self.assertIn("职称分组：实验师", note["敬佩瑜"][0])
        # 张涛有两个：石油工程教研室的按“副教授/副研究员”分组，流体与热工教研室的按
        # “教授/研究员”分组，两组组名都要在备注里出现。
        self.assertEqual({n.split("（")[1].split("）")[0] for n in note["张涛"]},
                         {"职称分组：副教授/副研究员", "职称分组：教授/研究员"})

    def test_every_row_cites_its_own_listing_page(self):
        for key, rows in self.parsed.items():
            spec = self.specs[key]
            for row in rows:
                with self.subTest(source=key, name=row["name"]):
                    self.assertEqual(row["assignment"]["url"], spec["listing"])
                    self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
                    self.assertEqual(row["institution"], spec["institution"])
                    self.assertEqual(row["department"], spec["department"])
                    self.assertTrue(row["homepage"].startswith("http"))

    def test_homepages_are_per_person_pages_or_the_listing(self):
        # 西南石油大学每个姓名都带个人页；东北石油大学有 7 条给的是空链接（``#``），
        # 按约定回落到名录页本身，所以 373 条里 366 条有个人页。
        hosts = {"西南石油大学": "http://www.swpu.edu.cn/sgy/",
                 "东北石油大学": "https://sygcxy.nepu.edu.cn/"}
        linked = {}
        for key, rows in self.parsed.items():
            spec = self.specs[key]
            per_person = [row for row in rows if row["homepage"] != spec["listing"]]
            linked[key] = len(per_person)
            self.assertGreater(len(per_person), 0, key)
            for row in per_person:
                with self.subTest(source=key, name=row["name"]):
                    self.assertTrue(
                        row["homepage"].startswith(hosts[spec["institution"]]),
                        row["homepage"])
        self.assertEqual(linked, {
            "swpu_petroleum_engineering": 184, "swpu_oil_gas_storage": 31,
            "swpu_offshore_petroleum": 18, "swpu_fluid_thermal": 11,
            "swpu_petroleum_lab": 27,
            "nepu_reservoir_engineering": 30, "nepu_well_engineering": 19,
            "nepu_oil_gas_storage": 22, "nepu_petroleum_lab": 12,
            "nepu_eor_institute": 12,
        })
        self.assertEqual(sum(linked.values()), 366)

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.all_rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("邮箱", blob)
        self.assertNotIn("电话", blob)
        self.assertNotIn("手机", blob)
        self.assertNotIn("联系方式已隐去", blob)
        self.assertNotIn("mailto", blob)

    def test_fixtures_are_redacted(self):
        # 两份真实页面在页脚都印着学院电话与邮箱（西南石油大学：院办电话 + 官方邮箱 +
        # 书记邮箱；东北石油大学：座机 + 学院邮箱），快照落盘前已按约定替换/删除。
        # 这里逐份重新读盘复核，并且连**宽泛**的电话正则也一并要求为 0：站点的
        # ``<!-- CustomerNO:… -->`` 授权指纹是一长串十六进制，宽泛正则会把它当成号码，
        # 因此该指纹也在落盘前一并隐去，保证任何扫描器看这份快照都是干净的。
        loose_phone = r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?\d{7,8}|1[3-9]\d{9})"
        email = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        for key, spec in self.specs.items():
            with self.subTest(source=key):
                text = self.html[key]
                self.assertGreater(len(text), 20000)
                self.assertNotRegex(text, email)
                self.assertNotRegex(text, loose_phone)
                self.assertIn("联系方式已隐去", text)
        # 原文里确实存在联系方式，快照里只剩下隐去后的标记。
        self.assertIn("联系方式已隐去", self.html["swpu_petroleum_engineering"])
        self.assertIn("官方邮箱", self.html["swpu_petroleum_engineering"])
        self.assertIn("联系方式已隐去", self.html["nepu_well_engineering"])
        self.assertIn("联系方式", self.html["nepu_well_engineering"])


if __name__ == "__main__":
    unittest.main()
