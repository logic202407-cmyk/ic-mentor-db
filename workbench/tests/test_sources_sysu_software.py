"""Offline checks for the 中山大学软件工程学院 source module (0835 软件工程).

读的是 ``workbench/tests/fixtures/sysu_software.html``——落盘前已把 6 处邮箱锚
替换成「联系方式已隐去」，所以这些断言既验证解析口径，也验证快照确实脱敏。
测试不碰网络。
"""
import json
import pathlib
import re
import unittest

from bs4 import BeautifulSoup

from workbench.sources.sysu_software import SPECS, parse, scan

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
MARK = "联系方式已隐去"
# 手机号、带区号座机（含「(0571) 87951234」「010-12345678」两种写法）。
PHONE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:1[3-9]\d{9}|\(\d{2,4}\)\s?\d{7,8}|0\d{2,3}[-\s]?\d{7,8})"
    r"(?![0-9A-Za-z])"
)
NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
# 职称词：姓名里一个都不能出现。
RANK_WORDS = ("教授", "副教授", "讲师", "研究员", "助教", "高工", "院士", "导师")

EXPECTED_NAMES = {
    "郑子彬", "余阳", "王若梅", "周育人", "吴嘉婧", "黄翰", "陈武辉", "黄华威",
    "苏玉鑫", "李丹", "南雨宏", "陈建国", "黄袁", "何笑雨", "孔树锋", "蒋子规",
    "刘名威", "娄坚", "江山", "吴炜滨", "张云灿", "刘井平", "廖国成", "陈文清",
    "王焱林", "张咏珊", "陈壮彬", "李涛涛", "王乐球", "郑沛霖", "林丹", "汪冉冉",
    "袁剑文", "孔雀屏", "梁峻源", "杨浩楠",
}
# 双聘教师：姓名要留，标记要去。
DUAL_NAMES = {"武汇岳", "徐宇", "林淑金", "陈湘萍"}
# 非专任教师序列，整组不收录（含唯一一位非汉字姓名）。
EXCLUDED_NAMES = {
    "刘杨",              # 外聘教授
    "吕荣聪", "钱德沛", "郭嵩",   # 校外导师
    "潘茂林", "王国利", "毛明志",  # 荣休教师
    "C.K.MichaelTse",    # 校外导师，非汉字姓名
}


class SysuSoftwareSpecTests(unittest.TestCase):
    """来源声明：学科、学校、入口与页数。"""

    def test_spec_targets_software_engineering_at_sysu(self):
        self.assertEqual(len(SPECS), 1)
        spec = SPECS[0]
        self.assertEqual(spec["key"], "sysu_software")
        self.assertEqual(spec["code"], "0835")
        self.assertEqual(spec["discipline"], "软件工程")
        self.assertEqual(spec["institution"], "中山大学")
        self.assertEqual(spec["department"], "软件工程学院")
        self.assertEqual(spec["listing"], "https://sse.sysu.edu.cn/teacher")
        # 一页即全集（五个职称子页合计 40 人，与合并页的 40 张专任教师卡片一致）。
        self.assertEqual(spec["max_pages"], 1)
        self.assertNotIn("{page}", spec["listing"])


class SysuSoftwareParseTests(unittest.TestCase):
    """解析口径：只收专任教师、姓名干净、方向不猜、每条都有本人详情页。"""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")
        cls.rows, cls.stats = scan(cls.html, cls.spec["listing"], cls.spec)
        cls.names = [row["name"] for row in cls.rows]
        cls.by_name = {row["name"]: row for row in cls.rows}

    def test_parser_finds_the_whole_teaching_roster(self):
        self.assertEqual(len(self.rows), 40)
        self.assertEqual(len(set(self.names)), 40)
        self.assertEqual(len(self.by_name), 40)

    def test_card_accounting_closes(self):
        # 48 张卡片 = 40 位专任教师 + 8 张非教学卡片；账要对得上，不能静默丢弃。
        self.assertEqual(self.stats["cards"], 48)
        self.assertEqual(self.stats["rows"], 40)
        self.assertEqual(self.stats["excluded_rank"],
                         {"外聘教授": 1, "校外导师": 3, "荣休教师": 3})
        self.assertEqual(self.stats["unknown_rank"], [])
        self.assertEqual(self.stats["no_detail"], [])
        excluded = sum(self.stats["excluded_rank"].values())
        self.assertEqual(self.stats["cards"],
                         self.stats["rows"] + excluded + len(self.stats["non_cjk"]))

    def test_non_cjk_name_is_skipped_and_counted(self):
        self.assertEqual(self.stats["non_cjk"], ["C.K.MichaelTse"])
        self.assertNotIn("C.K.MichaelTse", self.names)

    def test_names_are_people_without_rank(self):
        for name in self.names:
            self.assertRegex(name, NAME_RE.pattern)
            for rank in RANK_WORDS:
                self.assertNotIn(rank, name)
        self.assertTrue(EXPECTED_NAMES.issubset(set(self.names)))
        for noise in ("教授", "副教授", "讲师/教员", "研究员/副研究员", "师资队伍",
                      "了解更多", "荣休教师", "校外导师", "外聘教授", "现任职务"):
            self.assertNotIn(noise, self.names)

    def test_dual_appointment_marker_is_stripped_but_kept_in_note(self):
        # 原文是「武汇岳（双聘）」这类拼接：姓名取「武汇岳」，双聘写进备注。
        for name in DUAL_NAMES:
            self.assertIn(name, self.by_name)
            self.assertIn("双聘", self.by_name[name]["assignment"]["note"])
        self.assertNotIn("武汇岳（双聘）", self.names)
        self.assertNotIn("陈湘萍（双聘）", self.names)

    def test_non_teaching_groups_are_excluded(self):
        for name in EXCLUDED_NAMES:
            self.assertNotIn(name, self.by_name)

    def test_rank_never_becomes_a_research_direction(self):
        for row in self.rows:
            direction = row["assignment"]["direction"]
            self.assertEqual(direction, "方向待补")
            # 页面确实写了「研究方向」，但红线 2 要求方向字段留空，绝不照抄。
            for word in RANK_WORDS + ("软件", "区块链", "程序分析"):
                self.assertNotIn(word, direction)

    def test_every_row_links_the_persons_own_detail_page(self):
        homepages = [row["homepage"] for row in self.rows]
        self.assertEqual(len(set(homepages)), 40)
        for homepage in homepages:
            self.assertRegex(homepage, r"^https://sse\.sysu\.edu\.cn/teacher/\d+$")
        for row in self.rows:
            self.assertEqual(row["institution"], "中山大学")
            self.assertEqual(row["department"], "软件工程学院")
            self.assertEqual(row["assignment"]["url"], self.spec["listing"])
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertEqual(row["assignment"]["first_level_discipline"], "0835 软件工程")
            self.assertEqual(row["assignment"]["subject"], "083500 软件工程")
            self.assertEqual(row["assignment"]["year"], None)

    def test_no_contact_information_is_stored(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertNotIn("@", blob)
        self.assertNotIn("mailto", blob.lower())
        self.assertIsNone(PHONE_RE.search(blob))
        # 也不存「联系方式已隐去」以外的任何占位联系方式字段。
        for row in self.rows:
            self.assertNotIn("Email", row["assignment"]["note"])
            self.assertNotIn("电话", row["assignment"]["note"])


class SysuSoftwareFixtureTests(unittest.TestCase):
    """快照本身必须已脱敏：邮箱/电话/协议都不能留在 fixture 里。"""

    @classmethod
    def setUpClass(cls):
        cls.spec = SPECS[0]
        cls.html = (FIXTURES / f"{cls.spec['key']}.html").read_text(encoding="utf-8")

    def test_snapshot_is_sanitized(self):
        self.assertEqual(self.html.count(MARK), 6)
        self.assertNotIn("@", self.html)
        self.assertNotIn("mailto:", self.html.lower())
        self.assertIsNone(PHONE_RE.search(self.html))
        self.assertIn("Email：", self.html)  # 标签还在，值已被替换

    def test_snapshot_still_holds_the_roster(self):
        soup = BeautifulSoup(self.html, "html.parser")
        self.assertEqual(len(soup.select("div.list-images-1-1")), 48)
        self.assertEqual(
            len([a for a in soup.select("a[href]")
                 if re.fullmatch(r"/teacher/\d+", (a.get("href") or "").strip())]),
            96)  # 48 张卡片 ×（头像 + 了解更多）

    def test_parse_reads_the_snapshot_without_network(self):
        rows = parse(self.html, self.spec["listing"], self.spec)
        self.assertEqual(len(rows), 40)
        self.assertEqual(rows[0]["name"], "郑子彬")
        self.assertEqual(rows[0]["homepage"], "https://sse.sysu.edu.cn/teacher/100")


if __name__ == "__main__":
    unittest.main()
