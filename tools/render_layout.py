# -*- coding: utf-8 -*-
"""render_layout.py — 把页面真实计算出的布局画成图，用于直观看可读性"""
import json, os, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data/processed/_layout_lineage.json"), encoding="utf-8"))
P, E, scale = D["pos"], D["edges"], D["scale"]

SHORT = {"清华大学深圳国际研究生院": "清华深研院", "清华大学": "清华", "复旦大学": "复旦", "上海交通大学": "上交",
         "浙江大学": "浙大", "南京大学": "南大", "中国科学技术大学": "中科大", "北京大学": "北大", "东南大学": "东南",
         "西安电子科技大学": "西电", "电子科技大学": "成电", "哈尔滨工业大学": "哈工大", "天津大学": "天大",
         "华中科技大学": "华科", "北京航空航天大学": "北航", "西安交通大学": "西交",
         "中国科学院微电子研究所": "中科院微电子所", "中国科学院半导体研究所": "中科院半导体所",
         "中国科学院上海微系统与信息技术研究所": "中科院上海微系统所", "中国科学院计算技术研究所": "中科院计算所",
         "中国科学院自动化研究所": "中科院自动化所", "中国科学院上海高等研究院": "中科院上海高研院"}
COLORS = {"清华": "#8b5cf6", "清华深研院": "#a78bfa", "北大": "#ef4444", "复旦": "#3b82f6", "上交": "#06b6d4",
          "浙大": "#10b981", "南大": "#eab308", "中科大": "#ec4899", "东南": "#f97316", "西电": "#6366f1",
          "成电": "#14b8a6", "哈工大": "#a855f7", "天大": "#d97706", "华科": "#e11d48", "北航": "#2563eb",
          "西交": "#16a34a", "中科院微电子所": "#94a3b8", "中科院半导体所": "#a8a29e", "中科院上海微系统所": "#9ca3af",
          "中科院计算所": "#78716c", "中科院自动化所": "#6b7280", "中科院上海高研院": "#d4d4d8"}
for c in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
    if os.path.exists(c):
        fm.fontManager.addfont(c)
        matplotlib.rcParams["font.family"] = fm.FontProperties(fname=c).get_name()
        break
matplotlib.rcParams["axes.unicode_minus"] = False

# 按屏幕坐标系绘制（模拟浏览器视口）
W, H = D["W"], D["H"]
fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
fig.patch.set_facecolor("#0b0e14"); ax.set_facecolor("#0b0e14")

def S(k):
    p = P[k]
    return p["x"] * scale + D["ox"], p["y"] * scale + D["oy"]

for e in E:
    if e["s"] not in P or e["t"] not in P:
        continue
    x1, y1 = S(e["t"]); x2, y2 = S(e["s"])
    if e["k"] == "adv":
        col = "#fbbf24" if e["lv"] == 1 else "#f59e0b" if e["lv"] == 2 else "#a16207"
        lw = 2.2 if e["lv"] == 1 else 1.5 if e["lv"] == 2 else 0.8
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, alpha=.9, shrinkA=4, shrinkB=6))
    else:
        ax.plot([x1, x2], [y1, y2], color="#10b981", lw=.6, ls=":", alpha=.35)

for k, p in P.items():
    x, y = S(k)
    r = max(2.5, p["r"] * scale)
    ax.scatter([x], [y], s=r * r * 3.2, c=COLORS.get(SHORT.get(p["s"], p["s"]), "#64748b"),
               zorder=3, edgecolors="#0b0e14", linewidths=.8)

# 标签：屏幕坐标恒定字号（与页面一致）+ 简单避让
placed = []
items = sorted(P.items(), key=lambda kv: -kv[1]["pp"])
for k, p in items:
    x, y = S(k)
    if not (0 <= x <= W and 0 <= y <= H):
        continue
    if len(placed) > 90:
        break
    r = max(2.5, p["r"] * scale)
    ty = y - r - 4
    lx = x - len(p["n"]) * 3.2
    ok = all(not (lx < px2 and lx + len(p["n"]) * 6.4 > px1 and ty - 9 < py2 and ty > py1) for px1, px2, py1, py2 in placed)
    if not ok and p["pp"] < 60:
        continue
    placed.append((lx, lx + len(p["n"]) * 6.4, ty - 9, ty))
    ax.text(x, ty, p["n"], ha="center", va="bottom", fontsize=7.5, color="#e8edf5", zorder=4)

ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
ax.set_title(f"师承图谱（页面真实布局，scale={scale:.3f}，{len(P)} 节点 / {len(E)} 边）",
             color="#e5e7eb", fontsize=11)
out = os.path.join(ROOT, "reports", "_布局核对.png")
plt.tight_layout(); plt.savefig(out, facecolor="#0b0e14")
print("saved", out, "| 标注了", len(placed), "个标签")
