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


if __name__ == "__main__":
    unittest.main()
