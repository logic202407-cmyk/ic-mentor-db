# API 说明

服务默认监听 `http://127.0.0.1:8765`，所有接口都在同一源下，前端直接调用。

**约定**

- 请求与响应均为 JSON（`Content-Type: application/json`）；`/api/catalog/mentor/{id}/report.md` 返回 Markdown 文本。
- 写请求（`POST` / `PATCH` / `DELETE`）**必须带 `Origin` 头**，否则拒绝（本地 CSRF 防线）；`Host` 也做白名单校验。
- 请求体上限 12 MB；超限直接拒绝。
- 语义检索相关接口在向量模型不可用时**不返回 500**：检索类回落到 BM25 并在结果里带 `fallback`；`/openalex/*` 这类外部接口失败只影响该请求。
- 错误响应的 `detail` 是稳定的中文提示，**不回显 Python 异常原文**（原文只进服务端日志）。
- 本表按 `workbench/app.py` 的路由声明核对；**字段级口径以源码为准**，本文件不重复声明字段（避免文档与实际字段漂移）。

共 **38 个 API 路由**（GET 21 / POST 11 / PATCH 4 / DELETE 2；另有 4 个页面路由：`/`、`/eval`、`/classic`、`/legacy/network`）。

## 健康检查

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/health` | 返回服务状态、当前语义模型名与存储类型。脚本用它等启动。 |

## 导师目录（`/api/catalog`）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/catalog/name` | 按姓名查同名候选（身份核对入口） |
| GET | `/api/catalog/research` | 按已收录研究方向与学科查导师：`q`、`discipline`、`institution`、`direction`、`project_id`、`include_non_engineering`、`admission_signal` 可组合；关键词无匹配时返回空数组，含明确中英文同义词，不使用姓名、AI 推断或相似结果兜底 |
| GET | `/api/catalog/scope` | 学科范围（默认工学 38 个一级学科 / 含非工科） |
| GET | `/api/catalog/disciplines` | 一级学科列表与各学科记录数 |
| GET | `/api/catalog/institutions` | 机构（高校/院所）列表 |
| GET | `/api/catalog/directions` | 研究方向列表 |
| GET | `/api/catalog/mentors` | 按学科 / 机构 / 方向筛选导师候选 |
| GET | `/api/catalog/summary` | 首页用的汇总数字（**不含逐项明细**，明细见 `coverage`） |
| GET | `/api/catalog/coverage` | 覆盖统计：全库、工学、公开来源、机构数、学科分布 |
| GET | `/api/catalog/relations/summary` | 学术关系汇总（L1–L4 证据分层） |
| GET | `/api/catalog/mentor/{mentor_id}` | 导师完整档案（前端按五个折叠模块呈现） |
| GET | `/api/catalog/mentor/{mentor_id}/report.md` | 导出该导师档案为 Markdown |

## AI 建议（待复核）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/catalog/ai-hints` | 概览；产物未生成时计数为 0，不报错 |
| GET | `/api/catalog/mentor/{mentor_id}/ai-hints` | 某位导师的方向建议与同名待核提示 |

> 这两个接口返回的是**机器建议**，逐条带分数与候选，**不写入原始字段**；界面必须显示"不构成事实、不会被自动写入"。

## 调查记录与证据

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/catalog/mentor/{mentor_id}/investigation` | 该导师的本地调查记录概览 |
| POST | `/api/catalog/mentor/{mentor_id}/investigation` | 开始/更新调查记录 |
| PATCH | `/api/catalog/mentor/{mentor_id}/case` | 局部更新该导师的调查档案字段 |
| POST | `/api/catalog/mentor/{mentor_id}/evidence` | 追加一条证据 |
| PATCH | `/api/catalog/mentor/{mentor_id}/evidence/{evidence_id}` | 修改一条已记录的证据 |
| DELETE | `/api/catalog/mentor/{mentor_id}/evidence/{evidence_id}` | 删除一条证据 |
| POST | `/api/catalog/mentor/{mentor_id}/papers` | 追加一条论文线索 |
| DELETE | `/api/catalog/mentor/{mentor_id}/papers/{paper_id}` | 删除一条论文线索 |

写操作走 `workbench/storage.py`：文件锁 + 唯一临时文件 + fsync + 原子替换，覆盖前保留 `.bak`；JSON 损坏时可从 `.bak` 恢复。

## 公开来源

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| POST | `/api/catalog/mentor/{mentor_id}/public-research` | 刷新该导师的公开来源档案（读离线快照，**不联网**） |

## 论文元数据（可选联网）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/catalog/mentor/{mentor_id}/openalex/authors` | 查询候选同名作者 |
| POST | `/api/catalog/mentor/{mentor_id}/openalex/refresh` | 按 DOI / 作者刷新论文元数据 |

> 这两个接口需要外网。**失败不影响本地查询**；结果只作为**候选**，不自动认定论文归属。

## 调查项目与检索（`/api/projects`）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 新建项目 |
| POST | `/api/demo` | 生成演示项目 |
| GET | `/api/projects/{project_id}` | 项目详情 |
| POST | `/api/projects/{project_id}/import` | 导入档案（CSV / JSON，字段白名单校验） |
| POST | `/api/projects/{project_id}/profiles` | 向项目添加导师档案 |
| PATCH | `/api/projects/{project_id}/profiles/{profile_id}` | 局部更新某个导师档案的字段 |
| POST | `/api/projects/{project_id}/profiles/{profile_id}/sources` | 给档案添加来源 |
| PATCH | `/api/projects/{project_id}/profiles/{profile_id}/sources/{source_id}` | 修改某条来源记录 |
| POST | `/api/projects/{project_id}/search` | 检索导师。`mode` ∈ `semantic` / `keyword` / `bm25` / `hybrid` / `auto` |
| GET | `/api/projects/{project_id}/export` | 导出调查记录 |

`search` 的 `mode=auto` 对英文缩写（如 `VLSI`、`MEMS`、`EDA`）优先走 BM25，其余走混合检索；向量模型不可用时回落 BM25 并在响应里带 `fallback` 说明。

## 算法评测（只读）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/evaluation/summary` | 检索 / 方向推断 / 同名消歧的评测产物摘要 |

> 只读，不触发计算。产物缺失时返回空结构。评测页 `/eval` 用它渲染。
