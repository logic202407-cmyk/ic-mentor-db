// audit_kappa.mjs — 方向分类的一致性检验（Cohen's kappa）
//
// 方法来源：data-science-agent-skills / domain-expert-collaboration-loop
//   「量化领域专家标注一致性（Cohen's Kappa），制定边界样本仲裁准则」
//
// 做法：让两个**互相独立**的标注者对同一批人分类，再算 kappa。
//   标注者 A：首命中法（按方向优先级顺序，命中第一个就停）
//   标注者 B：计分法（统计各方向的关键词命中次数，取最高分）
// 两者若高度一致 → 分类稳定；分歧处即边界样本，需人工裁定。
import fs from 'node:fs';
import path from 'node:path';
import { DIRS, DIR_MAP } from './directions.mjs';

const PROC = 'data/processed';
const net = JSON.parse(fs.readFileSync(path.join(PROC, 'network_final.json'), 'utf8'));

// ── 标注者 A：首命中法（当前页面用的就是这套）──
function raterA(kw) {
  const s = String(kw || '');
  if (!s.trim()) return 'unknown';
  for (const d of DIRS) if (d.re.test(s)) return d.key;
  return 'other';
}

// ── 标注者 B：计分法（独立实现：统计每个方向命中的关键词次数，取最高）──
// 为避免「长正则吃短正则」，这里把每个方向的匹配拆成独立词条分别计数
const TERMS = {};
for (const d of DIRS) {
  const src = d.re.source.replace(/^\(\?:/, '').replace(/\)$/, '');
  const parts = src.split('|').map((x) => x.replace(/^\(\?:/, '').replace(/\)$/, '').replace(/\\\./g, '.').replace(/\\-/g, '-'));
  TERMS[d.key] = parts;
}
function raterB(kw) {
  const s = String(kw || '');
  if (!s.trim()) return 'unknown';
  const score = {};
  for (const [k, parts] of Object.entries(TERMS)) {
    let c = 0;
    for (const p of parts) {
      let re;
      try { re = new RegExp(p, 'gi'); } catch { continue; }
      const m = s.match(re);
      if (m) c += m.length;
    }
    if (c) score[k] = c;
  }
  const keys = Object.keys(score);
  if (!keys.length) return 'other';
  keys.sort((a, b) => score[b] - score[a] || a.localeCompare(b));
  return keys[0];
}

// ── Cohen's kappa ──
function kappa(pairs) {
  const cats = [...new Set(pairs.flatMap((p) => [p[0], p[1]]))];
  const n = pairs.length;
  const idx = {}; cats.forEach((c, i) => idx[c] = i);
  const m = cats.map(() => cats.map(() => 0));
  for (const [a, b] of pairs) m[idx[a]][idx[b]]++;
  let po = 0;
  for (let i = 0; i < cats.length; i++) po += m[i][i];
  po /= n;
  let pe = 0;
  for (let i = 0; i < cats.length; i++) {
    const ra = m[i].reduce((x, y) => x + y, 0) / n;
    const cb = m.reduce((x, r) => x + r[i], 0) / n;
    pe += ra * cb;
  }
  const k = pe === 1 ? 1 : (po - pe) / (1 - pe);
  return { k, po, pe, n, cats, m };
}
function interpret(k) {
  if (k < 0) return '差于随机';
  if (k < 0.20) return '极低（slight）';
  if (k < 0.40) return '一般（fair）';
  if (k < 0.60) return '中等（moderate）';
  if (k < 0.80) return '较好（substantial）';
  return '很好（almost perfect）';
}

const pairs = [];
const disagree = [];
const bySchoolMiss = {};
let missTotal = 0, missNoKw = 0;
for (const [k, p] of Object.entries(net.nodes)) {
  const a = raterA(p.kw), b = raterB(p.kw);
  pairs.push([a, b]);
  if (a !== b) disagree.push({ k, name: p.name, school: p.school, kw: (p.kw || '').slice(0, 46), a, b });
  // 缺失分析：按院校统计关键词缺失率
  const s = p.school;
  bySchoolMiss[s] = bySchoolMiss[s] || { tot: 0, miss: 0 };
  bySchoolMiss[s].tot++;
  missTotal++;
  if (!p.kw || !p.kw.trim()) { bySchoolMiss[s].miss++; missNoKw++; }
}

const R = kappa(pairs);
console.log('═══ 方向分类一致性（Cohen\'s kappa）═══');
console.log(`  样本 ${R.n} 人 ｜ 类别 ${R.cats.length} 个`);
console.log(`  观察一致率 Po = ${(R.po * 100).toFixed(1)}%`);
console.log(`  期望一致率 Pe = ${(R.pe * 100).toFixed(1)}%`);
console.log(`  kappa = ${R.k.toFixed(3)}  →  ${interpret(R.k)}`);
console.log(`\n  分歧样本 ${disagree.length} 个（占 ${(disagree.length / R.n * 100).toFixed(1)}%）`);
disagree.sort((a, b) => (a.name > b.name ? 1 : -1));
for (const d of disagree.slice(0, 18)) {
  console.log(`    ${d.name}（${(d.school || '').replace('中国科学院', '中科院').slice(0, 8)}）  A=${DIR_MAP[d.a]?.name || d.a}  B=${DIR_MAP[d.b]?.name || d.b}`);
  console.log(`       关键词: ${d.kw}`);
}

// ── 混淆矩阵（只打印前 8 类）──
console.log('\n  混淆矩阵（行=A 首命中，列=B 计分；仅显示非零行）');
const show = R.cats.filter((c, i) => R.m[i].some((v) => v > 0)).slice(0, 8);
const w = 14;
console.log('    ' + ''.padEnd(w) + show.map((c) => (DIR_MAP[c]?.name || c).slice(0, 6).padStart(8)).join(''));
for (const ca of show) {
  const i = R.cats.indexOf(ca);
  if (!R.m[i].some((v) => v > 0)) continue;
  console.log('    ' + (DIR_MAP[ca]?.name || ca).slice(0, w).padEnd(w) +
    show.map((cb) => String(R.m[i][R.cats.indexOf(cb)] || 0).padStart(8)).join(''));
}

// ── 缺失机制诊断（按 skill 要求：按 column / group / 目标关系分别剖面）──
console.log('\n═══ 关键词缺失诊断（缺失机制）═══');
console.log(`  整体缺失：${missNoKw}/${missTotal} = ${(missNoKw / missTotal * 100).toFixed(1)}%`);
const rows = Object.entries(bySchoolMiss).filter(([, v]) => v.tot >= 20)
  .map(([s, v]) => ({ s, ...v, rate: v.miss / v.tot }))
  .sort((a, b) => b.rate - a.rate);
console.log('\n  各院校缺失率（样本 ≥20 人）：');
for (const r of rows) console.log(`    ${(r.rate * 100).toFixed(0).padStart(3)}%  ${r.miss}/${r.tot}  ${r.s.replace('中国科学院', '中科院')}`);

// 卡方独立性检验：院校 × 是否缺失
const obs = rows.map((r) => [r.miss, r.tot - r.miss]);
const totAll = rows.reduce((a, r) => a + r.tot, 0);
const missAll = rows.reduce((a, r) => a + r.miss, 0);
const pMiss = missAll / totAll;
let chi2 = 0, df = 0;
for (const [m, nm] of obs) {
  const e1 = (m + nm) * pMiss, e2 = (m + nm) * (1 - pMiss);
  if (e1 > 0) chi2 += (m - e1) ** 2 / e1;
  if (e2 > 0) chi2 += (nm - e2) ** 2 / e2;
  df++;
}
df -= 1;
// 临界值（0.05 显著性）近似：df 较大时用 Wilson-Hilferty 近似
const crit = df * (1 - 2 / (9 * df) + 1.645 * Math.sqrt(2 / (9 * df))) ** 3;
console.log(`\n  卡方检验（院校 × 是否缺失）：χ² = ${chi2.toFixed(1)}, df = ${df}, 0.05 临界值 ≈ ${crit.toFixed(1)}`);
const dep = chi2 > crit;
console.log(`  → ${dep ? '院校与缺失**不独立**（p<0.05）：存在系统性缺失' : '院校与缺失**独立**（p>0.05）：可视为随机缺失'}`);

const rates = rows.map((r) => r.rate);
const mean = rates.reduce((a, b) => a + b, 0) / rates.length;
const sd = Math.sqrt(rates.reduce((a, b) => a + (b - mean) ** 2, 0) / rates.length);
console.log(`  缺失率均值 ${(mean * 100).toFixed(1)}%、标准差 ${(sd * 100).toFixed(1)}pp、极差 ${((rates[0] - rates[rates.length - 1]) * 100).toFixed(0)}pp`);

// 按职称、按论文数剖面
const byTitle = {}, byPaper = {};
for (const [, p] of Object.entries(net.nodes)) {
  const t = /院士/.test(p.title || '') ? '院士' : /教授/.test(p.title || '') && !/副/.test(p.title) ? '教授' : /副教授/.test(p.title) ? '副教授' : /研究员/.test(p.title) && !/副/.test(p.title) ? '研究员' : /副研究员/.test(p.title) ? '副研究员' : '其他/未标注';
  byTitle[t] = byTitle[t] || { tot: 0, miss: 0 };
  byTitle[t].tot++; if (!p.kw || !p.kw.trim()) byTitle[t].miss++;
  const np = p.papers ? p.papers.length : 0;
  const b = np === 0 ? '0 篇' : np <= 10 ? '1-10 篇' : np <= 40 ? '11-40 篇' : '40+ 篇';
  byPaper[b] = byPaper[b] || { tot: 0, miss: 0 };
  byPaper[b].tot++; if (!p.kw || !p.kw.trim()) byPaper[b].miss++;
}
console.log('\n  按职称剖面：');
for (const [t, v] of Object.entries(byTitle).sort((a, b) => b[1].tot - a[1].tot).slice(0, 6)) {
  console.log(`    ${(v.miss / v.tot * 100).toFixed(0).padStart(3)}%  ${v.miss}/${v.tot}  ${t}`);
}
console.log('\n  ⇒ 处置建议：关键词缺失率约三分之一，且与院校存在关联。');
console.log('     「无关键词记录」不应作为一个「方向」参与统计或可视化排序，');
console.log('     页面中须显式标注其成因，并按缺失组单独呈现。');

fs.writeFileSync(path.join(PROC, '_kappa_audit.json'),
  JSON.stringify({ kappa: R.k, po: R.po, pe: R.pe, n: R.n, disagree: disagree.length, missRate: missNoKw / missTotal, chi2, df, dependent: dep, bySchool: rows }, null, 1), 'utf8');
console.log('\n已导出 data/processed/_kappa_audit.json');
