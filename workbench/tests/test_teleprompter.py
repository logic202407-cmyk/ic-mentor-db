"""提词稿解析的测试。

提词稿的价值是"录制时照着念"——所以**镜头数、时长、旁白必须一条不漏**。
解析第一版漏了镜头 7：那一行把时长写成了加粗的 `**2:10–2:55**`，
正则直接失配，而漏一个镜头在录制时才会发现。

为什么不再依赖仓库里的真实脚本
------------------------------
演示视频脚本与提词稿属参赛专用交付物，仓库已**停止跟踪**（只留在所有者本机）。
所以测试自己造一份同样格式的最小脚本（3 个镜头，其中一行时长加粗——正是当年漏掉
镜头 7 的成因），把解析逻辑钉住，而不是把 1 万多字的真实脚本当测试前置。

覆盖两条契约：**有产物**时解析/生成必须正确；**无产物**时显式 SKIP、退出码 0、
输出写明「未随仓库发布，已跳过」（``--strict`` 时才判失败），且**不得**留下半成品
提词稿。
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from workbench.tools import make_teleprompter as tele
from workbench.tools.make_teleprompter import parse, seconds_of

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKIP_PHRASE = "未随仓库发布，已跳过"
REAL_SCRIPT = ROOT / "workbench/evaluation/records/演示视频脚本.md"
REAL_OUT = ROOT / "workbench/evaluation/records/录制提词稿.txt"

# 与真实脚本同格式：表头、分隔行、普通行、加粗时长行。
SAMPLE_SCRIPT = """# 演示视频脚本

| 镜头 | 时长 | 画面 | 旁白 |
|:--|:--|:--|:--|
| 1 | 0:00–0:18 | 首页概览 | **这是第一段旁白。** 紧接着第二句。 |
| 2 | 0:18–1:03 | 导师检索页 | 第二段旁白，说明检索流程怎么用。 |
| 3 | **1:03–1:35** | 导师档案页 | 第三段旁白，说明档案里的证据口径。 |
"""

SAMPLE_TOTAL_SECONDS = 18 + 45 + 32  # = 95


def run_main(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["prog", *argv]), contextlib.redirect_stdout(buf):
        code = tele.main()
    return code, buf.getvalue()


class SecondsTests(unittest.TestCase):

    def test_basic_span(self):
        self.assertEqual(seconds_of("0:00–0:18"), 18)

    def test_crosses_minute(self):
        self.assertEqual(seconds_of("2:10–2:55"), 45)

    def test_full_span(self):
        self.assertEqual(seconds_of("4:25–4:50"), 25)

    def test_malformed_returns_zero(self):
        self.assertEqual(seconds_of("没有时间"), 0)


class ParseTests(unittest.TestCase):

    def setUp(self):
        self.shots = parse(SAMPLE_SCRIPT)

    def test_all_shots_parsed(self):
        numbers = [s["no"] for s in self.shots]
        self.assertEqual(numbers, [1, 2, 3], f"镜头不全或被重排：{numbers}")

    def test_header_and_separator_rows_are_not_shots(self):
        self.assertEqual(len(self.shots), 3, "表头/分隔行被误解析成镜头")

    def test_bold_timing_does_not_break_parsing(self):
        # 真实脚本的镜头 7 时长是加粗的，曾导致整行被漏掉
        three = next(s for s in self.shots if s["no"] == 3)
        self.assertEqual(three["seconds"], 32)
        self.assertEqual(three["span"], "1:03–1:35")

    def test_every_shot_has_narration(self):
        for shot in self.shots:
            self.assertTrue(shot["narration"], f"镜头 {shot['no']} 没有旁白")
            self.assertGreater(len(shot["narration"]), 10)

    def test_every_shot_has_scene(self):
        for shot in self.shots:
            self.assertTrue(shot["scene"], f"镜头 {shot['no']} 没有画面说明")

    def test_total_duration_matches_timeline(self):
        total = sum(s["seconds"] for s in self.shots)
        self.assertEqual(total, SAMPLE_TOTAL_SECONDS,
                         f"旁白合计 {total} 秒，应为 {SAMPLE_TOTAL_SECONDS} 秒")

    def test_no_emphasis_markers_left(self):
        for shot in self.shots:
            self.assertNotIn("**", shot["narration"])
            self.assertNotIn("**", shot["scene"])


class OutputFileTests(unittest.TestCase):
    """「有产物」路径：真造一份脚本，真生成提词稿，检查成品。"""

    def _generate(self, tmp: str) -> tuple[int, str, pathlib.Path]:
        base = pathlib.Path(tmp)
        script = base / "演示视频脚本.md"
        script.write_text(SAMPLE_SCRIPT, encoding="utf-8")
        out = base / "提词稿.txt"
        code, stdout = run_main(["--script", str(script), "--out", str(out)])
        return code, stdout, out

    def test_writes_teleprompter_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, path = self._generate(tmp)
            self.assertEqual(code, 0, out)
            self.assertTrue(path.is_file(), "没有写出提词稿")
            self.assertIn("共 3 个镜头", path.read_text(encoding="utf-8"))

    def test_teleprompter_covers_all_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            _code, _out, path = self._generate(tmp)
            text = path.read_text(encoding="utf-8")
            for n in (1, 2, 3):
                self.assertIn(f"镜头 {n} ", text, f"提词稿缺镜头 {n}")

    def test_teleprompter_is_plain_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            _code, _out, path = self._generate(tmp)
            text = path.read_text(encoding="utf-8")
            # 提词稿要能直接读，不该残留 Markdown 表格竖线与强调标记
            self.assertNotIn("|---", text)
            self.assertNotIn("**", text)

    def test_script_without_shots_is_a_real_failure(self):
        """脚本在、但解析不出分镜——这不是"缺产物跳过"，必须判失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            script = base / "空脚本.md"
            script.write_text("# 只有标题，没有表格\n", encoding="utf-8")
            code, out = run_main(["--script", str(script), "--out", str(base / "x.txt")])
            self.assertEqual(code, 1, out)
            self.assertIn("没有解析到分镜行", out)
            self.assertFalse((base / "x.txt").exists(), "解析失败时不该留下半成品")


class MissingArtifactTests(unittest.TestCase):
    """「无产物」路径：缺脚本必须显式 SKIP、返回 0、且不生成文件。"""

    def test_missing_script_skips_with_explicit_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            absent = base / "没有这个脚本.md"
            out_path = base / "提词稿.txt"
            code, out = run_main(["--script", str(absent), "--out", str(out_path)])
            self.assertEqual(code, 0, "缺脚本时默认应显式 SKIP（退出码 0）\n" + out)
            self.assertIn("SKIP", out)
            self.assertIn(SKIP_PHRASE, out)
            self.assertIn("没有生成提词稿", out)
            self.assertFalse(out_path.exists(), "跳过时不该写出提词稿")

    def test_strict_turns_missing_script_into_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = pathlib.Path(tmp) / "没有这个脚本.md"
            code, out = run_main(["--script", str(absent),
                                  "--out", str(pathlib.Path(tmp) / "x.txt"), "--strict"])
            self.assertEqual(code, 1, out)


class RealScriptTests(unittest.TestCase):
    """所有者本机保留真实脚本时仍然钉住镜头表（干净 clone 上按本地副本决定是否跑）。"""

    def setUp(self):
        if not REAL_SCRIPT.is_file():
            self.skipTest(f"本机未保留 {REAL_SCRIPT.name}（参赛交付物未随仓库发布）")

    def test_all_twelve_shots_parsed(self):
        shots = parse(REAL_SCRIPT.read_text(encoding="utf-8"))
        numbers = [s["no"] for s in shots]
        self.assertEqual(numbers, list(range(1, 13)), f"镜头不全或被重排：{numbers}")

    def test_total_duration_matches_real_timeline(self):
        shots = parse(REAL_SCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(sum(s["seconds"] for s in shots), 290,
                         "旁白合计应等于 4:50 = 290 秒")

    def test_committed_teleprompter_matches_script(self):
        if not REAL_OUT.is_file():
            self.skipTest(f"本机未保留 {REAL_OUT.name}（参赛交付物未随仓库发布）")
        text = REAL_OUT.read_text(encoding="utf-8")
        for n in range(1, 13):
            self.assertIn(f"镜头 {n} ", text, f"提词稿缺镜头 {n}")


if __name__ == "__main__":
    unittest.main()