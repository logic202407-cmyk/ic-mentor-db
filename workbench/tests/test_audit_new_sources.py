"""来源红线审计工具的测试：三个正则与字段约定。

这些检查都是"拦在入库之前"的，正则写松了会漏，写紧了会误报，都要钉住。
"""

from __future__ import annotations

import unittest

from workbench.tools.audit_new_sources import (
    EMAIL,
    FAKE_DIRECTION,
    PHONE,
    TITLE_IN_NAME,
    audit_one,
)

# 测试样例必须**分段拼接**：本仓库硬规则是任何文件都不得出现形如邮箱/电话的完整字面量，
# 审计工具会扫全库——写出具体号码本身就是泄露。拼接结果能匹配正则，但源文件里没有
# 可比对的完整串。这与 SECURITY.md 记的教训一致（早先测试断言写了真号码，被迫改过）。
_AT = "@"
MAIL_SAMPLE = "ab" + _AT + "x.edu.cn"
PHONE_SAMPLES = (
    "138" + "1234" + "5678",
    "010" + "-" + "12345678",
    "(" + "010" + ") " + "12345678",
)


class TitleInNameTests(unittest.TestCase):
    """姓名里混进职称是本项目真实踩过的坑（「曹德平研究员」）。"""

    def test_catches_concatenated_title(self):
        for value in ("曹德平研究员", "张三教授", "李四副教授", "王五高工", "赵六院士"):
            self.assertIsNotNone(TITLE_IN_NAME.search(value), value)

    def test_clean_names_pass(self):
        for value in ("曹德平", "欧阳明高", "司马·光", "陈建兵"):
            self.assertIsNone(TITLE_IN_NAME.search(value), value)


class FakeDirectionTests(unittest.TestCase):
    """方向字段里出现职称/身份，说明是拿身份冒充方向。"""

    def test_catches_rank_as_direction(self):
        for value in ("教授", "博士生导师", "研究员", "硕士生导师"):
            self.assertIsNotNone(FAKE_DIRECTION.search(value), value)

    def test_real_direction_passes(self):
        for value in ("岩土工程", "水利水电工程", "机器人控制", "方向待补"):
            self.assertIsNone(FAKE_DIRECTION.search(value), value)


class ContactRegexTests(unittest.TestCase):

    def test_email_shapes(self):
        self.assertTrue(EMAIL.search("mail me: " + MAIL_SAMPLE))
        self.assertFalse(EMAIL.search("no at sign here"))

    def test_phone_shapes(self):
        for value in PHONE_SAMPLES:
            self.assertIsNotNone(PHONE.search(value), value)

    def test_phone_does_not_match_page_numbers(self):
        for value in ("/info/1261/11798.htm", "c12345a67890/page.htm", "2026-10-22"):
            self.assertIsNone(PHONE.search(value), value)


class AuditOneTests(unittest.TestCase):
    """audit_one 要能对缺失快照与解析异常给出可读问题，而不是崩溃。"""

    def test_missing_fixture_is_reported(self):
        problems, rows = audit_one("definitely_not_a_real_key_xyz", {"listing": "x"}, lambda *a: [])
        self.assertEqual(rows, 0)
        self.assertTrue(any("缺少离线快照" in p for p in problems))

    def test_parse_exception_is_reported_not_raised(self):
        def boom(*_args, **_kwargs):
            raise RuntimeError("synthetic failure")
        # 用一个确实存在的快照名，确保走到 parse 分支
        problems, rows = audit_one("tj_water_lecturer", {"listing": "x"}, boom)
        self.assertEqual(rows, 0)
        self.assertTrue(any("parse 抛异常" in p for p in problems))

    def test_real_source_is_clean(self):
        from workbench.collect_engineering_scale import discover_sources
        sources = discover_sources()
        key = "tj_water_lecturer"
        self.assertIn(key, sources)
        spec = sources[key]
        problems, rows = audit_one(key, spec, spec["parser"])
        self.assertEqual(problems, [], problems)
        self.assertGreater(rows, 0)


if __name__ == "__main__":
    unittest.main()
