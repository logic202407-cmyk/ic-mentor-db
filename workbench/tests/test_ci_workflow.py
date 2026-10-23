"""CI 配置的测试：确保「工作台校验」job 存在且覆盖当前作品。

为什么需要这条
--------------
仓库原有 CI 只校验早期 IC 专题（mentor_ranked.json、reports/*.html、邮箱），
**对当前作品（workbench 工作台 + AIC 提交材料）一项都不查**。
那种"绿了但没检查交付物"的 CI 比没有 CI 更危险——它给人虚假的安全感。

本测试钉住：新增的 workbench job 必须在，且必须是**零重依赖**的检查，
这样它不会因为安装 fastembed/onnxruntime 而在 CI 上变成脆弱的红 X。
"""

from __future__ import annotations

import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
WORKFLOW = ROOT / ".github/workflows/validate.yml"


class WorkflowTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.jobs = cls.data["jobs"]

    def test_workflow_is_valid_yaml(self):
        self.assertIn("jobs", self.data)

    def test_legacy_job_still_present(self):
        self.assertIn("validate", self.jobs)

    def test_workbench_job_present(self):
        self.assertIn("workbench", self.jobs,
                      "缺少覆盖当前作品的 CI job：旧 job 只校验早期 IC 专题")

    def test_workbench_job_checks_the_submission(self):
        text = yaml.safe_dump(self.jobs["workbench"], allow_unicode=True)
        for needle in (
            "workbench.tools.encoding_audit",
            "workbench.tools.check_readme_badges",
            "workbench.tools.check_report_sync",
            "workbench.tools.check_pdf_limits",
            "compileall",
        ):
            self.assertIn(needle, text, f"workbench job 缺少检查：{needle}")

    def test_workbench_job_installs_what_checks_import(self):
        """依赖必须覆盖检查真正 import 的东西。

        CI 曾只装 pypdf，而 README 徽章检查会经 catalog.coverage() -> public_research
        -> rom bs4 import BeautifulSoup，于是 CI 报
        ModuleNotFoundError: No module named 'bs4'（本地 venv 装了所以看不出来）。
        """
        text = yaml.safe_dump(self.jobs["workbench"], allow_unicode=True)
        self.assertIn("pypdf", text)
        self.assertIn("requests", text)
        # 修法不是"多装一个包"，而是把 bs4 改成惰性导入（读已存档案不需要 HTML 解析器）。
        # 这里断言 CI 不该再装 bs4；若变红，说明 public_research 又出现了模块级导入。
        self.assertNotIn("beautifulsoup4", text, "bs4 已惰性化，CI 不应再安装它")

    def test_workbench_job_stays_lightweight(self):
        # 不得在 CI 里安装 fastembed / onnxruntime（几百 MB，容易变红 X）
        text = yaml.safe_dump(self.jobs["workbench"], allow_unicode=True)
        for heavy in ("fastembed", "onnxruntime"):
            self.assertNotIn(heavy, text, f"workbench job 不应安装 {heavy}")

    def test_workbench_job_does_not_need_secrets(self):
        text = yaml.safe_dump(self.jobs["workbench"], allow_unicode=True)
        self.assertNotIn("secrets.", text)

    def test_triggers_on_push_to_main(self):
        trig = self.data.get("on") or self.data.get(True)
        self.assertIn("push", trig)

    def test_job_count_is_two(self):
        self.assertEqual(set(self.jobs), {"validate", "workbench"})


if __name__ == "__main__":
    unittest.main()
