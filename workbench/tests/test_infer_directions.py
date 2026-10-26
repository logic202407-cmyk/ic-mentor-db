"""方向推断模块的离线测试：只测不依赖模型下载的纯函数与词表逻辑。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from workbench import infer_directions
from workbench.infer_directions import (
    DEGENERATE,
    MIN_LABEL_COUNT,
    _as_text,
    build_vocab,
    label_of,
)


class FieldExtractionTests(unittest.TestCase):
    """``biography`` 实际是 ``{text,url}`` 结构，早前被当成字符串过。"""

    def test_dict_biography_yields_its_text(self):
        self.assertEqual(_as_text({"text": "2014- 北京大学 副教授",
                                   "url": "https://x"}), "2014- 北京大学 副教授")

    def test_list_of_dicts_is_flattened(self):
        value = [{"text": "甲"}, {"text": "乙"}]
        self.assertEqual(_as_text(value), "甲 乙")

    def test_empty_and_none_are_safe(self):
        for value in (None, "", [], {}):
            self.assertEqual(_as_text(value), "")

    def test_plain_string_passes_through(self):
        self.assertEqual(_as_text("研究方向：机器人"), "研究方向：机器人")


class LabelExtractionTests(unittest.TestCase):

    def test_prefers_direction_group(self):
        self.assertEqual(label_of({"direction_group": "机械设计",
                                   "interests": ["别的"]}), "机械设计")

    def test_falls_back_to_interests(self):
        self.assertEqual(label_of({"direction_group": "",
                                   "interests": ["机器人", "控制"]}), "机器人 控制")

    def test_missing_both_is_empty(self):
        self.assertEqual(label_of({}), "")


class VocabularyTests(unittest.TestCase):
    """词表必须剔除退化标签，否则模型只要全猜「不分研究方向」就能刷高准确率。"""

    def test_degenerate_labels_are_excluded(self):
        profiles = [{"direction_group": "不分研究方向"}] * 20
        profiles += [{"direction_group": "不区分研究方向"}] * 20
        vocab, counts = build_vocab(profiles)
        self.assertEqual(vocab, [])
        self.assertIn("不分研究方向", counts)      # 计数保留，只是不进词表
        for bad in ("不分研究方向", "不区分研究方向", "集成电路相关"):
            self.assertIn(bad, DEGENERATE)

    def test_rare_labels_are_excluded(self):
        profiles = [{"direction_group": "机器人与控制"}] * (MIN_LABEL_COUNT + 1)
        profiles += [{"direction_group": "只出现一次的方向"}]
        vocab, _ = build_vocab(profiles)
        self.assertIn("机器人与控制", vocab)
        self.assertNotIn("只出现一次的方向", vocab)

    def test_vocab_is_ordered_by_frequency(self):
        profiles = [{"direction_group": "常见"}] * 10 + [{"direction_group": "较少"}] * 6
        vocab, _ = build_vocab(profiles)
        self.assertEqual(vocab[:2], ["常见", "较少"])

    def test_pending_label_never_becomes_a_target(self):
        profiles = [{"direction_group": "方向待补"}] * 10
        vocab, _ = build_vocab(profiles)
        self.assertNotIn("方向待补", vocab)


class HybridDecisionTests(unittest.TestCase):
    """验证里用的分层阈值：字面命中优先，否则回落嵌入。行为要可预期。"""

    def test_keyword_score_is_one_when_label_appears_verbatim(self):
        from workbench.search import keyword_score
        text = "研究方向：电子器件与工艺；职称：教授"
        self.assertEqual(keyword_score("电子器件与工艺", text), 1.0)

    def test_keyword_score_is_low_when_absent(self):
        from workbench.search import keyword_score
        score = keyword_score("海洋工程结构", "研究方向：电子器件与工艺")
        self.assertLess(score, 0.5)

    def test_batch_scores_match_single_scores(self):
        """批量版只是把文本规范化提到循环外，打分必须逐项一致。"""
        from workbench.search import keyword_score, keyword_scores
        text = "研究方向：电子器件与工艺；职称：教授；论文 新型器件"
        labels = ["电子器件与工艺", "海洋工程", "器件", "", "电子器件"]
        got = keyword_scores(labels, text)
        for label in labels:
            self.assertAlmostEqual(got[label], keyword_score(label, text), places=12)


class TextLeakageTests(unittest.TestCase):
    """``discipline`` 字段装的是方向值，拼进推断文本就是把答案喂给模型。"""

    def _text_for(self, profile: dict, dossier: dict) -> str:
        from workbench import infer_directions as module
        original = module.research.load
        module.research.load = lambda _pid: dossier
        try:
            return module.profile_text(profile)
        finally:
            module.research.load = original

    def test_uses_first_level_discipline_not_direction_field(self):
        text = self._text_for(
            {"id": "x", "discipline": "电子器件与工艺",
             "first_level_discipline": "0809 电子科学与技术",
             "department": "集成电路学院", "summary": ""},
            {"biography": [], "papers": []})
        self.assertIn("0809 电子科学与技术", text)
        self.assertNotIn("电子器件与工艺", text)

    def test_pipeline_annotation_is_stripped(self):
        text = self._text_for(
            {"id": "x", "discipline": "射频与通信",
             "first_level_discipline": "0809 电子科学与技术", "department": "微电子学院"},
            {"biography": [{"text": "研究方向：射频电路。"},
                           {"text": "学科归属按公开研究关键词归入「0809」，用于工学导航"}],
             "papers": []})
        self.assertIn("射频电路", text)
        self.assertNotIn("用于工学导航", text)


class CalibrationTests(unittest.TestCase):
    """阈值校准与 unknown 拒绝：分数是相似度，不是概率。"""

    def test_confidence_band_thresholds(self):
        from workbench.infer_directions import confidence_band
        self.assertEqual(confidence_band(0.80), "high")
        self.assertEqual(confidence_band(0.66), "medium")
        self.assertEqual(confidence_band(0.60), "low")
        self.assertEqual(confidence_band(0.59), "unknown")
        self.assertEqual(confidence_band(None), "unknown")

    def test_calibration_curve_counts(self):
        from workbench.infer_directions import calibration_curve
        records = [
            {"score": 0.7, "pred": "a", "truth": "a"},
            {"score": 0.65, "pred": "b", "truth": "a"},
            {"score": 0.5, "pred": "a", "truth": "a"},
        ]
        curve = calibration_curve(records, "emb", thresholds=(0.6, 0.8))
        high = next(r for r in curve if r["score>="] == 0.6)
        self.assertEqual(high["accepted"], 2)
        self.assertAlmostEqual(high["precision"], 0.5)
        self.assertAlmostEqual(high["coverage"], 2 / 3)
        none = next(r for r in curve if r["score>="] == 0.8)
        self.assertEqual(none["accepted"], 0)
        self.assertIsNone(none["precision"])

    def test_recommend_threshold_respects_minimum_coverage(self):
        from workbench.infer_directions import recommend_threshold
        curve = [
            {"score>=": 0.5, "accepted": 90, "coverage": 0.9, "precision": 0.1},
            {"score>=": 0.6, "accepted": 20, "coverage": 0.2, "precision": 0.4},
            {"score>=": 0.7, "accepted": 1, "coverage": 0.01, "precision": 1.0},
        ]
        chosen = recommend_threshold(curve, target_precision=0.3, min_coverage=0.1)
        self.assertEqual(chosen["score>="], 0.6)


class InferenceConsistencyTests(unittest.TestCase):
    """学科约束会改变最终选择，``embedding_score`` 必须跟着换到同一个标签。

    历史缺陷：``embedding_score`` 取的是**全词表** ``argmax(sims)``，而 ``suggested``
    取的是学科约束后的 ``argmax(fused)``。两者不是同一个标签时，报出来的嵌入分属于
    另一个方向——「建议的方向，分数却不是它的」。
    """

    DISCIPLINE = "0809 电子科学与技术"
    IN_DISCIPLINE = ("甲方向", "乙方向", "丙方向", "丁方向", "戊方向", "己方向")
    OUTSIDE = "庚方向"
    # 待补文本的假向量：与「庚方向」几乎同向（0.954），与「甲方向」只有 0.301。
    TEXT_VECTOR = (0.30, 0.0, 0.0, 0.0, 0.0, 0.0, 0.95)

    def setUp(self):
        self.vocab = list(self.IN_DISCIPLINE) + [self.OUTSIDE]
        profiles = [{
            "id": f"label-{index}", "name": f"有向{index}", "institution": "示例大学",
            "direction_group": label, "first_level_discipline": self.DISCIPLINE,
            "department": "示例学院", "summary": "",
        } for index, label in enumerate(self.IN_DISCIPLINE)]
        profiles.append({
            "id": "pending-target", "name": "待补", "institution": "示例大学",
            "direction_group": "方向待补", "first_level_discipline": self.DISCIPLINE,
            "department": "示例学院", "summary": "研究方向：硅基器件",
        })
        self.profiles = profiles

    def _fake_embed(self, texts, batch_note=""):
        """标签各占一个正交方向，待补文本同向于约束外的「庚方向」。"""
        rows = []
        for text in texts:
            if text in self.vocab:
                row = np.zeros(len(self.vocab), dtype=np.float32)
                row[self.vocab.index(text)] = 1.0
            else:
                row = np.asarray(self.TEXT_VECTOR, dtype=np.float32)
            rows.append(row)
        matrix = np.asarray(rows, dtype=np.float32)
        return matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)

    def test_embedding_score_belongs_to_the_suggested_label(self):
        with mock.patch.object(infer_directions, "embed_texts", self._fake_embed):
            result = infer_directions.infer(self.profiles, self.vocab, min_score=0.0)
        self.assertEqual(len(result["suggestions"]), 1)
        suggestion = result["suggestions"][0]

        # 学科约束把候选裁到「甲…己方向」，所以建议里不应出现约束外的「庚方向」；
        # 而全词表 argmax(sims) 恰恰是「庚方向」——这就是旧实现会报错分的地方。
        self.assertEqual(suggestion["suggested"], "甲方向")
        text_vector = np.asarray(self.TEXT_VECTOR, dtype=np.float32)
        text_vector /= np.linalg.norm(text_vector)
        chosen_cosine = float(text_vector[self.vocab.index(suggestion["suggested"])])
        global_cosine = float(text_vector[self.vocab.index(self.OUTSIDE)])
        self.assertAlmostEqual(suggestion["embedding_score"], chosen_cosine, places=3,
                               msg="embedding_score 必须是被建议标签的余弦")
        self.assertGreater(global_cosine - chosen_cosine, 0.5,
                           "构造用例失效：全局 argmax 与被建议标签的余弦必须明显不同")
        self.assertLess(suggestion["embedding_score"], global_cosine,
                        "报出的嵌入分不能是约束外标签的余弦")

    def test_keyword_score_belongs_to_the_suggested_label(self):
        from workbench.search import keyword_score
        with mock.patch.object(infer_directions, "embed_texts", self._fake_embed):
            result = infer_directions.infer(self.profiles, self.vocab, min_score=0.0)
        suggestion = result["suggestions"][0]
        text = infer_directions.profile_text(self.profiles[-1])
        self.assertAlmostEqual(
            suggestion["keyword_score"],
            round(keyword_score(suggestion["suggested"], text), 4), places=3)


class SmallSampleTests(unittest.TestCase):
    """样本不足 2 条时 dev/test 会切成空集：要给提示，不能 ZeroDivisionError。"""

    def setUp(self):
        self.vocab = ["甲方向", "乙方向"]
        self.profiles = [
            {"id": "only-one", "name": "唯一", "institution": "示例大学",
             "direction_group": "甲方向", "first_level_discipline": "0809 电子科学与技术",
             "department": "示例学院", "summary": ""},
        ]

    def test_validate_reports_instead_of_dividing_by_zero(self):
        def fake_embed(texts, batch_note=""):
            matrix = np.eye(len(self.vocab), dtype=np.float32)[
                np.arange(len(texts)) % len(self.vocab)]
            return matrix

        with mock.patch.object(infer_directions, "embed_texts", fake_embed):
            result = infer_directions.validate(self.profiles, self.vocab, 1)
        self.assertEqual(result["sampled"], 1)
        tuning = result["fusion_tuning"]
        self.assertTrue(tuning.get("insufficient_sample"))
        self.assertIn("无法划分", tuning["note"])
        self.assertEqual(tuning["test"]["keyword"]["n"], 0)
        self.assertIsNone(tuning["test"]["keyword"]["top1"],
                          "空 test 集不能报 0%（那会被读成模型全错）")


class ThresholdNoteTests(unittest.TestCase):
    """报告里「默认阈值」必须是配置值：曾经硬编码 0.55，而实际默认已是 0.60。"""

    def test_note_prints_the_configured_threshold(self):
        row = {"score>=": 0.55, "accepted": 12, "coverage": 0.19, "precision": 0.35}
        note = infer_directions.threshold_note(0.55, row)
        self.assertIn("0.55", note)
        self.assertIn("12", note)
        self.assertIn("19.0%", note)

    def test_note_does_not_inherit_a_stale_default(self):
        note = infer_directions.threshold_note(0.60, None)
        self.assertIn("0.60", note)
        self.assertIn("不在本次校准网格上", note)

    def test_source_has_no_hardcoded_default_threshold_in_report_text(self):
        source = Path(infer_directions.__file__).read_text(encoding="utf-8")
        for literal in ("默认阈值 **0.55**", "**关于阈值**：0.60"):
            self.assertNotIn(literal, source,
                             f"报告文案里又出现写死的阈值：{literal}")


if __name__ == "__main__":
    unittest.main()
