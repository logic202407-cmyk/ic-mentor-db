"""同名消歧模块的离线测试：真值构造、URL 归一化与指标计算。"""

from __future__ import annotations

import unittest
from collections import Counter

from workbench.disambiguate_names import (
    DIFFERENT, SAME, UNKNOWN, PageIndex, _build_report, auc, build_pairs,
    canonical_home, confusion, evaluate_protocol, gold_agreement, identity_home,
    listing_url_reason, pair_label, prf, review,
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


def _profile(id_, name, home, *, inst="上海交通大学", dept="机械与动力工程学院",
             disc="0802 机械工程"):
    return {"id": id_, "name": name, "institution": inst, "department": dept,
            "first_level_discipline": disc, "homepage": home, "sources": []}


class EvidenceGradingMatrixTests(unittest.TestCase):
    """三类判定的判定矩阵：只有「直接证据」才给结论，单位归属差异一律 unknown。

    所有者判定（2026-10-26）：**仅有学科或院系差异不构成直接身份冲突证据**。
    同一位导师可能跨学科、兼任、历史学科调整或多院系关联；反过来同校同名的两个人
    也常常各在一个院系。因此这类组合必须进 unknown + 人工核验，不能判异人。
    """

    def _label(self, a, b):
        return pair_label(a, b, PageIndex([a, b]))

    def test_same_name_same_unit_same_discipline_is_unknown(self):
        """同名且同学科、同院系，只是两个不同的专属页 —— 无法区分。"""
        a = _profile("a", "张伟", "https://x.edu.cn/zhangwei1.htm")
        b = _profile("b", "张伟", "https://x.edu.cn/zhangwei2.htm")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertEqual(row["reason"], "same_unit_no_conflict")

    def test_same_name_cross_discipline_within_one_college_is_single_reason(self):
        """院系核心相同、只是挂在不同一级学科 —— 同一人跨学科录入的典型形态。"""
        a = _profile("a", "万文杰", "https://x.edu.cn/wanwenjie1.htm",
                     dept="物理与天文学院 / 光子传输与通信全国重点实验室",
                     disc="0809 电子科学与技术")
        b = _profile("b", "万文杰", "https://x.edu.cn/wanwenjie2.htm",
                     dept="物理与天文学院（含李政道研究所）", disc="0702 物理学")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertEqual(row["reason"], "same_unit_cross_discipline")
        self.assertTrue(row["same_unit_core"])

    def test_same_name_cross_department_is_unknown_not_different(self):
        """同名且跨院系 —— 旧版会判 different_person，现在必须 unknown。"""
        a = _profile("a", "刘世元", "https://x.edu.cn/liushiyuan1.htm",
                     dept="集成电路学院", disc="0809 电子科学与技术")
        b = _profile("b", "刘世元", "https://x.edu.cn/liushiyuan2.htm",
                     dept="机械电子信息工程系", disc="0802 机械工程")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN,
                         "院系不同不足以把身份判死")
        self.assertEqual(row["reason"], "unit_conflict_only")
        self.assertEqual(row["strength"], "none")

    def test_same_name_query_parameter_pages_stay_distinct(self):
        """查询串就是人 id：两页不同 → 仍然不能判同人。"""
        a = _profile("a", "张伟", "https://x.edu.cn/jiaoshi.php?aid=100&c=3")
        b = _profile("b", "张伟", "https://x.edu.cn/jiaoshi.php?aid=104&c=3")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertEqual(row["reason"], "same_unit_no_conflict")

    def test_same_name_shared_roster_page_is_unknown(self):
        """两人都指向同一个名录页 —— 名录页共用不代表同一人。"""
        a = _profile("a", "王涛", "https://x.edu.cn/szdw/jsml/list.htm")
        b = _profile("b", "王涛", "https://x.edu.cn/szdw/jsml/list.htm")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertIn("listing_page", row["reason"])

    def test_direct_identity_conflict_cross_institution_stays_different(self):
        """唯一保留的「直接冲突」：分属不同机构。"""
        a = _profile("a", "李敏", "https://x.edu.cn/limin.htm", inst="上海交通大学")
        b = _profile("b", "李敏", "https://y.edu.cn/limin.htm", inst="西安交通大学")
        row = self._label(a, b)
        self.assertEqual(row["label"], DIFFERENT)
        self.assertEqual(row["reason"], "distinct_pages_cross_institution")
        self.assertEqual(row["strength"], "strong")

    def test_unverifiable_missing_homepage_is_unknown(self):
        """完全无法核实：缺主页。"""
        a = _profile("a", "陈诚", "")
        b = _profile("b", "陈诚", "https://x.edu.cn/chencheng.htm")
        row = self._label(a, b)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertIn("missing_url", row["reason"])

    def test_review_marks_these_pairs_for_human_check(self):
        """改判后这些对必须明确进入人工待核，且永不自动合并。"""
        a = _profile("a", "刘洋", "https://x.edu.cn/liuyang1.htm",
                     dept="冶金工程（学科列表）", disc="0806 冶金工程")
        b = _profile("b", "刘洋", "https://x.edu.cn/liuyang2.htm",
                     dept="环境科学与工程（学科列表）", disc="0830 环境科学与工程")
        rows = [pair_label(a, b, PageIndex([a, b])) | {
            "name": "刘洋", "i": a, "j": b, "emb": 0.9}]
        queue = review(rows, PageIndex([a, b]))
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["label"], UNKNOWN)
        self.assertTrue(queue[0]["needs_human_review"])
        self.assertFalse(queue[0]["auto_merge"])
        self.assertEqual(queue[0]["verdict"], "待核")


class ListingUrlTests(unittest.TestCase):
    """URL 自身写着「列表」时不能当成个人专属页 —— 这是合并方向的真实假阳性。

    真实案例：``https://www.eias.ac.cn/?teachers_category=teachers-list`` 被判成
    personal，于是两条同校同名记录得出「同一专属主页 ⇒ 同一个人」（陈掌星 @ 上海交通大学）。
    反过来，``?id=``/``?aid=`` 这类「查询串就是人 id」的个人页**不能**被判成名录页。
    """

    def test_listing_markers_are_detected(self):
        for url, expected in [
            ("https://www.eias.ac.cn/?teachers_category=teachers-list", "listing_url_marker"),
            ("https://soo.sjtu.edu.cn/teacher-list.html", "listing_url_marker"),
            ("https://x.edu.cn/faculty_list.htm", "listing_url_marker"),
            ("https://x.edu.cn/people-list/", "listing_url_marker"),
            ("https://x.edu.cn/szdw/list.htm", "listing_file_name"),
            ("https://x.edu.cn/_t1477/azcp/listm.htm", "listing_file_name"),
            ("https://x.edu.cn/col/list_1.html", "listing_file_name"),
        ]:
            self.assertEqual(listing_url_reason(url), expected, url)

    def test_person_pages_are_not_mistaken_for_listings(self):
        for url in (
            "http://scce.sjtu.edu.cn/jiaoshi.php?aid=100&c=3",
            "https://caf.teacher.360eol.com/teacherBasic/preview?teacherId=31448",
            "https://ese.nju.edu.cn/_redirect?siteId=452&columnId=30446&articleId=464818",
            "https://upd-caup.tongji.edu.cn/3d/a9/c20527a343465/page.htm?id=03213",
            "https://me.sjtu.edu.cn/teacher_directory1/hujie",
            "https://www.ji.sjtu.edu.cn/cn/about/faculty-staff/faculty-directory/"
            "faculty-detail/131/",
            "http://dslx.ustc.edu.cn/?menu=expert_paper&expertid=100301",
            "",
        ):
            self.assertEqual(listing_url_reason(url), "", url)

    def test_teacher_list_url_no_longer_merges_two_people(self):
        """回归：陈掌星那一对必须从 same_person 降为 unknown。"""
        url = "https://www.eias.ac.cn/?teachers_category=teachers-list"
        a = _profile("a", "陈掌星", url, dept="数学科学学院", disc="0701 数学")
        b = _profile("b", "陈掌星", url, dept="化学化工学院", disc="0703 化学")
        pages = PageIndex([a, b])
        self.assertEqual(pages.kind(url), "roster")
        self.assertEqual(pages.kind_reason(url), "listing_url_marker")
        row = pair_label(a, b, pages)
        self.assertEqual(row["label"], UNKNOWN)
        self.assertIn("listing_page", row["reason"])


class DegenerateMetricTests(unittest.TestCase):
    """负例归零时，precision/F1/AUC 必须为 null，且**键仍然存在**。

    删键会让冻结的 /eval 前端把整节当成「还没跑过评测」；而填 0 或填一个
    必然成立的 1.0 都是假指标。正确做法：保留键，值为 null。
    """

    @staticmethod
    def _rows(positives: int, negatives: int):
        rows = [{"same": True, "label": SAME, "same_inst": True, "emb": 0.9,
                 "emb_clean": 0.9} for _ in range(positives)]
        rows += [{"same": False, "label": DIFFERENT, "same_inst": True, "emb": 0.2,
                  "emb_clean": 0.2} for _ in range(negatives)]
        return rows

    def test_precision_and_f1_are_null_without_negatives(self):
        result = evaluate_protocol(self._rows(5, 0), "test")
        self.assertEqual(result["negatives"], 0)
        self.assertIsNone(result["baseline_institution"]["precision"])
        self.assertIsNone(result["baseline_institution"]["f1"])
        self.assertIsNone(result["auc"]["embedding_only"])
        self.assertFalse(result["auc_defined"])
        self.assertTrue(result["metrics_note"])

    def test_keys_are_kept_so_frontend_does_not_degrade_to_pending(self):
        result = evaluate_protocol(self._rows(5, 0), "test")
        # 结构不变：键必须在，值才是 null。
        self.assertIn("precision", result["baseline_institution"])
        self.assertIn("recall", result["baseline_institution"])
        self.assertIn("f1", result["baseline_institution"])
        self.assertIn("embedding_only", result["auc"])
        self.assertIn("metrics_available", result)
        self.assertTrue(result["metrics_available"]["recall"])
        self.assertFalse(result["metrics_available"]["precision"])

    def test_metrics_are_computed_when_both_classes_exist(self):
        result = evaluate_protocol(self._rows(2, 3), "test")
        self.assertTrue(result["auc_defined"])
        self.assertIsNotNone(result["baseline_institution"]["precision"])
        self.assertIsNotNone(result["baseline_institution"]["f1"])

    def test_confusion_returns_none_only_for_missing_class(self):
        only_positive = [{"same": True, "inst": True}]
        m = confusion(only_positive, lambda r: r["inst"])
        self.assertEqual(m["tp"], 1)
        self.assertIsNone(m["precision"])
        self.assertIsNotNone(m["recall"])
        self.assertIsNone(m["f1"])

    def test_precision_is_null_when_nothing_is_predicted_positive(self):
        """tp+fp==0 时精确率是 0/0：不能落成 0.000（「没预测」≠「预测很差」）。"""
        rows = [{"same": True, "inst": False}, {"same": False, "inst": False}]
        m = confusion(rows, lambda r: r["inst"])
        self.assertEqual((m["tp"], m["fp"]), (0, 0))
        self.assertIsNone(m["precision"])
        self.assertIsNone(m["f1"])
        # 召回率仍有意义：两个正例一个没召回。
        self.assertEqual(m["recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
