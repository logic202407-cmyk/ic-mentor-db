"""提词稿解析的测试。

提词稿的价值是"录制时照着念"——所以**镜头数、时长、旁白必须一条不漏**。
解析第一版漏了镜头 7：那一行把时长写成了加粗的 `**2:10–2:55**`，
正则直接失配，而漏一个镜头在录制时才会发现。
"""

from __future__ import annotations

import pathlib
import unittest

from workbench.tools.make_teleprompter import SCRIPT, parse, seconds_of

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "workbench/aic-submission/录制提词稿.txt"


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

    @classmethod
    def setUpClass(cls):
        cls.shots = parse(SCRIPT.read_text(encoding="utf-8"))

    def test_all_twelve_shots_parsed(self):
        numbers = [s["no"] for s in self.shots]
        self.assertEqual(numbers, list(range(1, 13)),
                         f"镜头不全或被重排：{numbers}")

    def test_bold_timing_does_not_break_parsing(self):
        # 镜头 7 的时长在脚本里是加粗的，曾导致它被整行漏掉
        seven = next(s for s in self.shots if s["no"] == 7)
        self.assertEqual(seven["seconds"], 45)

    def test_every_shot_has_narration(self):
        for shot in self.shots:
            self.assertTrue(shot["narration"], f"镜头 {shot['no']} 没有旁白")
            self.assertGreater(len(shot["narration"]), 10)

    def test_every_shot_has_scene(self):
        for shot in self.shots:
            self.assertTrue(shot["scene"], f"镜头 {shot['no']} 没有画面说明")

    def test_total_duration_matches_timeline(self):
        total = sum(s["seconds"] for s in self.shots)
        self.assertEqual(total, 290, f"旁白合计 {total} 秒，应等于 4:50 = 290 秒")

    def test_no_emphasis_markers_left(self):
        for shot in self.shots:
            self.assertNotIn("**", shot["narration"])
            self.assertNotIn("**", shot["scene"])


class OutputFileTests(unittest.TestCase):

    def test_teleprompter_file_exists(self):
        self.assertTrue(OUT.is_file(), "缺少提词稿文件")

    def test_teleprompter_covers_all_shots(self):
        text = OUT.read_text(encoding="utf-8")
        for n in range(1, 13):
            self.assertIn(f"镜头 {n} ", text, f"提词稿缺镜头 {n}")

    def test_teleprompter_is_plain_text(self):
        text = OUT.read_text(encoding="utf-8")
        # 提词稿要能直接读，不该残留 Markdown 表格竖线
        self.assertNotIn("|---", text)
        self.assertNotIn("**", text)


if __name__ == "__main__":
    unittest.main()
