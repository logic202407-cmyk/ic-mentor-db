# -*- coding: utf-8 -*-
"""git_size.py — 统计已暂存文件的大小与清单（Unicode 安全）"""
import subprocess
import os

out = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, encoding="utf-8")
files = [f for f in out.stdout.splitlines() if f.strip()]
rows = []
for f in files:
    try:
        rows.append((f, os.path.getsize(f)))
    except OSError:
        rows.append((f, -1))
rows.sort(key=lambda x: -x[1])
total = sum(s for _, s in rows if s > 0)
print(f"暂存文件数: {len(rows)}  总计: {total/1024/1024:.2f} MB\n")
print("最大的 20 个:")
for f, s in rows[:20]:
    print(f"  {s/1024/1024:8.2f} MB  {f}")
print("\n目录汇总:")
agg = {}
for f, s in rows:
    if s <= 0:
        continue
    top = "/".join(f.split("/")[:2]) if "/" in f else "(根)"
    agg[top] = agg.get(top, 0) + s
for k, v in sorted(agg.items(), key=lambda x: -x[1]):
    print(f"  {v/1024/1024:8.2f} MB  {k}")
