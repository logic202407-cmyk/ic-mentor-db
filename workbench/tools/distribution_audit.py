"""分布达标审计：逐个工学学科算「最大单一机构占比」，列出未达标的学科与还差多少。

为什么需要这个工具
------------------
项目对"学科能否用于跨校比较"有一条硬标准：**最大单一机构占比 < 60%**。
此前这条标准靠临时脚本口算，容易出错——0801 力学就出过一次：我按"再补一所学校"
去做，结果补入量超过存量，主导校从上海交大换成了北京大学（73.3%），反而仍未达标。

这个工具把标准固化成一条命令，并在报告里给出**还差多少人**：

    还需补入 N，使 max(原主导数, N) / (原总数 + N) < 0.60

用法::

    python -m workbench.tools.distribution_audit            # all
    python -m workbench.tools.distribution_audit --only-failing
    python -m workbench.tools.distribution_audit --json out.json

'口径：只统计 38 个工学一级学科（`catalog.disciplines()` 的 engineering 项）。

**注意**：本工具按记录的 ``first_level_discipline`` 字段归科，而 HTTP 接口
（``/api/catalog/institutions``）按 ``discipline_assignments`` 归科，两者在少数跨学科
记录上会差几条（例如 0835 在接口里是 104 条、本工具是 97 条）。**对外引用请以接口为准**；
本工具的用途是"找出哪个学科还差多少人"，不是对外报数。

**注意**：本工具按记录的 ``first_level_discipline`` 字段归科，而 HTTP 接口
（``/api/catalog/institutions``）按 ``discipline_assignments`` 归科，两者在少数跨学科
记录上会差几条（例如 0835 在接口里是 104 条、本工具是 97 条）。**对外引用请以接口为准**；
本工具的用途是"找出哪个学科还差多少人"，不是对外报数。'
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from workbench import catalog  # noqa: E402

THRESHOLD = 0.60


def _discipline_of(profile: dict) -> str:
    return (profile.get("first_level_discipline") or "").strip()


def collect() -> list[dict]:
    pairs, _by_id, _raw, _net = catalog.static_catalog()
    engineering = {
        d["name"] for d in catalog.disciplines(None) if d.get("engineering")
    }
    per: dict[str, Counter] = {}
    for p in pairs:
        disc = _discipline_of(p)
        if disc and disc in engineering:
            per.setdefault(disc, Counter())[p.get("institution") or "未标注"] += 1

    rows = []
    for disc, counts in per.items():
        total = sum(counts.values())
        top_inst, top_n = counts.most_common(1)[0]
        share = top_n / total if total else 0.0
        rows.append({
            "discipline": disc,
            "total": total,
            "institutions": len(counts),
            "top_institution": top_inst,
            "top_count": top_n,
            "share": round(share, 4),
            "passes": share < THRESHOLD,
            "gap": needed_from_a_third_school(total, top_n),
        })
    rows.sort(key=lambda r: (-r["share"], -r["total"]))
    return rows


def needed_from_a_third_school(total: int, top_n: int) -> int:
    """要让 max(top_n, N)/(total+N) < 0.60，最少要补多少位（N 视作来自另一所学校）。

    若补入量最终小于 top_n，条件化为 ``top_n / (total + N) < 0.6``；
    若补入量超过 top_n，则 ``N / (total + N) < 0.6``。两段取可行的最小整数。

    **注意还有上限**：当补入量超过原主导数后，新校自身也受 60% 约束，即
    ``N / (total + N) < 0.6`` 推出 ``N < 1.5 * total``。所以可行区间是
    ``[本函数返回值, floor(1.5 * total)]``，**不是"越多越好"**。

    例如 0807 动力（total=103、top=101）的可行区间是 **[66, 154]**：
    补 65 得 60.12% 不达标；补 132 得 56.17% 达标；补 155 又回到 60.08% 不达标。

    这一点在实践中否掉了两个候选：上海理工大学 161 人（60.98%，超上限）、
    华北电力大学 56 人（不足下限）。两所都能抓到数据，但补完仍不成立。
    """
    if total <= 0:
        return 0
    if top_n / total < THRESHOLD:
        return 0
    # 第一段：补入量 <= top_n 时，只需 top_n/(total+N) < 0.6
    n_need = math.floor(top_n / THRESHOLD - total) + 1
    if n_need <= top_n:
        return n_need
    # 第二段：补入量 > top_n 时，需要 N/(total+N) < 0.6  →  N < 1.5*total
    n2 = top_n + 1
    while n2 / (total + n2) >= THRESHOLD:
        n2 += 1
    return n2


def format_table(rows: list[dict], all_rows: list[dict] | None = None) -> str:
    lines = [
        f"分布达标审计（标准：最大单一机构占比 < {THRESHOLD:.0%}）",
        "",
        f"{'学科':<24}{'条目':>6}{'机构':>5}{'最大占比':>9}{'状态':>6}{'还需补':>8}  最大机构",
    ]
    for r in rows:
        lines.append(
            f"{r['discipline']:<24}{r['total']:>6}{r['institutions']:>5}"
            f"{r['share']:>8.1%}{'达标' if r['passes'] else '未达标':>7}"
            f"{('—' if r['passes'] else r['gap']):>8}  {r['top_institution'][:16]}"
        )
    total_rows = all_rows if all_rows is not None else rows
    failing = [r for r in total_rows if not r["passes"]]
    lines += [
        "",
        f"合计 {len(total_rows)} 个工学学科，达标 {len(total_rows) - len(failing)}，未达标 {len(failing)}",
    ]
    if failing:
        lines.append("未达标学科：" + "、".join(
            f"{r['discipline'].split()[0]}({r['share']:.0%}, 需+{r['gap']})" for r in failing))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="工学学科机构分布达标审计")
    ap.add_argument("--only-failing", action="store_true", help="只列未达标学科")
    ap.add_argument("--json", type=str, default="", help="把明细写入该 JSON 路径")
    args = ap.parse_args()

    rows = collect()
    shown = [r for r in rows if not r["passes"]] if args.only_failing else rows
    text = format_table(shown, rows)
    try:
        print(text)
    except UnicodeEncodeError:  # Windows GBK 控制台
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))

    if args.json:
        Path(args.json).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\n明细 -> {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
