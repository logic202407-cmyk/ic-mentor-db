# -*- coding: utf-8 -*-
"""skill_heuristics.py — 调用 academic-investigation skill 的异常检测启发式规则
对导师库中每位导师的论文列表运行 CommonHeuristicsClassifier（C01–C07），
并把 flagged 结果与人工解读一并落盘。

用法（需把环境变量 ACADEMIC_SKILL_SCRIPTS 指向该 skill 的 scripts 目录）:
    ACADEMIC_SKILL_SCRIPTS=/path/to/skills/academic-investigation/scripts \\
        python tools/skill_heuristics.py [限制人数]
    （Windows PowerShell: $env:ACADEMIC_SKILL_SCRIPTS='...'; python tools/skill_heuristics.py）

未设置该环境变量时本步骤会安全跳过（不阻塞其余流程）。
输出:
    data/processed/heuristics_all.json
"""
import json
import os
import sys
from collections import Counter

# 依赖 academic-investigation skill 的通用启发式规则。
# 该 skill 不在本仓库内，故用环境变量指定；未设置时跳过本步骤。
SKILL_SCRIPTS = os.environ.get("ACADEMIC_SKILL_SCRIPTS", "")
if not SKILL_SCRIPTS or not os.path.isdir(SKILL_SCRIPTS):
    print("[跳过] 未设置 ACADEMIC_SKILL_SCRIPTS（academic-investigation skill 的 scripts 目录）。")
    print("       如需运行异常规则筛查，请先设置该环境变量后重试。")
    sys.exit(0)
sys.path.insert(0, SKILL_SCRIPTS)

from analysis.common_heuristics import CommonHeuristicsClassifier  # noqa: E402

# ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROC = os.path.join(REPO, 'data', 'processed')
db = json.load(open(os.path.join(PROC, "mentor_db.json"), encoding="utf-8"))
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if limit:
    db = db[:limit]

clf = CommonHeuristicsClassifier()
out = []
rule_counter = Counter()
for i, r in enumerate(db):
    papers = []
    for p in r.get("papers", []):
        coauthors = p.get("coauthors") or []
        papers.append({
            "year": p.get("year"),
            "journal": p.get("venue") or "Unknown",
            "title": p.get("title"),
            "citation_count": p.get("cited") or 0,
            "author_position": p.get("my_order") or 0,
            "num_authors": p.get("n_authors") or 0,
            "authors": [c.get("name") for c in coauthors] or ["(unknown)"],
        })
    years = [p["year"] for p in papers if p.get("year")]
    years_active = (max(years) - min(years) + 1) if years else 0
    profile = {
        "h_index": None,
        "total_citations": r.get("citations") or 0,
        "n_papers": len(papers),
    }
    flags = clf.classify(papers, profile, discipline="engineering", years_active=max(years_active, 1))
    for f in flags:
        rule_counter[f["rule_id"]] += 1
    out.append({
        "school": r["school"], "name_cn": r["name_cn"], "title": r.get("title"),
        "primary_direction": r.get("primary_direction"), "score": r.get("score"),
        "n_papers": len(papers), "years_active": years_active,
        "flags": [{"rule_id": f["rule_id"], "rule_name": f["rule_name"], "severity": f.get("severity"),
                   "confidence": f.get("confidence"), "description": f.get("description")} for f in flags],
    })
    if (i + 1) % 200 == 0:
        print(f"  ... {i+1}/{len(db)}", flush=True)

with open(os.path.join(PROC, "heuristics_all.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)

print("总人数:", len(out))
print("命中规则统计:", dict(rule_counter))
flagged = [x for x in out if x["flags"]]
print("有 flag 的人数:", len(flagged))
sev = Counter()
for x in flagged:
    for f in x["flags"]:
        sev[f["severity"]] += 1
print("严重度分布:", dict(sev))
print("\n高频 flag 示例：")
for x in flagged[:10]:
    print(f"  {x['name_cn']}({x['school'][:4]}) " + "; ".join(f"{f['rule_id']}:{f['description'][:40]}" for f in x["flags"]))
