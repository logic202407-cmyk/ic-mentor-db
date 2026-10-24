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

import unittest

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


if __name__ == "__main__":
    unittest.main()