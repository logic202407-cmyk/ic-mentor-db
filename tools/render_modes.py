# -*- coding: utf-8 -*-
"""render_modes.py — 渲染三种分类方式的总览，核对分组效果"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODE = sys.argv[1] if len(sys.argv) > 1 else 'school'
D = json.load(open(os.path.join(ROOT, "data/processed/_mode_%s.json" % MODE), encoding="utf-8"))
P, scale, GRP = D["pos"], D["scale"], D["groups"]
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

# 分组底板
for g in GRP:
    x, y = g["x"] * scale + D["ox"], g["y"] * scale + D["oy"]
    w, h = g["w"] * scale, g["h"] * scale
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=10",
                                facecolor=g["color"] + "12", edgecolor=g["color"] + "55", linewidth=1.3, zorder=1))
    ax.add_patch(FancyBboxPatch((x, y), min(w, 330), 22, boxstyle="round,pad=0,rounding_size=6",
                                facecolor=g["color"] + "3a", edgecolor="none", zorder=2))
    ax.text(x + 8, y + 11, g["name"], fontsize=10, fontweight="bold", color=g["color"],
            va="center", ha="left", zorder=6)
    ax.text(x + min(w, 330) - 6, y + 11, "%d 位导师" % g["n"], fontsize=8, color="#9aa7b8",
            va="center", ha="right", zorder=6)

for k, p in P.items():
    x, y = S(k)
    r = max(5.0, p["r"] * scale)
    if p.get("cross"):
        ax.scatter([x], [y], s=(r + 4) ** 2 * 2.6, facecolors="none", edgecolors="#f472b6",
                   linewidths=1.8, zorder=3)
    ax.scatter([x], [y], s=r * r * 3.0, c=p["color"], zorder=4,
               edgecolors="#0b0e14", linewidths=1.0)
    sub = ("跨 %d 个方向" % p.get("ndir", 0)) if (MODE == 'dir' and p.get("multi")) else ("%d 名学生" % p["cnt"])
    tw = len(p["n"]) * 14 * 0.95
    sw = len(sub) * 10.0   # 保守估计（中文全角，实际比 7.5 宽）
    if r * 2 > tw + 12 and r > 20:
        ax.text(x, y, p["n"], ha="center", va="center", fontsize=14, color="#ffffff",
                fontweight="bold", zorder=6)
        if r * 2 > sw + 8:
            ax.text(x, y + 15, sub, ha="center", va="center", fontsize=9,
                    color="#ffffffa0" if (MODE == 'dir' and p.get("multi")) else "#ffffffcc", zorder=6)
        if MODE == 'dir' and p.get("multi"):
            ax.scatter([x], [y], s=(r + 4) ** 2 * 2.6, facecolors="none", edgecolors="#ffffff48",
                       linewidths=1.2, linestyle="--", zorder=5)
    else:
        ax.text(x, y + r + 3, p["n"], ha="center", va="top", fontsize=8.5, color="#dbe3ee", zorder=5)

NAMES = {'school': '按院校', 'dir': '按研究方向', 'gen': '按师承层级'}
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
ax.set_title("师承树 · 总览（%s，%d 位导师 / %d 个分组）" % (NAMES.get(MODE, MODE), D["n"], len(GRP)),
             color="#e5e7eb", fontsize=12)
out = os.path.join(ROOT, "reports", "导师关系网络-分类-%s.png" % NAMES.get(MODE, MODE))
plt.tight_layout(); plt.savefig(out, facecolor="#0b0e14")
print("saved", out)
