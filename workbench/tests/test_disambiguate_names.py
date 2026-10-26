"""同名消歧模块的离线测试：真值构造、URL 归一化与指标计算。"""

from __future__ import annotations

import unittest
from collections import Counter

from workbench.disambiguate_names import (
    DIFFERENT, SAME, UNKNOWN, PageIndex, _build_report, auc, build_pairs,
    canonical_home, gold_agreement, identity_home, pair_label, prf,
)


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


class IdentityHomeTests(unittest.TestCase):
    """判「同一个页面」必须保留查询串；判「同一个站点的名录页」才抹掉它。"""

    def test_query_string_is_preserved(self):
        self.assertNotEqual(identity_home("http://x.edu.cn/p.php?aid=100"),
                            identity_home("http://x.edu.cn/p.php?aid=104"))
        self.assertNotEqual(
            identity_home("http://x.edu.cn/teacherBasic/preview?teacherId=31448"),
            identity_home("http://x.edu.cn/teacherBasic/preview?teacherId=31449"))

    def test_cosmetic_differences_are_ignored(self):
        self.assertEqual(identity_home("http://www.x.edu.cn/a.htm/"),
                         identity_home("https://x.edu.cn/a.htm#top"))
        self.assertEqual(identity_home("https://x.edu.cn/a/"),
                         identity_home("x.edu.cn/a"))

    def test_empty_is_empty(self):
        for value in ("", None, "   "):
            self.assertEqual(identity_home(value or ""), "")


class QueryIdentifiedPageTests(unittest.TestCase):
    """同一站点模板下按查询参数区分的两个个人页，不能判成同一个人。

    真实风险：``scce.sjtu.edu.cn/jiaoshi.php?aid=100`` 与 ``?aid=104`` 是**两位不同
    教师**的个人页。全库实测 473 条记录、471 个互不相同的个人页只因查询串不同就被
    ``canonical_home`` 压成 11 个 URL。旧实现用 ``canonical_home`` 判等，于是两页变
    同一个 URL，``pair_label`` 就得出「同一专属主页 ⇒ 同一个人」——仅凭姓名相同就把
    两个不同的人合并。
    """

    @staticmethod
    def _p(id_, home):
        return {"id": id_, "name": "张伟", "institution": "上海交通大学",
                "department": "化学化工学院", "first_level_discipline": "0703 化学",
                "homepage": home, "sources": []}

    def test_canonical_home_is_the_reason_the_old_check_collapsed_them(self):
        a = "http://scce.sjtu.edu.cn/jiaoshi.php?aid=100&c=3"
        b = "http://scce.sjtu.edu.cn/jiaoshi.php?aid=104&c=3"
        self.assertEqual(canonical_home(a), canonical_home(b))
        self.assertNotEqual(identity_home(a), identity_home(b))

    def test_distinct_query_ids_are_not_the_same_person(self):
        a = self._p("a", "http://scce.sjtu.edu.cn/jiaoshi.php?aid=100&c=3")
        b = self._p("b", "http://scce.sjtu.edu.cn/jiaoshi.php?aid=104&c=3")
        row = pair_label(a, b, PageIndex([a, b]))
        self.assertNotEqual(row["label"], SAME,
                            "不同查询 id 的个人页不能被合并成同一人")
        self.assertEqual(row["label"], UNKNOWN)
        self.assertEqual(row["reason"], "same_unit_no_conflict")

    def test_same_page_with_cosmetic_differences_is_still_one_person(self):
        a = self._p("a", "http://scce.sjtu.edu.cn/jiaoshi.php?aid=100&c=3")
        b = self._p("b", "https://www.scce.sjtu.edu.cn/jiaoshi.php?aid=100&c=3#top")
        row = pair_label(a, b, PageIndex([a, b]))
        self.assertEqual(row["label"], SAME)
        self.assertEqual(row["reason"], "shared_dedicated_page")


class GoldAgreementTests(unittest.TestCase):
    """一致率必须由样本现算，不能写死在文案里。"""

    def test_agreement_is_derived_from_the_pairs(self):
        gold = [{"auto_label": SAME, "verdict": SAME},
                {"auto_label": SAME, "verdict": UNKNOWN},
                {"auto_label": DIFFERENT, "verdict": DIFFERENT}]
        result = gold_agreement(gold)
        self.assertEqual(result["protocol_status"], "program-assisted")
        self.assertEqual(result["labelled_candidates"], 3)
        self.assertEqual(result["agreed"], 2)
        self.assertAlmostEqual(result["agreement"], 2 / 3)

    def test_empty_sample_reports_none_not_zero(self):
        result = gold_agreement([])
        self.assertIsNone(result["agreement"])


def _report_stats() -> dict:
    return {"groups": 3, "groups_with_missing_home": 1, "pairs_total": 5,
            "labels": Counter({SAME: 2, DIFFERENT: 2, UNKNOWN: 1}),
            "unknown_reasons": Counter({"missing_url": 1})}


def _reviewed() -> dict:
    return {"labelled_pairs": 4, "positives": 2, "negatives": 2,
            "excluded_unknown": 1,
            "auc": {"institution_only": 0.5, "embedding_only": 0.75,
                    "embedding_clean_only": 0.8},
            "baseline_institution": {"precision": 0.5, "recall": 1.0, "f1": 0.667},
            "thresholds": [{"emb>=": 0.5,
                            "emb_only": {"tp": 2, "fp": 1, "fn": 0,
                                         "precision": 0.667, "recall": 1.0,
                                         "f1": 0.8}}]}


class ReportAgreementTests(unittest.TestCase):
    """生成的报告只能引用本次实测算出的一致率。

    真实缺陷：``_build_report`` 里曾把 ``91.3%`` 直接写进文案。它恰好等于当时
    ``gold_pairs.json`` 的值，所以看起来没问题；但报告是重新生成的产物，数据一变就会
    继续复述一个**不再成立的「实测值」**——这正是数据真实性审计要消灭的写法。
    """

    def test_renders_the_measured_value(self):
        text = "\n".join(_build_report(
            _report_stats(), reviewed=_reviewed(),
            agreement={"agreement": 0.875, "agreed": 35,
                       "labelled_candidates": 40}))
        self.assertIn("87.5%", text)
        self.assertIn("35/40", text)

    def test_does_not_repeat_a_stale_number(self):
        text = "\n".join(_build_report(
            _report_stats(), reviewed=_reviewed(),
            agreement={"agreement": 0.5, "agreed": 5, "labelled_candidates": 10}))
        self.assertIn("50.0%", text)
        self.assertNotIn("91.3%", text)

    def test_invents_no_number_when_agreement_is_unknown(self):
        text = "\n".join(_build_report(_report_stats(), reviewed=_reviewed()))
        self.assertNotIn("91.3%", text)
        self.assertIn("只能说明规则之间是否自洽", text)


class HumanStatusRenderingTests(unittest.TestCase):
    """「人工标注状态」必须按磁盘上是否真有人工判断来渲染。

    真实缺陷：这一节曾写死成「**待完成**」。当前 `human_labels.json` 不存在，所以这句
    恰好是对的；一旦跑过 `--import-human`，报告会继续宣布人工标注「待完成」，
    同时把程序指标摆在最显眼位置——正好是「让自动结果顶替人工金标准」的反向版本。
    """

    def test_pending_when_no_human_labels_exist(self):
        text = "\n".join(_build_report(
            _report_stats(), reviewed=_reviewed(),
            human_status={"protocol_status": "pending"}))
        self.assertIn("人工标注状态：**待完成**", text)

    def test_not_pending_once_labels_are_collected(self):
        status = {"protocol_status": "human-collected", SAME: 12, DIFFERENT: 9,
                  UNKNOWN: 1, "distinct_pairs": 22, "conflicts": 2}
        text = "\n".join(_build_report(
            _report_stats(), reviewed=_reviewed(), human_status=status))
        self.assertNotIn("待完成", text)
        self.assertIn("已收集人工判断", text)
        self.assertIn("22", text)
        self.assertIn("争议 2 对", text)
        # 程序指标仍必须被明确标成"不是人工准确率"，不能因为有人工标注就混为一谈。
        self.assertIn("不是人工准确率", text)


if __name__ == "__main__":
    unittest.main()
