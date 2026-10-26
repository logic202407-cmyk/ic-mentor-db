"""报告产物同步校验的测试。

这条校验是为了防一个真实事故：Markdown 已改（写成 38/38 达标），但 PDF 没重新生成，
评审读到的还是旧的「35 达标 / 3 未达标」。**主交付物静默落后是最贵的错**。

为什么不再依赖仓库里的真实交付物
--------------------------------
技术报告三件产物属参赛专用交付物，仓库已**停止跟踪**（只留在所有者本机）。所以测试
自己用 tempdir 造最小样本：一张几 KB 的 md/html/pdf。这样干净 clone 与 CI 上也能真实
跑到校验逻辑，而不是"文件不在就红"或"干脆不测"。

覆盖两条契约：

1. **有产物**：哈希一致/落后、标记缺失、PDF 早于 HTML —— 都必须判对；
2. **无产物**：显式 SKIP、退出码 0、输出必须写明「未随仓库发布，已跳过」，
   ``--strict`` 时才判失败。跳过绝不能被读成"校验通过"。

另外保留一组「本机有原件时才跑」的整体校验：它对所有者本机仍有约束力，但缺原件时
按本地副本来判定，不会把干净 clone 弄红。
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from workbench.tools import check_pdf_limits as limits
from workbench.tools import check_report_sync as sync
from workbench.tools.check_report_sync import MARKER, sha256_of

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKIP_PHRASE = "未随仓库发布，已跳过"
HTML_MTIME = 1_700_000_000
PDF_MTIME = 1_700_000_100


def run_main(entry, argv: list[str]) -> tuple[int, str]:
    """在进程内跑工具的 main()，捕获退出码与 stdout（不碰仓库里的真实产物）。"""
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["prog", *argv]), contextlib.redirect_stdout(buf):
        code = entry()
    return code, buf.getvalue()


def build_artifacts(base: pathlib.Path, *, marker: str | None = "sync",
                    html_mtime: int = HTML_MTIME, pdf_mtime: int = PDF_MTIME,
                    with_pdf: bool = True, with_html: bool = True,
                    with_md: bool = True) -> tuple[pathlib.Path, ...]:
    """在 tempdir 里造一份最小报告三件产物。

    ``marker``: "sync" = 正确哈希；"stale" = 错的哈希；None = 没有标记。
    """
    base.mkdir(parents=True, exist_ok=True)
    md = base / "技术报告.md"
    html = base / "技术报告.html"
    pdf = base / "技术报告.pdf"
    if with_md:
        md.write_text("# 技术报告\n\n## 第五章\n工作台目录含 **15,719** 条记录。\n",
                      encoding="utf-8")
    if with_html:
        if marker is None:
            html.write_text("<html><body>旧版生成器</body></html>\n", encoding="utf-8")
        else:
            digest = sha256_of(md) if marker == "sync" else "f" * 64
            html.write_text(f"<!-- source-sha256: {digest} -->\n<html></html>\n",
                            encoding="utf-8")
        os.utime(html, (html_mtime, html_mtime))
    if with_pdf:
        pdf.write_bytes(b"%PDF-1.4\n% minimal stub, content not read by this check\n")
        os.utime(pdf, (pdf_mtime, pdf_mtime))
    return md, html, pdf


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


class SyncCheckTests(unittest.TestCase):
    """「有产物」路径：用 tempdir 最小样本验证判据本身。"""

    def test_in_sync_artifacts_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_artifacts(pathlib.Path(tmp))
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 0, out)
            self.assertIn("HTML 与 Markdown 一致", out)
            self.assertIn("PDF 不早于 HTML", out)
            self.assertNotIn("SKIP", out)

    def test_stale_html_hash_is_detected(self):
        """md 改了但 HTML 没重跑——主交付物静默落后的原发场景。"""
        with tempfile.TemporaryDirectory() as tmp:
            build_artifacts(pathlib.Path(tmp), marker="stale")
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 1, out)
            self.assertIn("HTML 落后于 Markdown", out)

    def test_missing_source_marker_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_artifacts(pathlib.Path(tmp), marker=None)
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 1, out)
            self.assertIn("没有 source-sha256 标记", out)

    def test_pdf_older_than_html_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_artifacts(pathlib.Path(tmp), html_mtime=PDF_MTIME, pdf_mtime=HTML_MTIME)
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 1, out)
            self.assertIn("PDF 早于 HTML", out)

    def test_custom_md_name_is_honoured(self):
        """--md 换名字时 html/pdf 要跟着换（后缀推导），不能写死三个文件名。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            build_artifacts(base)
            (base / "技术报告.md").rename(base / "另一份.md")
            html = (base / "技术报告.html").read_text(encoding="utf-8")
            (base / "另一份.html").write_text(html, encoding="utf-8")
            os.utime(base / "另一份.html", (HTML_MTIME, HTML_MTIME))
            (base / "技术报告.pdf").rename(base / "另一份.pdf")
            os.utime(base / "另一份.pdf", (PDF_MTIME, PDF_MTIME))
            code, out = run_main(sync.main, ["--base", tmp, "--md", "另一份.md"])
            self.assertEqual(code, 0, out)


class MissingArtifactTests(unittest.TestCase):
    """「无产物」路径：缺文件必须显式 SKIP 并返回 0，措辞不得像"通过"。"""

    def test_missing_artifacts_skip_with_explicit_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 0, "缺产物时默认应显式 SKIP（退出码 0）\n" + out)
            self.assertIn("SKIP", out)
            self.assertIn(SKIP_PHRASE, out)
            self.assertIn("不是校验通过", out)
            # 三个文件都要逐个点名，避免"只缺了一个"被整体跳过掩盖
            self.assertEqual(out.count("⊘ 缺少"), 3, out)

    def test_partial_artifacts_list_every_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_artifacts(pathlib.Path(tmp), with_html=False, with_pdf=False)
            code, out = run_main(sync.main, ["--base", tmp])
            self.assertEqual(code, 0, out)
            self.assertIn(SKIP_PHRASE, out)
            self.assertEqual(out.count("⊘ 缺少"), 2, out)
            self.assertNotIn("HTML 与 Markdown 一致", out)

    def test_strict_turns_missing_into_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(sync.main, ["--base", tmp, "--strict"])
            self.assertEqual(code, 1, "--strict 时缺产物必须判失败\n" + out)
            self.assertIn("缺少", out)


class RepoLocalCopyTests(unittest.TestCase):
    """所有者本机保留原件时的整体校验（干净 clone 上按本地副本判定是否跑）。"""

    HTML = ROOT / "workbench/evaluation/records/技术报告.html"
    PDF = ROOT / "workbench/evaluation/records/技术报告.pdf"

    def test_report_artifacts_are_in_sync_on_this_machine(self):
        # encoding/errors 必须显式指定：被测脚本会输出中文，Windows 默认按 GBK 解码，
        # 在非中文控制台或含 BOM 的输出上会抛 UnicodeDecodeError（曾真的报过一次）。
        result = subprocess.run(
            [sys.executable, "-m", "workbench.tools.check_report_sync"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(
            result.returncode, 0,
            "报告产物不同步：先跑 make_aic_html.py 再跑 make_aic_pdf.ps1\n"
            + (result.stdout or "") + (result.stderr or ""),
        )
        if not (ROOT / "workbench/evaluation/records/技术报告.md").is_file():
            # 干净 clone：本机没有原件，命令走的是 SKIP 分支，这同样是正确行为。
            self.assertIn(SKIP_PHRASE, result.stdout or "")

    def test_html_carries_source_hash(self):
        if not self.HTML.is_file():
            self.skipTest(f"本机未保留 {self.HTML.name}（参赛交付物未随仓库发布）")
        self.assertIsNotNone(MARKER.search(self.HTML.read_text(encoding="utf-8")))

    def test_pdf_is_not_empty(self):
        if not self.PDF.is_file():
            self.skipTest(f"本机未保留 {self.PDF.name}（参赛交付物未随仓库发布）")
        self.assertGreater(self.PDF.stat().st_size, 200_000)
        self.assertEqual(self.PDF.read_bytes()[:5], b"%PDF-")


def make_pdf(path: pathlib.Path, pages: int = 1, size: tuple[int, int] = (200, 200)) -> None:
    """用 Pillow 生成一个最小合法 PDF（页数可控，不含任何真实报告内容）。"""
    from PIL import Image

    images = [Image.new("L", size, 255) for _ in range(pages)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=72.0)


class PdfLimitTests(unittest.TestCase):
    """赛题要求技术报告 PDF 正文 ≤15 页、≤10 MB——硬限制，超了可能直接不合格。

    本项目真实踩过：补齐两章 AI 实证后页数从 15 涨到 18，而当时所有文档还写着"14 页"。
    加内容时没人会去数页数，所以把限制写成测试。样本由测试自己造，不依赖 1.26 MB 的
    真实 PDF。
    """

    def test_count_pages_reads_minimal_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = pathlib.Path(tmp) / "small.pdf"
            make_pdf(pdf, pages=3)
            self.assertEqual(limits.count_pages(pdf), 3)

    def test_pdf_within_limits_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = pathlib.Path(tmp) / "ok.pdf"
            make_pdf(pdf, pages=15)
            code, out = run_main(limits.main, ["--pdf", str(pdf)])
            self.assertEqual(code, 0, out)
            self.assertIn("页数 15（上限 15）  ✓", out)
            self.assertIn("大小", out)

    def test_too_many_pages_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = pathlib.Path(tmp) / "long.pdf"
            make_pdf(pdf, pages=18)
            code, out = run_main(limits.main, ["--pdf", str(pdf)])
            self.assertEqual(code, 1, out)
            self.assertIn("页数 18 超过上限 15", out)

    def test_too_large_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = pathlib.Path(tmp) / "big.pdf"
            make_pdf(pdf, pages=1)
            code, out = run_main(limits.main, ["--pdf", str(pdf), "--max-mb", "0.0001"])
            self.assertEqual(code, 1, out)
            self.assertIn("超过上限 0.0001 MB", out)

    def test_missing_pdf_skips_with_explicit_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = pathlib.Path(tmp) / "没有这个.pdf"
            code, out = run_main(limits.main, ["--pdf", str(absent)])
            self.assertEqual(code, 0, out)
            self.assertIn("SKIP", out)
            self.assertIn(SKIP_PHRASE, out)
            self.assertIn("不是校验通过", out)

    def test_strict_turns_missing_pdf_into_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = pathlib.Path(tmp) / "没有这个.pdf"
            code, out = run_main(limits.main, ["--pdf", str(absent), "--strict"])
            self.assertEqual(code, 1, out)
            self.assertIn("找不到", out)


class RepoPdfLimitTests(unittest.TestCase):
    """本机保留真实 PDF 时仍然钉住赛题硬限制（干净 clone 上按本地副本决定是否跑）。"""

    PDF = ROOT / "workbench/evaluation/records/技术报告.pdf"

    def test_real_pdf_within_page_limit(self):
        if not self.PDF.is_file():
            self.skipTest(f"本机未保留 {self.PDF.name}（参赛交付物未随仓库发布）")
        pages = limits.count_pages(self.PDF)
        self.assertLessEqual(pages, 15, f"页数 {pages} 超过 15 页上限，需精简内容或收紧排版")

    def test_real_pdf_within_size_limit(self):
        if not self.PDF.is_file():
            self.skipTest(f"本机未保留 {self.PDF.name}（参赛交付物未随仓库发布）")
        size_mb = self.PDF.stat().st_size / 1024 / 1024
        self.assertLessEqual(size_mb, 10.0, f"大小 {size_mb:.2f} MB 超过 10 MB 上限")

    def test_real_pdf_has_content(self):
        if not self.PDF.is_file():
            self.skipTest(f"本机未保留 {self.PDF.name}（参赛交付物未随仓库发布）")
        self.assertGreaterEqual(limits.count_pages(self.PDF), 8, "页数过少，疑似生成失败")


if __name__ == "__main__":
    unittest.main()