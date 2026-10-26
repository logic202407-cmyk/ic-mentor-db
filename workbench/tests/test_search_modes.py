"""检索方式接线的测试：BM25 / hybrid / auto 与模型不可用时的回退。"""

from __future__ import annotations

import random
import tempfile
import time
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


class _CountingEmbedder:
    """会数调用次数的假嵌入器：用来证明「同一份语料只建一次索引」。"""

    def __init__(self):
        self.embed_batches = []

    def embed(self, texts):
        texts = list(texts)
        self.embed_batches.append(len(texts))
        for index, _text in enumerate(texts):
            yield np.asarray([0.25, 0.25, 0.25, 0.9 + index * 1e-6], dtype=np.float32)

    def query_embed(self, texts):
        for _ in texts:
            yield np.asarray([0.25, 0.25, 0.25, 0.9], dtype=np.float32)


def _many_profiles(count: int) -> list[dict]:
    return [_profile(f"s{index:03d}", f"人{index:03d}", f"方向{index:03d} 硅光集成")
            for index in range(count)]


class VectorIndexCacheTests(unittest.TestCase):
    """索引按内容指纹寻址：同一份语料换项目 id 也必须复用，不许重建。"""

    def setUp(self):
        search.clear_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(
            search, "_index_path",
            lambda digest: Path(self.tmp.name) / f"{digest[:32]}.npz")
        self.patch.start()
        self.legacy_patch = mock.patch.object(
            search, "_legacy_index_path",
            lambda project_id: (Path(self.tmp.name) / f"{project_id}.npz")
            if project_id else None)
        self.legacy_patch.start()
        self.embedder = _CountingEmbedder()
        self.model_patch = mock.patch.object(search, "_embedder", lambda: self.embedder)
        self.model_patch.start()

    def tearDown(self):
        self.model_patch.stop()
        self.legacy_patch.stop()
        self.patch.stop()
        self.tmp.cleanup()
        search.clear_cache()

    def _project(self, project_id: str, profiles=None) -> dict:
        return {"id": project_id, "name": "缓存测试",
                "profiles": profiles or _many_profiles(8)}

    def test_index_is_shared_across_project_ids_with_identical_content(self):
        first = search.search(self._project("project-one"), "硅光集成", mode="semantic")
        builds_after_first = list(self.embedder.embed_batches)
        second = search.search(self._project("project-two"), "硅光集成", mode="semantic")
        self.assertEqual(self.embedder.embed_batches, builds_after_first,
                         "同一份语料换个项目 id 又把向量重建了一遍")
        self.assertEqual([row["profile"]["id"] for row in first],
                         [row["profile"]["id"] for row in second])
        files = sorted(Path(self.tmp.name).glob("*.npz"))
        self.assertEqual(len(files), 1, f"内容寻址后应只有一个索引文件，实际 {files}")

    def test_index_file_is_named_by_content_digest(self):
        project = self._project("project-one")
        search.search(project, "硅光集成", mode="semantic")
        digest = search._document_digest(
            project["profiles"], [search.document(p) for p in project["profiles"]])
        self.assertTrue(search._index_path(digest).exists())
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.npz"))), 1)

    def test_index_is_written_uncompressed(self):
        """压缩写 1.34 s / 未压缩 0.016 s（15,719×512 实测），读 0.17 s / 0.036 s。"""
        import zipfile
        project = self._project("project-one")
        search.search(project, "硅光集成", mode="semantic")
        path = sorted(Path(self.tmp.name).glob("*.npz"))[0]
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("vectors.npy")
        self.assertEqual(info.compress_type, zipfile.ZIP_STORED,
                         "索引应未压缩落盘：冷启动在意读耗时，文件只大 8%")

    def test_corrupted_index_is_rebuilt_instead_of_degreading_to_bm25(self):
        project = self._project("project-one")
        search.search(project, "硅光集成", mode="semantic")
        path = sorted(Path(self.tmp.name).glob("*.npz"))[0]
        path.write_bytes(b"not an npz at all")
        search.clear_cache()
        results = search.search(project, "硅光集成", mode="semantic")
        self.assertGreaterEqual(len(self.embedder.embed_batches), 2,
                                "损坏的索引必须重建，而不是永远回落到 BM25")
        self.assertEqual(results[0]["mode"], "semantic")
        self.assertEqual(results[0]["fallback"], "")
        with np.load(path, allow_pickle=False) as saved:      # 坏文件已被替换成好文件
            self.assertEqual(str(saved["model"]), search.MODEL_NAME)

    def test_content_change_invalidates_the_index(self):
        project = self._project("project-one")
        search.search(project, "硅光集成", mode="semantic")
        edited = self._project("project-one", _many_profiles(8) + [
            _profile("extra", "新人", "海底观测网")])
        search.search(edited, "海底观测网", mode="semantic")
        self.assertGreaterEqual(len(self.embedder.embed_batches), 2,
                                "记录变了必须重建索引，不能吃旧缓存")
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.npz"))), 2)

    def test_legacy_project_id_index_is_adopted_without_rebuild(self):
        """旧版本按 project id 命名索引；升级后要接管它，而不是白建一次。"""
        project = self._project("legacy-project")
        profiles = project["profiles"]
        digest = search._document_digest(
            profiles, [search.document(p) for p in profiles])
        vectors = np.asarray(list(self.embedder.embed(profiles and [
            search.document(p) for p in profiles])), dtype=np.float32)
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        legacy = Path(self.tmp.name) / "legacy-project.npz"
        np.savez_compressed(legacy, vectors=vectors, fingerprint=digest,
                            model=search.MODEL_NAME)
        self.embedder.embed_batches.clear()
        results = search.search(project, "硅光集成", mode="semantic")
        self.assertEqual(self.embedder.embed_batches, [],
                         "旧命名索引指纹一致时不该重建向量")
        self.assertEqual(results[0]["mode"], "semantic")
        self.assertTrue(search._index_path(digest).exists(), "应改写成内容寻址名")
        self.assertTrue(legacy.exists(), "旧文件不删：可能还有别的项目 id 指着它")


# ---------------------------------------------------------------------------
# 查询质量：没有研究条件的查询不得随机输出名单。
# 测试集在 workbench/evaluation/query_types.json（分 8 类真实样例）。
# ---------------------------------------------------------------------------

QUERY_TYPES_PATH = (Path(__file__).resolve().parent.parent
                    / "evaluation" / "query_types.json")
_NO_INFO_PROJECT = {"id": "9" * 32, "name": "质量门槛", "profiles": [
    _profile("q1", "甲", "数字电路与 AI 芯片 导师"),
    _profile("q2", "乙", "海洋工程结构"),
    _profile("q3", "丙", "中文问答与知识组织"),
]}


def _query_types() -> dict:
    import json
    return json.loads(QUERY_TYPES_PATH.read_text(encoding="utf-8"))["classes"]


class QueryQualityTests(unittest.TestCase):

    def setUp(self):
        search.clear_cache()

    def tearDown(self):
        search.clear_cache()

    def test_query_type_set_matches_the_classifier(self):
        classes = _query_types()
        self.assertGreaterEqual(len(classes), 6, "查询类型测试集至少要覆盖 6 类")
        for name, block in classes.items():
            for sample in block["samples"]:
                self.assertEqual(
                    search.query_quality(sample), block["expect"],
                    f"{name} 类样例「{sample}」判定不符：expect={block['expect']}")

    def test_no_information_query_returns_empty_in_every_mode(self):
        info = _query_types()["no_information"]["samples"]
        for sample in info:
            for mode in sorted(search.SEARCH_MODES):
                self.assertEqual(
                    search.search(_NO_INFO_PROJECT, sample, mode=mode), [],
                    f"「{sample}」在 {mode} 模式下不该出名单")

    def test_off_topic_queries_are_not_rejected_by_the_quality_gate(self):
        """无关查询有主题，归相关性空判管；两类拒绝原因不能混。"""
        for sample in _query_types()["off_topic"]["samples"]:
            self.assertEqual(search.query_quality(sample), "ok", sample)

    def test_acronyms_and_names_are_informative(self):
        for sample in ("MEMS", "FPGA", "EDA", "VLSI", "RISC-V", "6G", "TCAD",
                       "黄如", "刘雷波", "清华大学"):
            self.assertTrue(search.is_informative_query(sample), sample)
        for sample in ("MEMS", "FPGA", "EDA", "VLSI", "RISC-V"):
            self.assertTrue(search._looks_lexical(sample),
                            f"{sample} 应保留 BM25 分流优势")

    def test_cross_discipline_queries_stay_informative(self):
        for sample in ("AI 用于材料发现", "机器学习辅助芯片设计",
                       "深度学习用于医学影像诊断", "量子计算与密码学的交叉"):
            self.assertTrue(search.is_informative_query(sample), sample)

    def test_informative_query_still_returns_results(self):
        results = search.search(_NO_INFO_PROJECT, "海洋工程结构", mode="bm25")
        self.assertTrue(results)
        self.assertEqual(results[0]["profile"]["id"], "q2")

    def test_results_carry_query_quality_without_changing_existing_fields(self):
        results = search.search(_NO_INFO_PROJECT, "海洋工程", mode="bm25")
        self.assertTrue(results)
        row = results[0]
        self.assertEqual(row["query_quality"], "ok")
        for key in ("profile", "similarity", "mode", "requested_mode",
                    "fallback", "evidence_count"):
            self.assertIn(key, row, "已有字段不能变")

    def test_evaluation_queries_are_never_rejected(self):
        """226 条弱监督评测查询一条都不许被质量门槛拒掉（否则指标会掉）。"""
        from workbench import retrieval_eval
        entries = retrieval_eval.load_corpus()
        queries = (retrieval_eval.build_a_queries(entries, random.Random(retrieval_eval.SEED))
                   + retrieval_eval.build_b_queries(entries))
        rejected = [query for query in queries
                    if not search.is_informative_query(query["query"])]
        self.assertEqual(rejected, [], f"误拒了评测查询：{[q['query'] for q in rejected][:5]}")


class OfflineModelTests(unittest.TestCase):
    """离线可用性：本地没有模型且禁止下载时，必须**快速**回落，不能"假死"。

    实测背景：无模型环境下第一次语义检索会同步尝试联网下载，实测卡 71 s 才回落；
    这是离线部署的硬伤。改动后：缓存优先（local_files_only）→ 离线直接跳过下载 →
    失败判定只付一次代价。
    """

    def setUp(self):
        import os
        self.os = os
        search.clear_cache()
        self.model_patch = mock.patch.object(search, "_model", None)
        self.model_patch.start()

    def tearDown(self):
        search.clear_cache()
        self.model_patch.stop()

    def test_offline_without_cached_model_skips_download_and_degrades_fast(self):
        constructor = mock.Mock(side_effect=AssertionError("离线时不许尝试下载"))
        started = time.perf_counter()
        with mock.patch.dict(self.os.environ, {"IC_MENTOR_OFFLINE": "1"}), \
                mock.patch.object(search, "_model_cached", lambda _cache: False), \
                mock.patch.object(search, "_new_embedder", constructor):
            results = search.search(PROJECT, "我想做中文问答和知识组织", mode="semantic")
            bm25_results = search.search(PROJECT, "MEMS", mode="bm25")
            name_results = search.search(PROJECT, "VLSI 数字", mode="keyword")
        elapsed = time.perf_counter() - started
        constructor.assert_not_called()
        self.assertLess(elapsed, 2.0, f"离线回落耗时 {elapsed:.2f}s，太慢")
        self.assertTrue(results)
        self.assertEqual(results[0]["mode"], "bm25")
        self.assertIn("向量模型不可用", results[0]["fallback"])
        self.assertTrue(bm25_results, "BM25 检索在无模型时必须照常")
        self.assertTrue(name_results, "关键词检索在无模型时必须照常")

    def test_model_failure_is_remembered_and_not_retried(self):
        calls = {"count": 0}

        def broken(cache, local_only):
            calls["count"] += 1
            raise RuntimeError("模型文件损坏")

        with mock.patch.object(search, "_model_cached", lambda _cache: False), \
                mock.patch.object(search, "_new_embedder", broken):
            first = search.search(PROJECT, "中文问答", mode="semantic")
            second = search.search(PROJECT, "中文问答", mode="semantic")
        self.assertEqual(calls["count"], 1, "失败判定应只付一次代价，第二次不许再试")
        self.assertEqual(first[0]["mode"], "bm25")
        self.assertEqual(second[0]["mode"], "bm25")
        self.assertIn("向量模型不可用", second[0]["fallback"])

    def test_cached_model_is_initialised_without_network(self):
        recorded = {}

        class _Dummy:
            def embed(self, texts):
                for _ in texts:
                    yield np.asarray([0.25, 0.25, 0.25, 0.9], dtype=np.float32)

            def query_embed(self, texts):
                for _ in texts:
                    yield np.asarray([0.25, 0.25, 0.25, 0.9], dtype=np.float32)

        def build(cache, local_only):
            recorded["local_only"] = local_only
            return _Dummy()

        with mock.patch.object(search, "_model_cached", lambda _cache: True), \
                mock.patch.object(search, "_new_embedder", build):
            results = search.search(PROJECT, "中文问答", mode="semantic")
        self.assertTrue(recorded.get("local_only"),
                        "本地已有权重时必须 local_files_only=True，不做联网版本检查")
        self.assertEqual(results[0]["mode"], "semantic")


if __name__ == "__main__":
    unittest.main()