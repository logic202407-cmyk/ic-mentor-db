"""把本地重跑出来的 AI 产物同步进仓库副本（`workbench/reference/ai/`）。

为什么需要这个
--------------
AI 建议的产物默认写在 `.workbench-data/`（被 .gitignore 排除）。若不把它复制进仓库，
**评委 clone 后看不到「AI 建议（待复核）」区块**——而报告与视频都在展示它。
一份"演示里有、复现时没有"的功能，等于没有。

所以流程是：本地重跑推断 → `publish_ai_artifacts` 同步仓库副本 → 提交。

用法::

    python -m workbench.tools.infer_directions --validate 400 --apply
    python -m workbench.tools.publish_ai_artifacts
    python -m workbench.tools.publish_ai_artifacts --check   # 只比对是否落后

`--check` 会比对仓库副本与本地产物是否一致，不一致返回 1——可放进验收链，
避免"重跑了推断却忘了同步仓库"。
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PAIRS = (
    (ROOT / ".workbench-data/direction-inference/suggestions.json",
     ROOT / "workbench/reference/ai/direction_suggestions.json"),
    (ROOT / ".workbench-data/name-disambiguation/review.json",
     ROOT / "workbench/reference/ai/name_review.json"),
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="同步 AI 产物到仓库副本")
    ap.add_argument("--check", action="store_true", help="只比对，不写入")
    args = ap.parse_args()

    problems: list[str] = []
    lines: list[str] = []
    for src, dst in PAIRS:
        name = dst.name
        if not src.is_file():
            lines.append(f"  SKIP {name}（本地无产物，通常是没跑过推断）")
            continue
        if args.check:
            if not dst.is_file():
                problems.append(f"{name} 仓库副本缺失")
                lines.append(f"  FAIL {name}：仓库副本缺失")
                continue
            same = sha256(src) == sha256(dst)
            lines.append(f"  {'OK  ' if same else 'DIFF'} {name}"
                         f"（本地 {src.stat().st_size//1024} KB / 仓库 {dst.stat().st_size//1024} KB）")
            if not same:
                problems.append(f"{name} 与本地产物不一致，需重新 publish")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            text = dst.read_text(encoding="utf-8")
            dst.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
            lines.append(f"  WROTE {name}（{dst.stat().st_size//1024} KB）")

    header = "AI 产物同步" + ("（--check）" if args.check else "")
    text = "\n".join([header] + lines)
    if problems:
        text += "\n\n需要处理：" + "；".join(problems)
    text += "\n结论: " + ("一致" if not problems else "不一致")
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
