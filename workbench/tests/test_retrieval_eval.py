"""检索评测体系（`workbench/retrieval_eval.py` 与 `search.py` 新增组件）的测试。

覆盖点与「为什么需要」：

- **配额等价性**：评测里用 ``keyword_scores_fast`` 替代逐条 ``keyword_score``。
  若两者不等价，legacy 基线的所有数字都不成立，所以这里逐条核对。
- **BM25 基本性质**：词频单调、IDF 方向、中文 bigram 切分。BM25 是自己实现的，
  没有第三方库兜底，性质必须自己钉住。
- **融合的空集行为**：所有路都没有信号时，融合必须仍然“没有信号”，不能因为
  归一化把零分抬成正分——否则界面会重新开始硬塞结果。
- **阈值过滤**：低于阈值返回空、边际过平返回空、只裁尾巴三种情形的判定。
- **划分固定**：种子 42 的分层划分必须可复现且 dev/test 不相交，否则“只在 dev
  上调参”这句话就是空的。
- **指标手算**：Recall / MRR / NDCG 在构造样例上对比手算值。
"""

from __future__ import annotations

import json
import math
import random
import unittest
from pathlib import Path

import numpy as np

from workbench import retrieval_eval, search

ROOT = Path(__file__).resolve().parent.parent.parent
TERMS_PATH = ROOT / "workbench" / "reference" / "eval" / "terminology_map.json"

DOCS = [
    "学科：电子器件与工艺；研究方向：微波、毫米波集成电路；简介：；院系：电子科学与工程学院",
    "学科：光电子与硅光；研究方向：硅光、光电子集成、集成光子；简介：；院系：信息学院",
    "学科：海洋工程；研究方向：船舶与海洋工程结构、水声；简介：；院系：船舶海洋与建筑工程学院",
    "学科：机械工程；研究方向：机械制造、数控装备；简介：；院系：机械工程学院",
]

QUERIES = [
    "硅光", "微波毫米波", "海洋工程", "机械制造", "VLSI", "MEMS", "  ", "",
    "电子科学与技术", "a", "结构", "不存在的词条xyz",
]


class KeywordEquivalenceTests(unittest.TestCase):
    """``keyword_scores_fast`` 必须与 ``keyword_score`` 逐条等价。"""

    def test_matches_keyword_score_on_fixture(self):
        flat = retrieval_eval.normalized_texts(DOCS)
        for query in QUERIES:
            fast = retrieval_eval.keyword_scores_fast(query, flat)
            slow = [search.keyword_score(query, doc) for doc in DOCS]
            for index, (a, b) in enumerate(zip(fast, slow)):
                self.assertAlmostEqual(
                    float(a), b, places=7,
                    msg=f"查询 {query!r} 第 {index} 条不一致：{a} vs {b}")

    def test_keeps_legacy_verbatim_rule(self):
        """legacy 基线的核心语义还在：查询整串出现在文本里就是 1.0。"""
        flat = retrieval_eval.normalized_texts(DOCS)
        scores = retrieval_eval.keyword_scores_fast("硅光", flat)
        self.assertEqual(float(scores[1]), 1.0)
        self.assertEqual(search.keyword_score("硅光", DOCS[1]), 1.0)


class TokenizeTests(unittest.TestCase):
    def test_chinese_bigrams_and_latin_words(self):
        tokens = search.tokenize("微波毫米波 VLSI-2024 SoC")
        self.assertIn("微波", tokens)
        self.assertIn("毫米", tokens)
        self.assertIn("vlsi-2024", tokens)
        self.assertIn("soc", tokens)

    def test_single_cjk_character_kept(self):
        self.assertEqual(search.tokenize("硅"), ["硅"])

    def test_empty_input(self):
        self.assertEqual(search.tokenize(""), [])
        self.assertEqual(search.tokenize("   "), [])


class Bm25Tests(unittest.TestCase):
    def test_term_frequency_is_monotonic(self):
        """**等长文档**下，同一词项出现次数越多，得分越高。

        必须固定文档长度：BM25 的 b 会惩罚长文档，长度一变就混进了第二个变量，
        那时分数不单调是实现的正常行为，不是 bug。
        """
        index = search.BM25Index([
            "器件 填充 填充 填充",       # 不含查询词，长度 4
            "硅光 器件 填充 填充",       # 出现 1 次，长度 4
            "硅光 硅光 器件 填充",       # 出现 2 次，长度 4
            "硅光 硅光 硅光 器件",       # 出现 3 次，长度 4
        ])
        scores = [float(value) for value in index.scores("硅光")]
        self.assertEqual(scores[0], 0.0)
        self.assertLess(scores[1], scores[2])
        self.assertLess(scores[2], scores[3])

    def test_rare_term_scores_higher_than_common_term(self):
        """IDF 方向：语料里越少见的词项权重越大。"""
        index = search.BM25Index([
            "常见 常见 常见 罕见",
            "常见 常见 常见",
            "常见 常见 常见",
        ])
        rare = float(index.scores("罕见")[0])
        common = float(index.scores("常见")[0])
        self.assertGreater(rare, common)

    def test_longer_document_is_penalised(self):
        """b>0 时，同样命中一次，长文档得分更低。"""
        index = search.BM25Index([
            "硅光 器件",
            "硅光 器件 还有 很多 其他 的 研究方向 描述 文本 内容 填充 填充 填充",
        ])
        short, long = (float(value) for value in index.scores("硅光"))
        self.assertGreater(short, long)

    def test_empty_query_returns_zero_scores(self):
        index = search.BM25Index(["硅光 器件", "海洋 工程"])
        scores = index.scores("")
        self.assertEqual(float(np.abs(scores).sum()), 0.0)

    def test_statistics_are_self_describing(self):
        index = search.BM25Index(["硅光 器件", "海洋 工程"])
        stats = index.statistics()
        self.assertEqual(stats["documents"], 2)
        self.assertEqual(stats["k1"], 1.5)
        self.assertEqual(stats["b"], 0.75)
        self.assertGreater(stats["vocabulary"], 0)
        self.assertGreater(stats["array_bytes"], 0)


class FusionTests(unittest.TestCase):
    def test_all_zero_scores_stay_zero(self):
        """融合不能把“没有任何信号”变成“有信号”。"""
        fused = search.weighted_fuse([np.zeros(5, dtype=np.float32)] * 2, [0.5, 0.5])
        self.assertEqual(float(np.abs(fused).sum()), 0.0)
        returned, _ = retrieval_eval.returned_list(fused)
        self.assertEqual(returned, [])

    def test_rrf_on_all_zero_scores_is_uniform_not_signal(self):
        """RRF 只看名次，全零时名次仍然有序——所以它**不能**单独承担空集判定。

        这条断言把这件事写下来：结果必须是“全库等分”，因此界面层必须靠阈值
        空判，而不是靠融合分数是否大于 0。
        """
        fused = search.rrf_fuse([np.zeros(4, dtype=np.float32),
                                 np.zeros(4, dtype=np.float32)], k=60)
        self.assertEqual(len(set(np.round(fused.astype(float), 12))), 4)
        self.assertTrue(all(value > 0 for value in fused))

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            search.weighted_fuse([np.zeros(3), np.zeros(4)], [0.5, 0.5])
        with self.assertRaises(ValueError):
            search.rrf_fuse([np.zeros(3), np.zeros(4)])

    def test_empty_input_returns_empty(self):
        self.assertEqual(search.weighted_fuse([], []).size, 0)
        self.assertEqual(search.rrf_fuse([], []).size, 0)

    def test_normalize_is_scale_invariant_and_safe(self):
        values = np.asarray([0.0, 2.0, 4.0], dtype=np.float32)
        normalized = search.normalize_scores(values)
        self.assertEqual([round(float(v), 6) for v in normalized], [0.0, 0.5, 1.0])
        constant = search.normalize_scores(np.asarray([3.0, 3.0], dtype=np.float32))
        self.assertEqual([float(v) for v in constant], [0.0, 0.0])

    def test_weight_changes_ranking_direction(self):
        sparse = np.asarray([0.0, 1.0, 0.9], dtype=np.float32)
        dense = np.asarray([1.0, 0.0, 0.1], dtype=np.float32)
        sparse_heavy = search.weighted_fuse([sparse, dense], [1.0, 0.0])
        dense_heavy = search.weighted_fuse([sparse, dense], [0.0, 1.0])
        self.assertEqual(int(np.argmax(sparse_heavy)), 1)
        self.assertEqual(int(np.argmax(dense_heavy)), 0)

    def test_rrf_rewards_agreement(self):
        """两路都排第一的文档，必须胜过只在一路排第一的文档。"""
        left = np.asarray([9.0, 5.0, 0.0], dtype=np.float32)    # 名次 0 > 1 > 2
        right = np.asarray([9.0, 0.0, 5.0], dtype=np.float32)   # 名次 0 > 2 > 1
        fused = search.rrf_fuse([left, right], k=60)
        self.assertEqual(int(np.argmax(fused)), 0)


class FilterTests(unittest.TestCase):
    def test_below_threshold_yields_empty(self):
        keep, reason = search.relevance_decision([0.30, 0.29, 0.28], tau=0.52)
        self.assertEqual(reason, "below_threshold")
        self.assertFalse(any(keep))
        self.assertEqual(search.filter_low_relevance([0.30, 0.29], tau=0.52)[0], [])

    def test_above_threshold_keeps_only_tail_trimmed(self):
        kept, reason = search.filter_low_relevance([0.61, 0.55, 0.41, 0.30], tau=0.40)
        self.assertEqual(reason, "kept")
        self.assertEqual(kept, [0.61, 0.55, 0.41])

    def test_flat_margin_yields_empty(self):
        keep, reason = search.relevance_decision([0.60, 0.59, 0.58], tau=0.40, delta=0.10)
        self.assertEqual(reason, "flat_margin")
        self.assertFalse(any(keep))

    def test_sharp_margin_is_kept(self):
        keep, reason = search.relevance_decision([0.70, 0.55, 0.40], tau=0.30, delta=0.10)
        self.assertEqual(reason, "kept")
        self.assertTrue(all(keep))

    def test_short_list_skips_margin_check(self):
        """不足 3 条时无法算 top1−top3，不应因此判低置信。"""
        keep, reason = search.relevance_decision([0.61, 0.55], tau=0.40, delta=0.10)
        self.assertEqual(reason, "kept")
        self.assertTrue(all(keep))

    def test_empty_input(self):
        self.assertEqual(search.relevance_decision([], tau=0.4), ([], "empty"))
        self.assertEqual(search.filter_low_relevance([], tau=0.4)[0], [])

    def test_zero_tau_zero_delta_keeps_everything(self):
        kept, reason = search.filter_low_relevance([0.2, 0.1, 0.0], tau=0.0, delta=0.0)
        self.assertEqual(reason, "kept")
        self.assertEqual(kept, [0.2, 0.1, 0.0])


class MetricTests(unittest.TestCase):
    """指标函数在构造样例上对比手算值。"""

    def test_recall_mrr_ndcg_by_hand(self):
        # 相关集 3 条；返回列表里相关项落在第 1、3、10 位
        returned = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        relevant = {0, 2, 9}
        metrics = retrieval_eval.query_metrics(returned, relevant)
        self.assertAlmostEqual(metrics["recall@5"], 2 / 3, places=9)
        self.assertAlmostEqual(metrics["recall@10"], 1.0, places=9)
        self.assertAlmostEqual(metrics["recall@20"], 1.0, places=9)
        self.assertAlmostEqual(metrics["mrr@10"], 1.0, places=9)
        self.assertAlmostEqual(metrics["top1"], 1.0, places=9)
        # DCG@10 = 1/log2(2) + 1/log2(4) + 1/log2(11)
        # IDCG@10 = 1/log2(2) + 1/log2(3) + 1/log2(4)
        expected = ((1 / math.log2(2)) + (1 / math.log2(4)) + (1 / math.log2(11))) / (
            (1 / math.log2(2)) + (1 / math.log2(3)) + (1 / math.log2(4)))
        self.assertAlmostEqual(metrics["ndcg@10"], expected, places=9)

    def test_mrr_counts_from_first_relevant(self):
        metrics = retrieval_eval.query_metrics([1, 2, 0, 3], {0})
        self.assertAlmostEqual(metrics["mrr@10"], 1 / 3, places=9)
        self.assertEqual(metrics["top1"], 0.0)
        self.assertAlmostEqual(metrics["recall@5"], 1.0, places=9)

    def test_mrr_ignores_hits_beyond_ten(self):
        returned = list(range(12))   # 相关项只在第 11 位
        metrics = retrieval_eval.query_metrics(returned, {10})
        self.assertEqual(metrics["mrr@10"], 0.0)
        self.assertEqual(metrics["top1"], 0.0)

    def test_perfect_ranking_gets_one(self):
        metrics = retrieval_eval.query_metrics(list(range(10)), set(range(25)))
        self.assertAlmostEqual(metrics["ndcg@10"], 1.0, places=9)
        self.assertAlmostEqual(metrics["recall@10"], 10 / 25, places=9)

    def test_empty_return_is_penalised_not_crashed(self):
        metrics = retrieval_eval.query_metrics([], {0, 1})
        self.assertEqual(metrics["empty"], 1.0)
        self.assertEqual(metrics["top1"], 0.0)
        self.assertEqual(metrics["recall@5"], 0.0)
        self.assertEqual(metrics["mrr@10"], 0.0)
        self.assertEqual(metrics["ndcg@10"], 0.0)

    def test_aggregate_is_mean(self):
        rows = [{"metrics": retrieval_eval.query_metrics([0], {0})},
                {"metrics": retrieval_eval.query_metrics([1], {0})}]
        summary = retrieval_eval.aggregate(rows)
        self.assertAlmostEqual(summary["top1"], 0.5, places=9)
        self.assertEqual(summary["queries"], 2)

    def test_latency_percentiles(self):
        summary = retrieval_eval.latency_summary([0.001, 0.002, 0.003, 0.004])
        self.assertEqual(summary["n"], 4)
        self.assertAlmostEqual(summary["median_ms"], 2.5, places=6)
        self.assertAlmostEqual(summary["p95_ms"], 3.85, places=6)


def _fake_queries() -> list[dict]:
    queries = []
    for subclass, count in (("a_discipline", 10), ("a_direction", 10),
                            ("a_interest", 10), ("b_natural", 10)):
        for index in range(count):
            queries.append({"id": f"{subclass}-{index:02d}", "class": subclass[0].upper(),
                            "subclass": subclass, "query": f"q{index}",
                            "label": f"q{index}", "relevant": set()})
    return queries


class SplitTests(unittest.TestCase):
    def test_split_is_deterministic(self):
        first = retrieval_eval.assign_splits(_fake_queries())
        second = retrieval_eval.assign_splits(_fake_queries())
        self.assertEqual(first["dev"], second["dev"])
        self.assertEqual(first["test"], second["test"])
        self.assertEqual(first["seed"], 42)

    def test_split_is_disjoint_and_covers_everything(self):
        queries = _fake_queries()
        splits = retrieval_eval.assign_splits(queries)
        self.assertEqual(set(splits["dev"]) & set(splits["test"]), set())
        self.assertEqual(set(splits["dev"]) | set(splits["test"]),
                         {query["id"] for query in queries})
        self.assertEqual(len(splits["dev"]) + len(splits["test"]), len(queries))

    def test_every_stratum_appears_in_both_splits(self):
        queries = _fake_queries()
        splits = retrieval_eval.assign_splits(queries)
        by_id = {query["id"]: query for query in queries}
        for split in ("dev", "test"):
            subclasses = {by_id[identifier]["subclass"] for identifier in splits[split]}
            self.assertEqual(subclasses,
                             {"a_discipline", "a_direction", "a_interest", "b_natural"})

    def test_roughly_thirty_percent_is_dev(self):
        splits = retrieval_eval.assign_splits(_fake_queries())
        self.assertAlmostEqual(len(splits["dev"]) / 40, 0.30, delta=0.05)


class TerminologyMapTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(TERMS_PATH.read_text(encoding="utf-8"))

    def test_file_exists_and_is_json(self):
        self.assertIn("entries", self.data)
        self.assertEqual(self.data["kind"], "weak_supervision_qrels")

    def test_every_entry_declares_query_terms_rationale(self):
        identifiers = set()
        for entry in self.data["entries"]:
            self.assertTrue(entry["id"].startswith("b"))
            self.assertNotIn(entry["id"], identifiers, "术语表 id 不能重复")
            identifiers.add(entry["id"])
            self.assertGreaterEqual(len(entry["query"].strip()), 6)
            self.assertGreaterEqual(len(entry["terms"]), 1)
            self.assertGreaterEqual(len(entry["rationale"].strip()), 10)
            for group in entry.get("require") or []:
                self.assertGreaterEqual(len(group), 1)

    def test_entry_count_is_in_the_agreed_range(self):
        self.assertGreaterEqual(len(self.data["entries"]), 30)
        self.assertLessEqual(len(self.data["entries"]), 60)

    def test_it_says_it_is_not_manual_annotation(self):
        text = json.dumps(self.data, ensure_ascii=False)
        self.assertIn("不是外部人工标注", text)


_FIXTURE: dict | None = None


def _fixture() -> dict:
    """全量调用一次查询构造（静态目录 + 标签统计），后续用例共享。"""
    global _FIXTURE
    if _FIXTURE is None:
        entries = retrieval_eval.load_corpus()
        a_queries = retrieval_eval.build_a_queries(entries, random.Random(retrieval_eval.SEED))
        b_queries = retrieval_eval.build_b_queries(entries)
        _FIXTURE = {"entries": entries, "a": a_queries, "b": b_queries,
                    "all": a_queries + b_queries}
    return _FIXTURE


class QuerySetTests(unittest.TestCase):
    def test_a_class_size_in_agreed_range(self):
        self.assertGreaterEqual(len(_fixture()["a"]), 150)
        self.assertLessEqual(len(_fixture()["a"]), 300)

    def test_b_class_size_in_agreed_range(self):
        self.assertGreaterEqual(len(_fixture()["b"]), 30)
        self.assertLessEqual(len(_fixture()["b"]), 60)

    def test_every_query_has_identifiers_and_labels(self):
        identifiers = set()
        for query in _fixture()["all"]:
            self.assertTrue(query["id"])
            self.assertNotIn(query["id"], identifiers, "查询 id 必须唯一")
            identifiers.add(query["id"])
            self.assertTrue(query["query"].strip())
            self.assertTrue(query["label"].strip())
            self.assertIn(query["class"], {"A", "B"})

    def test_every_query_is_answerable(self):
        """每条查询在语料里都必须有相关记录，否则它只是噪声。"""
        for query in _fixture()["all"]:
            self.assertGreaterEqual(len(query["relevant"]), 3,
                                    f"{query['id']} 相关集过小：{query['query']}")

    def test_a1_relevance_is_exact_label_match(self):
        """A1 的相关集必须**等于**「带代码的完整学科标签」精确匹配的结果。

        不能写成“某两个学科不会混淆”：一位导师可能同时被列在「0703 化学」和
        「0817 化学工程与技术」下，两条标签**在记录层面天然重叠**，把断言写成
        集合互斥只会测到数据分布，测不到匹配规则。这里改为核对映射本身。
        """
        entries = _fixture()["entries"]
        labels = [retrieval_eval.discipline_names(profile) for profile in entries]
        queries = [query for query in _fixture()["a"]
                   if query["subclass"] == "a_discipline"]
        self.assertTrue(queries, "A1 查询为空，无法核对")
        for query in queries:
            expected = {index for index, names in enumerate(labels)
                        if query["label"] in names}
            self.assertEqual(
                query["relevant"], expected,
                f"查询「{query['query']}」的相关集与标签「{query['label']}」的精确匹配结果不一致")

    def test_a1_query_text_is_the_label_without_code(self):
        """查询文本是去掉四位代码的学科名，标签仍保留代码（用于精确匹配）。"""
        import re as _re
        for query in _fixture()["a"]:
            if query["subclass"] != "a_discipline":
                continue
            self.assertRegex(query["label"], r"^\d{4}\s")
            self.assertEqual(query["query"], _re.sub(r"^\d{4}\s*", "", query["label"]))

    def test_b_terms_that_exist_in_corpus_enter_the_qrels(self):
        """术语表里每个在语料中真实出现的标签，都必须真的带进相关集。

        带 ``require`` 的条目除外：那些标签会被组间交集过滤掉，是设计使然。
        """
        data = json.loads(TERMS_PATH.read_text(encoding="utf-8"))
        entries = _fixture()["entries"]
        blobs = [retrieval_eval.label_blob(profile) for profile in entries]
        queries = {query["id"]: query for query in _fixture()["b"]}
        for entry in data["entries"]:
            if entry.get("require"):
                continue
            query = queries[entry["id"]]
            for term in entry["terms"]:
                holders = {index for index, blob in enumerate(blobs) if term in blob}
                if not holders:
                    continue          # 该标签在语料中不存在，属已记录的边界
                self.assertTrue(
                    holders & query["relevant"],
                    f"{entry['id']} 的标签「{term}」在语料中有 {len(holders)} 条记录，"
                    "却没有进入相关集")

    def test_a_class_split_is_saved_and_reproducible(self):
        splits = retrieval_eval.assign_splits(_fixture()["all"])
        self.assertEqual(splits, retrieval_eval.assign_splits(_fixture()["all"]))
        dev = set(splits["dev"])
        test = set(splits["test"])
        self.assertEqual(dev & test, set())


class OffTopicBehaviourTests(unittest.TestCase):
    """无关查询必须返回空结果或明确低置信，而不是硬塞 10 条。"""

    def test_decision_layer_empties_a_flat_low_score_list(self):
        """语义检索对无关查询的典型形态：一串 0.2–0.4 的平坦余弦。"""
        realistic = [0.3627, 0.3581, 0.3512, 0.3490, 0.3411,
                     0.3398, 0.3315, 0.3290, 0.3241, 0.3187]
        kept, reason = search.filter_low_relevance(realistic, tau=0.40, delta=0.02)
        self.assertEqual(kept, [])
        self.assertEqual(reason, "below_threshold")

    def test_real_model_off_topic_query_returns_empty(self):
        """真跑一次：用缓存语料向量 + 模型给「红烧肉的做法」算最高相似度。"""
        cache = retrieval_eval.EVAL_DIR / "corpus_vectors.npy"
        if not cache.exists():
            self.skipTest("需要先运行 python -m workbench.retrieval_eval 生成语料向量")
        vectors = np.load(cache)
        top1 = float((vectors @ retrieval_eval.embed_query("红烧肉的做法")).max())
        kept, reason = search.filter_low_relevance(
            [top1], tau=search.SEMANTIC_EMPTY_TAU)
        self.assertLess(top1, search.SEMANTIC_EMPTY_TAU,
                        "无关查询的最高分不该达到低置信阈值")
        self.assertEqual(kept, [])
        self.assertEqual(reason, "below_threshold")


class ReportArtifactTests(unittest.TestCase):
    """提交用的精简结果：结构完整、且不含逐查询大数组。"""

    def setUp(self):
        path = ROOT / "workbench" / "reference" / "eval" / "retrieval.json"
        if not path.exists():
            self.skipTest("尚未生成 workbench/reference/eval/retrieval.json")
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def test_required_sections(self):
        for key in ("config", "splits", "corpus", "metrics", "latency",
                    "filter_eval", "off_topic", "probes", "honesty"):
            self.assertIn(key, self.data)

    def test_five_methods_present(self):
        for method in ("keyword_substring", "bm25", "embedding",
                       "hybrid_score", "hybrid_rrf"):
            self.assertIn(method, self.data["metrics"])
            self.assertIn("A/test", self.data["metrics"][method])
            self.assertIn("B/test", self.data["metrics"][method])

    def test_slim_file_has_no_per_query_arrays(self):
        self.assertNotIn("per_query", self.data)
        self.assertNotIn("failures", self.data)

    def test_split_ids_are_saved(self):
        self.assertEqual(self.data["splits"]["seed"], 42)
        self.assertTrue(self.data["splits"]["dev"])
        self.assertTrue(self.data["splits"]["test"])


if __name__ == "__main__":
    unittest.main()