"""仓库卫生：源码里不得出现维护者本机的绝对路径。

为什么需要这条
--------------
`tools/process_user_images.py` 曾经写死了两位维护者的本机路径：

    C:\\Users\\<某个 Windows 用户名>\\.gemini\\...\\.user_uploaded
    D:\\ic-mentor-db\\workbench\\web\\assets\\visuals

第二条违反本项目「脚本以自身位置解析仓库根目录、不含硬编码绝对路径」的约定（克隆到别处就跑不了），
第一条更糟——它把维护者的**本机用户目录名**泄进了公开仓库。两者都不会让任何测试变红、也不会让
CI 报错，属于「只要没人看就一直在那里」的问题，所以用一条扫描钉住。

扫描范围与判据
--------------
- 只看**代码文件**（.py/.mjs/.js/.cjs/.cmd/.ps1）。文档里出现示例路径是合理的（例如
  DISCLAIMER 讲「不要把本机路径写进产物」时必然会举例），代码里没有正当理由。
- 只认「用户主目录」形态：`<盘符>:\\Users\\<名字>`、`/home/<名字>/`、`/Users/<名字>/`。
  仓库内的相对路径、`C:\\path\\to\\...` 这类占位符不算。
- 本文件自身被排除：它必然要写出被禁的形态才能描述规则。
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SELF = pathlib.Path(__file__).resolve()
CODE_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".cmd", ".ps1"}

# 用分段拼装，避免这份规则自己命中自己。
_USER_DIR = re.compile(
    r"[A-Za-z]:\\Users\\[^\\\s\"']+"              # C:\Users\name
    r"|(?<![\w.])/home/[^/\s\"']+"                # /home/name
    r"|(?<![\w.])/Users/[^/\s\"']+"               # /Users/name
)


def tracked_code_files() -> list[pathlib.Path]:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if proc.returncode != 0:  # 非 git 检出（例如导出的压缩包）时退回全盘遍历
        return [p for p in ROOT.rglob("*") if p.suffix in CODE_SUFFIXES]
    out = []
    for rel in proc.stdout.split("\0"):
        if not rel.strip():
            continue
        path = ROOT / rel
        if path.suffix in CODE_SUFFIXES and path.is_file():
            out.append(path)
    return out


class AbsolutePathTests(unittest.TestCase):

    def test_no_maintainer_home_directory_in_code(self):
        offenders: list[str] = []
        for path in tracked_code_files():
            if path.resolve() == SELF:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in _USER_DIR.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line} -> {match.group(0)}")
        self.assertEqual(
            offenders, [],
            "源码里出现了维护者本机的用户目录路径（克隆到别人机器上会失效，\n"
            "并且会把本机用户名泄进公开仓库）。改为相对仓库根目录或由参数/环境变量传入：\n  "
            + "\n  ".join(offenders))

    def test_scan_actually_sees_the_repo(self):
        """防止扫描器因为路径写错而「零命中即通过」。"""
        files = tracked_code_files()
        self.assertGreater(len(files), 100)
        self.assertTrue(any(p.name == "app.py" for p in files))


if __name__ == "__main__":
    unittest.main()