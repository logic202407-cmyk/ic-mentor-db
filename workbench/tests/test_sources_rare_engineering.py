"""Offline checks for the three "one institution only" sources.

0829 林业工程（东北林业大学两页）、0821 纺织科学与工程（青岛大学两页）、
0826 兵器科学与技术（北理工四系 + 西安工业大学两页）。

每个用例只读 ``workbench/tests/fixtures`` 下的离线快照，不访问网络；快照在落盘前
已把联系方式替换为「联系方式已隐去」，这里再复核一遍 EMAIL / PHONE 两条正则。
"""
import json
import pathlib
import re
import unittest

from workbench.sources import nefu_forestry, qdu_textile, weapon_engineering_roster

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)


class RareEngineeringSourcesTest(unittest.TestCase):
    """三个来源模块的共同红线：人数、姓名、方向、主页、联系方式、快照脱敏."""

    @classmethod
    def setUpClass(cls):
        cls.modules = (nefu_forestry, qdu_textile, weapon_engineering_roster)
        cls.rows = []
        cls.fixtures = {}
        for module in cls.modules:
            for spec in module.SPECS:
                html = (FIXTURES / f"{spec['key']}.html").read_text(encoding="utf-8")
                cls.fixtures[spec["key"]] = html
                cls.rows.extend(module.parse(html, spec["listing"], spec))

    def test_row_counts(self):
        by_code = {}
        for row in self.rows:
            code = row["assignment"]["first_level_discipline"][:4]
            by_code[code] = by_code.get(code, 0) + 1
        self.assertEqual(by_code, {"0829": 61, "0821": 57, "0826": 139})
        self.assertEqual(len(self.rows), 257)
        self.assertEqual(len({(r["institution"], r["department"], r["name"]) for r in self.rows}),
                         257)

    def test_names_are_people_and_not_ranks(self):
        for row in self.rows:
            self.assertRegex(row["name"], r"^[\u4e00-\u9fff·]{2,8}$")
        names = {row["name"] for row in self.rows}
        for expected in ("李坚", "谢延军", "刘守新", "姜伟", "曲丽君", "白志玲", "马保吉"):
            self.assertIn(expected, names)
        for rank in ("教授", "副教授", "讲师", "院士"):
            self.assertNotIn(rank, names)

    def test_direction_is_never_a_rank(self):
        for row in self.rows:
            self.assertEqual(row["assignment"]["direction"], "方向待补")

    def test_every_row_links_a_personal_page_and_cites_the_listing(self):
        for row in self.rows:
            self.assertTrue(row["homepage"].startswith("https://"))
            self.assertTrue(row["assignment"]["url"].startswith("https://"))
            self.assertEqual(row["assignment"]["record_kind"], "faculty_directory")
            self.assertNotEqual(row["homepage"].rstrip("/"),
                                row["assignment"]["url"].rstrip("/"))

    def test_no_contact_information_in_rows_or_fixtures(self):
        blob = json.dumps(self.rows, ensure_ascii=False)
        self.assertIsNone(EMAIL.search(blob))
        self.assertIsNone(PHONE.search(blob))
        for key, html in self.fixtures.items():
            self.assertIsNone(EMAIL.search(html), f"{key} 快照里仍有邮箱")
            self.assertIsNone(PHONE.search(html), f"{key} 快照里仍有电话")


if __name__ == "__main__":
    unittest.main()
