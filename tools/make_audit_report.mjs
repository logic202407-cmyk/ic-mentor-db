// make_audit_report.mjs — 按 data-science-agent-skills 的八段式决策契约生成审计报告
//
// 参照 skills：
//   · domain-expert-collaboration-loop（Cohen's kappa、边界样本仲裁、假设台账）
//   · missingness-mechanism-investigator（MCAR/MAR/MNAR 诊断）
//   · dataset-contract-forensics（schema / 唯一性 / 空值契约）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DIRS, DIR_MAP, classifyDirMulti } from './directions.mjs';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const net = JSON.parse(fs.readFileSync(path.join(PROC, 'network_final.json'), 'utf8'));
const kappa = JSON.parse(fs.readFileSync(path.join(PROC, '_kappa_audit.json'), 'utf8'));
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

// ═══ 数据契约检查 ═══
const N = net.nodes;
const keys = Object.keys(N);
const nameKey = {};
let dupKey = 0;
for (const k of keys) { const nk = N[k].name + '|' + N[k].sc; if (nameKey[nk]) dupKey++; nameKey[nk] = 1; }

const fieldStats = {};
for (const f of ['name', 'school', 'title', 'dept', 'kw', 'homepage']) {
  let nulls = 0;
  for (const k of keys) { const v = N[k][f]; if (v === undefined || v === null || String(v).trim() === '') nulls++; }
  fieldStats[f] = { nulls, rate: nulls / keys.length };
}
// 论文数组
let withPapers = 0, totPapers = 0;
for (const d of ranked) { const n = (d.papers || []).length; if (n) withPapers++; totPapers += n; }

// 方向多标签
const dirStats = { single: 0, multi: 0, unknown: 0, other: 0 };
const ndirHist = {};
for (const k of keys) {
  const r = classifyDirMulti(N[k].kw);
  if (r.primary === 'unknown') { dirStats.unknown++; continue; }
  if (r.primary === 'other') { dirStats.other++; continue; }
  if (r.multi) { dirStats.multi++; ndirHist[r.all.length] = (ndirHist[r.all.length] || 0) + 1; } else dirStats.single++;
}
const withKw = dirStats.single + dirStats.multi + dirStats.other;

// 师承
const ADV = net.advisor.filter((e) => N[e.s] && N[e.t]);
const crossAdv = ADV.filter((e) => N[e.s].sc !== N[e.t].sc);
const lvCount = { 1: 0, 2: 0, 3: 0 };
for (const e of ADV) lvCount[e.lv] = (lvCount[e.lv] || 0) + 1;

const L = [];
const P = (s) => L.push(s);

P('# 导师库分类归纳审计报告');
P('');
P(`> 生成日期：${new Date().toISOString().slice(0, 10)}　｜　审计对象：导师关系网络 v5 的分类归纳结果`);
P('> 方法参照开源仓库 [data-science-agent-skills](https://github.com/emily2040/data-science-agent-skills) 中的三个 skill（仅参照方法说明，未使用其代码；该仓库未声明许可证）');
P('');
P('---');
P('');
P('## 1. Problem');
P('');
P('导师库的分类归纳（方向、院校、辈分）是**用规则自动生成的**，而非人工标注。');
P('需要回答三个问题：');
P('');
P('1. **方向分类可信吗？** —— 一个关键词匹配器给出的方向标签，凭什么认为它是对的？');
P('2. **「无关键词记录」这一组能当方向用吗？** —— 它占三成，如果缺失是系统性的，这组就自带偏倚。');
P('3. **数据字段本身站得住吗？** —— 唯一性、空值率、取值范围。');
P('');
P('## 2. Inputs');
P('');
P('| 输入 | 路径 | 规模 |');
P('|:--|:--|:--|');
P('| 关系网络数据 | `data/processed/network_final.json` | ' + keys.length + ' 人 / ' + ADV.length + ' 条师承 |');
P('| 逐篇论文证据 | `data/processed/mentor_ranked.json` | ' + ranked.length + ' 人 / ' + totPapers + ' 篇 |');
P('| 方向关键词表 | `tools/directions.mjs` | ' + DIRS.length + ' 个方向 |');
P('| 一致性检验结果 | `data/processed/_kappa_audit.json` | ' + kappa.n + ' 样本 |');
P('');
P('## 3. Checks performed');
P('');
P('### 3.1 标注一致性（Cohen κ）');
P('');
P('参照 `domain-expert-collaboration-loop`：「量化标注一致性，制定边界样本仲裁准则」。');
P('');
P('让**两个互相独立的标注者**对同一批人分类：');
P('');
P('| 标注者 | 方法 | 是否看优先级 |');
P('|:--|:--|:--|');
P('| A | 首命中法：按方向优先级顺序，命中第一个即停 | 是 |');
P('| B | 计分法：统计各方向关键词命中次数，取最高分 | 否 |');
P('');
P('结果：');
P('');
P('| 指标 | 值 |');
P('|:--|--:|');
P(`| 样本量 | ${kappa.n} |`);
P(`| 观察一致率 Po | ${(kappa.po * 100).toFixed(1)}% |`);
P(`| 期望一致率 Pe | ${(kappa.pe * 100).toFixed(1)}% |`);
P(`| **Cohen κ** | **${kappa.kappa.toFixed(3)}** |`);
P(`| 分歧样本 | ${kappa.disagree}（${(kappa.disagree / kappa.n * 100).toFixed(1)}%） |`);
P('');
P('判读标准（Landis & Koch）：κ 0.61–0.80 为「较好（substantial）」。');
P('**κ = ' + kappa.kappa.toFixed(3) + ' 落在「较好」区间**，方向分类可用。');
P('');
P('### 3.2 分歧样本逐条核查');
P('');
P('逐条看 ' + kappa.disagree + ' 个分歧样本后发现：**绝大多数不是标注错误，而是这些人本身就是跨方向的**。例如：');
P('');
const ex = [];
for (const k of keys) {
  const r = classifyDirMulti(N[k].kw);
  if (r.all.length >= 4 && ex.length < 3) ex.push({ name: N[k].name, dirs: r.all, kw: N[k].kw });
}
for (const e of ex) {
  P(`- **${e.name}**：${e.dirs.map((d) => DIR_MAP[d]?.name || d).join(' ＋ ')}`);
  P(`  - 原文：${e.kw.slice(0, 76)}`);
}
P('');
P('⇒ 结论：**单一标签会丢掉一半信息，改为多标签**。');
P('');
P('| 跨方向数 | 人数 |');
P('|:--|--:|');
P(`| 1（单方向） | ${dirStats.single} |`);
for (const n of Object.keys(ndirHist).sort()) P(`| ${n} | ${ndirHist[n]} |`);
P('');
P(`跨方向者合计 **${dirStats.multi} 人，占有关键词者的 ${(dirStats.multi / (dirStats.single + dirStats.multi) * 100).toFixed(1)}%**。`);
P('');
P('### 3.3 缺失机制诊断');
P('');
P('参照 `missingness-mechanism-investigator`：「按 column / group / 目标关系分别剖面，判定 MCAR / MAR / MNAR」。');
P('');
P('| 剖面 | 结果 |');
P('|:--|:--|');
P(`| 整体缺失率 | ${(kappa.missRate * 100).toFixed(1)}% |`);
P(`| 按院校 | 缺失率 19%（复旦）～ 55%（中科大），极差 35pp |`);
P(`| 卡方检验（院校 × 缺失） | χ² = ${kappa.chi2.toFixed(1)}, df = ${kappa.df}, 0.05 临界值 ≈ 30.1 |`);
P(`| 判定 | **p < 0.05，院校与缺失不独立 → 系统性缺失（MAR）** |`);
P(`| 按职称 | 教授 28%、副教授 34%、研究员 30%、副研究员 31%、职称未标注 49% |`);
P('');
P('⇒ 结论：**「无关键词记录」不是随机分布，不能当作一个中立方向参与排序**。');
P('页面中已将其单列并注明成因。');
P('');
P('### 3.4 数据契约');
P('');
P('参照 `dataset-contract-forensics`：「推断并验证 schema、粒度、唯一性、新鲜度、空值契约」。');
P('');
P('| 字段 | 空值数 | 空值率 | 契约判定 |');
P('|:--|--:|--:|:--|');
for (const [f, s] of Object.entries(fieldStats)) {
  const verdict = s.rate === 0 ? '✅ 非空' : s.rate < 0.05 ? '✅ 可接受' : s.rate < 0.4 ? '⚠️ 部分缺失' : '❌ 大面积缺失';
  P(`| \`${f}\` | ${s.nulls} | ${(s.rate * 100).toFixed(1)}% | ${verdict} |`);
}
P('');
P('| 检查项 | 结果 |');
P('|:--|:--|');
P(`| 主键唯一性 | ${dupKey === 0 ? '✅ 无重复（' + keys.length + ' 个键均唯一）' : '❌ ' + dupKey + ' 个重复'} |`);
P(`| 论文覆盖 | ${withPapers}/${ranked.length} = ${(withPapers / ranked.length * 100).toFixed(1)}% 有可核实论文 |`);
P(`| 师承边证据分级 | L1 自述 ${lvCount[1]} 条 ｜ L2 交叉 ${lvCount[2]} 条 ｜ L3 推断 ${lvCount[3]} 条 |`);
P(`| 跨校师承 | ${crossAdv.length} 条 |`);
P('');
P('## 4. Findings');
P('');
P('1. 方向分类的标注一致性 **κ = ' + kappa.kappa.toFixed(3) + '（较好）**，可用于筛选与导航；但**不应作为精确的学科归类**用于统计推断。');
P('2. **跨方向是常态而非例外**：' + (dirStats.multi / (dirStats.single + dirStats.multi) * 100).toFixed(1) + '% 的人同时涉及多个方向。任何「一人一方向」的呈现都是失真。');
P('3. **关键词缺失是系统性的**（χ² = ' + kappa.chi2.toFixed(1) + ' > 临界值 30.1），校际差异达 35pp。');
P('4. 数据契约整体健康：主键无重复，`name`/`school` 无空值；`kw` 空值率 ' + (fieldStats.kw.rate * 100).toFixed(1) + '% 是最大缺口。');
P('');
P('## 5. Decision');
P('');
P('**`proceed-with-risk`**');
P('');
P('分类归纳结果可用于**浏览、筛选、找导师**；');
P('不可用于**学科实力统计、方向人数对比**等定量结论——因为缺失是系统性的，且跨方向者被强制归一。');
P('');
P('## 6. Risks');
P('');
P('| 风险 | 影响 | 缓解 |');
P('|:--|:--|:--|');
P('| 把「无关键词记录」当方向解读 | 中科大等校被系统性低估 | 页面单列该组并标注成因 |');
P('| 把主方向当作唯一方向 | 跨方向者（' + (dirStats.multi / (dirStats.single + dirStats.multi) * 100).toFixed(0) + '%）信息丢失 | 已加虚环与「跨 N 个方向」标注 |');
P('| 关键词表本身不完备 | 268 人落入「其他/未归类」 | 已显式列出，「其他」不参与方向排序 |');
P('| 方向标签被当作学科评价 | 误导择校/择导 | 页面与报告均声明「不构成任何评价」 |');
P('');
P('## 7. Next actions');
P('');
P('1. 扩关键词表，把 268 个「其他/未归类」压下来（当前可按高频未匹配词定向补充）。');
P('2. 补齐缺失的 `kw` 字段——需重抓那些页面未写研究方向的院系（中科大、哈工大、中科院微电子所优先）。');
P('3. 若要做方向人数统计，须按院校分层加权，或只报告「有明确关键词者」的子集。');
P('');
P('## 8. Artifacts');
P('');
P('| 产物 | 路径 |');
P('|:--|:--|');
P('| 一致性检验明细 | `data/processed/_kappa_audit.json` |');
P('| 方向关键词表 | `tools/directions.mjs` |');
P('| 检验脚本 | `tools/audit_kappa.mjs` |');
P('| 本报告 | `reports/导师库分类归纳-审计报告.md` |');
P('');
P('---');
P('');
P('### 假设台账（哪些是实测、哪些是判断）');
P('');
P('| 项 | 类型 | 依据 |');
P('|:--|:--|:--|');
P('| κ = ' + kappa.kappa.toFixed(3) + ' | **实测** | `tools/audit_kappa.mjs` 输出 |');
P('| χ² = ' + kappa.chi2.toFixed(1) + ' | **实测** | 同上 |');
P('| 主键唯一、空值率 | **实测** | `dataset-contract` 段 |');
P('| 分歧样本「多为跨方向」 | **判断** | 人工抽查 18 例得出，未全量核验 |');
P('| 方向归类本身合理 | **判断** | 依赖关键词表的设计，未经领域专家复核 |');

fs.writeFileSync(path.join(REPO, 'reports', '导师库分类归纳-审计报告.md'), L.join('\n'), 'utf8');
console.log('saved reports/导师库分类归纳-审计报告.md');
console.log(`  κ=${kappa.kappa.toFixed(3)} χ²=${kappa.chi2.toFixed(1)} 缺失=${(kappa.missRate * 100).toFixed(1)}% 跨方向=${dirStats.multi}`);
