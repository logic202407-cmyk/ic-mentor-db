# -*- coding: utf-8 -*-
"""privacy_audit 的检测能力自测：每类检查都要有正例与反例。

约定：
- 全部用例都用临时目录构造夹具，不依赖仓库当前状态（仓库状态会随修复变化）。
- 只有 upload-limit 直接调用真实的 workbench.core（只读，不落盘）。
- origin-guard / json-error-path 反映的是 app.py **当下**的行为；修复后断言方向会反转，
  因此这里只断言"能返回结构化结论"，把严格断言放在 PRIVACY_AUDIT_STRICT=1 之后。
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from workbench.tools import privacy_audit as pa


class _Temp(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)

    def tearDown(self) -> None:
        self._dir.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class EmailScanTest(_Temp):
    # 夹具地址在运行时拼接：源码里不留字面量，否则本仓库自己的发布面扫描会命中测试文件
    REAL = "zhang" + ".san@" + "tsinghua" + ".edu" + ".cn"

    def test_clean_repository_passes(self):
        self.write("data/records.json", '{"name": "张三", "institution": "某大学"}')
        check = pa.check_email_scan(self.root)
        self.assertEqual(check.status, "PASS")

    def test_real_email_fails(self):
        self.write("data/records.json", '{"name": "张三", "contact": "%s"}' % self.REAL)
        check = pa.check_email_scan(self.root)
        self.assertEqual(check.status, "FAIL")
        self.assertIn("data/records.json", check.evidence[0])
        # 证据必须脱敏：不得回显完整邮箱
        self.assertNotIn(self.REAL, "\n".join(check.evidence))
        self.assertIn("***@t***", check.evidence[0])

    def test_reserved_test_domain_passes(self):
        self.write("workbench/tests/fixtures.json", '{"email": "someone@example.com"}')
        check = pa.check_email_scan(self.root)
        self.assertEqual(check.status, "PASS", check.detail)

    def test_noreply_github_passes(self):
        self.write("docs/note.md", "提交者 123+user@users.noreply.github.com")
        self.assertEqual(pa.check_email_scan(self.root).status, "PASS")

    def test_gzip_payload_is_scanned(self):
        import gzip

        path = self.root / "data/dossiers.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wb") as handle:
            handle.write(('{"text": "contact %s"}' % self.REAL).encode("utf-8"))
        check = pa.check_email_scan(self.root)
        self.assertEqual(check.status, "FAIL", "压缩后的数据必须解压后再扫")


class PhoneScanTest(_Temp):
    MOBILE = "138" + "1234" + "5678"      # 运行期拼接，避免本仓库扫描命中测试文件
    LANDLINE = "010" + "-" + "62751234"
    GRANT = "174" + "31904600"

    def test_clean_passes(self):
        self.write("data/records.json", '{"note": "2026-10-14 采集，DOI 10.1055/s-0039-1698837"}')
        self.assertEqual(pa.check_phone_scan(self.root).status, "PASS")

    def test_mobile_fails(self):
        self.write("data/records.json", '{"note": "电话 %s"}' % self.MOBILE)
        check = pa.check_phone_scan(self.root)
        self.assertEqual(check.status, "FAIL")
        self.assertNotIn(self.MOBILE, "\n".join(check.evidence))

    def test_landline_fails(self):
        self.write("data/records.json", '{"note": "咨询 %s"}' % self.LANDLINE)
        self.assertEqual(pa.check_phone_scan(self.root).status, "FAIL")

    def test_doi_suffix_not_flagged(self):
        self.write("data/records.json", '{"doi": "10.1055/s-0039-1698837", "url": "https://x.edu.cn/0020220087/"}')
        self.assertEqual(pa.check_phone_scan(self.root).status, "PASS")

    def test_article_number_not_flagged(self):
        self.write("data/records.json",
                   '{"text": "Advanced Materials 37 (2025) 2404698"}')
        self.assertEqual(pa.check_phone_scan(self.root).status, "PASS")

    def test_grant_number_is_suspect_not_blocking(self):
        """项目编号与手机号形态相同：降级为 RISK，交人工确认。"""
        self.write("data/records.json",
                   '{"text": "上海市科委生物医药科技重点项目（主持： %s）"}' % self.GRANT)
        check = pa.check_phone_scan(self.root)
        self.assertEqual(check.status, "RISK", check.detail)


class IdCardScanTest(_Temp):
    # 运行期拼接：源码里不留 18 位身份证字面量，否则本仓库自己的扫描会命中测试文件
    ID = "110101" + "19900307" + "1234"

    def test_clean_passes(self):
        self.write("data/records.json", '{"id": "20261016175530"}')
        self.assertEqual(pa.check_id_card_scan(self.root).status, "PASS")

    def test_id_card_fails(self):
        self.write("data/records.json", '{"id": "%s"}' % self.ID)
        check = pa.check_id_card_scan(self.root)
        self.assertEqual(check.status, "FAIL")
        self.assertNotIn(self.ID, "\n".join(check.evidence))


class DangerKeyTest(_Temp):
    def test_clean_passes(self):
        self.write("data/records.json", '{"name": "张三", "homepage": "https://x.edu.cn"}')
        self.assertEqual(pa.check_danger_keys(self.root).status, "PASS")

    def test_null_key_is_risk_not_fail(self):
        """键名保留但值为 null：与「不收录该字段」的措辞不一致，记 RISK。"""
        self.write("data/raw/x/roster_x.json", '{"name": "张三", "email": null}')
        check = pa.check_danger_keys(self.root)
        self.assertEqual(check.status, "RISK", check.detail)
        self.assertIn("email", check.evidence[0])

    def test_nonempty_value_fails(self):
        self.write("data/records.json", '{"name": "张三", "phone": "01062751234"}')
        check = pa.check_danger_keys(self.root)
        self.assertEqual(check.status, "FAIL")

    def test_other_sensitive_keys_detected(self):
        for key in ("id_card", "address", "political_status", "salary"):
            with self.subTest(key=key):
                self.write("data/records.json", '{"%s": "x"}' % key)
                self.assertEqual(pa.check_danger_keys(self.root).status, "FAIL")


class RedactionPlaceholderTest(_Temp):
    def test_good_placeholder_passes(self):
        self.write("data/records.json", '{"contact": "联系方式已隐去"}')
        self.assertEqual(pa.check_redaction_placeholder(self.root).status, "PASS")

    def test_redacted_at_host_fails(self):
        """占位符自身仍匹配邮箱正则，等于没脱敏（SECURITY.md 记载的历史错误）。"""
        self.write("data/records.json", '{"contact": "someone@redacted-host"}')
        check = pa.check_redaction_placeholder(self.root)
        self.assertEqual(check.status, "FAIL")

    def test_documentation_mention_is_ignored(self):
        """文档里引用历史错误不算残留。"""
        self.write("SECURITY.md", "第一次把邮箱替换成 redacted@host，仍然匹配邮箱正则")
        self.assertEqual(pa.check_redaction_placeholder(self.root).status, "PASS")


class UploadLimitTest(unittest.TestCase):
    def test_oversize_content_rejected(self):
        from workbench import core

        with self.assertRaises(ValueError):
            core.parse_import("big.csv", "a" * 10_000_001)

    def test_within_limit_accepted(self):
        from workbench import core

        rows = core.parse_import("ok.csv", "name,institution\n张三,某大学\n")
        self.assertEqual(len(rows), 1)

    def test_too_many_rows_rejected(self):
        from workbench import core

        body = "name,institution\n" + "".join(f"导师{i},某大学\n" for i in range(5001))
        with self.assertRaises(ValueError):
            core.parse_import("many.csv", body)

    def test_bad_extension_rejected(self):
        from workbench import core

        with self.assertRaises(ValueError):
            core.parse_import("x.exe", "abc")

    def test_check_reports_pass_on_repo(self):
        check = pa.check_upload_limit(pa.ROOT)
        self.assertEqual(check.status, "PASS", check.detail)


class GitignoreTest(_Temp):
    COMPLETE = (".workbench-data/\n*.log\n*.pyc\n__pycache__/\n"
                ".env\n*.pem\n*.key\ncredentials*\n")

    def test_complete_passes(self):
        self.write(".gitignore", self.COMPLETE)
        self.assertEqual(pa.check_gitignore(self.root).status, "PASS")

    def test_missing_required_fails(self):
        self.write(".gitignore", "*.pyc\n")
        check = pa.check_gitignore(self.root)
        self.assertEqual(check.status, "FAIL")
        self.assertIn(".workbench-data", check.detail)

    def test_missing_optional_is_risk(self):
        """必需项齐全、但缺 .env / 私钥兜底规则 → RISK（不阻塞）。"""
        self.write(".gitignore", ".workbench-data/\n*.log\n*.pyc\n__pycache__/\n")
        check = pa.check_gitignore(self.root)
        self.assertEqual(check.status, "RISK", check.detail)
        self.assertIn(".env", check.detail)

    def test_no_gitignore_fails(self):
        self.assertEqual(pa.check_gitignore(self.root).status, "FAIL")


class PersonalRecordsTest(_Temp):
    def test_record_outside_local_dir_fails(self):
        self.write("data/processed/case.json",
                   '{"mentor_id": "official-1", "section_status": {"身份与任职": "已人工核查"}}')
        check = pa.check_personal_records(self.root)
        self.assertEqual(check.status, "FAIL")

    def test_record_inside_local_dir_passes(self):
        self.write(".workbench-data/investigations/a.json",
                   '{"mentor_id": "official-1", "section_status": {}}')
        check = pa.check_personal_records(self.root)
        self.assertEqual(check.status, "PASS", check.detail)

    def test_no_local_dir_is_skip(self):
        self.write("data/records.json", '{"name": "张三"}')
        self.assertEqual(pa.check_personal_records(self.root).status, "SKIP")


class LongVerbatimTest(_Temp):
    def test_short_text_passes(self):
        self.write("data/records.json", json.dumps({"text": "短摘要" * 20}, ensure_ascii=False))
        self.assertEqual(pa.check_long_verbatim(self.root).status, "PASS")

    def test_very_long_field_is_risk(self):
        self.write("data/records.json", json.dumps({"text": "原" * 2500}, ensure_ascii=False))
        check = pa.check_long_verbatim(self.root)
        self.assertEqual(check.status, "RISK")
        self.assertIn("2500", check.evidence[0])


class LicenseScopeTest(_Temp):
    def test_uncovered_dir_is_risk(self):
        (self.root / "workbench/reference").mkdir(parents=True)
        self.write("workbench/reference/admission.json", "{}")
        self.write("LICENSE-DATA", "本许可适用于 data/ 与 reports/。")
        check = pa.check_license_scope(self.root)
        self.assertEqual(check.status, "RISK")
        self.assertIn("workbench/reference", check.detail)

    def test_covered_passes(self):
        (self.root / "workbench/reference").mkdir(parents=True)
        self.write("workbench/reference/admission.json", "{}")
        self.write("LICENSE-DATA", "本许可适用于 data/、reports/ 与 workbench/reference 目录。")
        self.assertEqual(pa.check_license_scope(self.root).status, "PASS")

    def test_missing_license_fails(self):
        self.assertEqual(pa.check_license_scope(self.root).status, "FAIL")


class RunnerTest(unittest.TestCase):
    # 用 upload-limit 作夹具：它不扫全仓，测试才不至于每次跑几十秒
    FAST = "upload-limit"

    def test_run_returns_structured_checks(self):
        checks = pa.run(only={self.FAST})
        self.assertEqual([c.id for c in checks], [self.FAST])
        for check in checks:
            self.assertIn(check.status, {"PASS", "RISK", "FAIL", "SKIP"})
            self.assertTrue(check.title)

    def test_only_skips_other_factories(self):
        """--only 必须在调用前过滤，否则"只跑一项"会连带触发全仓扫描与 app 探针。"""
        calls = []
        original = pa.ALL_CHECKS

        def boom(_root):
            calls.append("called")
            return pa.Check("boom", "boom")

        try:
            pa.ALL_CHECKS = (boom,)
            self.assertEqual(pa.run(only={self.FAST}), [])
        finally:
            pa.ALL_CHECKS = original
        self.assertEqual(calls, [])

    def test_main_check_returns_int(self):
        self.assertIn(pa.main(["--check", "--only", self.FAST]), (0, 1))

    def test_json_output_is_parseable(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            pa.main(["--json", "--only", self.FAST])
        payload = json.loads(buffer.getvalue())
        self.assertIn("counts", payload)
        self.assertEqual(len(payload["checks"]), 1)

    def test_unknown_only_filter_yields_nothing(self):
        self.assertEqual(pa.run(only={"does-not-exist"}), [])


@unittest.skipUnless(os.environ.get("PRIVACY_AUDIT_STRICT") == "1",
                     "严格断言：需在 app.py 修复 Origin / JSON 处理之后启用")
class AppGuardStrictTest(unittest.TestCase):
    def test_write_without_origin_is_rejected(self):
        self.assertEqual(pa.check_origin_guard(pa.ROOT).status, "PASS")

    def test_invalid_json_is_4xx(self):
        self.assertEqual(pa.check_json_error_path(pa.ROOT).status, "PASS")


if __name__ == "__main__":
    unittest.main()