# -*- coding: utf-8 -*-
"""render_school.py — 渲染「院校分区」视图，核对分区布局与跨校连线"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data/processed/_layout_school.json"), encoding="utf-8"))
P, E, scale, PAN = D["pos"], D["edges"], D["scale"], D.get("panels", [])
W, H = D["W"], D["H"]

for c in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
    if os.path.exists(c):
        fm.fontManager.addfont(c)
        matplotlib.rcParams["font.family"] = fm.FontProperties(fname=c).get_name()
        break
matplotlib.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
fig.patch.set_facecolor("#0b0e14"); ax.set_facecolor("#0b0e14")
S = lambda k: (P[k]["x"] * scale + D["ox"], P[k]["y"] * scale + D["oy"])

# 面板底板
for p in PAN:
    x, y = p["x"] * scale + D["ox"], p["y"] * scale + D["oy"]
    w, h = p["w"] * scale, p["h"] * scale
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=10",
                                facecolor=p["color"] + "12", edgecolor=p["color"] + "66", linewidth=1.3, zorder=1))
    ax.text(x + 7, y + 12, p["school"], fontsize=9.5, fontweight="bold", color=p["color"], zorder=5)
    # 人数右对齐到面板标题条右侧，避免与校名重叠
    ax.text(x + min(w, 280) - 8, y + 12, str(p["n"]) + " 人", fontsize=8, color="#7c8ba1",
            zorder=5, ha="right")

# 边：先画校内，再画跨校（跨校后画，压在上层）
inE = [e for e in E if not e.get("cross")]
crE = [e for e in E if e.get("cross")]
for e in inE:
    if e["s"] not in P or e["t"] not in P: continue
    x1, y1 = S(e["t"]); x2, y2 = S(e["s"])
    if e["k"] == "adv":
        col = "#fbbf24" if e["lv"] == 1 else "#f59e0b" if e["lv"] == 2 else "#a16207"
        lw = 2.0 if e["lv"] == 1 else 1.4 if e["lv"] == 2 else 0.8
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, alpha=.9, shrinkA=4, shrinkB=6), zorder=2)
    else:
        ax.plot([x1, x2], [y1, y2], color="#10b981", lw=.6, ls=":", alpha=.3, zorder=2)
for e in crE:
    if e["s"] not in P or e["t"] not in P: continue
    x1, y1 = S(e["t"]); x2, y2 = S(e["s"])
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color="#f472b6", lw=1.5, alpha=.42,
                                connectionstyle="arc3,rad=0.22", shrinkA=5, shrinkB=8), zorder=6)

for k, p in P.items():
    x, y = S(k)
    r = max(2.5, p["r"] * scale)
    ax.scatter([x], [y], s=r * r * 3.4, c=D.get("colorOf", {}).get(k) or "#64748b", zorder=3,
               edgecolors="#0b0e14", linewidths=.8)

# 标签（屏幕坐标，简单避让）
placed = []
for k, p in sorted(P.items(), key=lambda kv: -kv[1]["pp"]):
    x, y = S(k)
    if not (0 <= x <= W and 0 <= y <= H): continue
    if len(placed) > 110: break
    r = max(2.5, p["r"] * scale); ty = y - r - 3
    lx = x - len(p["n"]) * 3.4
    ok = all(not (lx < b and lx + len(p["n"]) * 6.8 > a and ty - 9 < d and ty > c) for a, b, c, d in placed)
    if not ok and p["pp"] < 80: continue
    placed.append((lx, lx + len(p["n"]) * 6.8, ty - 9, ty))
    ax.text(x, ty, p["n"], ha="center", va="bottom", fontsize=7.5, color="#e8edf5", zorder=4)

ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
ax.set_title(f"院校分区族谱（页面真实布局，scale={scale:.3f}，{len(P)} 节点 / {len(E)} 边 / {len(crE)} 条跨校）",
             color="#e5e7eb", fontsize=11)
out = os.path.join(ROOT, "reports", "导师关系网络-院校分区.png")
plt.tight_layout(); plt.savefig(out, facecolor="#0b0e14")
print("saved", out, "| 面板", len(PAN), "| 标签", len(placed))
