// report_recommend.mjs — 生成「导师推荐与招生信息」报告（中性版）
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const PROC = path.join(REPO, 'data', 'processed');
const OUT = path.join(REPO, 'reports', '导师推荐与招生信息.md');
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));
// 全库规模动态读取，避免文案与数据脱节
const RANKED = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const TOTAL = RANKED.length;
const N_SCHOOLS = new Set(RANKED.map((d) => d.school)).size;

const schoolNames = [...new Set(RANKED.map((d) => d.school))];
const schoolNamesDot = schoolNames.join(' · ');
const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电', 哈尔滨工业大学: '哈工大', 天津大学: '天大', 华中科技大学: '华科', 北京航空航天大学: '北航', 西安交通大学: '西交', 中国科学院微电子研究所: '中科院微电子所', 中国科学院半导体研究所: '中科院半导体所', 中国科学院上海微系统与信息技术研究所: '中科院上海微系统所', 中国科学院计算技术研究所: '中科院计算所', 中国科学院自动化研究所: '中科院自动化所', 中国科学院上海高等研究院: '中科院上海高研院', 中国科学院: '中科院' };
const sh = (s) => SHORT[s] || s;
const TIER_LABEL = { T0: '顶刊顶会密集（≥72）', T1: '一流产出稳定（58–72）', T2: '有稳定产出（42–58）', T3: '公开证据较少（26–42）', T4: '公开证据不足（<26 或论文<3）' };
const HDR = '| # | 姓名 | 学校 | 职称 | 主方向 | 综合分 | 梯队 | S/A | 论文 | 近3年 | 引用 | 学生(估) | 招生 | 主页 |\n|--:|:--|:--|:--|:--|--:|:--:|:--|--:|--:|--:|--:|:--|:--|';

function line(d, i) {
  const rc = d.recruit_signal_count > 0 ? '✅在招' : '未明';
  return `| ${i} | **${d.name}** | ${sh(d.school)} | ${(d.title || '—').replace(/\|/g, '/')} | ${d.group_name} | ${d.composite} | ${d.tier} | ${d.S}/${d.A} | ${d.n_ic_papers} | ${d.recent3} | ${d.citations} | ${d.n_students_est || 0} | ${rc} | ${d.homepage ? '[主页](' + d.homepage + ')' : '—'} |`;
}
function tbl(list, n) {
  return HDR + '\n' + list.slice(0, n).map((d, i) => line(d, i + 1)).join('\n');
}

const groups = [...new Set(rows.flatMap((d) => d.group_names))];
const schools = [...new Set(rows.map((d) => d.school))];
const recruiting = rows.filter((d) => d.recruit_signal_count > 0).sort((a, b) => b.composite - a.composite);
const young = rows.filter((d) => /助理教授|准聘|青年研究员|特任|百人计划|助理研究员|博士后/.test(d.title || '') && d.composite >= 45).sort((a, b) => b.composite - a.composite);
const ethicsGood = rows.filter((d) => d.n_ic_papers >= 20 && d.student_led_ratio !== null && d.student_led_ratio >= 0.3).sort((a, b) => b.student_led_ratio - a.student_led_ratio);
const bigTeam = rows.filter((d) => (d.n_students_est || 0) >= 20).sort((a, b) => b.n_students_est - a.n_students_est);

let md = `# 集成电路设计与 AI 交叉方向 · 导师推荐与招生信息

> ⚠️ **重要说明（请先阅读）**
> 本报告是**公开学术信息的整理与可视化**，用于帮助学生了解导师的研究方向与公开学术产出。
> 其中的「综合分」与「梯队」**只反映公开文献计量证据的多少**，
> **不构成学术评价、人事评价或报考建议，也不对任何个人作出负面判断**。
> T3「公开证据较少」与 T4「公开证据不足」**通常源于姓名重名、英文署名不一致或中文文献未覆盖等数据原因，不代表导师水平或指导质量**。
> 完整说明见仓库 [DISCLAIMER.md](../DISCLAIMER.md)（免责与合规）与 [docs/使用指南.md](../docs/使用指南.md)（使用教程）。
> 本项目采用 CC BY-NC-SA 4.0（**非商业性使用**），**禁止将文中联系方式用于批量群发或其他骚扰行为**；如需更正或删除信息，请提 Issue，我们将在 7 个工作日内处理。

> **覆盖院校（${schoolNames.length} 校/单位）**：${schoolNamesDot}
> **收录范围**：从 ${TOTAL} 位导师的全库排名（${N_SCHOOLS} 校/单位）中收录 **${rows.length} 位**，分两类：
> ① **集成电路设计与 AI 交叉方向** ${rows.filter((d) => d.scope === 'focus').length} 位（数字/AI 芯片 · 体系结构 · 存算一体 · 模拟/电源 · EDA · 类脑 · 芯片安全 · 算力相关器件）；
> ② **其他 IC 方向但主页明确在招** ${rows.filter((d) => d.scope === 'recruiting').length} 位（射频/毫米波 · 光电/硅光 · MEMS/生医 · 器件/工艺 · 量子等）。
> **招生信息覆盖**：抓取 ${rows.filter((d) => d.page_status.startsWith('ok')).length} 位导师的个人/课题组主页，其中 **${recruiting.length} 位**主页有明确招生表述
> **数据来源**：各高校官方师资页面 + Crossref 文献库（2008–2026）+ Crossref 撤稿/更正关系核查
> **截至日期**：2026-09-24

---

## 一、这份名单怎么来的

| 步骤 | 口径 |
|:--|:--|
| 1. 全库构建 | ${N_SCHOOLS} 校/单位的相关院系官网逐人抓取师资名录（${TOTAL} 人），按「姓名拼音（含多音字异读组合）× 机构」逐人检索 Crossref 并做作者名 + 机构双校验 |
| 2. 清洗 | 姓名精确匹配 + 作者本人机构校验 + 非工科期刊剔除（全库剔除 1400+ 篇同名他人论文） |
| 3. 评分 | 8 维综合分：产出强度 40% + 顶刊顶会密度 13% + 影响力 10% + 近期活跃 10% + 署名伦理 8% + 头衔平台 8% + 团队规模 6% + 诚信 5% |
| 4. 范围筛选 | 保留集成电路设计本体及其 AI/算力交叉方向；剔除以射频/微波无源、光电材料、生物医学为主业者 |
| 5. 课题组主页 | 抓取 ${rows.filter((d) => d.page_status.startsWith('ok')).length} 位导师主页，用精确句式提取**招生原话** |
| 6. 方向归类 | 按研究内容做多标签归类（一人可属多个方向，平均 2.5 个标签） |

**S 级（顶刊顶会）**＝ISSCC / JSSC / VLSI Symposium / ISCA / MICRO / HPCA / ASPLOS / IEDM / Nature Electronics
**A 级（一流）**＝CICC / A-SSCC / ESSCIRC / RFIC / TCAS-I / TCAS-II / TVLSI / TCAD / TED / MTT / TPEL / TC / DAC / ICCAD / FPGA / SSC-L / JLT

---

## 二、总览

### 2.1 覆盖规模

| 学校 | 本页人数 | 其中主页明确在招 | 顶刊顶会(S)合计 |
|:--|--:|--:|--:|
`;
for (const s of schools) {
  const sub = rows.filter((d) => d.school === s);
  md += `| ${sh(s)} | ${sub.length} | ${sub.filter((d) => d.recruit_signal_count > 0).length} | ${sub.reduce((a, b) => a + b.S, 0)} |\n`;
}
md += `| **合计** | **${rows.length}** | **${recruiting.length}** | **${rows.reduce((a, b) => a + b.S, 0)}** |\n`;

md += `
### 2.2 细分方向分布（多标签，一人可属多方向）

| 研究方向 | 人数 |
|:--|--:|
`;
for (const g of groups) {
  const n = rows.filter((d) => d.group_names.includes(g)).length;
  if (n) md += `| ${g} | ${n} |\n`;
}
md += `| *（合计 ${rows.length} 人，平均 2.5 个方向标签）* | — |\n`;

md += `
### 2.3 梯队分布

| 梯队 | 人数 |
|:--|--:|
`;
for (const t of ['T0', 'T1', 'T2', 'T3', 'T4']) {
  md += `| ${t} ${TIER_LABEL[t]} | ${rows.filter((d) => d.tier === t).length} |\n`;
}

// ── 学校 × 方向 交叉矩阵 ──
const matrixGroups = groups.filter((g) => rows.filter((d) => d.group_names.includes(g)).length >= 5);
md += `
### 2.4 学校 × 方向 交叉矩阵（选校参考）

> 单元格＝该校该方向的收录人数（含方向交叉，一人可计入多列）。**括号内为其中主页明确在招的人数**。
> 这张表回答的是"我想做 X 方向，哪几所学校可选的人多"，**不代表方向实力排名**。

| 学校 | ${matrixGroups.join(' | ')} | 合计 |
|:--|${matrixGroups.map(() => '--:').join('|')}|--:|
`;
for (const s of schools) {
  const sub = rows.filter((d) => d.school === s);
  const cells = matrixGroups.map((g) => {
    const hit = sub.filter((d) => d.group_names.includes(g));
    const rec = hit.filter((d) => d.recruit_signal_count > 0).length;
    return hit.length ? `${hit.length}${rec ? `（${rec}）` : ''}` : '—';
  });
  md += `| ${sh(s)} | ${cells.join(' | ')} | ${sub.length} |\n`;
}
md += `| **合计** | ${matrixGroups.map((g) => `**${rows.filter((d) => d.group_names.includes(g)).length}**`).join(' | ')} | **${rows.length}** |\n`;

// ── 招生信息 ──
md += `
---

## 三、主页明确在招的导师（${recruiting.length} 人）

> 以下导师的个人/课题组主页**直接写明了招收研究生**，且引用了主页原文。这是本报告最有操作价值的部分——但"写了在招"≠"一定还有名额"，发信前请以官网最新通知为准。

`;
for (const d of recruiting) {
  md += `### ${d.name} ｜ ${sh(d.school)} ｜ ${d.title}\n\n`;
  md += `- **院系**：${d.department || '—'}\n`;
  md += `- **课题组**：${d.lab_names.slice(0, 2).join(' / ') || '（主页未明确）'}\n`;
  md += `- **方向**：${d.group_names.join(' · ')}\n`;
  md += `- **学术**：综合分 ${d.composite}（${d.tier}）｜ 顶刊顶会 S${d.S} / 一流 A${d.A} ｜ 论文 ${d.n_ic_papers} 篇 ｜ 近 3 年 ${d.recent3} 篇 ｜ 引用 ${d.citations}\n`;
  md += `- **组内学生（估）**：${d.n_students_est || 0} 人 ｜ 学生一作占比：${d.student_led_ratio === null ? '—' : Math.round(d.student_led_ratio * 100) + '%'}\n`;
  md += `- **联系方式**：本项目**不收录邮箱**，请通过个人/课题组主页获取\n`;
  md += `- **主页**：${d.homepage || '—'}\n`;
  md += `- **官方方向**：${(d.research_keywords || []).join('、')}\n\n`;
  md += `**主页招生原话**：\n`;
  for (const s of d.recruit_signals.slice(0, 2)) md += `> ${s.snippet}\n>\n`;
  if (d.recent_titles.length) {
    md += `\n**可引用的近期论文**：\n`;
    for (const t of d.recent_titles.slice(0, 2)) md += `- ${t}\n`;
  }
  md += `\n---\n\n`;
}

// ── 分方向榜单 ──
md += `## 四、分方向推荐榜单（各方向 Top 20）

`;
for (const g of groups) {
  const sub = rows.filter((d) => d.group_names.includes(g)).sort((a, b) => b.composite - a.composite);
  if (sub.length < 3) continue;
  md += `### ${g}（${sub.length} 人）\n\n${tbl(sub, 20)}\n\n`;
}

// ── 分学校 ──
md += `---

## 五、分学校推荐榜单（各校 Top 15）

`;
for (const s of schools) {
  const sub = rows.filter((d) => d.school === s).sort((a, b) => b.composite - a.composite);
  if (!sub.length) continue;
  md += `### ${s}（${sub.length} 人）\n\n${tbl(sub, 15)}\n\n`;
}

// ── 专题 ──
md += `---

## 六、专题榜

### 6.1 青年 PI（助理教授 / 准聘 / 青年研究员 / 百人计划，综合分≥45，${young.length} 人）

> 青年 PI 通常刚建组 1–5 年，指导学生更细、更愿意给一作，但经费与名气不如资深组。

${tbl(young, 40)}

### 6.2 署名结构健康（学生一作占比 ≥30%，且论文 ≥20 篇，${ethicsGood.length} 人）

> 学生一作占比高 = 组内习惯"学生一作 + 导师通讯"，对希望以一作积累成果的学生友好。

| 姓名 | 学校 | 职称 | 论文 | 导师一作占比 | **学生一作占比** | 组内学生(估) | 综合分 | 主页 |
|:--|:--|:--|--:|--:|--:|--:|--:|:--|
`;
for (const d of ethicsGood.slice(0, 30)) {
  md += `| ${d.name} | ${sh(d.school)} | ${d.title || '—'} | ${d.n_ic_papers} | ${Math.round((d.advisor_first_ratio || 0) * 100)}% | **${Math.round(d.student_led_ratio * 100)}%** | ${d.n_students_est} | ${d.composite} | ${d.homepage ? '[主页](' + d.homepage + ')' : '—'} |\n`;
}

md += `
### 6.3 大团队（组内学生估计 ≥20 人，${bigTeam.length} 人）

> 大组资源多、流片机会多、师兄师姐网络强；但需确认**实际带你的小导师是谁**。

| 姓名 | 学校 | 职称 | 组内学生(估) | 论文 | S | 综合分 | 主页 |
|:--|:--|:--|--:|--:|--:|--:|:--|
`;
for (const d of bigTeam.slice(0, 25)) md += `| ${d.name} | ${sh(d.school)} | ${d.title || '—'} | **${d.n_students_est}** | ${d.n_ic_papers} | ${d.S} | ${d.composite} | ${d.homepage ? '[主页](' + d.homepage + ')' : '—'} |\n`;

// ── 邮件模板 ──
md += `
---

## 七、联系导师的邮件模板与建议

### 7.1 中文模板

\`\`\`
主题：研究生申请咨询 - [你的学校] - [你的姓名] - [目标方向]

尊敬的 X 老师：

您好！我是 [学校] [专业] 20XX 级本科生 [姓名]，专业排名 [X/Y]（前 X%），
预计获得推免资格 / 正在准备考研，希望申请您课题组的研究生。

我在您课题组主页看到「[引用主页上的招生原话]」，非常希望有机会加入您的团队。

【我的基础】
- 修过课程：[数字集成电路设计 / 模拟集成电路设计 / 半导体器件 / Verilog HDL …]（成绩 [X]）
- 项目经历：[项目名称]，我负责 [具体工作]，完成了 [可量化结果]
- 熟悉工具：[Cadence Virtuoso / Synopsys DC / ModelSim / Vivado / Python …]

我关注到您近期的工作《[引用 1 篇 2025–2026 年的论文标题]》，
其中 [用一句话说明你理解的技术点] 让我很受启发，这与我 [课程/项目] 中的经历相关。

若您当年度还有招生名额，希望能有机会进一步沟通，也愿意提前做文献阅读或小任务。
附件为我的简历与成绩单。

感谢您的时间！

[姓名] | [电话] | [邮箱] | [个人主页/GitHub]
\`\`\`

### 7.2 英文模板

\`\`\`
Subject: Prospective Graduate Student - [Your Name] - [Target Area]

Dear Professor [Last Name],

I am [Name], a undergraduate in [Major] at [University] (GPA [X], rank [X/Y]).
I am applying for graduate admission and am very interested in joining your group.

I read on your group website that "[quote the recruiting statement]".

My background:
- Relevant courses: [Digital IC Design / Analog IC Design / Semiconductor Devices / Verilog HDL]
- Project: [project name] — I was responsible for [work], achieving [quantified result]
- Tools: [Cadence Virtuoso / Synopsys DC / ModelSim / Vivado / Python]

I was particularly interested in your recent work "[paper title]", especially [one specific
technical point]. I would be glad to do any reading or a small task in advance.

Could you let me know whether you will have openings? My CV and transcript are attached.

Best regards,
[Name] | [Phone] | [Email]
\`\`\`

### 7.3 发信建议

1. **一次发 3–5 位**，按"主页明确在招 → 方向高度匹配 → 其他"分批发，避免同时联系过多；
2. **主题行要具体**（学校 + 姓名 + 方向），不要只写"咨询"；
3. **附简历 PDF（1 页）+ 成绩单**，文件命名：\`姓名-学校-专业-申请方向.pdf\`；
4. **引用的论文要真读过**——模板化邮件一眼可辨；
5. 若导师主页写了具体要求（如"发送简历与研究兴趣简介"），**严格照做**；
6. 一周无回复可简短跟进一次，仍无回复则转向其他导师；
7. 联系"院士/院长/校长"级导师时，建议同时了解**组内实际指导的小导师是谁**。

---

## 八、时间线参考

| 目标入学 | 关键节点 | 建议动作 |
|:--|:--|:--|
| **次年秋季（推免）** | 夏令营：入学前一年 5–7 月｜预推免：8–9 月｜推免系统填报：9 月底–10 月 | 夏令营前 3–6 个月开始联系导师；预推免阶段以邮件 + 官网通知为准 |
| **次年秋季（统考）** | 初试：12 月｜复试：次年 3–4 月 | 初试后即可联系导师，附初试估分与本科成绩 |

> 各校研究生院每年会发布《接收推荐免试研究生报名通知》，是最权威的时间节点来源。

---

## 九、局限与免责声明

1. **同名污染**：中文拼音重名严重，已做三重过滤，仍可能有残留；标记为"低置信"或"疑似漏检"的记录请以官方主页为准；
2. **顶会漏计**：Crossref 对 IEEE 会议论文（尤其 ISSCC/CICC）作者机构字段收录不完整，会**系统性低估**顶会产出；中文期刊（CNKI/万方）未覆盖；
3. **未做逐篇全文质量评分**：论文 PDF 多数在订阅墙内，质量维度基于 venue 层级 + 引用 + 产出结构；
4. **"公开证据不足"≠ 学术水平低**：多为英文名重名或拼写差异导致自动匹配失败；
5. **招生信息有时效性**：主页表述可能滞后，以导师本人回复与院系最新通知为准；
6. **不含指导质量**：导师性格、组会风格、补助、毕业去向、是否允许实习等无法从文献数据获得，务必向在读/毕业学生核实；
7. 本报告为公开信息整理，**不构成学术评价、人事评价或报考建议**。

*数据文件：\`data/processed/curated.json\`、\`curated.csv\`；交互页面：\`reports/导师推荐.html\`*
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, md, 'utf8');
console.log('saved', OUT, (md.length / 1024).toFixed(0) + 'KB');
console.log('在招', recruiting.length, '| 青年PI', young.length, '| 署名健康', ethicsGood.length, '| 大团队', bigTeam.length);
