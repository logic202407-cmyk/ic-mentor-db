# 同名导师消歧：人工独立标注协议

> 状态：**待收集**。仓库目前**没有**人工金标准；`human_annotation/annotation-template.csv`
> 是空白盲标表，`human_labels.json` 尚不存在。在收集到足够人工判断之前，任何
> Precision / Recall / F1 都只能标注为「程序规则复核」，不得写成人工验证结果。

## 一、为什么需要人工标注

仓库里的 `workbench/evaluation/gold_pairs.json` 由 `adjudicate()` 生成。它按规则读
主页类型（专属页 / 名录页）、站点归属与院系冲突，给出 `verdict`；而 `auto_label`
来自另一套规则 `pair_label()`。**两者都是程序**，所以：

- 它只能回答「自动协议与规则复核是否一致」（报告里给出的那个一致率属于这一类）；
- 它**不能**回答「判定到底准不准」——规则自己不会发现规则的盲区。

人工独立标注要回答的是后者：标注者只看证据，不看模型分数与自动判定。

## 二、样本怎么来（`--export-human`）

- 范围：**同校同名**的全部组合（跨校同名几乎必然是两个人，难度低，不进入主标注集）。
- 分类限流，保证难样本都有代表（每类最多 60 对）。分类（`category`）**只用于内部
  分层抽样与统计，不写进盲标表**——它由程序复核结论派生，给了标注者等于泄漏答案：

| 类别（内部，不公开给标注者） | 含义 | 为什么重要 |
|:--|:--|:--|
| `shared_homepage` | 两条记录指向同一专属主页、院系相同 | 最像同一个人 |
| `shared_homepage_cross_dept` | 同一主页、院系不同 | 可能是交叉任职，也可能是主页接错 |
| `shared_homepage_unit_mismatch` | 同一主页，但站点归属与院系不符 | 最危险的「按姓名接错」 |
| `distinct_personal` | 两个不同的专属主页 | 需要判断是否同一人多主页 |
| `listing_page` | 至少一条指向学院名录页 | 名录页共用不代表同一人 |
| `missing_homepage` | 至少一条缺主页 | 证据不足，通常应为 unknown |

### 盲标可见字段（完整清单）

标注者**只能**看到下面这些公开证据，一行一对：

| 列 | 说明 |
|:--|:--|
| `pair_id` | 配对编号（两条记录 id 排序后哈希，稳定可复现） |
| `a_name` / `b_name` | 两侧记录上的姓名 |
| `a_institution` / `b_institution` | 两侧记录的机构 |
| `a_dept` / `b_dept` | 两侧院系 |
| `a_discipline` / `b_discipline` | 两侧一级学科 |
| `a_home` / `b_home` | 两侧主页 URL |
| `a_page_kind` / `b_page_kind` | 该主页的**公开形态**：`personal`（本人专属页）/ `roster`（名录或多人共用页）/ `none`（未收录）。这是对 URL 与来源标题的确定性归类，不是身份判断 |
| `a_source_urls` / `b_source_urls` | 该记录登记过的来源 URL（最多 5 条），供标注者自行打开核对 |

**明确不提供**（写进 `annotation-template-key.json`，标注者不得查看）：

| 字段 | 为什么不能给 |
|:--|:--|
| `category` | 由 `adjudicate()` 的结论派生（如 `shared_homepage_unit_mismatch`、`listing_page`），等于把程序的身份结论写在脸上 |
| `emb` | 模型嵌入相似度，会诱导标注者按分数而非证据判断 |
| `program_label` / `program_verdict` | 程序自动判定与规则复核结论 |
| `reason` | 程序给出的判定依据代号 |
| `a_id` / `b_id` | 记录级 id（需要回查时用 `pair_id` 在 key 文件里查） |

> 盲标表里仍然保留 `a_page_kind`：标注者本来就需要知道「这一页是不是本人专属页」，
> 否则无法完成标注；它是对**公开 URL 与来源标题**的可复核归类，与「这两个记录是不是
> 同一个人」是两件事。

## 三、标注规则

对每一对记录，先读两边的姓名、机构、院系、一级学科与主页，再打开主页核对。

| 判定 | 适用条件 |
|:--|:--|
| `same_person` | 有**直接证据**表明是同一人：同一专属主页；或主页内容（照片/履历/研究方向）与两条记录同时一致 |
| `different_person` | 有**直接冲突证据**：分属不同机构；或记录中出现标识自然人本身的冲突（出生年、ORCID、邮箱、英文名等）；或主页内容明显是另一个人（照片/履历完全不同） |
| `unknown` | 证据不足、页面打不开、只有名录页、无法判断；**以及「只有院系或一级学科不同」** |

原则：

1. **拿不准就写 `unknown`**。宁可留空，也不猜。`unknown` 不进入指标。
2. 学院名录页、搜索结果页、多人共用页**不能**作为「同一人」的证据。
3. **仅有院系或学科差异，不构成「不同人」的证据**。同一位导师可能跨学科研究、在两个
   院系兼任、因院系调整或历史沿革被录入到不同单位；反过来，同校同名的两个人也常常
   各在一个院系。单位归属差异对这两种假设都成立，因此只能判 `unknown` 并转人工核验。
   （2026-10-26 起程序判据也按此执行：`reason=unit_conflict_only` /
   `same_unit_cross_discipline`。）
4. 一人多主页（课题组页 / 旧版页 / 英文页）→ 若主页内容一致，可判 `same_person`，
   并在 `evidence_note` 注明两个 URL 的关系。
5. 不允许根据「自动判定」「相似度」反推答案；标注时不要打开 key 文件。
6. 判断「这一页是不是人名录页」时，注意 URL 里可能直接写着 `teachers-list`、
   `faculty_list` 之类的列表标记——这类页面即使两条记录都指向它，也**不是**同一人的证据。

## 四、流程

1. 导出：

   ```bat
   .venv\Scripts\python.exe -m workbench.disambiguate_names --export-human workbench/evaluation/human_annotation/annotation-template.csv
   ```

2. 两位标注者**各自独立**填写同一个 CSV（建议复制成 `annotator-A.csv` / `annotator-B.csv`），
   互不讨论。每位标注者填写 `reviewer`（姓名或代号）与 `reviewed_at`（YYYY-MM-DD）。
3. 分歧处理：对两人判定不同的行，由第三人或两人协商后给出最终值，
   在 `evidence_note` 写「分歧记录：A=…，B=…，最终=…，理由=…」。
4. 汇总成一个 CSV（保留最终判定与 reviewer）后导入：

   ```bat
   .venv\Scripts\python.exe -m workbench.disambiguate_names --import-human path\to\final.csv --min-human 30
   ```

5. 导入会写 `workbench/evaluation/human_labels.json` 与 `human_metrics.json`。

## 五、什么时候才允许报告指标

`--min-human`（默认 30）与正负例各 ≥5 的门槛同时满足，工具才会计算
Precision / Recall / F1 与嵌入阈值曲线；否则 `status=insufficient`，
只记录条数，**不输出任何比率**。这是为了防止「3 条标注也算出 100% 精确率」。

## 六、字段说明（CSV）

盲标表的完整表头就是下面这些列（`BLIND_FIELDS + ANNOTATION_FIELDS`）；
**不含 `category`**，也不含任何模型分数或程序判定结果。

| 列 | 说明 |
|:--|:--|
| `pair_id` | 配对编号（由两条记录 id 排序后哈希，稳定可复现） |
| `a_name` / `b_name` | 两侧姓名（同校同名组内两者相同） |
| `a_institution` / `b_institution` | 两侧机构 |
| `a_dept` / `b_dept` | 两侧院系 |
| `a_discipline` / `b_discipline` | 两侧一级学科 |
| `a_home` / `b_home` | 两侧主页 URL |
| `a_page_kind` / `b_page_kind` | 主页公开形态：`personal` / `roster` / `none` |
| `a_source_urls` / `b_source_urls` | 该记录登记过的来源 URL（最多 5 条，分号分隔） |
| `human_verdict` | **必填**：`same_person` / `different_person` / `unknown` |
| `human_confidence` | 选填：`low` / `medium` / `high` |
| `reviewer` | **必填**：标注者代号 |
| `reviewed_at` | **必填**：YYYY-MM-DD |
| `evidence_note` | 判定依据（看到了什么、哪个 URL、哪段履历） |

## 七、数据与隐私

- 只用公开页面；不记录联系方式、身份证号、住址等个人信息。
- 标注文件含真实公开姓名与主页链接，属于公开信息整理；`annotator-*.csv` 为过程文件，
  不入库（`.gitignore` 已忽略 `workbench/evaluation/human_annotation/annotator-*`）。
- 若某条来源已失效，保留原链接并在 `evidence_note` 注明「页面已失效，依据为保存时的快照」。

## 八、当前状态与后续

**人工金标准：待完成。** 仓库里没有任何真实标注者提交的判断，
`human_labels.json` / `human_metrics.json` 均不存在；程序侧的一致率与阈值曲线
**都不是**人工准确率。

- [x] 工具与协议（本文件、导出 CSV、导入校验、指标门槛）
- [x] 程序复核结论已重新标注为「程序辅助核验」
- [x] 盲标表已移除 `category` 等程序判定派生字段（2026-10-26）
- [ ] 招募 **≥2 位** 真实标注者，各自独立填写
- [ ] 完成 **≥30 个独立 `pair_id`**（同一对多份标注只算一条，不会翻倍）
- [ ] 对判定相反的对做**冲突仲裁**，在 `evidence_note` 记录分歧与理由
- [ ] 导入后重算指标；在此之前对外保持「人工金标准待完成」表述