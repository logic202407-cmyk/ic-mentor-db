"""版式体检的测试：竖向填充度指标必须能区分"填满的页"与"半页空白"。

这个指标的第一版是错的——统计"非白像素占比"，结果所有文字页都只有 12%–26%，
全被误判。原因是文字页的墨迹覆盖率本来就低，那个指标衡量的是"字排得密不密"，
而不是"这页填满了没有"。现有测试把正确指标钉住。

为什么不再依赖仓库里的真实报告 PDF
----------------------------------
技术报告属参赛专用交付物，仓库已**停止跟踪**（只留在所有者本机）。所以测试用 Pillow
在 tempdir 里造最小 PDF：每页画一块墨迹，下边缘精确落在我们想看的位置。这样
"填满页 / 半页空白"两种样本都能自己造，1.26 MB 的真实 PDF 不再是测试前置。

覆盖两条契约：**有产物**时指标与阈值判定必须正确；**无产物**时显式 SKIP、退出码 0、
输出写明「未随仓库发布，已跳过」（``--strict`` 时才判失败）。
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from workbench.tools import pdf_layout_check as layout
from workbench.tools.pdf_layout_check import INK_THRESHOLD, page_bottom_fill

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKIP_PHRASE = "未随仓库发布，已跳过"
PAGE_W, PAGE_H = 300, 400


def make_pdf(path: pathlib.Path, fills: list[float]) -> pathlib.Path:
    """造一个 PDF：每页从页顶画一块墨迹，下边缘落在 ``fills[i]`` 处（占页高比例）。

    与 ``page_bottom_fill`` 的口径对齐：返回值 = 最下方墨迹所在行 / 页高。
    """
    from PIL import Image, ImageDraw

    images = []
    for fill in fills:
        image = Image.new("L", (PAGE_W, PAGE_H), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            [int(PAGE_W * 0.08), int(PAGE_H * 0.04),
             int(PAGE_W * 0.92), int(PAGE_H * fill)],
            fill=0,
        )
        images.append(image)
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=72.0)
    return path


def fills_of(spec: list[float], dpi: int = 72) -> list[float]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = make_pdf(pathlib.Path(tmp) / "sample.pdf", spec)
        return page_bottom_fill(pdf, dpi=dpi)


def run_main(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["prog", *argv]), contextlib.redirect_stdout(buf):
        code = layout.main()
    return code, buf.getvalue()


class MetricTests(unittest.TestCase):

    def test_ink_threshold_is_reasonable(self):
        # 阈值太高会把浅色文字当空白，太低会把纸张纹理当墨迹
        self.assertGreaterEqual(INK_THRESHOLD, 150)
        self.assertLessEqual(INK_THRESHOLD, 240)

    def test_dense_page_scores_high(self):
        fills = fills_of([0.97])
        self.assertEqual(len(fills), 1)
        self.assertGreaterEqual(fills[0], 0.92, f"填满的页只量到 {fills[0]:.1%}")

    def test_half_blank_page_scores_low(self):
        fills = fills_of([0.50])
        self.assertLessEqual(fills[0], 0.60, f"半页空白量到 {fills[0]:.1%}，指标失效")

    def test_metric_measures_vertical_extent_not_ink_coverage(self):
        """回归：指标是"墨迹到哪一行"，不是"墨迹占多少像素"。

        稀疏页（一条细横线铺满整页宽度，覆盖像素极少但一直落到页底）应当判高分；
        密实但只填半页的块应当判低分。若指标退回"非白像素占比"，这两者会颠倒。
        """
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmp:
            sparse = pathlib.Path(tmp) / "sparse.pdf"
            image = Image.new("L", (PAGE_W, PAGE_H), 255)
            draw = ImageDraw.Draw(image)
            for y in range(int(PAGE_H * 0.05), int(PAGE_H * 0.96), 40):
                draw.line([(10, y), (PAGE_W - 10, y)], fill=0, width=1)
            image.save(sparse, "PDF", resolution=72.0)
            sparse_fill = page_bottom_fill(sparse, dpi=72)[0]

            dense = pathlib.Path(tmp) / "dense.pdf"
            image = Image.new("L", (PAGE_W, PAGE_H), 255)
            draw = ImageDraw.Draw(image)
            draw.rectangle([0, 0, PAGE_W, int(PAGE_H * 0.45)], fill=0)
            image.save(dense, "PDF", resolution=72.0)
            dense_fill = page_bottom_fill(dense, dpi=72)[0]

        self.assertGreater(sparse_fill, 0.90,
                           f"铺到页底的稀疏内容被误判为留白（{sparse_fill:.1%}）")
        self.assertLess(dense_fill, 0.60,
                        f"只填半页的密实内容被误判为填满（{dense_fill:.1%}）")

    def test_multipage_fills_track_expected(self):
        fills = fills_of([0.95, 0.90, 0.55])
        self.assertEqual(len(fills), 3)
        self.assertAlmostEqual(fills[0], 0.95, delta=0.03)
        self.assertAlmostEqual(fills[1], 0.90, delta=0.03)
        self.assertAlmostEqual(fills[2], 0.55, delta=0.03)
        for value in fills:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class ThresholdTests(unittest.TestCase):
    """阈值判定：正文页低于硬阈值判失败，末页偏空豁免。"""

    def test_body_page_under_threshold_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = make_pdf(pathlib.Path(tmp) / "gap.pdf", [0.95, 0.50, 0.90])
            code, out = run_main(["--pdf", str(pdf)])
            self.assertEqual(code, 1, out)
            self.assertIn("1 页下方留白偏多", out)
            self.assertIn("第 2 页", out)

    def test_filled_body_pages_pass_and_last_page_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = make_pdf(pathlib.Path(tmp) / "ok.pdf", [0.95, 0.90, 0.40])
            code, out = run_main(["--pdf", str(pdf)])
            self.assertEqual(code, 0, "末页偏空不应判失败\n" + out)
            self.assertIn("版式正常", out)

    def test_custom_threshold_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = make_pdf(pathlib.Path(tmp) / "mid.pdf", [0.85, 0.85, 0.85])
            code, out = run_main(["--pdf", str(pdf), "--min-fill", "0.90"])
            self.assertEqual(code, 1, out)


class MissingArtifactTests(unittest.TestCase):

    def test_missing_pdf_skips_with_explicit_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = pathlib.Path(tmp) / "没有这个.pdf"
            code, out = run_main(["--pdf", str(absent)])
            self.assertEqual(code, 0, "缺 PDF 时默认应显式 SKIP（退出码 0）\n" + out)
            self.assertIn("SKIP", out)
            self.assertIn(SKIP_PHRASE, out)
            self.assertIn("不是版式体检通过", out)

    def test_strict_turns_missing_pdf_into_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = pathlib.Path(tmp) / "没有这个.pdf"
            code, out = run_main(["--pdf", str(absent), "--strict"])
            self.assertEqual(code, 1, out)


class RealPdfTests(unittest.TestCase):
    """所有者本机保留真实报告时仍然钉住版式质量（干净 clone 上按本地副本决定是否跑）。"""

    @classmethod
    def setUpClass(cls):
        cls.pdf = ROOT / "workbench/evaluation/records/技术报告.pdf"
        cls.fills = page_bottom_fill(cls.pdf, dpi=60) if cls.pdf.is_file() else []

    def setUp(self):
        if not self.pdf.is_file():
            self.skipTest(f"本机未保留 {self.pdf.name}（参赛交付物未随仓库发布）")

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