"""检索方式接线的测试：BM25 / hybrid / auto 与模型不可用时的回退。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

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


# ---------------------------------------------------------------------------
# 索引缓存：`search()` 是每请求调用一次的，与查询无关的工作只能做一遍。
# 旧实现每次请求都重新切词建 BM25 索引，全量目录实测单请求 0.48–1.70 s，
# 而建好之后的打分只要 0.07 ms。这一组把「只建一次」和「内容变了要重建」都钉住。
# ---------------------------------------------------------------------------

class _CountingIndex(search.BM25Index):
    builds = 0

    def __init__(self, *args, **kwargs):
        type(self).builds += 1
        super().__init__(*args, **kwargs)


class IndexCacheTests(unittest.TestCase):

    def setUp(self):
        search.clear_cache()
        _CountingIndex.builds = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(
            search, "_index_path",
            lambda project_id: Path(self.tmp.name) / f"{project_id}.npz")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()
        search.clear_cache()

    def test_bm25_index_is_built_once_for_repeated_queries(self):
        with mock.patch.object(search, "BM25Index", _CountingIndex):
            first = search.search(PROJECT, "MEMS", mode="bm25")
            second = search.search(PROJECT, "MEMS", mode="bm25")
        self.assertEqual(_CountingIndex.builds, 1, "同一份内容不应重复建索引")
        self.assertEqual([row["profile"]["id"] for row in first],
                         [row["profile"]["id"] for row in second])

    def test_edited_profile_invalidates_the_cached_index(self):
        self.assertEqual(search.search(PROJECT, "海洋工程", mode="bm25"), [])
        edited = {"id": PROJECT["id"], "name": PROJECT["name"], "profiles": [
            _profile("p1", "甲", "VLSI 数字集成电路设计"),
            _profile("p2", "乙", "海洋工程结构"),
            _profile("p3", "丙", "中文问答与知识组织"),
        ]}
        results = search.search(edited, "海洋工程", mode="bm25")
        self.assertTrue(results, "内容改了以后必须重建索引，不能吃旧缓存")
        self.assertEqual(results[0]["profile"]["id"], "p2")

    def test_keyword_batch_matches_single_text_scoring(self):
        texts = [search.document(profile) for profile in PROJECT["profiles"]]
        normalized = [search._normalize_text(text) for text in texts]
        for query in ("MEMS", "VLSI 数字", "中文问答", "", "不存在的词xyz", "a"):
            batch = search.keyword_scores_for_texts(query, normalized)
            for index, text in enumerate(texts):
                self.assertAlmostEqual(
                    float(batch[index]), search.keyword_score(query, text), places=7,
                    msg=f"查询 {query!r} 第 {index} 条批量分与单条分不一致")


# ---------------------------------------------------------------------------
# 低相关空判：评测层验证过的规则要真的接进产品路径。
# 旧实现里 semantic 模式对任何查询都返回 20 条（无关查询最高余弦只有 0.36），
# 也就是「硬塞」；而 SEMANTIC_EMPTY_TAU 定义着却没人用。
# ---------------------------------------------------------------------------

class _FakeEmbedder:
    """4 维假向量：三篇文档各占一个正交方向，查询向量与三者余弦都不超过 0.25。"""

    DOC_VECTORS = {"VLSI": [1.0, 0.0, 0.0, 0.0],
                   "MEMS": [0.0, 1.0, 0.0, 0.0],
                   "中文": [0.0, 0.0, 1.0, 0.0]}
    QUERY_VECTOR = [0.25, 0.25, 0.25, 0.9]

    def embed(self, texts):
        for text in texts:
            vector = next((value for key, value in self.DOC_VECTORS.items() if key in text),
                          [0.0, 0.0, 0.0, 1.0])
            yield np.asarray(vector, dtype=np.float32)

    def query_embed(self, texts):
        for _ in texts:
            yield np.asarray(self.QUERY_VECTOR, dtype=np.float32)


# 与 PROJECT 用不同的 id，避免和别的用例共用缓存条目。
GUARD_PROJECT = {"id": "f" * 32, "name": "空判测试", "profiles": PROJECT["profiles"]}


class GuardedEmptyTests(unittest.TestCase):

    def setUp(self):
        search.clear_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(
            search, "_index_path",
            lambda project_id: Path(self.tmp.name) / f"{project_id}.npz")
        self.patch.start()
        self.embedder = mock.patch.object(search, "_embedder", lambda: _FakeEmbedder())
        self.embedder.start()

    def tearDown(self):
        self.embedder.stop()
        self.patch.stop()
        self.tmp.cleanup()
        search.clear_cache()

    def test_decision_truth_table(self):
        self.assertFalse(search.guarded_empty_decision([0.7, 0.5], 0.0),
                         "余弦够高就不该判空")
        self.assertFalse(search.guarded_empty_decision([0.3, 0.2], 5.0),
                         "还有字面命中就不该判空")
        self.assertTrue(search.guarded_empty_decision([0.3, 0.2], 0.0),
                        "余弦低且毫无字面证据才判空")
        self.assertFalse(search.guarded_empty_decision([], 0.0))

    def test_off_topic_query_returns_empty_instead_of_twenty_rows(self):
        self.assertEqual(search.search(GUARD_PROJECT, "红烧肉的做法", mode="semantic"), [])
        self.assertEqual(search.search(GUARD_PROJECT, "红烧肉的做法", mode="hybrid"), [])

    def test_lexical_evidence_keeps_results(self):
        results = search.search(GUARD_PROJECT, "MEMS", mode="semantic")
        self.assertTrue(results, "有字面命中时不能因为余弦低就删结果")
        self.assertEqual(len(results), 3)

    def test_filtered_search_is_not_emptied(self):
        results = search.search(GUARD_PROJECT, "红烧肉的做法", mode="semantic",
                                discipline="微机电")
        self.assertTrue(results, "带学科筛选时按评测口径不做空判")


if __name__ == "__main__":
    unittest.main()