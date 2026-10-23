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

用法::

    python -m workbench.tools.make_teleprompter
    python -m workbench.tools.make_teleprompter --out 我的提词稿.txt
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "workbench/aic-submission/演示视频脚本.md"
DEFAULT_OUT = ROOT / "workbench/aic-submission/录制提词稿.txt"

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


def main() -> int:
    ap = argparse.ArgumentParser(description="生成演示视频提词稿")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    if not SCRIPT.is_file():
        print(f"找不到 {SCRIPT}")
        return 1
    shots = parse(SCRIPT.read_text(encoding="utf-8"))
    if not shots:
        print("脚本里没有解析到分镜行")
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
    print(f"写出 {out.relative_to(ROOT)}：{len(shots)} 个镜头 / "
          f"{total // 60} 分 {total % 60} 秒 / {len(text)} 字符")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
