"""版式体检的测试：竖向填充度指标必须能区分"填满的页"与"半页空白"。

这个指标的第一版是错的——统计"非白像素占比"，结果所有文字页都只有 12%–26%，
全被误判。原因是文字页的墨迹覆盖率本来就低，那个指标衡量的是"字排得密不密"，
而不是"这页填满了没有"。现有测试把正确指标钉住。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from workbench.tools.pdf_layout_check import INK_THRESHOLD, page_bottom_fill

ROOT = Path(__file__).resolve().parent.parent.parent
PDF = ROOT / "workbench/aic-submission/技术报告.pdf"


class MetricTests(unittest.TestCase):

    def test_ink_threshold_is_reasonable(self):
        # 阈值太高会把浅色文字当空白，太低会把纸张纹理当墨迹
        self.assertGreaterEqual(INK_THRESHOLD, 150)
        self.assertLessEqual(INK_THRESHOLD, 240)


class RealPdfTests(unittest.TestCase):
    """真实报告：正文页必须都填得比较满；末页允许偏空。"""

    @classmethod
    def setUpClass(cls):
        cls.fills = page_bottom_fill(PDF, dpi=60)

    def test_page_count_matches(self):
        self.assertGreaterEqual(len(self.fills), 10)

    def test_body_pages_are_well_filled(self):
        body = self.fills[:-1]
        low = [i + 1 for i, v in enumerate(body) if v < 0.60]
        self.assertEqual(low, [], f"以下正文页填充度过低（疑似半页空白）：{low}")

    def test_average_fill_is_high(self):
        body = self.fills[:-1]
        avg = sum(body) / len(body)
        self.assertGreater(avg, 0.85, f"正文页平均填充度仅 {avg:.1%}")

    def test_all_values_are_fractions(self):
        for v in self.fills:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


if __name__ == "__main__":
    unittest.main()
