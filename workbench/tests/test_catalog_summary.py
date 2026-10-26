"""首页轻量计数接口（/api/catalog/summary）的一致性测试。

为什么要单独钉住
----------------
首页首屏此前直接等 `/api/catalog/coverage`，而它会为 1.2 万条记录逐条读档案，
冷启动 8–17 秒，首屏长期停在「—」。轻量计数只做集合统计，但**一旦它和完整
coverage 的口径漂移**，首页与评测/报告就会各说一套数字。所以这里同时校验：

1. 轻量计数与完整 coverage 的关键字段一致；
2. 接口返回的就是 ``catalog.public_counts()``，没有第二条取数路径。
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from workbench import catalog
from workbench.app import app


class SummaryCountsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.counts = catalog.public_counts()

    def test_required_keys(self) -> None:
        for key in ("total_records", "public_records", "official_records",
                    "secondary_records", "public_institutions",
                    "disciplines_total", "disciplines_engineering"):
            self.assertIn(key, self.counts)
            self.assertIsInstance(self.counts[key], int)

    def test_matches_full_coverage_headline(self) -> None:
        coverage = catalog.coverage()
        self.assertEqual(self.counts["total_records"], coverage["total_records"])
        self.assertEqual(self.counts["public_records"], coverage["public_records"])
        self.assertEqual(self.counts["official_records"], coverage["official_records"])
        self.assertEqual(self.counts["public_institutions"],
                         coverage["public_institutions"])

    def test_engineering_discipline_count(self) -> None:
        # 工学一级学科：现有数据里是 38 个；这条也是首页 KPI 的来源
        self.assertGreaterEqual(self.counts["disciplines_engineering"], 30)
        self.assertLessEqual(self.counts["disciplines_engineering"],
                             self.counts["disciplines_total"])

    def test_endpoint_serves_the_same_numbers(self) -> None:
        client = TestClient(app)
        response = client.get("/api/catalog/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.counts)


class CaseWriterTests(unittest.TestCase):
    """``_write_case`` 只能有一份实现，且必须是「加锁 + 原子写」的安全版。

    真实缺陷（本次审计与 storage-security 各自独立复现）
    ---------------------------------------------------
    ``workbench/catalog.py`` 里 ``_write_case`` 被定义了两次：

    - 第 509 行：``storage.file_lock`` + ``storage.atomic_write_json``（安全版）；
    - 第 529 行：``path.with_suffix(".tmp")`` 固定临时文件名、无锁、无 fsync（旧版）。

    Python 后定义覆盖前定义，于是**安全版成了死代码**，实际生效的是旧版。它当前没有
    调用点，所以还没有暴露故障；但这正是 storage 层修过的「固定临时文件名 + 读写无
    互斥 ⇒ 并发写坏 JSON」缺陷的复活点——只要将来有人调用一次就会踩中。
    因此这里用 AST 钉住「只有一份」，用源码钉住「那一份必须是加锁原子写」。
    """

    def setUp(self) -> None:
        self.source = pathlib.Path(catalog.__file__).read_text(encoding="utf-8")

    def _definitions(self) -> list[ast.FunctionDef]:
        tree = ast.parse(self.source)
        return [node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "_write_case"]

    def test_defined_exactly_once(self) -> None:
        self.assertEqual(
            len(self._definitions()), 1,
            "catalog.py 出现了多份 _write_case 定义：后者会静默覆盖前者，"
            "安全实现会变成死代码")

    def test_implementation_is_locked_and_atomic(self) -> None:
        body = inspect.getsource(catalog._write_case)
        self.assertNotIn("with_suffix", body,
                         "不得使用 path.with_suffix('.tmp') 这类固定临时文件名")
        self.assertIn("file_lock", body, "_write_case 必须在文件锁内写")
        self.assertIn("atomic_write_json", body, "_write_case 必须走原子写")

    def test_no_call_sites_is_recorded_not_assumed(self) -> None:
        """当前没有调用点：正因如此才更要保留安全版，而不是删掉整个函数。"""
        calls = [node for node in ast.walk(ast.parse(self.source))
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "_write_case"]
        self.assertEqual(calls, [])

    def test_mutate_case_creates_a_missing_case_directory(self) -> None:
        """行为级兜底：写档案时目录不存在也要能安全落盘。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "nested" / "case.json"
            with mock.patch.object(catalog, "_case_path", return_value=target):
                catalog.mutate_case("mentor-missing-dir",
                                    lambda record: record.update({"notes": "补充说明"}))
            self.assertTrue(target.is_file())
            stored = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(stored["notes"], "补充说明")
            self.assertEqual(stored["revision"], 1)


class DataQualityConsistencyTests(unittest.TestCase):
    """数据质量报告的数字必须与主流程口径一致，不能各说一套。

    这两处漂移都会被读者当成「报告写错了」：
    - 工学条目按 ``first_level_discipline`` 判断会漏掉「主学科是数学、同时在 0804
      下挂靠」的记录（全库 104 条），与 ``catalog.in_scope`` 的界面口径不一致；
    - 主页类型只看「来源声明的名录页」会把被多人共用的列表页报成本人专属页。
    """

    @classmethod
    def setUpClass(cls) -> None:
        from workbench.tools import data_quality
        cls.payload = data_quality.collect()
        cls.entries = catalog.static_catalog()[0]
        cls.public = [p for p in cls.entries
                      if p.get("catalog_source")
                      or (p.get("id") or "").startswith("pilot-")]

    def test_engineering_count_matches_scope(self) -> None:
        expected = sum(1 for p in self.public if catalog.in_scope(p))
        self.assertEqual(self.payload["records"]["engineering"], expected)

    def test_homepage_kind_uses_the_stricter_criteria(self) -> None:
        from workbench.disambiguate_names import PageIndex
        pages = PageIndex(self.public)
        expected = {}
        for profile in self.public:
            kind = pages.kind((profile.get("homepage") or "").strip())
            expected[kind] = expected.get(kind, 0) + 1
        self.assertEqual(self.payload["homepage_kind"], expected)
        # 只看「来源声明的名录页」会少算一大批共用的列表页。
        import workbench.homepage_kind as homepage_kind
        declared_only = sum(1 for p in self.public
                            if homepage_kind.kind_of(p.get("homepage") or "") == "roster")
        self.assertGreater(self.payload["homepage_kind"].get("roster", 0), declared_only)

    def test_missing_papers_splits_absent_from_uncollected(self) -> None:
        from workbench import public_research
        missing = self.payload["missing_fields"]
        for key in ("papers_not_searched", "papers_none_extracted",
                    "recruitment_not_searched", "recruitment_none_extracted"):
            self.assertIn(key, missing)
        # 两行之和必须等于「没有论文记录的公开来源条目数」：拆开只是分口径，
        # 不能顺手改掉总数。
        absent = sum(1 for profile in self.public
                     if not (public_research.load(profile["id"]) or {}).get("papers"))
        self.assertEqual(
            missing["papers_not_searched"] + missing["papers_none_extracted"], absent)

    def test_same_name_groups_reported_for_both_denominators(self) -> None:
        records = self.payload["records"]
        self.assertIn("duplicate_name_groups_all_scope", records)
        self.assertGreaterEqual(records["duplicate_name_groups_all_scope"],
                                records["duplicate_name_groups"])


if __name__ == "__main__":
    unittest.main()