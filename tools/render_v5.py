# -*- coding: utf-8 -*-
"""render_v5.py — 渲染 v5 师承树（总览或展开），核对直观性"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tag = sys.argv[1] if len(sys.argv) > 1 else 'overview'
D = json.load(open(os.path.join(ROOT, "data/processed/_v5_%s.json" % tag), encoding="utf-8"))
P, E, scale = D["pos"], D["edges"], D["scale"]
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

for e in E:
    if e["a"] not in P or e["b"] not in P:
        continue
    x1, y1 = S(e["a"]); x2, y2 = S(e["b"])
    col = "#f472b6" if e.get("cross") else ("#fbbf24" if e["lv"] == 1 else "#f59e0b" if e["lv"] == 2 else "#a16207")
    lw = 2.4 if e.get("cross") else (2.0 if e["lv"] == 1 else 1.3)
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, alpha=.92, shrinkA=5, shrinkB=7), zorder=2)

for k, p in P.items():
    x, y = S(k)
    r = max(4.0, p["r"] * scale)
    if p.get("cross"):
        ax.scatter([x], [y], s=(r + 4) ** 2 * 2.6, facecolors="none", edgecolors="#f472b6", linewidths=1.8, zorder=3)
    ax.scatter([x], [y], s=r * r * 3.0, c=p["color"], zorder=4, edgecolors="#0b0e14", linewidths=1.0)

placed = []
for k, p in sorted(P.items(), key=lambda kv: (not kv[1].get("root"), -kv[1]["pp"])):
    x, y = S(k)
    if not (-60 <= x <= W + 60 and -30 <= y <= H + 30):
        continue
    r = max(4.0, p["r"] * scale)
    fs = 9.5 if p.get("root") else 8
    label = p["n"]
    # 与页面一致：根节点足够大时，名字直接画在圆内，避免被节点盖住
    tw_est = len(label) * (14 if p.get("root") else fs) * 0.95
    if p.get("root") and r * 2 > tw_est + 10 and r > 16:
        ax.text(x, y, label, ha="center", va="center", fontsize=14, color="#ffffff",
                fontweight="bold", zorder=6)
        if p.get("cnt"):
            ax.text(x, y + 15, "%d 名学生" % p["cnt"], ha="center", va="center",
                    fontsize=9, color="#ffffffcc", zorder=6)
        continue
    ty = y + r + fs + 3
    tw = len(label) * fs * 0.95
    ok = all(not (x - tw / 2 < b and x + tw / 2 > a and ty - fs < d and ty > c) for a, b, c, d in placed)
    if not ok and not p.get("root"):
        continue
    placed.append((x - tw / 2, x + tw / 2, ty - fs, ty))
    ax.text(x, ty, label, ha="center", va="top", fontsize=fs,
            color="#fbbf24" if p.get("root") else "#dbe3ee", zorder=5,
            fontweight="bold" if p.get("root") else "normal")
    if p.get("root") and p.get("cnt"):
        ax.text(x, ty + fs + 4, "%d 名学生" % p["cnt"], ha="center", va="top", fontsize=7.5, color="#7c8ba1", zorder=5)

title = ("师承树 · 展开「%s」（%d 节点 / %d 边）" % (D["focus"], D["n"], D["ne"])) if D.get("focus") \
    else ("师承树 · 总览（%d 位导师，点击可展开其师承树）" % D["n"])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
ax.set_title(title, color="#e5e7eb", fontsize=12)
out = os.path.join(ROOT, "reports", "导师关系网络-%s.png" % ("聚焦展开" if D.get("focus") else "总览"))
plt.tight_layout(); plt.savefig(out, facecolor="#0b0e14")
print("saved", out, "| 标注", len(placed), "个标签")
