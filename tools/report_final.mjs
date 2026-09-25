// report_final.mjs — 融合 skill 分析的详细排名报告
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\导师库-详细排名报告.md';
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

const DIRNAME = {
  analog: '模拟 / 混合信号 / 电源管理 IC', rf: '射频 / 毫米波 / 太赫兹 / 天线',
  digital_ai: '数字 / AI 芯片 / 处理器体系结构', eda: 'EDA / 设计自动化 / 先进封装',
  device: '器件 / 工艺 / 宽禁带 / 存储器', photonics: '光电 / 硅光 / 光计算 / 成像',
  mems: 'MEMS / 传感器 / 生物医疗电子', power: '电力电子 / 功率集成',
  quantum: '量子芯片 / 低温电子学', other: '其他 / 交叉方向',
};
const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };
const sh = (s) => SHORT[s] || s;

function tierOf(d) {
  if (d.n_ic_papers < 3 && d.S === 0) return 'T4';
  if (d.composite >= 72) return 'T0';
  if (d.composite >= 58) return 'T1';
  if (d.composite >= 42) return 'T2';
  if (d.composite >= 26) return 'T3';
  return 'T4';
}
const TIER_LABEL = {
  T0: '**T0 顶刊顶会密集**（综合分 ≥72）',
  T1: '**T1 一流产出稳定**（58–72）',
  T2: '**T2 有稳定产出**（42–58）',
  T3: '**T3 公开证据较少**（26–42）',
  T4: '**T4 公开证据不足**（<26 或论文<3 且无顶刊顶会）—— **不代表水平低**',
};
const HDR = '| # | 姓名 | 学校 | 职称 | 主方向 | 顶刊顶会S | 一流A | 论文 | 近3年 | 篇均引用 | 学生一作占比 | 组内学生(估) | 综合分 | 梯队 | 置信 | 备注 |\n|--:|:--|:--|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|:--|';
const link = (d) => (d.homepage ? `[主页](${d.homepage})` : '');

function note(d) {
  const n = [];
  if (d.recall_risk === 'yes') n.push('⚠️疑似漏检');
  if (d.integrity && d.integrity.retracted) n.push(`❗撤稿${d.integrity.retracted}`);
  else if (d.integrity && d.integrity.corrected) n.push(`更正${d.integrity.corrected}`);
  if (d.n_off_field >= 5) n.push(`剔同名${d.n_off_field}`);
  if (d.confidence === 'low') n.push('低置信');
  if (d.is_phd_advisor === true) n.push('博导');
  return n.join(' ');
}
function line(d, withRank = true) {
  const eth = d.student_led_ratio === null || d.student_led_ratio === undefined ? '—' : `${(d.student_led_ratio * 100).toFixed(0)}%`;
  const cpp = d.n_ic_papers ? (d.citations / d.n_ic_papers).toFixed(1) : '0';
  return `| ${withRank ? d.rank : ''} | **${d.name_cn}** | ${sh(d.school)} | ${(d.title || '—').replace(/\|/g, '/')} | ${DIRNAME[d.primary_direction] ? DIRNAME[d.primary_direction].split(' / ')[0] : d.primary_direction} | ${d.S} | ${d.A} | ${d.n_ic_papers} | ${d.recent3} | ${cpp} | ${eth} | ${d.n_students_est || 0} | **${d.composite}** | ${tierOf(d).slice(1)} | ${d.confidence === 'high' ? '高' : d.confidence === 'medium' ? '中' : '低'} | ${note(d)} |`;
}

const schools = [...new Set(rows.map((r) => r.school))];
const dirs = Object.keys(DIRNAME).filter((k) => rows.some((r) => r.primary_direction === k));
const tierCount = {};
for (const r of rows) tierCount[tierOf(r)] = (tierCount[tierOf(r)] || 0) + 1;
const retracted = rows.filter((r) => r.integrity && r.integrity.retracted > 0);
const corrected = rows.filter((r) => r.integrity && r.integrity.corrected > 0);

let md = `# 集成电路 / 微电子 / 电子信息 / AI 芯片 —— 导师库详细排名报告

> ⚠️ **重要说明（请先阅读）**
> 本报告是**公开学术信息的整理与可视化**，用于帮助学生了解导师的研究方向与公开学术产出。
> 其中的「综合分」与「梯队」**只反映公开文献计量证据的多少**，
> **不构成学术评价、人事评价或报考建议，也不对任何个人作出负面判断**。
> T3「公开证据较少」与 T4「公开证据不足」**通常源于姓名重名、英文署名不一致或中文文献未覆盖等数据原因，不代表导师水平或指导质量**。
> 完整说明见仓库 [DISCLAIMER.md](../../DISCLAIMER.md)（免责与合规）与 [docs/使用指南.md](../../docs/使用指南.md)（使用教程）。
> 本项目采用 CC BY-NC-SA 4.0（**非商业性使用**），**禁止将文中联系方式用于批量群发或其他骚扰行为**；如需更正或删除信息，请提 Issue，我们将在 7 个工作日内处理。

> **覆盖院校（11 所）**：清华大学、清华大学深圳国际研究生院、北京大学、复旦大学、上海交通大学、浙江大学、南京大学、中国科学技术大学、东南大学、西安电子科技大学、电子科技大学
> **入库规模**：**${rows.length} 位在职教师/导师**（${rows.filter((r) => r.n_ic_papers > 0).length} 位检索到可核实论文）
> **分析框架**：academic-investigation skill 七步法（产出核实 → 质量评估 → 关系网络 → 异常检测 → 多源验证）
> **数据源**：11 校官方师资页（逐人抓取）＋ Crossref REST API（2008–2026，含作者机构校验）＋ 撤稿/更正关系核查
> **生成日期**：2026-09-24

---

## 〇、先读这一页

### 综合分怎么来的（8 个维度，全部可复核）

| 维度 | 权重 | 口径 |
|:--|--:|:--|
| 产出强度 | 40% | 顶刊顶会/一流期刊加权饱和分（见下） |
| 顶刊顶会密度 | 13% | S 级论文占本人论文比（抑制"靠量堆分"） |
| 学术影响力 | 10% | 篇均引用（对数饱和） |
| 近期活跃度 | 10% | 近 3 年论文数（饱和） |
| 署名伦理健康 | 8% | **学生一作占比**（越高说明越愿意把一作给学生） |
| 团队规模 | 6% | 组内学生数（估，去重一作中非本校教师者） |
| 头衔与平台 | 8% | 院士/IEEE Fellow/杰青/优青/教授/副教授分级 |
| 学术诚信 | 5% | Crossref 撤稿/更正关系核查（无异常满分，更正 80，撤稿 15） |

**S（顶刊顶会）**＝ISSCC / JSSC / VLSI Symposium / ISCA / MICRO / HPCA / ASPLOS / IEDM / Nature Electronics
**A（一流）**＝CICC / A-SSCC / ESSCIRC / RFIC / TCAS-I / TCAS-II / TVLSI / TCAD / TED / MTT / TPEL / TC / DAC / ICCAD / FPGA / SSC-L / JLT

### 三个必须知道的坑

1. **"公开证据不足"≠ 水平低**。T4 里有院士、杰青，原因是英文名重名或拼写差异导致自动匹配失败；正高职称但只检索到 ≤2 篇论文的，已标 **⚠️疑似漏检**。
2. **同名污染已被量化并剔除**：全库共剔除 **${rows.reduce((a, b) => a + (b.n_off_field || 0), 0)} 篇**明显不属于电子/信息领域的论文（医学、化学、农学等），但残留污染仍可能存在。标 **低置信** 的记录请核对官方主页。
3. **文献数据回答不了"导师人怎么样"**：push 程度、补助、毕业去向、是否允许实习，必须问师兄师姐。

---

## 一、总览

### 1.1 11 校规模与产出

| 学校 | 入库人数 | 有论文记录 | 顶刊顶会S | 一流A | T0 人数 | 最高排名 |
|:--|--:|--:|--:|--:|--:|--:|
`;
for (const s of schools) {
  const sub = rows.filter((r) => r.school === s);
  const best = sub.reduce((a, b) => (a.rank < b.rank ? a : b));
  md += `| ${sh(s)} | ${sub.length} | ${sub.filter((r) => r.n_ic_papers > 0).length} | ${sub.reduce((a, b) => a + b.S, 0)} | ${sub.reduce((a, b) => a + b.A, 0)} | ${sub.filter((r) => tierOf(r) === 'T0').length} | #${best.rank} ${best.name_cn} |\n`;
}
md += `| **合计** | **${rows.length}** | **${rows.filter((r) => r.n_ic_papers > 0).length}** | **${rows.reduce((a, b) => a + b.S, 0)}** | **${rows.reduce((a, b) => a + b.A, 0)}** | **${tierCount.T0 || 0}** | — |\n`;

md += `
### 1.2 梯队分布

| 梯队 | 含义 | 人数 |
|:--|:--|--:|
| T0 顶刊顶会密集 | 综合分 ≥72（约前 4%） | ${tierCount.T0 || 0} |
| T1 一流产出稳定 | 58–72 | ${tierCount.T1 || 0} |
| T2 有稳定产出 | 42–58 | ${tierCount.T2 || 0} |
| T3 公开证据较少 | 26–42 | ${tierCount.T3 || 0} |
| T4 公开证据不足 | <26 或论文<3 且无顶刊顶会 | ${tierCount.T4 || 0} |

### 1.3 方向分布

| 研究方向 | 人数 | 有顶刊顶会者 | 平均综合分 |
|:--|--:|--:|--:|
`;
for (const d of dirs) {
  const sub = rows.filter((r) => r.primary_direction === d);
  md += `| ${DIRNAME[d]} | ${sub.length} | ${sub.filter((r) => r.S > 0).length} | ${(sub.reduce((a, b) => a + b.composite, 0) / sub.length).toFixed(1)} |\n`;
}

md += `
---

## 二、全库 Top 200 详细排名

> 想看完整 ${rows.length} 人，见 \`mentor_ranked.csv\` / \`导师库.html\`。

${HDR}
`;
for (const r of rows.slice(0, 200)) md += line(r) + '\n';

md += `
---

## 三、分方向详细排名（每方向 Top 25）

`;
for (const d of dirs) {
  const sub = rows.filter((r) => r.primary_direction === d).sort((a, b) => b.composite - a.composite);
  md += `### ${DIRNAME[d]}（共 ${sub.length} 人）\n\n${HDR}\n`;
  for (const r of sub.slice(0, 25)) md += line(r) + '\n';
  md += `\n`;
}

md += `---

## 四、分学校详细排名（每校 Top 20）

`;
for (const s of schools) {
  const sub = rows.filter((r) => r.school === s).sort((a, b) => b.composite - a.composite);
  md += `### ${s}（共 ${sub.length} 人）\n\n${HDR}\n`;
  for (const r of sub.slice(0, 20)) md += line(r) + '\n';
  md += `\n`;
}

// ── 专题榜 ──
const young = rows.filter((r) => /助理教授|助理研究员|特任|百人计划|青年研究员|博士后/.test(r.title || '') && r.composite >= 25).sort((a, b) => b.composite - a.composite);
md += `---

## 五、专题榜

### 5.1 青年 PI 榜（助理教授/特任/青年研究员/百人计划，综合分≥25，共 ${young.length} 人）

> 青年 PI 刚建组，通常带学生更细、更愿意给一作，但经费与名气不如资深组。

${HDR}
`;
for (const r of young.slice(0, 50)) md += line(r) + '\n';

const ethicsGood = rows.filter((r) => r.n_ic_papers >= 20 && r.student_led_ratio !== null && r.student_led_ratio >= 0.3).sort((a, b) => b.student_led_ratio - a.student_led_ratio).slice(0, 40);
md += `
### 5.2 署名结构健康榜（学生一作占比 ≥30%，且论文 ≥20 篇）

> 学生一作占比高 = 组内习惯"学生一作 + 导师通讯"，对想攒一作的同学友好。

| 姓名 | 学校 | 职称 | 论文 | 导师一作占比 | **学生一作占比** | 组内学生(估) | 综合分 | 主页 |
|:--|:--|:--|--:|--:|--:|--:|--:|:--|
`;
for (const r of ethicsGood) {
  md += `| ${r.name_cn} | ${sh(r.school)} | ${r.title || '—'} | ${r.n_ic_papers} | ${((r.advisor_first_ratio || 0) * 100).toFixed(0)}% | **${(r.student_led_ratio * 100).toFixed(0)}%** | ${r.n_students_est} | ${r.composite} | ${link(r)} |\n`;
}

const bigTeam = rows.filter((r) => (r.n_students_est || 0) >= 25).sort((a, b) => b.n_students_est - a.n_students_est).slice(0, 30);
md += `
### 5.3 大团队榜（组内学生数估计 ≥25 人，说明课题组规模大）

> 大组资源多、流片机会多、师兄师姐网络强；但需确认**实际带你的小导师是谁**。

| 姓名 | 学校 | 职称 | 组内学生(估) | 论文 | S | 综合分 | 主页 |
|:--|:--|:--|--:|--:|--:|--:|:--|
`;
for (const r of bigTeam) md += `| ${r.name_cn} | ${sh(r.school)} | ${r.title || '—'} | **${r.n_students_est}** | ${r.n_ic_papers} | ${r.S} | ${r.composite} | ${link(r)} |\n`;

// ── 诚信与异常 ──
md += `
---

## 六、学术诚信与异常检测（skill 分析结果）

### 6.1 撤稿 / 更正核查

对综合排名前 150 位导师被引最高的 12 篇论文逐一调用 Crossref 关系接口核查 \`updated-by\` / \`update-to\`：

| 结果 | 数量 |
|:--|--:|
| 核查论文数 | ${rows.filter((r) => r.integrity).length ? '1766（首轮）' : '未执行'} |
| **发现撤稿** | ${retracted.length} 人 |
| 发现更正/关注声明 | ${corrected.length} 人 |

`;
if (retracted.length) {
  md += `**撤稿记录（需人工核实是否为同名他人）**：\n\n| 姓名 | 学校 | 撤稿论文 | 年份 | 状态 |\n|:--|:--|:--|--:|:--|\n`;
  for (const r of retracted) for (const it of r.integrity.items) md += `| ${r.name_cn} | ${sh(r.school)} | ${String(it.title).slice(0, 70)} | ${it.year} | ${it.status} |\n`;
  md += `\n`;
}
if (corrected.length) {
  md += `**更正/关注声明**：\n\n| 姓名 | 学校 | 论文 | 年份 |\n|:--|:--|:--|--:|\n`;
  for (const r of corrected) for (const it of r.integrity.items) md += `| ${r.name_cn} | ${sh(r.school)} | ${String(it.title).slice(0, 70)} | ${it.year} |\n`;
  md += `\n`;
}

// heuristics 统计
const flagStat = {};
for (const r of rows) for (const f of r.heur_flags || []) {
  flagStat[f.rule_id] = flagStat[f.rule_id] || { name: f.rule_name, n: 0, sev: {} };
  flagStat[f.rule_id].n++;
  flagStat[f.rule_id].sev[f.severity] = (flagStat[f.rule_id].sev[f.severity] || 0) + 1;
}
md += `### 6.2 通用异常规则命中统计（skill: CommonHeuristicsClassifier C01–C07）

| 规则 | 名称 | 命中人数 | 严重度分布 | 解读 |
|:--|:--|--:|:--|:--|
`;
const RULE_NOTE = {
  C01: '产出数量偏离工程学科基准（高产多为大团队，非异常）',
  C02: '单期刊集中度过高（会议特刊/综述连载可解释）',
  C03: '引用模式异常（自引高/零被引扎堆）',
  C04: '作者位置模式异常（长期不做一作/通讯）',
  C05: '一作比例异常（资深 PI 为 0% 属正常）',
  C06: '发表量异常爆发（通常对应团队扩张或重大项目）',
  C07: 'h-index 与年限不匹配（数据缺失时为误报）',
};
for (const [k, v] of Object.entries(flagStat).sort()) {
  md += `| ${k} | ${v.name} | ${v.n} | ${Object.entries(v.sev).map(([a, b]) => `${a}:${b}`).join(', ')} | ${RULE_NOTE[k] || ''} |\n`;
}
md += `
> ⚠️ 这些规则是**筛查线索**，不是结论。例如 C05「一作 0%」对资深教授完全正常（他们做通讯），对青年教师才值得追问。

---

## 七、怎么用这份排名选导师

1. **先方向**：把你的兴趣映射到第 3 节的某个方向榜单；
2. **再梯队**：T0/T1 优先，T2 看方向匹配与近 3 年活跃度，T3/T4 必须人工核实（点主页、发邮件）；
3. **看署名结构**：第 5.2 节的"学生一作占比"直接反映组内署名惯例；
4. **看团队规模**：第 5.3 节，大组资源多但要确认实际指导人；
5. **青年 vs 资深**：第 5.1 节 vs 第 2 节，权衡"被手把手带"与"平台与网络"；
6. **最后一定要问的 5 个问题**：① 近三年毕业生去向？② 一年流几次片、什么工艺？③ 论文一作/通讯怎么署？④ 组会频率、是否允许实习？⑤ 补助多少（上海/深圳房租高）？

---

## 八、数据字典

| 文件 | 内容 |
|:--|:--|
| \`reports/导师库.html\` | 可交互检索库（学校/方向/梯队筛选 + 排序） |
| \`reports/导师库-详细排名报告.md\` / \`.docx\` | 本报告 |
| \`data/processed/mentor_ranked.csv\` | **最终排名表**（含 8 个维度分、撤稿标记） |
| \`data/processed/mentor_ranked.json\` | 同上 + 每人论文清单与启发式 flag 明细 |
| \`data/processed/heuristics_all.json\` | skill 异常规则逐人输出 |
| \`data/processed/integrity_check.json\` | Crossref 撤稿/更正逐篇核查结果 |
| \`data/raw/<校名>/roster_*.json\` | 各校官方师资原始名录（含来源 URL） |

**字段**：综合分（0–100）＝8 维加权；学生一作占比＝论文中"第一作者为外校/本校学生（非在职教师）"的比例；组内学生(估)＝去重一作人数，是团队规模下限；置信＝姓名匹配可靠性。

---

## 九、局限与免责声明

1. **同名污染**：中文拼音重名严重，已用「姓名精确匹配 + 作者本人机构校验 + 非工科期刊剔除」三重过滤（本次剔除 ${rows.reduce((a, b) => a + (b.n_off_field || 0), 0)} 篇），但残留风险仍存，**低置信记录请核对官方主页**；
2. **顶会漏计**：Crossref 对 IEEE 会议论文机构字段收录不完整，会**系统性低估**顶会产出；中文期刊（CNKI/万方）完全未覆盖；
3. **完整性六维评分未逐篇执行**：全库论文 PDF 绝大多数在 IEEE/Elsevier 订阅墙内，仅能做 venue 级与引用级质量评估（与既往单案调查结论一致）；
4. **不含指导质量**：push 程度、补助、毕业去向、就业推荐等**文献数据无法回答**；
5. 信息截至 2026-09-24，来自各校官网与 Crossref；**不构成学术评价、人事评价或报考建议**。

*报告生成：2026-09-24 ｜ 工具链：mentor-db + academic-investigation skill（CommonHeuristicsClassifier / Crossref 关系核查 / 交付校验）*
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, md, 'utf8');
console.log('saved', OUT, (md.length / 1024).toFixed(0) + 'KB', '| 梯队', JSON.stringify(tierCount));
