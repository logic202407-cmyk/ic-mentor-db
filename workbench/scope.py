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

# The legacy corpus carries a curated ``primary_direction`` code for every row
# (device / photonics / rf / digital_ai / mems / analog / eda / quantum / power /
# other). That curated field is a far stronger signal than free-text keywords, so
# it is consulted first and keywords only refine within it.
LEGACY_PRIMARY_DISCIPLINE: dict[str, str] = {
    "device": "0809",      # 电子器件与工艺
    "photonics": "0809",   # 光电子与硅光
    "rf": "0810",          # 射频与通信
    "digital_ai": "0812",  # 数字电路与 AI 芯片
    "mems": "0809",        # 微机电系统
    "analog": "0809",      # 模拟电路
    "eda": "0812",         # 电子设计自动化
    "quantum": "0809",     # 量子技术
    "power": "0808",       # 电力电子
    "other": "0809",
}

# Keyword rules refine the assignment when the free-text keywords are usable.
# Order matters: the first match wins, so specific areas are listed before broad
# ones. A bare "算法" or "系统" is deliberately NOT matched on its own, because
# those words appear in physics and chemistry descriptions too.
LEGACY_DISCIPLINE_RULES: tuple[tuple[str, str], ...] = (
    ("0809", r"集成电路|微电子|半导体|光电子|硅光|物理电子|"
             r"电子科学|电路与系统|芯片|存储器|类脑|存算|忆阻|封装|"
             r"射频器件|功率器件|MEMS|传感器|光电|量子器件"),
    ("0810", r"射频|毫米波|太赫兹|天线|无线|通信|信号处理|雷达|"
             r"电磁超材料|收发信机|功率放大器|光通信|网络协议|物联网|"
             r"电磁场|微波"),
    ("0812", r"计算机|体系结构|处理器|操作系统|编译|数据库|机器学习|深度学习|"
             r"人工智能|神经网络|加速器|并行计算|异构计算|图计算|存储系统|"
             r"电子设计自动化|EDA|软件工程|算法设计|信息安全|密码"),
    ("0811", r"控制|自动化|机器人|导航|制导|模式识别|检测技术|系统工程|运动控制"),
    ("0805", r"材料|薄膜|纳米|陶瓷|金属|合金|高分子|复合材料"),
    ("0803", r"光学|激光|光谱|成像|光学工程"),
    ("0804", r"仪器|测量|计量|精密仪器"),
    ("0808", r"电气|电机|电力|电网|电源|变流|高压"),
    ("0807", r"热能|动力|发动机|燃烧|流体机械|制冷|工程热物理"),
    ("0802", r"机械|制造|机床|精密工程|车辆工程|机电"),
    ("0801", r"力学|固体力学|流体力学|振动力学"),
)

# Default bucket when neither the curated field nor the keywords resolve.
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


def legacy_discipline(keywords, primary_direction: str | None = None) -> str:
    """Assign a legacy IC row to an engineering discipline.

    Resolution order, strongest signal first:

    1. Free-text keywords, when they name an identifiable area. This is the most
       specific evidence, so it wins when it fires.
    2. The curated ``primary_direction`` code, which every legacy row carries.
    3. :data:`LEGACY_DEFAULT` (0809 电子科学与技术), the closest engineering home
       for a corpus that is explicitly an integrated-circuit corpus.

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
    curated = LEGACY_PRIMARY_DISCIPLINE.get((primary_direction or "").strip())
    if curated:
        return _catalogue()[curated]
    return _catalogue()[LEGACY_DEFAULT]


def scope_summary() -> dict:
    return {
        "engineering_prefix": ENGINEERING_PREFIX,
        "engineering_count": len(engineering_disciplines()),
        "non_engineering_count": len(non_engineering_disciplines()),
        "note": "非工科学科保留在数据中并可通过开关显示，不从数据文件删除。",
    }
