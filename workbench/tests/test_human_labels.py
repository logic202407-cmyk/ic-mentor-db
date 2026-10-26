"""人工标注流程的测试：盲标导出、伪造防护、样本不足不报指标。"""

from __future__ import annotations

import csv
import json
import pathlib
import tempfile
import unittest

from workbench import human_labels


def _write_labels(path: pathlib.Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=human_labels.COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class ExportTests(unittest.TestCase):

    def test_export_is_blind_and_has_a_separate_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = pathlib.Path(tmp) / "annotation.csv"
            result = human_labels.export(csv_path, per_category=3)
            self.assertTrue(csv_path.is_file())
            key_path = pathlib.Path(tmp) / "annotation-key.json"
            self.assertTrue(key_path.is_file())
            header = csv_path.read_text(encoding="utf-8-sig").splitlines()[0]
            for hidden in ("emb", "program_label", "program_verdict"):
                self.assertNotIn(hidden, header, "盲标表不应包含模型分数或自动判定")
            for required in ("human_verdict", "reviewer", "reviewed_at", "pair_id"):
                self.assertIn(required, header)
            key = json.loads(key_path.read_text(encoding="utf-8"))
            self.assertTrue(key["items"])
            self.assertGreaterEqual(result["pairs"], 1)


class BlindFieldLeakTests(unittest.TestCase):
    """盲标表不得泄漏任何由程序判定派生的字段。

    真实缺陷（2026-10-26）：盲标表里带着 ``category``，取值形如
    ``shared_homepage_unit_mismatch`` / ``listing_page``——它由 ``adjudicate()`` 的
    复核结论派生，等于把程序的身份判断写在标注者眼前，「盲标」名不副实。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = pathlib.Path(cls._tmp.name)
        cls.csv_path = cls.dir / "annotation.csv"
        cls.result = human_labels.export(cls.csv_path, per_category=2)
        cls.header = cls.csv_path.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
        cls.key = json.loads((cls.dir / "annotation-key.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_header_has_no_program_derived_fields(self) -> None:
        for leaked in ("category", "emb", "program_label", "program_verdict",
                       "reason", "a_id", "b_id"):
            self.assertNotIn(
                leaked, self.header,
                f"盲标表不得包含由程序判定派生的字段 {leaked}")

    def test_header_keeps_the_public_evidence_fields(self) -> None:
        for required in ("pair_id", "a_name", "b_name",
                         "a_institution", "b_institution",
                         "a_dept", "b_dept", "a_home", "b_home",
                         "a_page_kind", "b_page_kind",
                         "a_source_urls", "b_source_urls"):
            self.assertIn(required, self.header)

    def test_category_is_still_kept_in_the_key(self) -> None:
        items = self.key["items"]
        self.assertTrue(items)
        first = next(iter(items.values()))
        self.assertIn("category", first,
                      "category 必须留在评分键里：分层抽样与统计需要")
        self.assertTrue(first["category"])
        self.assertIn("category", self.key["held_back_fields"])

    def test_columns_equal_blind_plus_annotation(self) -> None:
        self.assertEqual(
            human_labels.COLUMNS,
            list(human_labels.BLIND_FIELDS) + list(human_labels.ANNOTATION_FIELDS))
        self.assertNotIn("category", human_labels.COLUMNS)

    def test_key_marks_model_scores_as_held_back(self) -> None:
        self.assertIn("emb", self.key["held_back_fields"])
        self.assertIn("program_label", self.key["held_back_fields"])
        first = next(iter(self.key["items"].values()))
        self.assertIn("emb", first)
        self.assertIn("program_label", first)


class CategoryRecoveryTests(unittest.TestCase):
    """盲标表不再带 category 后，导入仍要从评分键把它补回来（内部分层需要）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_import_recovers_category_and_name_from_key(self) -> None:
        path = self.dir / "labels.csv"
        _write_labels(path, [_label("p1", "same_person", "甲")])
        _write_key(path, {"p1": {"emb": 0.91, "program_label": "same_person",
                                 "program_verdict": "same_person",
                                 "category": "shared_homepage",
                                 "name": "张伟", "a_id": "a", "b_id": "b"}})
        human_labels.import_labels(path, out_dir=self.dir / "out")
        stored = json.loads((self.dir / "out" / "human_labels.json")
                            .read_text(encoding="utf-8"))
        label = stored["labels"][0]
        self.assertEqual(label["category"], "shared_homepage")
        self.assertEqual(label["name"], "张伟")
        # 这些字段仍然只能来自 key，不能出现在盲标 CSV 里。
        self.assertNotIn("category", path.read_text(encoding="utf-8-sig").splitlines()[0])


class ImportGuardTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _row(self, **overrides) -> dict:
        row = {name: "" for name in human_labels.COLUMNS}
        row.update({"pair_id": "p1", "human_verdict": "same_person",
                    "reviewer": "张三", "reviewed_at": "2026-10-24",
                    "human_confidence": "medium"})
        row.update(overrides)
        return row

    def test_missing_reviewer_is_rejected(self) -> None:
        path = self.dir / "a.csv"
        _write_labels(path, [self._row(reviewer="")])
        with self.assertRaises(ValueError) as ctx:
            human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertIn("reviewer", str(ctx.exception))

    def test_missing_date_is_rejected(self) -> None:
        path = self.dir / "b.csv"
        _write_labels(path, [self._row(reviewed_at="")])
        with self.assertRaises(ValueError):
            human_labels.import_labels(path, out_dir=self.dir / "out")

    def test_unknown_verdict_is_rejected(self) -> None:
        path = self.dir / "c.csv"
        _write_labels(path, [self._row(human_verdict="maybe")])
        with self.assertRaises(ValueError):
            human_labels.import_labels(path, out_dir=self.dir / "out")

    def test_empty_table_is_rejected(self) -> None:
        path = self.dir / "d.csv"
        _write_labels(path, [self._row(human_verdict="")])
        with self.assertRaises(ValueError):
            human_labels.import_labels(path, out_dir=self.dir / "out")

    def test_small_sample_reports_status_but_no_metrics(self) -> None:
        path = self.dir / "e.csv"
        rows = [self._row(pair_id=f"p{i}", human_verdict="same_person",
                          reviewer="张三") for i in range(5)]
        rows += [self._row(pair_id=f"q{i}", human_verdict="different_person",
                           reviewer="李四") for i in range(5)]
        _write_labels(path, rows)
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["status"], "insufficient")
        self.assertNotIn("program_rule", summary, "样本不足时不得报告精确率")
        self.assertEqual(summary["usable_pairs"], 10)

    def test_unknown_is_kept_and_excluded(self) -> None:
        path = self.dir / "f.csv"
        _write_labels(path, [self._row(pair_id="u1", human_verdict="unknown")])
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["unknown"], 1)
        self.assertEqual(summary["usable_pairs"], 0)

    def test_enough_labels_compute_metrics(self) -> None:
        path = self.dir / "g.csv"
        # 测试夹具：仅为验证"达到门槛后才会计算指标"的代码路径，不代表真实标注。
        rows = [self._row(pair_id=f"s{i}", human_verdict="same_person") for i in range(20)]
        rows += [self._row(pair_id=f"d{i}", human_verdict="different_person") for i in range(20)]
        _write_labels(path, rows)
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["status"], "ready")
        self.assertIn("program_rule", summary)
        self.assertEqual(summary["positives"], 20)
        self.assertTrue((self.dir / "out" / "human_labels.json").is_file())


class StatusTests(unittest.TestCase):

    def test_missing_labels_mean_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = human_labels.status(pathlib.Path(tmp))
            self.assertEqual(result["protocol_status"], "pending")


def _label(pair_id: str, verdict: str, reviewer: str, **overrides) -> dict:
    row = {name: "" for name in human_labels.COLUMNS}
    row.update({"pair_id": pair_id, "human_verdict": verdict, "reviewer": reviewer,
                "reviewed_at": "2026-10-24", "human_confidence": "medium"})
    row.update(overrides)
    return row


def _write_key(csv_path: pathlib.Path, items: dict) -> None:
    key_path = csv_path.with_name(csv_path.stem + "-key.json")
    key_path.write_text(
        json.dumps({"schema": "mentor-workbench/human-annotation-key/v1",
                    "items": items}, ensure_ascii=False),
        encoding="utf-8")


class ReviewerIndependenceTests(unittest.TestCase):
    """同一对的多份人工判断只能算一条真值，否则样本量会凭空翻倍。

    真实事故形态：协议建议两位标注者，于是 15 对 × 2 人 = 30 行，
    旧实现把它当成 30 对独立样本，直接跨过 ``MIN_LABELS=30`` 的「人工金标准 ready」
    门槛——用重复计数冒充了足够的标注量。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_two_reviewers_on_the_same_pairs_do_not_double_the_sample(self) -> None:
        rows = []
        for index in range(10):
            for reviewer in ("标注者甲", "标注者乙"):
                rows.append(_label(f"p{index}", "same_person", reviewer))
        for index in range(5):
            for reviewer in ("标注者甲", "标注者乙"):
                rows.append(_label(f"q{index}", "different_person", reviewer))
        path = self.dir / "two-reviewers.csv"
        _write_labels(path, rows)
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["labelled_total"], 15)
        self.assertEqual(summary["usable_pairs"], 15)
        self.assertEqual(summary["positives"], 10)
        self.assertEqual(summary["negatives"], 5)
        self.assertEqual(summary["status"], "insufficient",
                         "15 对即使有两位标注者也不能算达到 30 对门槛")

    def test_conflicting_reviewers_are_flagged_and_excluded(self) -> None:
        path = self.dir / "conflict.csv"
        _write_labels(path, [_label("p0", "same_person", "甲"),
                             _label("p0", "different_person", "乙")])
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["conflicts"], 1)
        self.assertEqual(summary["usable_pairs"], 0,
                         "互相矛盾的两位标注者不能被同时当成真值")
        self.assertEqual(summary["positives"], 0)
        self.assertEqual(summary["negatives"], 0)
        stored = json.loads((self.dir / "out" / "human_labels.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(len(stored["labels"]), 1, "同一 pair_id 只保留一条真值")
        self.assertTrue(stored["labels"][0]["conflict"])
        self.assertEqual(stored["conflicts"], ["p0"])

    def test_blank_pair_id_is_rejected(self) -> None:
        path = self.dir / "blank.csv"
        _write_labels(path, [_label("", "same_person", "甲")])
        with self.assertRaises(ValueError) as ctx:
            human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertIn("pair_id", str(ctx.exception))


class UnmeasuredMetricTests(unittest.TestCase):
    """评分用键缺失时，指标必须输出 null，绝不能输出 0.0。

    旧实现把缺失的 ``emb`` 当成 0、把缺失的 ``program_label`` 当成「不是同人」，
    于是打印出「精确率 0.000 / 召回率 0.000」——读者会以为是实测结果很差，
    实际上根本没有测过。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _enough_rows(self) -> list[dict]:
        rows = [_label(f"s{i}", "same_person", "甲") for i in range(20)]
        rows += [_label(f"d{i}", "different_person", "甲") for i in range(20)]
        return rows

    def test_missing_key_yields_null_metrics(self) -> None:
        path = self.dir / "nokey.csv"
        _write_labels(path, self._enough_rows())
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["status"], "ready")
        self.assertIsNone(summary["program_rule"],
                          "评分用键缺失时不得报告程序规则指标")
        self.assertIsNone(summary["embedding_thresholds"],
                          "评分用键缺失时不得报告嵌入阈值指标")
        self.assertEqual(summary["embedding_pairs"], 0)
        self.assertIn("metrics_note", summary)

    def test_key_present_still_produces_metrics(self) -> None:
        path = self.dir / "withkey.csv"
        _write_labels(path, self._enough_rows())
        items = {}
        for index in range(20):
            items[f"s{index}"] = {"emb": 0.9, "program_label": "same_person"}
        for index in range(20):
            items[f"d{index}"] = {"emb": 0.2, "program_label": "different_person"}
        _write_key(path, items)
        summary = human_labels.import_labels(path, out_dir=self.dir / "out")
        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["embedding_pairs"], 40)
        self.assertEqual(summary["program_rule"]["tp"], 20)
        self.assertEqual(summary["program_rule"]["fp"], 0)
        self.assertAlmostEqual(summary["program_rule"]["precision"], 1.0)
        top = summary["embedding_thresholds"][0]
        self.assertEqual(top["emb>="], 0.50)
        self.assertEqual((top["tp"], top["fp"]), (20, 0))


if __name__ == "__main__":
    unittest.main()