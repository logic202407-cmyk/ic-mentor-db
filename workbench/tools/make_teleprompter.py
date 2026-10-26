"""从演示视频脚本生成「提词稿」纯文本，供录制时照着念。

为什么需要
----------
脚本里的旁白写在 Markdown 表格里（`| 镜头 | 时长 | 画面 | 旁白 |`）。录制时一边看表格
一边念很别扭：列宽会折行、画面提示和旁白混在一行里。

提词稿把每个镜头拆成：

    镜头 7   ｜ 2:10–2:55 ｜ 45 秒
    画面：导师档案页顶部「AI 建议（待复核）」区块 …
    ─────────────────────────────────────────
    这是 AI 在本作品里真正的作用：……
    ─────────────────────────────────────────

输入缺失时为什么跳过而不是报错
------------------------------
演示视频脚本与提词稿都是**参赛专用交付物**，已停止跟踪：干净 clone 上没有
`演示视频脚本.md`。那不是「生成失败」，而是「本来就不该有这个文件」。但跳过必须
**显式**：打印 `状态: SKIP — …未随仓库发布，已跳过` 并以 0 退出，绝不静默当作已生成。
需要把缺失当失败时用 ``--strict``。

用法::

    python -m workbench.tools.make_teleprompter
    python -m workbench.tools.make_teleprompter --out 我的提词稿.txt
    python -m workbench.tools.make_teleprompter --script 临时脚本.md --out 临时稿.txt
    python -m workbench.tools.make_teleprompter --strict   # 缺脚本即失败

退出码：写出提词稿返回 0；脚本缺失返回 0（显式 SKIP），加 ``--strict`` 时返回 1。
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "workbench/evaluation/records/演示视频脚本.md"
DEFAULT_OUT = ROOT / "workbench/evaluation/records/录制提词稿.txt"
SKIP_REASON = "未随仓库发布，已跳过"

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([0-9:–\-]+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
EMPH = re.compile(r"\*\*(.+?)\*\*")


def seconds_of(span: str) -> int:
    """把 '2:10–2:55' 换算成秒数，失败返回 0。"""
    parts = re.findall(r"(\d+):(\d+)", span)
    if len(parts) < 2:
        return 0
    a = int(parts[0][0]) * 60 + int(parts[0][1])
    b = int(parts[1][0]) * 60 + int(parts[1][1])
    return max(0, b - a)


def parse(text: str) -> list[dict]:
    shots = []
    for line in text.splitlines():
        # 先剥掉强调标记：有的分镜把时长写成 **2:10–2:55**，直接匹配会漏。
        cleaned = line.strip().replace('**', '')
        m = ROW.match(cleaned)
        if not m:
            continue
        number, span, scene, narration = m.groups()
        if not narration or narration.startswith("---"):
            continue
        shots.append({
            "no": int(number),
            "span": span,
            "seconds": seconds_of(span),
            "scene": EMPH.sub(r"\1", scene).replace("**", "").strip(),
            "narration": EMPH.sub(r"\1", narration).replace("**", "").strip(),
        })
    return shots


def _display(path: pathlib.Path) -> str:
    """仓库内路径显示相对路径；临时目录里的路径显示绝对路径（不因越界而崩）。"""
    try:
        return pathlib.Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return pathlib.Path(path).as_posix()


def _emit(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))


def skip_text(script: pathlib.Path) -> str:
    """缺输入时的显式 SKIP 说明。措辞必须让人一眼看出「没生成」。"""
    return "\n".join([
        "演示视频提词稿生成",
        "",
        f"  状态: SKIP — 演示视频脚本{SKIP_REASON}（没有生成提词稿）",
        f"    ⊘ 缺少 {_display(script)}",
        "  说明: 演示视频脚本与提词稿属参赛专用交付物，仓库已停止跟踪，",
        "        原件只保留在所有者本机；在持有原件的机器上重跑本命令即可生成。",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="生成演示视频提词稿")
    ap.add_argument("--script", default=str(SCRIPT), help="演示视频脚本（Markdown 表格）")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--strict", action="store_true",
                    help="脚本缺失时判为失败（默认显式跳过并返回 0）")
    args = ap.parse_args()

    script = pathlib.Path(args.script)
    if not script.is_file():
        if not args.strict:
            _emit(skip_text(script))
            return 0
        _emit(f"演示视频提词稿生成\n\n  ✗ 找不到 {_display(script)}")
        return 1

    shots = parse(script.read_text(encoding="utf-8"))
    if not shots:
        _emit("脚本里没有解析到分镜行")
        return 1

    total = sum(s["seconds"] for s in shots)
    lines = [
        "演示视频 · 提词稿",
        "",
        f"共 {len(shots)} 个镜头，旁白合计约 {total // 60} 分 {total % 60} 秒（不含停顿）。",
        "录制提示：每念完一个镜头停 1 秒，方便后期剪辑对齐。",
        "",
        "=" * 68,
        "",
    ]
    for s in shots:
        lines.append(f"镜头 {s['no']}   ｜ {s['span']} ｜ {s['seconds']} 秒")
        lines.append("")
        lines.append(f"【画面】{s['scene']}")
        lines.append("")
        lines.append("【旁白】")
        # 按句号断行，念起来更顺
        for chunk in re.split(r"(?<=[。！？])", s["narration"]):
            chunk = chunk.strip()
            if chunk:
                lines.append("    " + chunk)
        lines.append("")
        lines.append("-" * 68)
        lines.append("")

    text = "\n".join(lines)
    out = pathlib.Path(args.out)
    out.write_text(text, encoding="utf-8", newline="\n")
    _emit(f"写出 {_display(out)}：{len(shots)} 个镜头 / "
          f"{total // 60} 分 {total % 60} 秒 / {len(text)} 字符")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())