"""分布审计工具的测试：重点是"还需补多少人"那段算术。

0801 力学出过一次错：补入量超过存量时，补入校会变成新的主导校（上交 97.1% →
北大 73.3%，仍未达标）。这段算术就是防止再犯，必须钉住。
"""

from __future__ import annotations

import math
import unittest

from workbench.tools.distribution_audit import (
    THRESHOLD,
    needed_from_a_third_school,
)


class NeededCountTests(unittest.TestCase):
    """needed_from_a_third_school 返回"再补多少人、且假设来自另一所学校"。"""

    def _check(self, total: int, top_n: int, need: int) -> None:
        """补 need 人后，最大占比必须 < 阈值；补 need-1 人时仍不达标。"""
        after_total = total + need
        after_top = max(top_n, need)
        self.assertLess(after_top / after_total, THRESHOLD,
                        f"{top_n}/{total} 补 {need} 后为 {after_top/after_total:.3f}")
        if need > 0:
            worse_total = total + need - 1
            worse_top = max(top_n, need - 1)
            self.assertGreaterEqual(worse_top / worse_total, THRESHOLD,
                                    f"只补 {need-1} 就该仍不达标")

    def test_already_passing_needs_zero(self):
        self.assertEqual(needed_from_a_third_school(100, 59), 0)
        self.assertEqual(needed_from_a_third_school(100, 10), 0)

    def test_empty_discipline_needs_zero(self):
        self.assertEqual(needed_from_a_third_school(0, 0), 0)

    def test_dominant_school_case(self):
        # 上交往 34/35 = 97.1% 的情形：补 22 就够（22/57 = 38.6%）
        need = needed_from_a_third_school(35, 34)
        self.assertEqual(need, 22)
        self._check(35, 34, need)

    def test_water_engineering_case(self):
        # 武大 139/210 = 66.2% → 补 22 就达标（139/232 = 59.9%）
        need = needed_from_a_third_school(210, 139)
        self.assertEqual(need, 22)
        self._check(210, 139, need)

    def test_single_institution_case(self):
        # 只有一所（61/61 = 100%）：补 41 人后 61/102 = 59.8% 即达标。
        # 注意**不需要**把原校"挤下去"——它仍是第一大机构，只是占比降到 60% 以下。
        need = needed_from_a_third_school(61, 61)
        self._check(61, 61, need)
        self.assertEqual(need, 41)
        self.assertGreater(max(61, need), need)   # 原校仍居首，这不影响达标

    def test_small_discipline_case(self):
        # 0822 轻工：19 条、15 条主导（78.9%）→ 只需 7 人
        need = needed_from_a_third_school(19, 15)
        self.assertEqual(need, 7)
        self._check(19, 15, need)

    def test_just_over_threshold_needs_one(self):
        # 0831 生物医学工程：78 条、47 条（60.3%）→ 只需 1 人
        need = needed_from_a_third_school(78, 47)
        self.assertEqual(need, 1)

    def test_monotonic_in_top_count(self):
        """主导校占比越高，需要补的人越多（同一总量下）。"""
        prev = -1
        for top in (50, 60, 70, 80, 90, 100):
            need = needed_from_a_third_school(100, top)
            self.assertGreaterEqual(need, prev)
            prev = need

    def test_never_returns_negative(self):
        for total in (1, 5, 50):
            for top in range(0, total + 1):
                self.assertGreaterEqual(needed_from_a_third_school(total, top), 0)

    def test_result_is_int(self):
        self.assertIsInstance(needed_from_a_third_school(210, 139), int)
        self.assertTrue(math.isfinite(needed_from_a_third_school(210, 139)))


if __name__ == "__main__":
    unittest.main()
