# 同名导师消歧：人工独立标注协议

> 状态：**待收集**。仓库目前**没有**人工金标准；`human_annotation/annotation-template.csv`
> 是空白盲标表，`human_labels.json` 尚不存在。在收集到足够人工判断之前，任何
> Precision / Recall / F1 都只能标注为「程序规则复核」，不得写成人工验证结果。

## 一、为什么需要人工标注

仓库里的 `workbench/evaluation/gold_pairs.json` 由 `adjudicate()` 生成。它按规则读
主页类型（专属页 / 名录页）、站点归属与院系冲突，给出 `verdict`；而 `auto_label`
来自另一套规则 `pair_label()`。**两者都是程序**，所以：

- 它只能回答「自动协议与规则复核是否一致」（一致率 91.3% 属于这一类）；
- 它**不能**回答「判定到底准不准」——规则自己不会发现规则的盲区。

人工独立标注要回答的是后者：标注者只看证据，不看模型分数与自动判定。

## 二、样本怎么来（`--export-human`）

- 范围：**同校同名**的全部组合（跨校同名几乎必然是两个人，难度低，不进入主标注集）。
- 分类限流，保证难样本都有代表（每类最多 60 对）：

| 类别 | 含义 | 为什么重要 |
|:--|:--|:--|
| `shared_homepage` | 两条记录指向同一专属主页、院系相同 | 最像同一个人 |
| `shared_homepage_cross_dept` | 同一主页、院系不同 | 可能是交叉任职，也可能是主页接错 |
| `shared_homepage_unit_mismatch` | 同一主页，但站点归属与院系不符 | 最危险的「按姓名接错」 |
| `distinct_personal` | 两个不同的专属主页 | 需要判断是否同一人多主页 |
| `listing_page` | 至少一条指向学院名录页 | 名录页共用不代表同一人 |
| `missing_homepage` | 至少一条缺主页 | 证据不足，通常应为 unknown |

- 盲标：导出的 CSV **不含**嵌入相似度与自动判定；分数与自动结论另存
  `annotation-template-key.json`，**标注者不得查看**，只在评分时使用。

## 三、标注规则

对每一对记录，先读两边的姓名、机构、院系、一级学科与主页，再打开主页核对。

| 判定 | 适用条件 |
|:--|:--|
| `same_person` | 有**直接证据**表明是同一人：同一专属主页；或主页内容（照片/履历/研究方向）与两条记录同时一致 |
| `different_person` | 有直接冲突：两个不同的专属主页且院系/学科不符；或同名但明显不同研究方向与履历 |
| `unknown` | 证据不足、页面打不开、只有名录页、无法判断 |

原则：

1. **拿不准就写 `unknown`**。宁可留空，也不猜。`unknown` 不进入指标。
2. 学院名录页、搜索结果页、多人共用页**不能**作为「同一人」的证据。
3. 同名同姓、同一学院但不同研究方向 → 通常 `different_person`，但需在 `evidence_note` 写依据。
4. 一人多主页（课题组页 / 旧版页 / 英文页）→ 若主页内容一致，可判 `same_person`，
   并在 `evidence_note` 注明两个 URL 的关系。
5. 不允许根据「自动判定」「相似度」反推答案；标注时不要打开 key 文件。

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

| 列 | 说明 |
|:--|:--|
| `pair_id` | 配对编号（由两条记录 id 排序后哈希，稳定可复现） |
| `category` | 上述困难类别 |
| `name` / `institution` | 同名姓名与机构 |
| `a_*` / `b_*` | 两侧的 id、院系、一级学科、主页 URL、主页类型（personal / roster / none） |
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

- [x] 工具与协议（本文件、导出 CSV、导入校验、指标门槛）
- [x] 程序复核结论已重新标注为「程序辅助核验」
- [ ] 招募两位标注者，完成 ≥30 对独立判断
- [ ] 记录分歧与最终判定，导入后重算指标
- [ ] 技术报告第 5.2 节据此更新；在此之前保持「人工金标准待完成」表述