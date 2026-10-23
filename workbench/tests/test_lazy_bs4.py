"""验证并钉住：读已存档案不需要 HTML 解析器（bs4）。

背景：`catalog.coverage()` 只是数档案，却因为 `public_research` 在模块层
`from bs4 import BeautifulSoup` 而必须有 bs4。这导致：
- CI 必须装 beautifulsoup4 才能跑一个纯计数检查（本轮 CI 红的真因）；
- 应用启动白白 import 一个 HTML 解析器。

改动：把 bs4 的两处导入挪进真正解析 HTML 的函数（`parse_page`、`admission_notices`）。
本测试用子进程 + 导入拦截器证明"没有 bs4 也能算出覆盖率"。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

PROBE = r'''
import sys

class Blocker:
    """拦掉 bs4，模拟"没装 beautifulsoup4"的环境。"""
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "bs4" or fullname.startswith("bs4."):
            raise ImportError("bs4 blocked for test")
        return None

sys.meta_path.insert(0, Blocker())

from workbench import catalog
cov = catalog.coverage()
print("OK", cov["total_records"], cov["public_records"])
'''


class NoBs4Tests(unittest.TestCase):

    def test_coverage_works_without_bs4(self):
        proc = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(
            proc.returncode, 0,
            "没有 bs4 时 catalog.coverage() 失败了——说明读档案仍依赖 HTML 解析器：\n"
            + (proc.stdout or "") + (proc.stderr or ""),
        )
        self.assertIn("OK", proc.stdout or "")
        self.assertIn("15719", proc.stdout or "")

    def test_bs4_is_not_imported_at_module_level(self):
        """源码层面确认：模块顶部不得再出现 from bs4 import。"""
        source = (ROOT / "workbench/public_research.py").read_text(encoding="utf-8")
        head = source.splitlines()[:80]
        top_imports = [ln.strip() for ln in head
                       if ln.startswith(("import ", "from ")) and "bs4" in ln]
        self.assertEqual(top_imports, [],
                         f"public_research 模块级仍导入 bs4：{top_imports}")

    def test_bs4_still_importable_where_needed(self):
        """惰性导入位置仍然正确：两个解析函数里各自 import。"""
        source = (ROOT / "workbench/public_research.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("from bs4 import BeautifulSoup"), 2,
                                "parse_page / admission_notices 里应保留惰性导入")


if __name__ == "__main__":
    unittest.main()
