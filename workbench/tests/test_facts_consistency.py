"""事实一致性检查与档案打包清单的回归测试。

这两道检查存在的理由都是"同一个错误发生过不止一次"：

- 技术报告曾长期写 15,177 条，而事实表是 15,719——因为没有任何机制把
  文档里的数字钉到数据上；
- `pack_research_bundle --check` 在干净 clone 上直接返回 1，因为它要求本机存在
  被 gitignore 的 `.workbench-data/public-research`，于是"一条命令全绿"的验收
  在评审机器上永远不成立。

所以这里既测"当前仓库是一致的"，也测"一旦写错必须能报出来"——只测前者会得到一个
永远通过的假测试。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workbench.tools import check_facts_consistency as facts
from workbench.tools import pack_research_bundle as bundle


class FactsConsistencyTests(unittest.TestCase):
    # 这里**故意不测**"当前仓库内容是否一致"。
    # 原因：那会让每新增一个测试方法就把本测试弄红（测试数本身也是被校验的事实），
    # 于是维护者会习惯性放宽断言。内容一致性由上传前验收关卡
    # `python -m workbench.tools.check_facts_consistency` 负责——
    # 那里红了就是真的该改文档，而不是该改测试。

    def test_detects_wrong_number(self):
        """写错的数字必须被发现——否则这道检查没有价值。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("全库 15,177 条记录\n", encoding="utf-8")
            claim = {
                "file": "report.md", "name": "全库记录", "context": "全库",
                "pattern": r"全库\s*[*]{0,2}([\d,]{3,})", "fact": "records_total",
            }
            problems = facts.check_file(path, [claim], {"records_total": 15719})
            self.assertEqual(len(problems), 1)
            self.assertIn("15,177", problems[0]["问题"])
            self.assertIn("15,719", problems[0]["问题"])

    def test_missing_sentence_is_reported(self):
        """登记过的句子被改写掉时，要提示同步更新声明表，而不是静默放过。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("这一段完全没有登记过的句子。\n", encoding="utf-8")
            claim = {
                "file": "report.md", "name": "全库记录", "context": "全库",
                "pattern": r"全库\s*[*]{0,2}([\d,]{3,})", "fact": "records_total",
            }
            problems = facts.check_file(path, [claim], {"records_total": 15719})
            self.assertEqual(len(problems), 1)
            self.assertIn("未在文件里找到", problems[0]["问题"])

    def test_historical_number_not_flagged_when_context_differs(self):
        """同一段里量纲不同的句子（「全库有 N 条记录方向待补」）不能被误杀。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("全库有 5,478 条记录的研究方向仍是「方向待补」。\n",
                            encoding="utf-8")
            claim = {
                "file": "report.md", "name": "全库记录", "context": "工作台目录含",
                "pattern": r"工作台目录含\s*[*]{0,2}([\d,]{3,})", "fact": "records_total",
            }
            problems = facts.check_file(path, [claim], {"records_total": 15719})
            # 没有命中任何句子，因此报"未找到"而不是"数字错"——这正是设计意图。
            self.assertTrue(all("未在文件里找到" in p["问题"] for p in problems))


class ResearchBundleManifestTests(unittest.TestCase):
    def test_manifest_matches_committed_bundle(self):
        """清单是干净 clone 上唯一能自证副本完整性的东西，必须与副本一致。"""
        self.assertTrue(bundle.MANIFEST.is_file(), "清单缺失")
        self.assertTrue(bundle.OUT.is_file(), "档案副本缺失")
        manifest = json.loads(bundle.MANIFEST.read_text(encoding="utf-8"))
        blob = bundle.OUT.read_bytes()
        self.assertEqual(manifest["sha256"], hashlib.sha256(blob).hexdigest())
        self.assertEqual(manifest["count"], bundle._count_lines(bundle.OUT))
        self.assertGreater(manifest["count"], 0)

    def test_check_passes_when_local_source_absent(self):
        """干净 clone 上没有本机原始档案——那应判为"已校验完整性"，不是失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-dir"
            with mock.patch.object(bundle, "SRC_DIR", missing):
                self.assertEqual(bundle.check(), 0)

    def test_check_detects_corrupted_bundle(self):
        """副本被改动时必须失败，否则清单形同虚设。"""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dossiers.json.gz"
            out.write_bytes(gzip.compress(b'{"id":"x"}\n', compresslevel=9, mtime=0))
            manifest = Path(tmp) / "dossiers.manifest.json"
            manifest.write_text(json.dumps(
                {"count": 99, "sha256": "0" * 64}), encoding="utf-8")
            with mock.patch.object(bundle, "OUT", out), \
                 mock.patch.object(bundle, "MANIFEST", manifest), \
                 mock.patch.object(bundle, "SRC_DIR", Path(tmp) / "missing"):
                self.assertEqual(bundle.check(), 1)


if __name__ == "__main__":
    unittest.main()