"""给 test_readme_badges 补 quotepath 回归测试。

CI 曾在「README 徽章与体积表」这一步红，本地却一直通过。
根因：`git ls-files` 默认把非 ASCII 路径转义成八进制（`core.quotepath=true`），
`启动.cmd` 变成 `"\\345\\220\\257..."`，匹配不到真实文件，文件数从 591 掉到 558。

我的本地 git 关过 quotepath，所以这个 bug **只在别人的环境里出现**。
本测试用环境变量强制打开 quotepath，验证统计结果不变。
"""

from __future__ import annotations

import os
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _with_quotepath(value: str):
    """构造强制 core.quotepath 的环境变量补丁。"""
    return patch.dict(os.environ, {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.quotepath",
        "GIT_CONFIG_VALUE_0": value,
    }, clear=False)


class QuotePathTests(unittest.TestCase):
    """核心命题：仓库里有非 ASCII 文件名时，统计结果不能被 git 的路径转义影响。"""

    def test_repo_has_non_ascii_paths(self):
        # 前提条件：这个仓库确实有中文文件名，否则本测试没有意义
        names = [p.name for p in ROOT.iterdir()]
        has_non_ascii = any(any(ord(c) > 127 for c in n) for n in names)
        self.assertTrue(has_non_ascii,
                        "仓库根目录应有中文文件名（启动.cmd 等），否则 quotepath 测试失去意义")

    def _measure(self, quotepath: str) -> tuple[int, float]:
        with _with_quotepath(quotepath):
            source = ROOT / "workbench/tools/check_readme_badges.py"
            ns: dict = {"__file__": str(source), "__name__": "probe"}
            exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), ns)
            return ns["tracked_size"]()

    def test_count_is_identical_with_quotepath_enabled(self):
        normal = self._measure("false")
        quoted = self._measure("true")
        self.assertEqual(
            normal[0], quoted[0],
            f"quotepath 打开后文件数从 {normal[0]} 变成 {quoted[0]}——"
            "说明统计依赖了本地 git 配置，在 CI / 别人的机器上会算错",
        )

    def test_size_is_identical_with_quotepath_enabled(self):
        normal = self._measure("false")
        quoted = self._measure("true")
        self.assertAlmostEqual(normal[1], quoted[1], places=1)

    def test_count_is_large_enough(self):
        count, _mb = self._measure("true")
        self.assertGreater(count, 400, f"跟踪文件数异常偏小：{count}")


if __name__ == "__main__":
    unittest.main()
