"""档案打包（clone 后可复现）的测试。

核心命题：**评委 clone 仓库后，界面上仍然能看到论文与招生记录**。
档案原本只存 `.workbench-data/public-research/`（6503 个文件 / 28.5 MB，被 gitignore），
clone 后 `load()` 会全部返回空——而技术报告写的是"3,434 位有论文目录"。

处理办法是把精简字段打包成 `workbench/reference/research/dossiers.json.gz`（约 4.8 MB），
`load()` 在找不到逐人文件时回落到它。
"""

from __future__ import annotations

import gzip
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from workbench import catalog, public_research  # noqa: E402

BUNDLE = ROOT / "workbench/reference/research/dossiers.json.gz"


class BundleFileTests(unittest.TestCase):

    def test_bundle_exists_and_is_gzip(self):
        self.assertTrue(BUNDLE.is_file(), "缺少档案打包：clone 后记录会全空")
        with open(BUNDLE, "rb") as fh:
            self.assertEqual(fh.read(2), b"\x1f\x8b", "不是 gzip 格式")

    def test_bundle_size_is_reasonable(self):
        mb = BUNDLE.stat().st_size / 1024 / 1024
        self.assertLess(mb, 12.0, f"打包过大（{mb:.1f} MB），需进一步精简")

    def test_bundle_lines_are_valid_json(self):
        count = 0
        with gzip.open(BUNDLE, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                self.assertIn("id", item)
                count += 1
                if count >= 200:
                    break
        self.assertGreater(count, 100)


class BundleContentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.table = public_research._bundle()

    def test_bundle_has_many_records(self):
        self.assertGreater(len(self.table), 1000)

    def test_some_records_carry_papers(self):
        with_papers = sum(1 for v in self.table.values() if v.get("papers"))
        self.assertGreater(with_papers, 100, "打包里几乎没有论文数据")

    def test_some_records_carry_biography(self):
        with_bio = sum(1 for v in self.table.values() if v.get("biography"))
        self.assertGreater(with_bio, 500, "打包里几乎没有履历数据")

    def test_ids_are_real_catalog_ids(self):
        pairs, _by, _raw, _net = catalog.static_catalog()
        real = {p["id"] for p in pairs}
        sample = list(self.table)[:50]
        for mid in sample:
            self.assertIn(mid, real)


class FallbackTests(unittest.TestCase):
    """模拟 clone：本机没有逐人档案时，load() 必须从打包里取到内容。"""

    def test_fallback_returns_bundled_data(self):
        pairs, _by, _raw, _net = catalog.static_catalog()
        missing = Path("/nonexistent/public-research")
        hits = 0
        for profile in pairs[:200]:
            with patch.object(public_research, "path_for", lambda _m: missing):
                data = public_research.load(profile["id"])
            if data and data.get("bundled"):
                hits += 1
                if hits >= 5:
                    break
        self.assertGreaterEqual(hits, 5, "回退没取到数据：clone 后界面会是空的")

    def test_fallback_keeps_version(self):
        pairs, _by, _raw, _net = catalog.static_catalog()
        missing = Path("/nonexistent/public-research")
        with patch.object(public_research, "path_for", lambda _m: missing):
            for profile in pairs[:100]:
                data = public_research.load(profile["id"])
                if data and data.get("bundled"):
                    self.assertIn("version", data)
                    return
        self.skipTest("前 100 条没有可回退的档案")


if __name__ == "__main__":
    unittest.main()
