"""前端模板的静态防回归测试：专门盯住"作用域里没有的变量"这类错。

为什么需要
----------
修改压缩成一行的前端代码时，`new Function(...)` 只能检查**语法**，查不出**未定义变量**。
本项目真实踩过：在 `renderDossier()` 里写了 `d.homepage_kind`，而该函数只声明了
`const data=state.mentor, p=data.profile`——于是 `ReferenceError: d is not defined`
在运行时抛出，**该函数后半段全部不执行**：AI 建议区块不渲染、侧栏显示报错文本。

这类错只有真跑起来才看得见。这里用静态分析把已知的作用域约束钉住。
"""

from __future__ import annotations

import pathlib
import re
import unittest

DESK = pathlib.Path(__file__).resolve().parent.parent / "web" / "desk.html"


def read_desk() -> str:
    return DESK.read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    """取 `function <name>(...){...}` 的函数体（按花括号配平）。"""
    start = src.find(f"function {name}(")
    if start < 0:
        raise AssertionError(f"找不到函数 {name}")
    brace = src.find("{", start)
    depth = 0
    for i in range(brace, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace:i + 1]
    raise AssertionError(f"函数 {name} 花括号不配平")


class DeclaredScopeTests(unittest.TestCase):
    """每个被检查的函数里，只允许使用它自己声明过的局部变量名。"""

    def test_dossier_uses_data_not_d(self):
        """renderDossier 里只声明了 data/p，用 d 会 ReferenceError。"""
        body = function_body(read_desk(), "renderDossier")
        self.assertIn("const data=state.mentor", body)
        # 不应出现独立的 d. 引用（排除 data. 与 id. 之类）
        offenders = re.findall(r"(?<![A-Za-z0-9_$.])d\.", body)
        self.assertEqual(
            offenders, [],
            "renderDossier 内出现未声明的 d. 引用（应改用 data.）",
        )

    def test_ai_hints_uses_data_not_d(self):
        body = function_body(read_desk(), "renderAiHints")
        offenders = re.findall(r"(?<![A-Za-z0-9_$.])d\.", body)
        self.assertEqual(offenders, [], "renderAiHints 内出现未声明的 d. 引用")


class ContainerWiringTests(unittest.TestCase):
    """AI 建议区块的容器与调用必须同时存在，否则区块永远不显示。"""

    def test_container_exists_exactly_once(self):
        src = read_desk()
        self.assertEqual(src.count('<div id="aiHints"'), 1)

    def test_container_is_inside_basic_introduction(self):
        src = read_desk()
        dossier = src.find('<article id="dossier"')
        region = src.find('id="region-identity"')
        container = src.find('<div id="aiHints"')
        self.assertGreater(dossier, -1)
        self.assertGreater(region, dossier)
        self.assertGreater(container, region)
        self.assertLess(container, src.find('id="pane-identity"'))

    def test_render_ai_hints_is_called_on_open(self):
        src = read_desk()
        self.assertIn("renderAiHints(id)", src)

    def test_disclaimer_is_present_in_render(self):
        src = read_desk()
        body = function_body(src, "renderAiHints")
        self.assertIn("disclaimer", body)
        self.assertIn("待复核", body)


class ApiFieldTests(unittest.TestCase):
    """界面依赖的后端字段必须真的在返回里。"""

    def test_homepage_kind_field_is_returned(self):
        from workbench import catalog, homepage_kind
        pairs, _by, _raw, _net = catalog.static_catalog()
        dossier = catalog.dossier(pairs[0]["id"])
        self.assertIsNotNone(dossier)
        kind = homepage_kind.kind_of((dossier.get("profile") or {}).get("homepage") or "")
        self.assertIn(kind, {"roster", "personal", "none"})


if __name__ == "__main__":
    unittest.main()
