"""Regenerate the AIC evidence log with clean, reproducible command output.

Runs the three verification commands, strips PowerShell's stderr artefacts
(System.Management.Automation.RemoteException lines that unittest emits because
it writes progress dots to stderr), and writes a single UTF-8 log.

Why the log is still published while other AIC files are not
------------------------------------------------------------
`aic-submission/evidence/*.md` stays tracked: those are the evaluation /
audit records a reader needs to judge the work. The参赛专用 deliverables
(report md/html/pdf, video script, teleprompter) are no longer tracked.

Why this tool skips instead of crashing
---------------------------------------
It shells out to the local `.venv` interpreter and to Node — both of which only
exist on the owner's machine (CI and a clean clone have neither). Those missing
prerequisites are not "the log is wrong"; it just cannot be regenerated here.
Skipping must be **explicit**: it prints `状态: SKIP — …未随仓库发布，已跳过`-style
text and exits 0, and it must **not** overwrite the committed log with a
half-empty one. Use ``--strict`` to turn missing prerequisites into a failure.

Usage::

    python -m workbench.tools.make_evidence_log
    python -m workbench.tools.make_evidence_log --out 临时记录.md
    python -m workbench.tools.make_evidence_log --strict   # 本机缺前置即失败
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()
PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "workbench" / "aic-submission" / "evidence" / "测试与审计记录.md"
SKIP_REASON = "未随仓库发布，已跳过"

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


def missing_prerequisites(py: pathlib.Path) -> list[str]:
    """本机开发环境才有的前置：venv 解释器与 node。"""
    missing: list[str] = []
    if not pathlib.Path(py).is_file():
        missing.append(f"本机 Python 解释器 {pathlib.Path(py).as_posix()}")
    if shutil.which("node") is None:
        missing.append("Node.js（node 命令不在 PATH）")
    return missing


def _emit(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))


def skip_text(missing: list[str]) -> str:
    """缺前置时的显式 SKIP 说明：说明没重新生成，且已保留原文件。"""
    lines = [
        "证据日志生成",
        "",
        f"  状态: SKIP — 本机生成前置{SKIP_REASON}（本文件未重新生成，仍是上一次的真实记录）",
    ]
    lines += [f"    ⊘ 缺少 {item}" for item in missing]
    lines += [
        "  说明: 本工具依赖本机 .venv 与 Node.js，属录制/发布机专用流程；",
        "        干净 clone 与 CI 上没有这些前置，因此不改写已提交的证据日志。",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="重新生成 AIC 证据日志")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--strict", action="store_true",
                    help="缺前置时判为失败（默认显式跳过并返回 0）")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    missing = missing_prerequisites(PY)
    if missing:
        if not args.strict:
            _emit(skip_text(missing))
            return 0
        _emit(f"证据日志生成\n\n  ✗ 缺前置：" + "；".join(missing))
        return 1

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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())