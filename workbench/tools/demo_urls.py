"""生成演示视频的录制 URL 清单：每个镜头一条可直接粘贴的地址。

为什么需要
----------
录视频时最怕现场点错、点慢、点不到想要的那条记录。详情页支持深链
``http://127.0.0.1:8765/?mentor=<导师ID>``，所以可以在录制前把每个镜头的地址
预先算好，切镜头时直接粘贴。

这份清单挑的是**真实目录里最有展示价值**的记录：

- 一条**有同名待核**的（展示 AI 建议区块的同名消歧部分）；
- 一条**有方向建议**且已过阈值的（展示方向补全部分）；
- 一条**个人主页是本人页**的（展示"导师主页"按钮）；
- 一条**主页是名录页**的（展示「所在名录页」标签，说明我们如实标注了这种情况）。

用法::

    python -m workbench.tools.demo_urls
    python -m workbench.tools.demo_urls --base http://127.0.0.1:8765 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from workbench import catalog, homepage_kind  # noqa: E402

SUG = Path(".workbench-data/direction-inference/suggestions.json")
REV = Path(".workbench-data/name-disambiguation/review.json")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(base: str) -> list[dict]:
    pairs, _by, _raw, _net = catalog.static_catalog()
    by_id = {p["id"]: p for p in pairs}

    sug = load_json(SUG) or {}
    applied = {
        s["id"]: s for s in (sug.get("suggestions") or [])
        if s.get("apply") and s.get("id") in by_id
    }
    review = load_json(REV) or []
    reviewed: dict[str, dict] = {}
    for pair in review:
        for side in ("a", "b"):
            mid = (pair.get(side) or {}).get("id")
            if mid in by_id:
                reviewed.setdefault(mid, pair)

    shots: list[dict] = []

    # 镜头 7：同名待核（优先挑同时也有方向建议的）
    both = [mid for mid in reviewed if mid in applied]
    pick = both[0] if both else (next(iter(reviewed), None))
    if pick:
        p = by_id[pick]
        pair = reviewed[pick]
        shots.append({
            "shot": "镜头 7：AI 建议（同名待核部分）",
            "url": f"{base}/?mentor={pick}",
            "name": p.get("name"),
            "institution": p.get("institution"),
            "why": f"同名待核：{pair.get('verdict')} · 相似度 {pair.get('emb')}",
        })

    # 镜头 7 续：方向建议
    if applied:
        pick = next(iter(applied))
        p = by_id[pick]
        item = applied[pick]
        shots.append({
            "shot": "镜头 7：AI 建议（方向补全部分）",
            "url": f"{base}/?mentor={pick}",
            "name": p.get("name"),
            "institution": p.get("institution"),
            "why": f"方向建议 {item.get('suggested')} · {item.get('score')} · {item.get('method')}",
        })

    # 镜头 5：普通导师档案（主页是本人页）
    personal = next(
        (p for p in pairs if homepage_kind.kind_of(p.get("homepage") or "") == "personal"),
        None,
    )
    if personal:
        shots.append({
            "shot": "镜头 5：导师档案（主页为本人页，按钮显示「导师主页」）",
            "url": f"{base}/?mentor={personal['id']}",
            "name": personal.get("name"),
            "institution": personal.get("institution"),
            "why": "homepage_kind=personal",
        })

    # 可选的"所在名录页"演示
    roster = next(
        (p for p in pairs if homepage_kind.kind_of(p.get("homepage") or "") == "roster"),
        None,
    )
    if roster:
        shots.append({
            "shot": "可选：主页是名录页时按钮显示「所在名录页」",
            "url": f"{base}/?mentor={roster['id']}",
            "name": roster.get("name"),
            "institution": roster.get("institution"),
            "why": "homepage_kind=roster（如实标注，不冒充个人页）",
        })

    shots.append({
        "shot": "镜头 1/3/4：主页（姓名路径与学科路径）",
        "url": f"{base}/",
        "name": "",
        "institution": "",
        "why": "首屏",
    })
    return shots


def main() -> int:
    ap = argparse.ArgumentParser(description="生成演示视频录制 URL 清单")
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    shots = build(args.base)
    lines = ["# 录制 URL 清单（按镜头）", ""]
    for s in shots:
        lines.append(f"## {s['shot']}")
        lines.append("")
        lines.append(f"`{s['url']}`")
        lines.append("")
        who = " · ".join(x for x in (s.get("name"), s.get("institution")) if x)
        if who:
            lines.append(f"- 记录：**{who}**")
        if s.get("why"):
            lines.append(f"- 用途：{s['why']}")
        lines.append("")
    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))

    if args.json:
        Path(args.json).write_text(
            json.dumps(shots, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\n明细 -> {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
