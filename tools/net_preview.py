# -*- coding: utf-8 -*-
"""net_preview.py — 生成关系网络静态预览图（PNG），用于快速核对布局与关系是否合理"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
net = json.load(open(os.path.join(ROOT, "data", "processed", "network_final.json"), encoding="utf-8"))
N = net["nodes"]
ADV = net["advisor"]          # lv: 1 自述 / 2 交叉 / 3 推断
SIB = net["sibling"]
# 预览只用可靠性最高的 L1 + L2
ADV = [e for e in ADV if e.get("lv") in (1, 2)]
print(f"L1+L2 师承边 {len(ADV)} 条（L1 {sum(1 for e in ADV if e['lv']==1)} / L2 {sum(1 for e in ADV if e['lv']==2)}）")

SHORT = {
    "清华大学深圳国际研究生院": "清华深研院", "清华大学": "清华", "复旦大学": "复旦", "上海交通大学": "上交",
    "浙江大学": "浙大", "南京大学": "南大", "中国科学技术大学": "中科大", "北京大学": "北大",
    "东南大学": "东南", "西安电子科技大学": "西电", "电子科技大学": "成电", "哈尔滨工业大学": "哈工大",
    "天津大学": "天大", "华中科技大学": "华科", "北京航空航天大学": "北航", "西安交通大学": "西交",
    "中国科学院微电子研究所": "中科院微电子所", "中国科学院半导体研究所": "中科院半导体所",
    "中国科学院上海微系统与信息技术研究所": "中科院上海微系统所", "中国科学院计算技术研究所": "中科院计算所",
    "中国科学院自动化研究所": "中科院自动化所", "中国科学院上海高等研究院": "中科院上海高研院",
}
COLORS = {
    "清华": "#7c3aed", "清华深研院": "#a78bfa", "北大": "#dc2626", "复旦": "#2563eb", "上交": "#0891b2",
    "浙大": "#059669", "南大": "#ca8a04", "中科大": "#db2777", "东南": "#ea580c", "西电": "#4f46e5",
    "成电": "#0d9488", "哈工大": "#9333ea", "天大": "#b45309", "华科": "#be123c", "北航": "#1d4ed8",
    "西交": "#15803d", "中科院微电子所": "#64748b", "中科院半导体所": "#78716c", "中科院上海微系统所": "#71717a",
    "中科院计算所": "#52525b", "中科院自动化所": "#3f3f46", "中科院上海高研院": "#a1a1aa",
}
# 中文字体
for cand in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
    if os.path.exists(cand):
        fm.fontManager.addfont(cand)
        matplotlib.rcParams["font.family"] = fm.FontProperties(fname=cand).get_name()
        break
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 只用师承 + 同门边，且只保留有学生的导师所在的连通分量 ──
mentor_of, students_of = {}, {}
for e in ADV:
    mentor_of.setdefault(e["s"], []).append(e["t"])
    students_of.setdefault(e["t"], []).append(e["s"])

# 选取全部 L1/L2 涉及的节点（33 条边，全画）
keep = set()
for e in ADV:
    keep.add(e["s"]); keep.add(e["t"])
# 补上这些节点的同门边
sib = [e for e in SIB if e["s"] in keep and e["t"] in keep]
edges = ADV
print(f"核心导师 {len(set(e['t'] for e in edges))} 人 | 节点 {len(keep)} | 师承边 {len(edges)} | 同门边 {len(sib)}")

# ── 层次布局：每个分量一棵树，横向打包 ──
adj = {k: set() for k in keep}
for e in edges + sib:
    adj[e["s"]].add(e["t"]); adj[e["t"]].add(e["s"])
comp, comps = {}, []
for k in keep:
    if k in comp:
        continue
    cid, stack, mem = len(comps), [k], []
    comp[k] = cid
    while stack:
        x = stack.pop(); mem.append(x)
        for y in adj[x]:
            if y not in comp:
                comp[y] = cid; stack.append(y)
    comps.append(mem)
comps.sort(key=len, reverse=True)

pos = {}
MAXW = 1560
MAXCOL = 9          # 每行最多放 9 个，超出换行
DX, DY = 74, 62     # 节点间距
PAD_COMP, PAD_ROW = 46, 80

# 先算出每个分量的"块尺寸"，再按行打包，避免边算边排导致错位
blocks = []
for mem in comps:
    mset = set(mem)
    depth = {}
    roots = [k for k in mem if not [m for m in mentor_of.get(k, []) if m in mset]]
    q = [(k, 0) for k in (roots or [mem[0]])]
    seen = set(x[0] for x in q)
    while q:
        k, d = q.pop(0); depth[k] = d
        for s in students_of.get(k, []):
            if s in mset and s not in seen:
                seen.add(s); q.append((s, d + 1))
    for k in mem:
        depth.setdefault(k, 0)
    layers = {}
    for k in mem:
        layers.setdefault(depth[k], []).append(k)
    for d in layers:
        layers[d].sort(key=lambda k: -len(students_of.get(k, [])))
    w = max(min(MAXCOL, len(v)) for v in layers.values()) * DX
    h = sum(math.ceil(len(v) / MAXCOL) * DY + PAD_COMP for v in layers.values())
    blocks.append({"layers": layers, "w": w, "h": h, "center": w / 2})

# 行打包
ROWW = (MAXW - 40)
cx, cy, rowh = 20, 60, 0
for b in blocks:
    if cx + b["w"] > 20 + ROWW and cx > 20:      # 本行放不下 -> 换行
        cx = 20; cy += rowh + PAD_ROW; rowh = 0
    yoff = 0
    for d in sorted(b["layers"]):
        arr = b["layers"][d]
        cols = min(MAXCOL, len(arr))
        x0 = cx + b["center"] - (cols * DX) / 2 + DX / 2
        for i, k in enumerate(arr):
            r, c = divmod(i, MAXCOL)
            pos[k] = (x0 + c * DX, cy + yoff + r * DY)
        yoff += math.ceil(len(arr) / MAXCOL) * DY + PAD_COMP
    cx += b["w"] + 60
    rowh = max(rowh, yoff)
print(f"布局: {len(blocks)} 个分量 / 放入 {len(pos)} 个节点 / 总高 {cy + rowh:.0f}")

# ── 绘制 ──
fig, ax = plt.subplots(figsize=(20, 13), dpi=110)
ax.set_facecolor("#0f1117"); fig.patch.set_facecolor("#0f1117")
for e in edges:
    if e["s"] not in pos or e["t"] not in pos:
        continue
    x1, y1 = pos[e["t"]]; x2, y2 = pos[e["s"]]      # 导师 -> 学生
    lv = e.get("lv", 1)
    col = "#fbbf24" if lv == 1 else "#f59e0b"
    w = (2.4 if lv == 1 else 1.6) + min(1.6, (e.get("n") or 2) * 0.18)
    ax.annotate("", xy=(x2, y2 - 0.9), xytext=(x1, y1 + 0.9),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=w, alpha=0.9, shrinkA=6, shrinkB=9))
for e in sib:
    if e["s"] in pos and e["t"] in pos:
        x1, y1 = pos[e["s"]]; x2, y2 = pos[e["t"]]
        if abs(y1 - y2) < 1:
            ax.plot([x1, x2], [y1, y2], color="#10b981", lw=0.6, ls=":", alpha=0.5)

for k, (x, y) in pos.items():
    p = N[k]
    s = SHORT.get(p["school"], p["school"])
    ns = len(students_of.get(k, []))
    r = 40 + min(340, ns * 26)
    ax.scatter([x], [y], s=r, c=COLORS.get(s, "#64748b"), zorder=3,
               edgecolors="#0f1117", linewidths=1.4, alpha=0.95)
    label = p["name"] + (f"({ns})" if ns else "")
    ax.text(x, y - 0.45, label, ha="center", va="bottom", fontsize=8.5 if ns else 7,
            color="#e5e7eb" if ns else "#94a3b8",
            fontweight="bold" if ns >= 3 else "normal", zorder=4)
    ax.text(x, y + 0.55, s, ha="center", va="top", fontsize=6.5, color="#6b7280", zorder=4)

ax.set_xlim(0, MAXW); ax.set_ylim(0, cy + rowh + 60)
ax.invert_yaxis(); ax.axis("off")
n1 = sum(1 for e in edges if e.get("lv") == 1)
n2 = sum(1 for e in edges if e.get("lv") == 2)
ax.set_title(
    f"微电子导师师承图谱 · 仅收录「可核实证据」的 {len(edges)} 条关系（{len(pos)} 人）\n"
    f"L1 自述师承 {n1} 条（本人页面明写「导师为/师从 XX」）｜L2 学历×论文交叉证据 {n2} 条（毕业院校 × 早期一作 × 该院校教授任末位作者）\n"
    f"箭头：导师 → 学生；括号内为该导师在本图中的学生数",
    color="#e5e7eb", fontsize=12, pad=16)
out = os.path.join(ROOT, "reports", "导师关系网络-师承图谱.png")
plt.tight_layout(); plt.savefig(out, facecolor="#0f1117", bbox_inches="tight")
print("saved", out)
