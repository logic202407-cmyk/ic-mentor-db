"""界面冒烟：用无头浏览器打开导师详情页，检查运行时错误与关键区块是否真的渲染。

为什么需要
----------
前端代码压缩成一行，`new Function(...)` 只能查**语法**。本项目真实踩过两次：

1. 在 `renderDossier()` 里写了该作用域未声明的变量，`ReferenceError` 在运行时抛出，
   **函数后半段全不执行**——AI 建议区块不显示，侧栏还把报错文本显示给用户；
2. AI 区块容器放错位置，显示在导师姓名之前（先看到建议、才看到是谁）。

这两种错**只有真跑起来才看得见**。所以这个工具用 Edge 无头模式打开真实页面、
把渲染后的 DOM 取回来做断言。

前置：本机服务已在 `http://127.0.0.1:8765` 运行。

用法::

    python -m workbench.tools.ui_smoke                    # 自动挑一个有 AI 建议的导师
    python -m workbench.tools.ui_smoke --mentor <id>
    python -m workbench.tools.ui_smoke --url http://127.0.0.1:8765

退出码：全部通过 0，否则 1。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

RUNTIME_ERROR_TEXT = re.compile(
    r"is not defined|is not a function|Cannot read propert|undefined is not"
)


def find_edge() -> str:
    for path in EDGE_CANDIDATES:
        if Path(path).is_file():
            return path
    raise SystemExit("找不到 Edge，无法做界面冒烟")


def dump_dom(url: str, timeout: int = 60) -> str:
    edge = find_edge()
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "profile"
        proc = subprocess.run(
            [
                edge,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=12000",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    if not proc.stdout:
        raise SystemExit(f"取不到 DOM（returncode={proc.returncode}）")
    return proc.stdout


def pick_mentor() -> str:
    """挑一位既有方向建议、又有同名待核的记录——这样 AI 区块内容最全。"""
    sug = Path(".workbench-data/direction-inference/suggestions.json")
    rev = Path(".workbench-data/name-disambiguation/review.json")
    applied = set()
    if sug.is_file():
        data = json.loads(sug.read_text(encoding="utf-8"))
        applied = {s["id"] for s in data.get("suggestions") or [] if s.get("apply")}
    if rev.is_file() and applied:
        pairs = json.loads(rev.read_text(encoding="utf-8"))
        for pair in pairs:
            for side in ("a", "b"):
                mid = (pair.get(side) or {}).get("id")
                if mid in applied:
                    return mid
    if applied:
        return sorted(applied)[0]
    raise SystemExit("没有可用的 AI 建议产物，先跑 infer_directions.py")


def main() -> int:
    ap = argparse.ArgumentParser(description="界面运行时冒烟")
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--mentor", default="")
    args = ap.parse_args()

    checks: list[tuple[str, bool, str]] = []

    # 1) 落地页
    home = dump_dom(args.base + "/")
    checks.append(("落地页可渲染", "找导师" in home, ""))
    checks.append(("落地页无运行时错误", not RUNTIME_ERROR_TEXT.search(home), ""))

    # 2) 导师详情页（含 AI 建议区块）
    mentor_id = args.mentor or pick_mentor()
    dom = dump_dom(f"{args.base}/?mentor={mentor_id}")

    clean = not RUNTIME_ERROR_TEXT.search(dom)
    checks.append(("详情页无运行时错误（未定义变量等）", clean,
                   "" if clean else RUNTIME_ERROR_TEXT.search(dom).group(0)))
    checks.append(("详情页显示了导师姓名", "mentorTitle" in dom, ""))
    checks.append(("导出资料链接在", 'id="reportLink"' in dom, ""))

    # AI 区块：容器存在、且不是 hidden
    container = re.search(r'<div id="aiHints"([^>]*)>', dom)
    checks.append(("AI 建议容器存在", container is not None, ""))
    if container:
        attrs = container.group(1) or ""
        hidden = "hidden" in attrs.split()
        checks.append(("AI 建议区块已渲染（未 hidden）", not hidden, attrs.strip()))
        body_start = container.end()
        tail = dom[body_start:body_start + 4000]
        checks.append(("AI 区块含『待复核』", "待复核" in tail, ""))
        checks.append(("AI 区块含免责说明", "不构成事实" in tail, ""))

    # 3) 无「d is not defined」这种半渲染残局
    # 成功文案在 2026-10 改为「已打开导师档案」；两种写法都认，并把「无异常」单独判一次。\n    status_ok = ("已打开导师档案" in dom) or ("已打开导师资料" in dom)\n    checks.append(("侧栏状态为成功文案而非报错", status_ok, ""))

    ok = all(passed for _name, passed, _detail in checks)
    print(f"界面冒烟：mentor={mentor_id}")
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        suffix = f"  [{detail}]" if detail else ""
        print(f"  {mark}  {name}{suffix}")
    print("结果:", "ALL PASS" if ok else "有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
