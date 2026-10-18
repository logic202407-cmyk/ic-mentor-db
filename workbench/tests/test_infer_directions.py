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


if __name__ == "__main__":
    unittest.main()
