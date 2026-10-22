"""全库来源红线审计：逐个已发现的来源模块，用离线快照重跑 parse，检查红线。

为什么单独做这个工具
--------------------
`SourceModuleContractTests` 管的是**契约**（有没有 SPECS、有没有快照、能不能解析）。
这个工具管的是**数据红线**，也就是"这条记录能不能入库"：

1. **姓名里不得含职称**。「曹德平研究员」这种把姓名与职称拼在一起的卡片，若不剥后缀
   就会把职称写进姓名。本项目在同类页面上遇到过两次（同济水利、同济航发）。
2. **方向不得被凭空填写**。名录不写方向就必须是「方向待补」，不允许拿学科名充数。
3. **不得出现邮箱或电话**。快照在落盘前已替换为「联系方式已隐去」，这里复核。
4. **每条记录必须有可追溯的来源 URL 与个人主页**。

用法::

    python -m workbench.tools.audit_new_sources             # 全部来源
    python -m workbench.tools.audit_new_sources --key tj_water_professor
    python -m workbench.tools.audit_new_sources --limit 5   # 只看前 5 个有问题的

退出码：发现违规返回 1，否则 0（便于放进 CI）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from workbench.collect_engineering_scale import discover_sources  # noqa: E402
from workbench.collect_thin_discipline_depth import NO_DIRECTION  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(
    r"(?<![0-9A-Za-z.\/-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s?\d{7,8})(?![0-9A-Za-z-])"
)
# 出现在姓名里就说明职称没剥干净
TITLE_IN_NAME = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后")
# 方向字段里出现这些词，说明是拿职称/身份冒充方向
FAKE_DIRECTION = re.compile(r"教授|副教授|讲师|研究员|高工|院士|博士后|博士生导师|硕士生导师")


def audit_one(key: str, spec: dict, parse) -> tuple[list[str], int]:
    """返回 (问题列表, 记录数)。"""
    problems: list[str] = []
    fixture = FIXTURES / f"{key}.html"
    if not fixture.is_file():
        return [f"缺少离线快照 {fixture.name}"], 0
    raw = fixture.read_text(encoding="utf-8")

    hits = EMAIL.findall(raw) + PHONE.findall(raw)
    if hits:
        problems.append(f"快照里仍有 {len(hits)} 处联系方式未脱敏")

    try:
        rows = parse(raw, spec.get("listing", ""), spec)
    except Exception as exc:  # noqa: BLE001 - 解析失败要报出来，不能吞
        return [f"parse 抛异常：{type(exc).__name__}: {exc}"], 0

    for row in rows:
        name = row.get("name") or ""
        if TITLE_IN_NAME.search(name):
            problems.append(f"姓名含职称：{name!r}")
        assignment = row.get("assignment") or {}
        direction = assignment.get("direction") or ""
        if direction and direction != NO_DIRECTION and FAKE_DIRECTION.search(direction):
            problems.append(f"方向像职称/身份：{row.get('name')!r} -> {direction!r}")
        if not row.get("homepage"):
            problems.append(f"缺少个人主页：{name!r}")
        # 来源 URL 记录在 assignment.url（roster_row 的约定），不是顶层 source。
        if not assignment.get("url"):
            problems.append(f"缺少来源 URL：{name!r}")
    return problems, len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="来源数据红线审计")
    ap.add_argument("--key", default="", help="只审这个 key")
    ap.add_argument("--limit", type=int, default=0, help="最多显示多少条问题")
    args = ap.parse_args()

    sources = discover_sources()
    total_keys = total_rows = 0
    bad: list[tuple[str, list[str]]] = []

    for key, spec in sources.items():
        if args.key and key != args.key:
            continue
        total_keys += 1
        problems, rows = audit_one(key, spec, spec["parser"])
        total_rows += rows
        if problems:
            bad.append((key, problems))

    lines = [
        f"来源红线审计：{total_keys} 个 key / {total_rows} 条记录",
        f"有问题的 key：{len(bad)}",
    ]
    shown = bad[: args.limit] if args.limit else bad
    for key, problems in shown:
        lines.append(f"  [{key}] {len(problems)} 处")
        for p in problems[:6]:
            lines.append(f"      - {p}")
        if len(problems) > 6:
            lines.append(f"      … 其余 {len(problems) - 6} 处")
    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
