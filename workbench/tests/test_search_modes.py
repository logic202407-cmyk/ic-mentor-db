"""检索方式接线的测试：BM25 / hybrid / auto 与模型不可用时的回退。"""

from __future__ import annotations

import unittest
from unittest import mock

from workbench import search


def _profile(pid: str, name: str, interests: str) -> dict:
    return {
        "id": pid, "name": name, "institution": "示例大学", "department": "示例学院",
        "discipline": interests, "first_level_discipline": "0809 电子科学与技术",
        "direction_group": interests, "interests": interests, "summary": "",
        "sources": [{"title": "来源", "url": "https://example.edu.cn"}],
    }


PROJECT = {"id": "a" * 32, "name": "测试", "profiles": [
    _profile("p1", "甲", "VLSI 数字集成电路设计"),
    _profile("p2", "乙", "MEMS 微机电系统"),
    _profile("p3", "丙", "中文问答与知识组织"),
]}


class ModeValidationTests(unittest.TestCase):

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            search.search(PROJECT, "芯片", mode="magic")

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            search.search(PROJECT, "   ")

    def test_no_matching_profiles_returns_empty(self):
        self.assertEqual(search.search(PROJECT, "芯片", mode="bm25",
                                       discipline="不存在的学科"), [])


class RetrievalModeTests(unittest.TestCase):

    def test_bm25_ranks_term_match_first(self):
        results = search.search(PROJECT, "MEMS", mode="bm25")
        self.assertTrue(results)
        self.assertEqual(results[0]["profile"]["id"], "p2")
        self.assertEqual(results[0]["mode"], "bm25")

    def test_keyword_mode_still_works(self):
        results = search.search(PROJECT, "中文问答", mode="keyword")
        self.assertEqual(results[0]["profile"]["id"], "p3")

    def test_auto_uses_bm25_for_acronyms(self):
        results = search.search(PROJECT, "VLSI", mode="auto")
        self.assertEqual(results[0]["mode"], "bm25")
        self.assertEqual(results[0]["profile"]["id"], "p1")

    def test_auto_falls_back_when_model_missing(self):
        # 自然语言查询本应走 hybrid；模型不可用时必须回落到 BM25 并写明原因
        with mock.patch.object(search, "_embedder", side_effect=RuntimeError("model missing")):
            results = search.search(PROJECT, "我想做中文问答和知识组织", mode="hybrid")
        self.assertTrue(results)
        self.assertEqual(results[0]["mode"], "bm25")
        self.assertIn("向量模型不可用", results[0]["fallback"])

    def test_semantic_falls_back_instead_of_raising(self):
        with mock.patch.object(search, "_embedder", side_effect=ImportError("no fastembed")):
            results = search.search(PROJECT, "中文问答", mode="semantic")
        self.assertTrue(results)
        self.assertEqual(results[0]["mode"], "bm25")
        self.assertIn("ImportError", results[0]["fallback"])


class LexicalHeuristicTests(unittest.TestCase):

    def test_acronyms_are_lexical(self):
        for query in ("VLSI", "MEMS", "EDA", "RISC-V", "AI for Science"):
            self.assertTrue(search._looks_lexical(query), query)

    def test_natural_language_is_not_lexical(self):
        for query in ("我想做中文问答和知识组织", "怎么用深度学习做医学影像", "帮我找做芯片设计的导师"):
            self.assertFalse(search._looks_lexical(query), query)


if __name__ == "__main__":
    unittest.main()