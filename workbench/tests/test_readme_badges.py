"""README 徽章数字的测试。

徽章是评审打开仓库第一眼看到的内容，但它只是写死的字符串——**没有任何机制会更新它**。
实测发现两个都错得很远：写着「tests-321 passed」（实际 707）、
「记录-14,271 条」（实际 15,719）。这类过期比正文里的数字过期更显眼。
"""

from __future__ import annotations

import pathlib
import re
import unittest

from workbench.tools.check_readme_badges import (
    TESTS_BADGE,
    actual_numbers,
    badge_numbers,
    count_tests,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"


class ParseTests(unittest.TestCase):

    def test_tests_badge_regex(self):
        m = TESTS_BADGE.search("tests-707%20passed-brightgreen")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "707")

    def test_badge_numbers_reads_both(self):
        text = ("[![Tests](https://img.shields.io/badge/tests-99%20passed-x.svg)]"
                "[![Records](https://img.shields.io/badge/记录-15%2C719%20条-x.svg)]")
        got = badge_numbers(text)
        self.assertEqual(got["tests"], 99)
        self.assertEqual(got["records"], 15719)

    def test_badge_numbers_tolerates_missing(self):
        got = badge_numbers("没有徽章")
        self.assertIsNone(got["tests"])
        self.assertIsNone(got["records"])


class CountingTests(unittest.TestCase):

    def test_count_tests_is_positive(self):
        self.assertGreater(count_tests(), 100)

    def test_actual_numbers_keys(self):
        nums = actual_numbers()
        self.assertIn("tests", nums)
        self.assertIn("records", nums)
        self.assertGreater(nums["records"], 1000)


class ReadmeConsistencyTests(unittest.TestCase):
    """真仓库的徽章必须与实际一致——不一致时这条会红。"""

    def test_readme_badges_match_actual(self):
        text = README.read_text(encoding="utf-8")
        claimed = badge_numbers(text)
        actual = actual_numbers()
        self.assertEqual(claimed["tests"], actual["tests"],
                         f"徽章测试数过期：写 {claimed['tests']}，实际 {actual['tests']}")
        self.assertEqual(claimed["records"], actual["records"],
                         f"徽章记录数过期：写 {claimed['records']}，实际 {actual['records']}")

    def test_size_row_matches_actual(self):
        """README 体积表里的文件数必须等于实测——它自己都写着"会过期"却仍是写死的。"""
        from workbench.tools.check_readme_badges import SIZE_ROW, tracked_size
        text = README.read_text(encoding='utf-8')
        m = SIZE_ROW.search(text)
        self.assertIsNotNone(m, 'README 体积表行未找到')
        files, mb = int(m.group(1)), int(m.group(2))
        act_files, act_mb = tracked_size()
        self.assertEqual(files, act_files, f'体积表文件数 {files} != 实际 {act_files}')
        # 体积允许 ±15%（构建产物大小会有正常波动），但不能差一倍
        self.assertLess(abs(mb - act_mb), max(3.0, act_mb * 0.15),
                        f'体积表 {mb} MB 与实际 {act_mb:.1f} MB 偏差过大')

    def test_readme_has_badges(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("img.shields.io", text)
        self.assertRegex(text, re.compile(r"tests-\d+%20passed"))


if __name__ == "__main__":
    unittest.main()
