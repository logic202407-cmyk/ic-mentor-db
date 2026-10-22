"""编码体检的测试：那些"被外部程序读取"的文件不能用 UTF-8 中文。

本项目连续踩过三次同类错误：
- `*.cmd` 写成 UTF-8 → cmd.exe 用 OEM 码页解析，命令被切坏；
- `requirements.txt` 写中文注释 → pip 用系统区域编码读，UnicodeDecodeError；
- `.gitattributes` 带 BOM → git 不认行首 #，每次 clone 报警告。

这些文件的共同点是：**读它们的是程序，不是人**。
"""

from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BOM = b"\xef\xbb\xbf"


class BatchFileTests(unittest.TestCase):
    """cmd.exe 按 OEM 代码页解析批处理，中文会导致行被切断。"""

    def test_cmd_files_are_pure_ascii(self):
        offenders = []
        for path in ROOT.glob("*.cmd"):
            raw = path.read_bytes()
            bad = sum(1 for b in raw if b > 127)
            if bad:
                offenders.append(f"{path.name}（{bad} 个非 ASCII 字节）")
        self.assertEqual(offenders, [], "批处理必须是纯 ASCII：" + "; ".join(offenders))

    def test_launchers_exist(self):
        names = {p.name for p in ROOT.glob("*.cmd")}
        for required in ("启动.cmd", "停止.cmd"):
            self.assertIn(required, names, f"缺少启动脚本 {required}")


class RequirementsFileTests(unittest.TestCase):

    def test_requirements_is_pure_ascii(self):
        raw = (ROOT / "workbench/requirements.txt").read_bytes()
        bad = [i for i, b in enumerate(raw) if b > 127]
        self.assertEqual(bad, [],
                         f"requirements.txt 含 {len(bad)} 个非 ASCII 字节；"
                         "pip 用系统区域编码读取，中文注释会让安装直接失败")

    def test_requirements_has_no_bom(self):
        raw = (ROOT / "workbench/requirements.txt").read_bytes()
        self.assertFalse(raw.startswith(BOM))


class GitConfigTests(unittest.TestCase):
    """git 按字节解析这些文件；中文注释无害，BOM 才有害。"""

    def test_git_files_have_no_bom(self):
        for name in (".gitattributes", ".gitignore"):
            path = ROOT / name
            if not path.is_file():
                continue
            self.assertFalse(path.read_bytes().startswith(BOM),
                             f"{name} 带 BOM：会让行首 # 失效，注释被当成规则")


class AuditToolTests(unittest.TestCase):

    def test_audit_passes_on_repo(self):
        from workbench.tools.encoding_audit import main
        import contextlib
        import io
        import sys
        from unittest.mock import patch
        buffer = io.StringIO()
        with patch.object(sys, 'argv', ['encoding_audit']), contextlib.redirect_stdout(buffer):
            code = main()
        self.assertEqual(code, 0, buffer.getvalue())

    def test_rule_set_covers_the_three_known_offenders(self):
        from workbench.tools.encoding_audit import RULES
        patterns = {pattern for pattern, _kind, _why in RULES}
        for required in ("*.cmd", "workbench/requirements.txt", ".gitattributes"):
            self.assertIn(required, patterns)

    def test_rule_kinds_are_valid(self):
        from workbench.tools.encoding_audit import RULES
        for _pattern, kind, _why in RULES:
            self.assertIn(kind, {"ascii", "no-bom", "utf8"})


if __name__ == "__main__":
    unittest.main()
