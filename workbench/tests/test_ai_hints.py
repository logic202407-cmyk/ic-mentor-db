"""AI 建议读取层的测试：产物缺失要安全、建议不得冒充事实。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workbench import ai_hints


class _TempArtifacts:
    """把两个产物指到临时文件，避免测试依赖 .workbench-data/ 的实际内容。"""

    def __init__(self, suggestions: dict | None = None, review: list | None = None):
        self.dir = tempfile.TemporaryDirectory()
        base = Path(self.dir.name)
        self.sug_path = base / "suggestions.json"
        self.rev_path = base / "review.json"
        if suggestions is not None:
            self.sug_path.write_text(json.dumps(suggestions, ensure_ascii=False), encoding="utf-8")
        if review is not None:
            self.rev_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
        self._patches = [
            patch.object(ai_hints, "SUGGESTIONS_PATH", self.sug_path),
            patch.object(ai_hints, "REVIEW_PATH", self.rev_path),
        ]

    def __enter__(self):
        for p in self._patches:
            p.start()
        ai_hints.clear_cache()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        ai_hints.clear_cache()
        self.dir.cleanup()


SUG = {
    "pending": 10, "with_text": 9, "would_apply": 4, "min_score": 0.55,
    "by_method": {"keyword": 2, "embedding": 7},
    "suggestions": [{
        "id": "m1", "name": "张三", "institution": "A 大学",
        "suggested": "机器人", "score": 0.71, "method": "embedding", "apply": True,
        "top3": [{"label": "机器人", "score": 0.71}, {"label": "控制", "score": 0.6}],
    }],
}

REV = [{
    "name": "王晶", "institution": "西安交通大学", "emb": 0.99, "verdict": "疑似同人",
    "a": {"id": "m1", "dept": "机器人所", "home": "http://a"},
    "b": {"id": "m2", "dept": "先进制造所", "home": "http://b"},
}]


class MissingArtifactTests(unittest.TestCase):
    """产物在 .workbench-data/（gitignore），未跑过推断时必须安全降级。"""

    def test_summary_is_safe_when_files_absent(self):
        with _TempArtifacts():
            s = ai_hints.summary()
        self.assertFalse(s["direction"]["available"])
        self.assertEqual(s["name_review"]["pairs"], 0)
        self.assertIn("不构成事实", s["disclaimer"])

    def test_hints_for_unknown_mentor_is_empty(self):
        with _TempArtifacts():
            h = ai_hints.hints_for("nope")
        self.assertIsNone(h["direction_suggestion"])
        self.assertEqual(h["name_review"], [])


class WithArtifactTests(unittest.TestCase):

    def test_direction_suggestion_is_returned_with_score_and_method(self):
        with _TempArtifacts(SUG, REV):
            item = ai_hints.direction_suggestion("m1")
        self.assertEqual(item["suggested"], "机器人")
        self.assertEqual(item["method"], "embedding")
        self.assertTrue(item["passes_threshold"])
        self.assertEqual(len(item["top3"]), 2)

    def test_every_suggestion_carries_the_disclaimer(self):
        with _TempArtifacts(SUG, REV):
            item = ai_hints.direction_suggestion("m1")
        self.assertIn("不构成事实", item["disclaimer"])
        self.assertIn("不会", item["disclaimer"])

    def test_name_review_shows_the_other_side(self):
        with _TempArtifacts(SUG, REV):
            pairs = ai_hints.name_review("m1")
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["other"]["dept"], "先进制造所")

    def test_name_review_is_symmetric(self):
        with _TempArtifacts(SUG, REV):
            from_a = ai_hints.name_review("m1")
            from_b = ai_hints.name_review("m2")
        self.assertEqual(from_a[0]["other"]["dept"], "先进制造所")
        self.assertEqual(from_b[0]["other"]["dept"], "机器人所")

    def test_summary_counts_come_from_artifact(self):
        with _TempArtifacts(SUG, REV):
            s = ai_hints.summary()
        self.assertTrue(s["direction"]["available"])
        self.assertEqual(s["direction"]["would_apply"], 4)
        self.assertEqual(s["name_review"]["pairs"], 1)

    def test_suggestion_never_claims_to_be_fact(self):
        """建议里不得出现会被误读成"已确认"的字段。"""
        with _TempArtifacts(SUG, REV):
            item = ai_hints.direction_suggestion("m1")
        self.assertNotIn("confirmed", item)
        self.assertNotIn("applied", item)


if __name__ == "__main__":
    unittest.main()
