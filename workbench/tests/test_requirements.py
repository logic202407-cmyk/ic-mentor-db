"""依赖完整性测试：模块级 import 的第三方库必须在 requirements.txt 里声明。

为什么需要
----------
`requirements.txt` 原先只有 5 个包，**漏了 `numpy`**——而 `search.py` 在模块层
`import numpy`，`app.py` 又在模块层 `from .search import ...`。也就是说：
**依赖没声明、但应用启动就要它。**

实际安装时它靠 fastembed 的传递依赖带上了，所以本地一直正常——**这类问题在
"自己环境里什么都有"的情况下永远发现不了**，只有别人按 requirements 装一遍才暴露。

本测试把这件事钉死：只要新增一个模块级第三方 import 而没写进 requirements，这里就红。
"""

from __future__ import annotations

import ast
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PKG = ROOT / "workbench"
REQUIREMENTS = PKG / "requirements.txt"

# 导入名 -> 发行包名（两者不一致时映射）
IMPORT_TO_DIST = {
    "bs4": "beautifulsoup4",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "google": "protobuf",
}
# 由 fastapi/starlette 等一并安装，不单独声明
PROVIDED = {"starlette", "pydantic", "anyio", "click", "h11", "typing_extensions"}
# 惰性导入（函数体内）或仅开发工具使用的第三方库：运行工作台不需要。
LAZY_ONLY = {"pdfplumber"}          # collect_caas_catalog 的 main() 内惰性导入
# 仅开发者本地跑一次性工具的依赖，运行工作台不需要，CI 也不执行。
#   markdown          -> tools/make_aic_html.py（用系统 Python 跑）
#   PIL / playwright  -> tools/generate_visual_assets.py：顶层过程式脚本，一次性生成
#     workbench/web/assets/visuals/ 下的配图；它不被任何模块 import，也不在 CI 里跑，
#     所以不进 requirements.txt（其中 playwright 还要额外装浏览器内核）。
#     清单写在 requirements.txt 末尾的 Optional / development only 注释里。
DEV_ONLY = {"markdown", "PIL", "playwright"}


def declared() -> set[str]:
    names: set[str] = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0].strip()
        if name:
            names.add(name.lower())
    return names


def module_level_imports() -> dict[str, list[str]]:
    """返回 第三方模块名 -> 出现位置。只看模块级 import（函数体内的算惰性）。"""
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, list[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        if "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:  # 只看顶层
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in stdlib or name == "workbench":
                    continue
                found.setdefault(name, []).append(f"{path.relative_to(ROOT)}")
    return found


class RequirementsTests(unittest.TestCase):

    def test_requirements_file_exists(self):
        self.assertTrue(REQUIREMENTS.is_file())

    def test_every_module_level_third_party_import_is_declared(self):
        have = declared()
        missing: list[str] = []
        for module, locations in module_level_imports().items():
            if module in PROVIDED or module in LAZY_ONLY or module in DEV_ONLY:
                continue
            dist = IMPORT_TO_DIST.get(module, module).lower()
            if dist not in have:
                missing.append(f"{module}（{dist}）← {', '.join(sorted(set(locations))[:3])}")
        self.assertEqual(missing, [], "以下模块级第三方依赖未写进 requirements.txt：\n  "
                                      + "\n  ".join(missing))

    def test_numpy_is_declared_explicitly(self):
        # numpy 曾只作为 fastembed 的传递依赖存在，应用却直接 import 它
        self.assertIn("numpy", declared(), "numpy 必须在 requirements.txt 里显式声明")

    def test_requirements_file_is_ascii_only(self):
        """requirements.txt 必须纯 ASCII。

        pip 用**系统区域编码**读这个文件（中文 Windows 上是 cp936/GBK）。
        写中文注释会让 pip install -r requirements.txt 直接
        UnicodeDecodeError 退出——本项目真实踩过：加了中文注释后 dry-run 立刻失败，
        而本地环境早已装好依赖，完全无感。
        """
        raw = REQUIREMENTS.read_bytes()
        offenders = [i for i, b in enumerate(raw) if b > 127]
        self.assertEqual(
            offenders, [],
            f'requirements.txt 含 {len(offenders)} 个非 ASCII 字节（首个偏移 {offenders[0] if offenders else -1}），'
            '中文 Windows 上 pip 会读不了',
        )

    def test_requirements_are_pinned(self):
        text = REQUIREMENTS.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.assertIn("==", line, f"依赖未锁版本：{line}")


if __name__ == "__main__":
    unittest.main()
