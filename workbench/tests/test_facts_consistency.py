"""事实一致性检查与档案打包清单的回归测试。

这两道检查存在的理由都是"同一个错误发生过不止一次"：

- 技术报告曾长期写 15,177 条，而事实表是 15,719——因为没有任何机制把
  文档里的数字钉到数据上；
- `pack_research_bundle --check` 在干净 clone 上直接返回 1，因为它要求本机存在
  被 gitignore 的 `.workbench-data/public-research`，于是"一条命令全绿"的验收
  在评审机器上永远不成立。

所以这里既测"当前仓库是一致的"，也测"一旦写错必须能报出来"——只测前者会得到一个
永远通过的假测试。

参赛交付物停止跟踪后新增的契约
------------------------------
技术报告与提交材料 README 已停止跟踪，干净 clone 上不存在。它们缺失时必须**显式跳过**
（返回 0、输出写明「未随仓库发布，已跳过」），而不是报「文件缺失」把 CI 弄红；
根 `README.md` 的声明**继续生效**，缺失仍然是问题。这两条都用 tempdir 里的最小样本测。
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workbench.tools import check_facts_consistency as facts
from workbench.tools import pack_research_bundle as bundle

SKIP_PHRASE = "未随仓库发布，已跳过"


def claim(file: str, *, context: str = "全库", name: str = "全库记录",
          pattern: str = r"全库\s*[*]{0,2}([\d,]{3,})",
          fact: str = "records_total") -> dict:
    return {"file": file, "name": name, "context": context,
            "pattern": pattern, "fact": fact}


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
            claim_spec = claim("report.md")
            problems = facts.check_file(path, [claim_spec], {"records_total": 15719})
            self.assertEqual(len(problems), 1)
            self.assertIn("15,177", problems[0]["问题"])
            self.assertIn("15,719", problems[0]["问题"])

    def test_missing_sentence_is_reported(self):
        """登记过的句子被改写掉时，要提示同步更新声明表，而不是静默放过。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("这一段完全没有登记过的句子。\n", encoding="utf-8")
            problems = facts.check_file(path, [claim("report.md")],
                                        {"records_total": 15719})
            self.assertEqual(len(problems), 1)
            self.assertIn("未在文件里找到", problems[0]["问题"])

    def test_historical_number_not_flagged_when_context_differs(self):
        """同一段里量纲不同的句子（「全库有 N 条记录方向待补」）不能被误杀。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text("全库有 5,478 条记录的研究方向仍是「方向待补」。\n",
                            encoding="utf-8")
            problems = facts.check_file(
                path, [claim("report.md", context="工作台目录含",
                             pattern=r"工作台目录含\s*[*]{0,2}([\d,]{3,})")],
                {"records_total": 15719})
            # 没有命中任何句子，因此报"未找到"而不是"数字错"——这正是设计意图。
            self.assertTrue(all("未在文件里找到" in p["问题"] for p in problems))


class OptionalFileTests(unittest.TestCase):
    """参赛交付物缺失 → 显式跳过；根 README 缺失 → 仍然是问题。"""

    SUBMISSION = "workbench/aic-submission/技术报告.md"

    def test_missing_optional_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, skipped, checked = facts.run_checks(
                Path(tmp), [claim(self.SUBMISSION)], {"records_total": 15719},
                optional_files={self.SUBMISSION})
            self.assertEqual(problems, [], "可选交付物缺失不应判为问题")
            self.assertEqual(checked, 0)
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["文件"], self.SUBMISSION)
            self.assertEqual(skipped[0]["声明数"], 1)

    def test_missing_required_file_is_still_a_problem(self):
        """根 README.md 是长期开源仓库的必需文档——缺失必须红。"""
        with tempfile.TemporaryDirectory() as tmp:
            problems, skipped, checked = facts.run_checks(
                Path(tmp), [claim("README.md")], {"records_total": 15719},
                optional_files={self.SUBMISSION})
            self.assertEqual(skipped, [])
            self.assertEqual(checked, 1)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0]["名称"], "文件缺失")
            self.assertIn("不存在", problems[0]["问题"])

    def test_strict_turns_missing_optional_into_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, skipped, _checked = facts.run_checks(
                Path(tmp), [claim(self.SUBMISSION)], {"records_total": 15719},
                strict=True, optional_files={self.SUBMISSION})
            self.assertEqual(skipped, [])
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0]["名称"], "文件缺失")

    def test_skip_does_not_mask_a_real_mismatch_in_required_file(self):
        """跳过一份交付物时，根 README 的声明必须照常生效（不能被整体跳过带走）。"""
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text("当前进度：全库 15,177 条记录\n", encoding="utf-8")
            problems, skipped, checked = facts.run_checks(
                Path(tmp),
                [claim(self.SUBMISSION), claim("README.md")],
                {"records_total": 15719},
                optional_files={self.SUBMISSION})
            self.assertEqual([s["文件"] for s in skipped], [self.SUBMISSION])
            self.assertEqual(checked, 1)
            self.assertEqual(len(problems), 1)
            self.assertIn("15,177", problems[0]["问题"])
            self.assertEqual(problems[0]["文件"], "README.md")

    def test_claim_table_marks_exactly_the_submission_docs_optional(self):
        """声明表与 OPTIONAL_FILES 必须对齐：否则漏标一份就又让 CI 变红。"""
        files = {c["file"] for c in facts.CLAIMS}
        self.assertIn("README.md", files, "根 README 的声明不应消失")
        self.assertNotIn("README.md", facts.OPTIONAL_FILES,
                         "根 README 是必需文档，不能标成可选")
        submission = {f for f in files if f.startswith("workbench/aic-submission/")}
        self.assertEqual(submission, set(facts.OPTIONAL_FILES),
                         "工作量声明表引用的参赛交付物与 OPTIONAL_FILES 不一致")

    def test_summary_says_skipped_was_not_verified(self):
        """跳过不能被读成"通过"：结论必须点明未做实质校验。"""
        lines = facts.summary_lines(
            {"records_total": 15719}, [], [{"文件": self.SUBMISSION, "声明数": 5}],
            checked=10, files_total=3)
        text = "\n".join(lines)
        self.assertIn("⊘ 跳过", text)
        self.assertIn(SKIP_PHRASE, text)
        self.assertIn("未校验", text)
        self.assertIn("未做实质校验", text)
        self.assertNotIn("结论: 一致\n", text + "\n")

    def test_summary_clean_pass_has_no_skip_noise(self):
        lines = facts.summary_lines({"records_total": 15719}, [], [], checked=15,
                                    files_total=3)
        text = "\n".join(lines)
        self.assertNotIn("跳过", text)
        self.assertTrue(text.rstrip().endswith("结论: 一致"), text)

    def test_main_exits_zero_when_only_skips(self):
        """端到端：只有可选交付物、且都不存在时，CLI 退出码必须是 0。

        事实表本身在这里换成桩：本测试只验证「跳过 ⇒ 0 且说明清楚」这条契约，
        不必重跑整条事实计算链路（那会让单测慢到十几秒）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            claims = [claim(self.SUBMISSION)]
            buf = io.StringIO()
            with mock.patch.object(facts, "ROOT", Path(tmp)), \
                 mock.patch.object(facts, "CLAIMS", claims), \
                 mock.patch.object(facts, "build_facts", lambda: {"records_total": 15719}), \
                 mock.patch.object(facts, "_extra_facts", lambda: {}), \
                 mock.patch("workbench.catalog.coverage", lambda **_kw: {}), \
                 mock.patch.object(sys, "argv", ["prog"]), \
                 contextlib.redirect_stdout(buf):
                code = facts.main()
            out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertIn(SKIP_PHRASE, out)


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