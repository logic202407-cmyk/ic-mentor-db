"""把本机实跑的评测产物整理成**随仓库提交**的只读副本（供 /eval 页消费）。

为什么要单独做一步
------------------
评测脚本的原始产物写在 ``.workbench-data/``（被 gitignore）。干净 clone 上没有这些
文件，于是「评测页」要么打不开，要么只能显示假数字。这里把**聚合指标**（不含逐人
姓名等原始记录）复制到 ``workbench/evaluation/``，让复现者不用先跑几十分钟模型也能
看到同一份结果；要复核数字时再按 ``how_to_reproduce`` 重跑即可。

只搬聚合结果，不搬个人数据
--------------------------
- 方向推断：只搬 Top-1/Top-3、分层、消融，以及条数；不搬逐人建议。
- 同名消歧：只搬指标、混淆矩阵、阈值曲线与**已公开在 evidence 文档里的**高危案例；
  不搬 review.json 的逐人待核清单。

用法::

    python -m workbench.tools.pack_eval_artifacts            # 生成/更新副本
    python -m workbench.tools.pack_eval_artifacts --check     # 只校验副本是否齐全
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / ".workbench-data"
OUT_DIR = ROOT / "workbench" / "evaluation"

DIRECTION_VALIDATION = DATA / "direction-inference" / "validation.json"
DIRECTION_ABLATION = DATA / "direction-inference" / "text_ablation.json"
DISAMBIG_DIR = DATA / "name-disambiguation"
DISAMBIG_EVAL = DISAMBIG_DIR / "evaluation.json"
DISAMBIG_LEGACY = DISAMBIG_DIR / "legacy_evaluation.json"
DISAMBIG_COMPARISON = DISAMBIG_DIR / "comparison.json"
DISAMBIG_RISK = DISAMBIG_DIR / "high_risk.json"
GOLD = OUT_DIR / "gold_pairs.json"

OUT_DIRECTION = OUT_DIR / "direction_validation.json"
OUT_DISAMBIG = OUT_DIR / "disambiguation_eval.json"

RISK_CASES = 12      # 与 evidence 文档里展示的条数保持一致


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def build_directions() -> dict:
    validation = _read(DIRECTION_VALIDATION)
    payload = {
        "schema": "mentor-workbench/direction-validation/v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "how_to_reproduce": "python -m workbench.infer_directions --validate 400 --ablate-text",
        "note": "指标由本机实跑产生；逐人建议在 .workbench-data，未随仓库提交。",
    }
    payload.update(validation)
    if DIRECTION_ABLATION.is_file():
        payload["text_ablation"] = _read(DIRECTION_ABLATION)
    return payload


def build_disambiguation() -> dict:
    evaluated = _read(DISAMBIG_EVAL)
    gold = _read(GOLD) if GOLD.is_file() else {}
    risk = _read(DISAMBIG_RISK) if DISAMBIG_RISK.is_file() else []
    payload = {
        "schema": "mentor-workbench/disambiguation-eval/v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "how_to_reproduce": "python -m workbench.disambiguate_names --evaluate --gold",
        "protocol": gold.get("protocol"),
        "description": gold.get("description"),
        "stats": evaluated.get("stats"),
        "primary": evaluated.get("primary"),
        "reviewed": evaluated.get("reviewed"),
        "supplementary": evaluated.get("supplementary"),
        "combined": evaluated.get("combined"),
        "gold_agreement": gold.get("agreement"),
        "risk_cases": risk[:RISK_CASES],
        "risk_total": len(risk),
        "legacy": _read(DISAMBIG_LEGACY) if DISAMBIG_LEGACY.is_file() else None,
        "comparison": _read(DISAMBIG_COMPARISON) if DISAMBIG_COMPARISON.is_file() else None,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="整理评测产物副本（供 /eval 页读取）")
    ap.add_argument("--check", action="store_true", help="只校验副本是否齐全")
    args = ap.parse_args(argv)

    if args.check:
        problems = []
        for path in (OUT_DIRECTION, OUT_DISAMBIG):
            if not path.is_file():
                problems.append(f"缺副本：{path.relative_to(ROOT)}")
                continue
            try:
                payload = _read(path)
            except ValueError as exc:
                problems.append(f"{path.name} 不是合法 JSON：{exc}")
                continue
            if not payload.get("how_to_reproduce"):
                problems.append(f"{path.name} 缺 how_to_reproduce")
        if problems:
            print("评测产物副本：不一致")
            for line in problems:
                print("  -", line)
            return 1
        print("评测产物副本：齐全")
        return 0

    missing = [p for p in (DIRECTION_VALIDATION, DISAMBIG_EVAL) if not p.is_file()]
    if missing:
        print("缺原始评测产物，请先跑对应评测：")
        for path in missing:
            print("  -", path.relative_to(ROOT))
        print("  python -m workbench.infer_directions --validate 400 --ablate-text")
        print("  python -m workbench.disambiguate_names --evaluate --gold")
        return 1

    directions = build_directions()
    disambiguation = build_disambiguation()
    _write(OUT_DIRECTION, directions)
    _write(OUT_DISAMBIG, disambiguation)
    print(f"写出 {OUT_DIRECTION.relative_to(ROOT)}"
          f"（验证 {directions.get('sampled')} 条）")
    print(f"写出 {OUT_DISAMBIG.relative_to(ROOT)}"
          f"（主指标 {disambiguation['primary']['labelled_pairs']} 对）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())