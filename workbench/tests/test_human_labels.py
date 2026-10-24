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


if __name__ == "__main__":
    unittest.main()