"""上传前验收：一条命令跑完全部关卡，给出通过/失败清单。

为什么需要
----------
这个仓库的验证分散在七个地方（Python 测试、前端测试、公开前审计、文档数字一致性、
报告三件产物同步、来源红线、机构分布），此前靠临时脚本逐个跑，**漏跑一道就可能带着
问题提交**——本项目已经真实发生过两次：报告数字过期、主交付物 PDF 落后于 Markdown。

合成一条命令的价值不在省事，而在**不会有遗漏**。

用法::

    python -m workbench.tools.acceptance              # 全部关卡
    python -m workbench.tools.acceptance --skip-ui    # 没启动服务时跳过界面冒烟
    python -m workbench.tools.acceptance --json out.json

退出码：全部通过 0，否则 1。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, f"超时（>{timeout}s）"
    except FileNotFoundError as exc:
        return 127, f"命令不存在：{exc}"


def tail(text: str, n: int = 3) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return " | ".join(lines[-n:]) if lines else "(无输出)"


def main() -> int:
    ap = argparse.ArgumentParser(description="上传前验收")
    ap.add_argument("--skip-ui", action="store_true", help="跳过需要服务的界面冒烟")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    checks: list[dict] = []

    def check(name: str, cmd: list[str], ok_hint: str = "", timeout: int = 900) -> None:
        started = time.time()
        code, out = run(cmd, timeout=timeout)
        checks.append({
            "名称": name,
            "通过": code == 0,
            "耗时秒": round(time.time() - started, 1),
            "命令": " ".join(cmd),
            "输出尾部": tail(out, 2),
        })

    check("Python 测试", [PY, "-m", "unittest", "discover", "-s", "workbench/tests"])
    check("前端测试", ["node", "--test", "workbench/tests/test_ui_races.cjs",
                      "workbench/tests/test_research_ui.cjs"])
    check("公开前审计", ["node", "tools/audit_prepublish.mjs"])
    check("文档数字一致性", ["node", "tools/check_doc_numbers.mjs"])
    # README 徽章是评审第一眼看到的东西，却只是写死的字符串，没人会去更新。
    # 实测曾写着「321 项测试 / 14,271 条记录」，而实际是 707 / 15,719。
    check("README 徽章数字", [PY, "-m", "workbench.tools.check_readme_badges"])
    # 编码体检：批处理/依赖清单被 cmd.exe、pip 用区域编码读取，
    # 这些文件若含中文或 BOM，别人装环境时会直接失败。
    check("编码体检（被工具读取的文件）", [PY, "-m", "workbench.tools.encoding_audit"])
    check("报告三件产物同步", [PY, "-m", "workbench.tools.check_report_sync"])
    check("来源红线", [PY, "-m", "workbench.tools.audit_new_sources"])
    check("机构分布审计", [PY, "-m", "workbench.tools.distribution_audit"])
    # 赛题要求技术报告 PDF 正文 ≤15 页、≤10 MB。页数会随着往报告里加内容而悄悄超限
    # （本项目真实发生过：加了两章 AI 实证后从 15 页涨到 18 页），必须有一道显式检查。
    check("报告页数与大小", [PY, "-m", "workbench.tools.check_pdf_limits"])
    # 版式体检：逐页竖向填充度，抓"整块内容被推到下页"造成的半页空白。
    # 报告卡在 15 页上限，白吃页数的排版浪费必须有工具兜住。
    check("报告版式体检", [PY, "-m", "workbench.tools.pdf_layout_check"])
    # AI 产物必须同步进仓库副本，否则 clone 后「AI 建议」区块会消失。
    check("AI 产物已同步进仓库", [PY, "-m", "workbench.tools.publish_ai_artifacts", "--check"])
    # 档案打包必须与本地档案一致，否则 clone 后论文/招生记录会是空的。
    check("档案打包已同步", [PY, "-m", "workbench.tools.pack_research_bundle", "--check"])

    if not args.skip_ui:
        check("界面运行时冒烟", [PY, "-m", "workbench.tools.ui_smoke"], timeout=300)
        check("录制前就绪（演示资料/语义检索缓存/深链）",
              [PY, "-m", "workbench.tools.recording_readiness"], timeout=600)

    passed = sum(1 for c in checks if c["通过"])
    lines = ["=" * 60, f"上传前验收：{passed}/{len(checks)} 项通过", "=" * 60]
    for c in checks:
        mark = "PASS" if c["通过"] else "FAIL"
        lines.append(f"[{mark}] {c['名称']:<16} {c['耗时秒']:>6.1f}s")
        if not c["通过"]:
            lines.append(f"       命令：{c['命令']}")
            lines.append(f"       输出：{c['输出尾部']}")
    if passed == len(checks):
        lines.append("\n全部通过。可以提交。")
    else:
        lines.append(f"\n有 {len(checks) - passed} 项未通过，请先修复再提交。")

    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))

    if args.json:
        Path(args.json).write_text(
            json.dumps(checks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\n明细 -> {args.json}", file=sys.stderr)

    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
