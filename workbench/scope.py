"""Engineering-only scope: which first-level disciplines the workbench shows by default.

The 2022 catalogue lists 117 first-level disciplines across all faculties. This
workbench now positions itself as an *engineering* mentor workbench, so the
39 discipline codes under the 08 (工学) faculty are the default scope.

Nothing is deleted. Non-engineering entries stay in the data files, keep their
stable IDs, and remain reachable through ``include_non_engineering=True`` or the
"显示非工科" switch in the interface. Hiding is a default view, not a data
retraction — that keeps every previously published ID resolvable.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISCIPLINES_2022 = ROOT / "workbench" / "reference" / "first_level_disciplines_2022.json"

# The 工学 faculty prefix in the 2022 catalogue.
ENGINEERING_PREFIX = "08"

# Legacy IC corpus rows carry no first-level discipline. They are assigned to an
# engineering discipline from their research keywords, in this order: the first
# pattern that matches wins, so list the most specific areas first.
LEGACY_DISCIPLINE_RULES: tuple[tuple[str, str], ...] = (
    ("0812", r"计算机|体系结构|处理器|芯片架构|操作系统|编译|数据库|机器学习|深度学习|"
             r"人工智能|神经网络|算法|软件|并行计算|异构计算|图计算|存储系统"),
    ("0810", r"通信|射频|毫米波|天线|太赫兹|无线|信号处理|雷达|光通信|网络协议|物联网"),
    ("0811", r"控制|自动化|机器人|导航|制导|模式识别|检测技术|系统工程|运动控制"),
    ("0809", r"集成电路|微电子|半导体|器件|工艺|光电子|硅光|光电|电磁场|微波|"
             r"电子科学|电路与系统|EDA|电子设计|封装|MEMS|传感器|类脑|存算|量子器件"),
    ("0805", r"材料|薄膜|纳米|陶瓷|金属|合金|高分子|复合材料"),
    ("0803", r"光学|激光|光谱|成像|光学工程"),
    ("0804", r"仪器|测量|计量|精密仪器"),
    ("0808", r"电气|电机|电力|电网|电源|变流|高压"),
    ("0807", r"热能|动力|发动机|燃烧|流体机械|制冷|工程热物理"),
    ("0802", r"机械|制造|机床|精密工程|车辆工程|机电"),
    ("0801", r"力学|固体力学|流体力学|振动力学"),
)

# Default bucket when no keyword matches. 0809 is the closest engineering home for
# a corpus that is explicitly an integrated-circuit corpus.
LEGACY_DEFAULT = "0809"


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, str]:
    """code -> "code name" for every first-level discipline in the 2022 catalogue."""
    data = json.loads(DISCIPLINES_2022.read_text(encoding="utf-8"))["disciplines"]
    return {row["code"]: f"{row['code']} {row['name']}" for row in data}


@lru_cache(maxsize=1)
def engineering_codes() -> frozenset[str]:
    return frozenset(code for code in _catalogue() if code.startswith(ENGINEERING_PREFIX))


@lru_cache(maxsize=1)
def engineering_disciplines() -> tuple[str, ...]:
    """"0809 电子科学与技术" style names, in catalogue order."""
    return tuple(_catalogue()[code] for code in sorted(engineering_codes()))


@lru_cache(maxsize=1)
def non_engineering_disciplines() -> tuple[str, ...]:
    return tuple(name for code, name in sorted(_catalogue().items())
                 if not code.startswith(ENGINEERING_PREFIX))


def code_of(discipline_name: str) -> str:
    """Extract the leading 4-digit code from a discipline label, if any."""
    match = re.match(r"^(\d{4})", (discipline_name or "").strip())
    return match.group(1) if match else ""


def is_engineering(discipline_name: str) -> bool:
    code = code_of(discipline_name)
    return bool(code) and code.startswith(ENGINEERING_PREFIX)


def legacy_discipline(keywords) -> str:
    """Assign a legacy IC row to an engineering discipline from its keywords.

    ``keywords`` may be a string, a list, or None depending on the source row, so
    it is flattened the same way the rest of the catalogue flattens list fields.
    """
    if isinstance(keywords, (list, tuple, set)):
        text = "、".join(str(x) for x in keywords)
    else:
        text = str(keywords or "")
    for code, pattern in LEGACY_DISCIPLINE_RULES:
        if re.search(pattern, text):
            return _catalogue()[code]
    return _catalogue()[LEGACY_DEFAULT]


def scope_summary() -> dict:
    return {
        "engineering_prefix": ENGINEERING_PREFIX,
        "engineering_count": len(engineering_disciplines()),
        "non_engineering_count": len(non_engineering_disciplines()),
        "note": "非工科学科保留在数据中并可通过开关显示，不从数据文件删除。",
    }
