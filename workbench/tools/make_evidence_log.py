"""Regenerate the AIC evidence log with clean, reproducible command output.

Runs the three verification commands, strips PowerShell's stderr artefacts
(System.Management.Automation.RemoteException lines that unittest emits because
it writes progress dots to stderr), and writes a single UTF-8 log.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re
import subprocess

ROOT = pathlib.Path(".").resolve()
PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "workbench" / "aic-submission" / "evidence" / "测试与审计记录.md"

NOISE = re.compile(r"^\s*System\.Management\.Automation\.RemoteException\s*$")
CATEGORY = re.compile(r"^\s*(所在位置|CategoryInfo|FullyQualifiedErrorId|\+)\s")


def run(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    kept = [ln for ln in text.splitlines() if not NOISE.match(ln) and not CATEGORY.match(ln)]
    return "\n".join(kept).strip()


def tail(text: str, n: int) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def main() -> int:
    py_out = run([str(PY), "-m", "unittest", "discover", "-s", "workbench/tests", "-v"])
    node_out = run(["node", "--test",
                    "workbench/tests/test_ui_races.cjs",
                    "workbench/tests/test_research_ui.cjs"])
    audit_out = run(["node", "tools/audit_prepublish.mjs"])

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [
        "# 测试与审计记录（佐证材料）",
        "",
        f"生成时间：{stamp}　｜　生成环境：本机 Windows，Python 3.12.7，Node.js 24.13.1",
        "",
        "本文件由 `workbench/tools/make_evidence_log.py` 生成，可重新运行核验。",
        "以下为三条命令的实际终端输出（已过滤 PowerShell 的 stderr 包装行）。",
        "",
        "## 1. Python 行为测试",
        "",
        "```",
        r"$ .\.venv\Scripts\python.exe -m unittest discover -s workbench\tests -v",
        tail(py_out, 6),
        "```",
        "",
        "## 2. 前端异步竞态测试",
        "",
        "```",
        r"$ node --test workbench\tests\test_ui_races.cjs workbench\tests\test_research_ui.cjs",
        tail(node_out, 9),
        "```",
        "",
        "## 3. 公开前审计",
        "",
        "```",
        r"$ node tools\audit_prepublish.mjs",
        tail(audit_out, 24),
        "```",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
