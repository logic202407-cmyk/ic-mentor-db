"""方向推断模块的离线测试：只测不依赖模型下载的纯函数与词表逻辑。"""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
