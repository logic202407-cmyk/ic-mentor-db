"""报告产物同步校验的测试。

这条校验是为了防一个真实事故：Markdown 已改（写成 38/38 达标），但 PDF 没重新生成，
评审读到的还是旧的「35 达标 / 3 未达标」。**主交付物静默落后是最贵的错**。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
import tempfile
import unittest

from workbench.tools.check_report_sync import MARKER, sha256_of

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


class MarkerTests(unittest.TestCase):

    def test_marker_matches_64_hex(self):
        digest = "a" * 64
        self.assertIsNotNone(MARKER.search(f"<!-- source-sha256: {digest} -->"))

    def test_marker_rejects_short_hash(self):
        self.assertIsNone(MARKER.search("<!-- source-sha256: abc123 -->"))

    def test_marker_tolerates_spacing(self):
        self.assertIsNotNone(MARKER.search("<!--source-sha256:" + "b" * 64 + "-->"))


class Sha256Tests(unittest.TestCase):

    def test_hash_is_stable_and_content_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = pathlib.Path(tmp) / "a.md"
            a.write_text("# 标题\n内容\n", encoding="utf-8")
            first = sha256_of(a)
            self.assertEqual(first, sha256_of(a))
            a.write_text("# 标题\n内容改了一行\n", encoding="utf-8")
            self.assertNotEqual(first, sha256_of(a))
            self.assertEqual(len(first), 64)


class RealRepoTests(unittest.TestCase):
    """真实仓库里的三件产物应当同步；不同步时这个测试会红，提示需要重新生成。"""

    def test_report_artifacts_are_in_sync(self):
        result = subprocess.run(
            [sys.executable, "-m", "workbench.tools.check_report_sync"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            "报告产物不同步：先跑 make_aic_html.py 再跑 make_aic_pdf.ps1\n"
            + (result.stdout or "") + (result.stderr or ""),
        )

    def test_html_carries_source_hash(self):
        html = ROOT / "workbench/aic-submission/技术报告.html"
        self.assertTrue(html.is_file())
        self.assertIsNotNone(MARKER.search(html.read_text(encoding="utf-8")))

    def test_pdf_is_not_empty(self):
        pdf = ROOT / "workbench/aic-submission/技术报告.pdf"
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 200_000)
        self.assertEqual(pdf.read_bytes()[:5], b"%PDF-")


class PdfLimitTests(unittest.TestCase):
    """赛题要求技术报告 PDF 正文 ≤15 页、≤10 MB——硬限制，超了可能直接不合格。

    本项目真实踩过：补齐两章 AI 实证后页数从 15 涨到 18，而当时所有文档还写着"14 页"。
    加内容时没人会去数页数，所以把限制写成测试。
    """

    PDF = ROOT / "workbench/aic-submission/技术报告.pdf"

    def test_pdf_within_page_limit(self):
        from workbench.tools.check_pdf_limits import count_pages

        pages = count_pages(self.PDF)
        self.assertLessEqual(pages, 15, f"页数 {pages} 超过 15 页上限，需精简内容或收紧排版")

    def test_pdf_within_size_limit(self):
        size_mb = self.PDF.stat().st_size / 1024 / 1024
        self.assertLessEqual(size_mb, 10.0, f"大小 {size_mb:.2f} MB 超过 10 MB 上限")

    def test_pdf_has_content(self):
        from workbench.tools.check_pdf_limits import count_pages

        self.assertGreaterEqual(count_pages(self.PDF), 8, "页数过少，疑似生成失败")


if __name__ == "__main__":
    unittest.main()
