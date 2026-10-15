"""Repair the thin-discipline audit's before/after values.

Background: ``collect_thin_discipline_depth`` originally recomputed ``before`` from
the live catalogue on every run. A later ``--enrich`` re-run therefore merged
nothing new and rewrote ``before`` so that it equalled ``after``, destroying the
recorded baseline of the batch (8 -> 16 for 民族学, 8 -> 118 for 矿业工程).

The true baseline is still derivable, independently of the live catalogue:
``gap_admission_faculty.json`` is the source that created these two disciplines in
the first place, and it holds exactly 8 people per discipline (中国社会科学院大学
and 江西理工大学 respectively).

This script restores the baseline from that provenance, records how it was
recovered, and leaves a note so the correction is auditable rather than silent.
The collector itself has been fixed to preserve the first observed ``before``.
"""

from __future__ import annotations

import json
import pathlib

REF = pathlib.Path("workbench/reference")
AUDIT = REF / "thin_discipline_audit_20261015.json"
PROVENANCE = REF / "gap_admission_faculty.json"
TARGETS = {
    "0304 民族学": "中国社会科学院大学",
    "0819 矿业工程": "江西理工大学",
}


def main() -> int:
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    rows = prov.get("profiles", [])
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    baseline = {}
    for discipline, institution in TARGETS.items():
        code = discipline.split()[0]
        hits = [p for p in rows
                if str(p.get("first_level_discipline", "")).startswith(code)
                and p.get("institution") == institution]
        people = {(p.get("institution"), p.get("department"), p.get("name")) for p in hits}
        baseline[discipline] = len(people)

    current = {d: audit["after"][d] for d in TARGETS}

    repaired_before = dict(audit["before"])
    for discipline, value in baseline.items():
        repaired_before[discipline] = value

    audit["before"] = repaired_before
    audit["after"] = {**audit["after"], **current}
    audit["merge"] = {
        "added": sum(current[d] - baseline[d] for d in TARGETS),
        "enriched": 0,
        "note": "added 为两个目标学科的净新增人数；加总不含其他学科变动。",
    }
    audit["baseline_recovered_from"] = {
        "file": "workbench/reference/gap_admission_faculty.json",
        "reason": "collect_thin_discipline_depth 曾在校验重跑时把 before 重算为合并后的值，"
                  "导致基准丢失；此处按该学科的原始来源文件独立重建基准。",
        "per_discipline": baseline,
    }
    audit.setdefault("first_recorded_at", "2026-10-15")
    audit["limits"] = [
        "学院在职教师名录用于学科导航归类，不代表当年招生专业或名额。",
        "名录按职称或学系分组，不含个人研究方向，故方向字段一律为“方向待补”；职称只写入来源说明，不作为研究方向。",
        "不收录邮箱、电话等联系方式。",
        "before 基准由 gap_admission_faculty.json 独立重建（见 baseline_recovered_from）。",
    ]
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "after": current, "merge": audit["merge"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
