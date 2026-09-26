# -*- coding: utf-8 -*-
"""patch_readme2.py — 更新 README：新增落地页、CI、维护指南、Pages 说明"""
import io
import os

ROOT = r"E:\ytm\mentor-db"
p = os.path.join(ROOT, "README.md")
s = io.open(p, encoding="utf-8").read()

# 1) 顶部加徽章
s = s.replace(
    "# 集成电路 / AI 芯片 方向导师库（IC Mentor DB）\n",
    "# 集成电路 / AI 芯片 方向导师库（IC Mentor DB）\n\n"
    "[![数据与产出校验](https://github.com/logic202407-cmyk/ic-mentor-db/actions/workflows/validate.yml/badge.svg)]"
    "(https://github.com/logic202407-cmyk/ic-mentor-db/actions/workflows/validate.yml)\n"
    "[![许可: CC BY-NC-SA 4.0](https://img.shields.io/badge/%E6%95%B0%E6%8D%AE-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE-DATA)\n"
    "[![许可: MIT](https://img.shields.io/badge/%E4%BB%A3%E7%A0%81-MIT-blue.svg)](LICENSE)\n",
    1,
)

# 2) 快速开始里加网页入口
s = s.replace(
    "## 🚀 快速开始（3 分钟）\n\n1. **下载本仓库**",
    "## 🚀 快速开始（3 分钟）\n\n"
    "> **在线浏览**：开启 GitHub Pages 后可直接打开 `https://<用户名>.github.io/ic-mentor-db/`（见文末「开启在线浏览」）。\n"
    "> **离线使用**：\n\n1. **下载本仓库**",
    1,
)

# 3) 仓库内容表加 index.html 与维护指南
s = s.replace(
    "| `docs/使用指南.md` | 面向学生的完整使用教程 |",
    "| `index.html` | 落地页（GitHub Pages 入口，汇总所有产出的导航） |\n"
    "| `docs/使用指南.md` | 面向学生的完整使用教程 |\n"
    "| `docs/维护指南.md` | 面向后续维护者：数据更新节奏、全量重建流程、排错表、红线 |",
    1,
)

# 4) 在「更新记录」前插入 Pages 说明与 CI 说明
pages = """
---

## 🌐 开启在线浏览（GitHub Pages）

仓库里的两个 HTML 是自包含单文件，可以直接当静态站点发布，学生**无需下载**即可浏览：

1. 把仓库设为 **Public**（私有仓库的 Pages 需要付费计划）；
2. **Settings → Pages → Source** 选 `Deploy from a branch`，分支 `main`、目录 `/ (root)`，保存；
3. 约 1 分钟后访问 `https://<用户名>.github.io/ic-mentor-db/` —— 落地页 `index.html` 会引导到推荐页与全库页。

> 仓库已包含 `.nojekyll`，可避免 Jekyll 处理中文文件名。

---

## ✅ 自动校验（GitHub Actions）

每次 push / PR 会自动跑 `.github/workflows/validate.yml`，检查四件事：

| 检查 | 说明 |
|:--|:--|
| **邮箱残留** | `strip_emails.mjs --check`：产物中不得出现任何邮箱地址（**隐私红线，不通过则 CI 失败**） |
| JSON 可解析 | 全部入库数据文件必须能被解析 |
| HTML 产出完整 | 内嵌数据 JSON 可解析、script 标签闭合、无个人化/评价性词汇 |
| 字段完整性 | 全库与推荐集人数在下限之上，且**不含 `email` 字段** |

本地预检（提交前建议跑一遍）：

```bash
node tools/strip_emails.mjs --check
node tools/verify_html.mjs reports/导师推荐.html reports/导师库.html
```

"""
s = s.replace("\n---\n\n## 📌 更新记录", pages + "\n---\n\n## 📌 更新记录", 1)

# 5) 更新记录追加
s = s.replace(
    "| 2026-09-24 | **数据完善**：低召回导师定向补检（+130 篇论文）、垃圾关键词清洗、主页抓取 231 → 1030 位、明确在招 53 → **152 位**、推荐集扩为两层 458 人 |",
    "| 2026-09-24 | **数据完善**：低召回导师定向补检（+130 篇论文）、垃圾关键词清洗、主页抓取 231 → 1030 位、明确在招 53 → **152 位**、推荐集扩为两层 458 人 |\n"
    "| 2026-09-26 | 移除「主页明确写了不招」清单（避免对个人形成负面指向）；纯负面招生表述不再计入\"在招\" |\n"
    "| 2026-09-26 | 新增落地页 `index.html`、`docs/维护指南.md`、GitHub Actions 自动校验、Pages 部署说明 |",
    1,
)

# 6) 在招人数同步为 151
s = s.replace("| **主页明确写了在招** | **152 位** |", "| **主页明确写了在招** | **151 位** |")
s = s.replace("**152 位主页明确在招**", "**151 位主页明确在招**")

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("README updated")
