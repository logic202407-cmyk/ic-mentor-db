# 工程审计报告（接收基线）

- 审计时间：2026-10-23
- 审计对象：`logic202407-cmyk/ic-mentor-db` @ `main` = `9c1c126`
- 审计方式：**实际执行**。本文所有"通过/失败/数字"均来自本机命令输出，不引用 README 的自我声明。
- 审计者身份：新加入的开发代理（GitHub 账号 `3331083641-prog`，`viewerPermission=WRITE`）。
  此前各版本由仓库原团队完成，本文不对其贡献作任何改写或归属主张。

---

## 一、接收与基线（可复现）

### 1.1 仓库接收

| 项 | 实测值 |
|:--|:--|
| 克隆方式 | `git clone https://github.com/logic202407-cmyk/ic-mentor-db.git .`（内容直接落在仓库根，无嵌套目录） |
| 默认分支 | `main`，本地与 `origin/main` 同步，工作区干净 |
| 提交总数 | **198** |
| 远端分支 | `main`、`aic-ai-open-source-2026`（后者已完全并入 main，`rev-list --left-right --count` = `156 0`） |
| 标签 | `v1.0.0`、`v1.1.0` |
| 工作树体积 | 约 154 MB（含 `.git`）；`reports/` 另有 6.3 MB、`data/` 44.4 MB、`workbench/` 54.9 MB |
| LFS | 未使用 LFS，无缺失文件 |

### 1.2 环境

| 项 | 实测值 |
|:--|:--|
| Python | 3.12.4（`D:\Python312\python.exe`）；**`py` 启动器在本机不存在**——文档中所有 `py -3.12` 命令在本机不可直接执行 |
| 虚拟环境 | `.venv`（3.12.4） |
| 依赖安装 | 全局 pip 配置指向清华镜像，**该镜像当日 SSL 失败**（`SSLEOFError`）；改用 `--index-url https://pypi.org/simple` 安装成功。未修改全局 pip 配置 |
| 可选依赖 | `markdown pypdf pypdfium2 pillow pdfplumber` 不在 `requirements.txt` 内，缺省时 3 项测试直接报错 |
| Node | v24.15.0 / npm 11.12.1 |
| 嵌入模型 | `BAAI/bge-small-zh-v1.5` 经 `HF_ENDPOINT=https://hf-mirror.com` 下载成功（41.6 s，512 维） |

### 1.3 基线测试（真实执行）

| 检查 | 命令 | 结果 |
|:--|:--|:--|
| Python 测试 | `python -m unittest discover -s workbench/tests` | **751 项全部通过**（约 51 s） |
| 前端测试 | `node --test workbench/tests/test_ui_races.cjs workbench/tests/test_research_ui.cjs` | **11 项通过** |
| 服务启动 | `uvicorn workbench.app:app --port 8765` | 正常，`/api/health` 返回 `{"ok":true,"model":"BAAI/bge-small-zh-v1.5"}` |
| 接口口径 | `GET /api/catalog/coverage` | `total_records=15719`、`public_records=12546`、`public_institutions=67` |
| 事实表 | `python -m workbench.tools.report_facts` | 见下表 |

**唯一统计口径**（`report_facts` 与 `/api/catalog/coverage` 一致）：

| 概念 | 数值 | 取数方式 |
|:--|--:|:--|
| 记录条数（学科—导师条目） | **15,719** | `catalog.static_catalog()` |
| 其中公开来源记录 | **12,546** | `coverage()['public_records']` |
| 其中官方来源记录 | 12,530 | `coverage()['official_records']` |
| 公开来源机构数 | **67** | `coverage()['public_institutions']` |
| 一级学科数 | **117** | `catalog.disciplines()` |
| 其中工学学科 | **38** | 同上 `engineering` 标记 |
| 工学学科—导师条目 | **11,082** | 工学学科 `count` 之和 |
| 来源模块 / 来源 key | **53 / 139** | `discover_sources()` |
| 离线快照 | **201** | `tests/fixtures/*.html` |
| 最大单一机构占比 < 60% 的学科 | **38 / 38** | `report_facts` 分布统计 |
| 方向待补 / 已有方向 | **5,478 / 10,241** | `infer_directions.label_of` |
| 可读档案 / 论文 / 师承 / 招生 | 12,546 / 3,434 / 376 / 6,620 | `coverage()['research']` |
| 随仓库提交的逐人档案 | **6,498** 份 `dossiers.json.gz` | 实读 gzip 行数 |

> 口径警告：**"记录条数"是"学科—导师关系条目"，不是自然人数量。**同一自然人若在两条来源下各出现一次，会计两条。全库自然人数量目前**没有**独立去重统计，任何"覆盖 N 位导师"的表述都必须加限定语。

---

## 二、状态矩阵（严格区分四类）

图例：**已测** = 本次实跑通过；**仅声明** = 文档写了但本次未独立验证；**未验证** = 本次未跑或环境不可达；**未实现** = 确认不存在。

### 2.1 数据与检索

| 能力 | 状态 | 依据 |
|:--|:--|:--|
| 15,719 条结构化目录 + 117 学科分类 | 已测 | `report_facts`、`/api/catalog/coverage` |
| 38 个工学学科分布达标（<60%） | 已测 | `distribution_audit`（并入验收） |
| 来源溯源（每条含 URL、抓取时间、来源 key） | 已测 | `catalog.static_catalog()` 返回 `sources` |
| 名录页回落标记（`homepage_kind`） | 已测 | `workbench/homepage_kind.py` + 测试 |
| 关键词检索基线 | 已测 | `search.keyword_score` |
| 语义检索（bge-small-zh，带向量缓存与指纹校验） | 已测 | 本机实跑模型推理成功 |
| **语义检索的效果证据** | **仅声明** | 报告第 5 章只有"8 条试点 × 8 查询"，`evaluate_pilot.py` 未在本次执行；无独立测试集、无 Recall@K/MRR/NDCG、无延迟测量 |

### 2.2 AI 两条治理链路

| 能力 | 状态 | 依据 |
|:--|:--|:--|
| 方向补全（混合策略，阈值 0.55） | 已测（管线） | `infer_directions --validate/--apply` 可运行 |
| 报告所称 64.0% / 9.0% / 66.2% | **仅声明** | 本次已重跑复现，结果见 §4.2；**评测协议本身有缺陷** |
| 同名消歧（机构+院系+学科+履历嵌入） | 已测（管线） | `disambiguate_names --evaluate/--review` 可运行 |
| 报告所称 P 86.7% / F1 88.3% / AUC 0.952 | **仅声明** | 本次已重跑；**真值定义即为主要缺陷**，见 §4.1 |
| AI 产物随仓库提交（clone 后可见） | 已测 | `workbench/reference/ai/`、`research/dossiers.json.gz` 实读 |
| **AI 产物与当前数据同步** | **已测：不同步** | 产物内 `pending=4,936`，当前实际待补 **5,478**，缺口 542 条 |

### 2.3 学生向展示

| 能力 | 状态 | 依据 |
|:--|:--|:--|
| 读研体验参考分（四维加权 + 覆盖度归一） | 已测 | `student_score.compute()`；**但产品定位存在问题，见 §4.3** |
| 缺失≠0 | **部分实现** | `guidance_structure`/`team_capacity` 缺失时置 `unknown` 并归一；但 `group_activity` 在**无任何论文记录**时仍算出 0 分，等价于"不活跃"——与文档承诺相反 |
| 四级关系证据 L1–L4 | 已测 | `relations.analyze()`；仅 L1 标为师承，逻辑正确 |
| 关系可视化 | 已测（弱） | `reports/导师关系网络.html` 为静态历史产物；档案页内无交互式网络图 |

### 2.4 调查闭环与工程

| 能力 | 状态 | 依据 |
|:--|:--|:--|
| 核查记录（证据增删改、状态、导出 Markdown） | 已测 | `catalog.*` + `investigation.py` + 测试 |
| 导入导出（CSV/JSON，10 MB、5,000 行上限，去重） | 已测 | `core.parse_import` + 测试 |
| 15 道上传前验收关卡 | **部分可复现** | 实跑 14/15 通过；**`pack_research_bundle --check` 在全新 clone 上直接返回 1**，见 §4.4 |
| 文档数字自动一致 | **覆盖不足** | `check_doc_numbers.mjs` 只校验**旧 IC 专题**（3,179 人 / 22 校），完全不覆盖 15,719 口径与技术报告 |
| 公开前隐私审计 | **覆盖不足** | `audit_prepublish.mjs` 17 项检查同样针对旧专题产物；对 `workbench/reference/**` 的大文件与新增来源只查"邮箱/电话"两类 |
| CI | 已测（存在） | `.github/workflows/validate.yml` 新增工作台校验 job |
| 独立用户研究 | **未实现** | 报告第 5 章已如实说明，不声称效率提升 |

---

## 三、真实缺陷清单（按优先级）

### P0 — 会造成"对外材料自相矛盾"，必须先修

| # | 缺陷 | 证据 | 影响 |
|:--|:--|:--|:--|
| P0-1 | 技术报告规模数字过期 | `技术报告.md:382-383` 写 **15,177 条 / 工学 10,540 / 公开来源 12,004 / 61 所**；事实表为 **15,719 / 11,082 / 12,546 / 67** | 读者按报告核对接口会立刻对不上；这是评审可一击命中的硬伤 |
| P0-2 | 两份 AI 证据文档口径过期 | `evidence/方向推断评测.md:8` 写 14,271 条、待补 4,936；`evidence/同名消歧评测.md:9` 写 14,271 条、979 组 / 2,231 条 | 与 P0-1 同源，且与 AI 产物自身一致、但与当前数据不一致 |
| P0-3 | `competition_readiness.md` 停留在旧版本 | 写 10,441 条、75 项测试、8 条试点检索 | 该文档是自查依据，过期会误导后续决策 |
| P0-4 | CHANGELOG / 提交材料测试数过期 | CHANGELOG `1.1.0` 写 715 项；`aic-submission/README.md:40` 写 694 项；实测 **751 项** | 三个数字互相矛盾 |
| P0-5 | 数字一致性工具**不覆盖**当前口径 | `check_doc_numbers.mjs` 只查 3,179/22 校；`report_facts` 只算不校验 | 是 P0-1~4 反复复发的**根因**。不修它，下一次扩数据还会错 |
| P0-6 | `pack_research_bundle --check` 在全新 clone 上失败 | `.workbench-data/public-research` 被 gitignore；缺失即 `return 1` | 验收"一条命令全绿"的声明在他人环境不成立，直接损害复现性主张 |

### P1 — 影响 AI 结论的可信度（本赛道核心）

| # | 缺陷 | 证据 | 影响 |
|:--|:--|:--|:--|
| P1-1 | **同名消歧真值定义不成立** | `disambiguate_names.py:11-17` 断言"两两不同 URL 必为不同人" | 一人多主页 / 学校改 URL / 名录页共用 → 标注噪声混入标签；用户明确要求改 |
| P1-2 | **方向推断存在分布偏移 + 自我验证** | 验证池 = "已有方向"记录（履历常直接写"研究方向：X"）；推断目标 = "方向待补"记录（按定义缺这句） | 66.2% 不能迁移到真实目标集；且 verbatim 分层用同一 `keyword_score` 定义与预测，属循环论证 |
| P1-3 | 混合策略 Top-3 计算错误 | `infer_directions.py:173` 关键词命中时 `top3` 只含 1 个元素 | 系统性低估混合 Top-3 |
| P1-4 | 检索评测体系不成立 | 8 条试点 × 8 查询，无独立测试集、无 Recall@K/MRR/NDCG、无延迟、无低相关过滤 | "AI 显著优于关键词"无法证明，"AI 是否有用"也无法回答 |
| P1-5 | 嵌入单用 Top-1 仅 9.0% 的原因未定位 | `profile_text` 把 600 字履历 + 院系 + 学科 + 论文题拼接后整体编码 | 用户已点名的怀疑点；需字段分离实验 |
| P1-6 | AI 产物落后当前数据 542 条 | `reference/ai/direction_suggestions.json` pending=4,936 vs 实际 5,478 | 最新记录无建议，界面与数据不同步 |

### P2 — 产品表达、界面与材料

| # | 缺陷 | 证据 | 影响 |
|:--|:--|:--|:--|
| P2-1 | "读研体验参考分"名不副实 | `student_score.py` 四维加权后输出单一综合分；`team_capacity` 用 `log1p(学生数)/log1p(30)`，人为设定"30 人=100 分" | 用户明确要求改为分维度证据展示、取消跨导师综合排名 |
| P2-2 | `group_activity` 把"无数据"算成 0 分 | `int(row.get("recent3") or 0)` | 与"缺失≠0"的文档承诺直接矛盾 |
| P2-3 | 评测结果无可视化 | 报告只有表格数字 | 用户要求方法对比条形图、阈值曲线、消融图、失败案例、推理流程图 |
| P2-4 | 演示脚本与材料需与整改后系统对齐 | `演示视频脚本.md`、`录制提词稿.txt` | 视频尚未录制，脚本必须与最终功能一致 |
| P2-5 | `LICENSE-DATA` 与实际收集字段/来源授权的一致性未复核 | 本次未逐项核 | 涉及第三方权利，公开材料须如实 |

---

## 四、复现实验记录

### 4.1 同名消歧（重跑，`--evaluate --review`）

结果见 `workbench/aic-submission/evidence/同名消歧评测.md` 更新后的版本。**本次重跑的首要目的不是复现数字，而是证明"URL 当真值"这一协议本身有标注噪声**：需构造独立人工复核集替代。

### 4.2 方向推断（重跑，`--validate 400`）

重跑结果与报告数字的差异、以及分层结论的可靠性，记录于 `evidence/方向推断评测.md`（整改后版本）。

### 4.3 参考分

`student_score.compute()` 在无 `recent3` 字段时输出 0 分而非 unknown——已由代码阅读确认，将补测试固定。

---

## 五、整改计划与验收标准

| 阶段 | 内容 | 验收 |
|:--|:--|:--|
| S1 口径统一 | 修 P0-1~4；新增**工作台事实表一致性检查**并纳入验收（P0-5）；修 `pack_research_bundle --check` 的 clean-clone 行为（P0-6） | `acceptance` 15/15；全新 clone 上同样 15/15 |
| S2 算法真值 | 同名消歧改用独立人工复核小集 + 保守合并（P1-1）；方向推断控制偏移与循环论证、修 Top-3（P1-2/3/5）；重建检索评测（P1-4）；重跑并同步 AI 产物（P1-6） | 每项都有可重跑脚本、固定种子、原始基线保留、失败案例记录 |
| S3 产品表达 | 参考分改为「课题组公开信息观察」分维度展示、取消综合排名（P2-1/2）；关系网络交互化 | 缺失≠0 有测试；页面无跨导师综合排名 |
| S4 界面 | 首页信息架构、档案页分区、评测可视化 | 全部数值来自评测产物；响应式与键盘可用 |
| S5 材料 | 技术报告数字同步 + 重新生成 HTML/PDF（≤15 页 / ≤10 MB）；演示脚本对齐 | `check_report_sync`、`check_pdf_limits`、`pdf_layout_check` 全绿 |

### 协作与提交纪律

- 不做 `git init`，不改写历史，不用 `push --force` / `reset --hard`。
- 每次推送前 `git fetch` + 检查并行提交；冲突按双方独立正确性合并，冲突不可靠解决时保留现场并上报。
- 每个阶段：本地测试 → 实际效果检查 → 回归 → Git 提交 → 推送 → 核实远端。
- 提交信息描述真实修改；不声称未执行的验证。