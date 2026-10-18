"""同名消歧模块的离线测试：真值构造、URL 归一化与指标计算。"""

from __future__ import annotations

import unittest

from workbench.disambiguate_names import auc, build_pairs, canonical_home, prf


class CanonicalHomeTests(unittest.TestCase):
    """主页 URL 归一化：判等必须忽略协议、www、锚点、查询串与末尾斜杠。"""

    def test_protocol_and_www_are_stripped(self):
        self.assertEqual(canonical_home("https://www.faculty.x.edu.cn/a/zh_CN/index.htm"),
                         canonical_home("http://faculty.x.edu.cn/a/zh_CN/index.htm"))

    def test_trailing_slash_and_anchor_are_ignored(self):
        self.assertEqual(canonical_home("https://a.b/c/#x"), "a.b/c")
        self.assertEqual(canonical_home("https://a.b/c"), "a.b/c")

    def test_query_string_is_ignored(self):
        self.assertEqual(canonical_home("https://a.b/c?id=1"), canonical_home("https://a.b/c?id=2"))

    def test_empty_is_empty(self):
        for value in ("", None, "   "):
            self.assertEqual(canonical_home(value or ""), "")


class BuildPairsTests(unittest.TestCase):
    """真值只来自 homepage；缺主页的组必须跳过，不能猜。"""

    @staticmethod
    def _p(id_, name, inst, home):
        return {"id": id_, "name": name, "institution": inst, "homepage": home,
                "department": "", "discipline": "", "summary": ""}

    def test_same_url_is_a_positive_pair(self):
        group = [self._p("1", "张三", "A 大学", "http://x.edu.cn/zhangsan.htm"),
                 self._p("2", "张三", "A 大学", "https://www.x.edu.cn/zhangsan.htm")]
        labelled, stats = build_pairs(group)
        self.assertEqual(len(labelled), 1)
        self.assertTrue(labelled[0]["same"])
        self.assertEqual(stats["positives"], 1)

    def test_different_url_is_a_negative_pair(self):
        group = [self._p("1", "张彤", "A 大学", "http://x.edu.cn/zhangtong1.htm"),
                 self._p("2", "张彤", "A 大学", "http://x.edu.cn/zhangtong2.htm")]
        labelled, stats = build_pairs(group)
        self.assertFalse(labelled[0]["same"])
        self.assertEqual(stats["negatives"], 1)

    def test_group_with_a_missing_url_is_skipped_entirely(self):
        group = [self._p("1", "杨军", "A 大学", "http://x.edu.cn/yangjun.htm"),
                 self._p("2", "杨军", "B 大学", "")]
        labelled, stats = build_pairs(group)
        self.assertEqual(labelled, [])
        self.assertEqual(stats["skipped_missing_home"], 1)

    def test_single_record_name_yields_no_pairs(self):
        labelled, _ = build_pairs([self._p("1", "李四", "A 大学", "http://x.edu.cn/l.htm")])
        self.assertEqual(labelled, [])

    def test_three_records_yield_three_pairs(self):
        group = [self._p(str(i), "王伟", "A 大学", f"http://x.edu.cn/w{i}.htm") for i in range(3)]
        labelled, _ = build_pairs(group)
        self.assertEqual(len(labelled), 3)


class MetricTests(unittest.TestCase):

    def test_auc_perfect_separation_is_one(self):
        rows = [{"same": True, "s": 0.9}, {"same": True, "s": 0.8},
                {"same": False, "s": 0.2}, {"same": False, "s": 0.1}]
        self.assertEqual(auc(rows, "s"), 1.0)

    def test_auc_reversed_separation_is_zero(self):
        rows = [{"same": True, "s": 0.1}, {"same": False, "s": 0.9}]
        self.assertEqual(auc(rows, "s"), 0.0)

    def test_auc_with_single_class_is_zero(self):
        self.assertEqual(auc([{"same": True, "s": 0.5}], "s"), 0.0)

    def test_prf_counts(self):
        rows = [{"same": True, "hit": True}, {"same": False, "hit": True},
                {"same": True, "hit": False}, {"same": False, "hit": False}]
        m = prf(rows, lambda r: r["hit"])
        self.assertEqual((m["tp"], m["fp"], m["fn"]), (1, 1, 1))
        self.assertAlmostEqual(m["precision"], 0.5)
        self.assertAlmostEqual(m["recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
