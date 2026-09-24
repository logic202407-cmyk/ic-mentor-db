# -*- coding: utf-8 -*-
"""inspect_enriched.py — 快速查看某校富化结果（姓名/职称/论文数/代表venue）"""
import json
import sys
import collections

p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
print("学校:", d["school"], "人数:", len(d["people"]))
for per in d["people"]:
    venues = collections.Counter(x["venue"] for x in per["papers"] if x["venue"])
    top = "; ".join(f"{v[:28]}x{c}" for v, c in venues.most_common(3))
    print(f"{per['name_cn']:<8} {str(per['title'])[:10]:<12} n={per['paper_count']:<4} {top[:110]}")
    print(f"          variants={per['variants'][:3]}")
