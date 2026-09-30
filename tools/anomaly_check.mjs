// anomaly_check.mjs — 异常值核查：找出指标不合常理的条目
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

console.log('=== 1. 置信度 / 漏检标记分布 ===');
const conf = {}, rr = {};
for (const d of ranked) { conf[d.confidence] = (conf[d.confidence] || 0) + 1; rr[d.recall_risk] = (rr[d.recall_risk] || 0) + 1; }
console.log('  confidence:', JSON.stringify(conf));
console.log('  recall_risk:', JSON.stringify(rr));

console.log('\n=== 2. 指标矛盾项 ===');
const bad = [];
for (const d of ranked) {
  if (d.n_ic_papers > 0 && d.S + d.A + d.B > d.n_ic_papers) bad.push(`${d.name_cn}: S+A+B(${d.S + d.A + d.B}) > 论文数(${d.n_ic_papers})`);
  if (d.n_ic_papers > 0 && d.recent3 > d.n_ic_papers) bad.push(`${d.name_cn}: 近3年(${d.recent3}) > 总数(${d.n_ic_papers})`);
  if (d.n_students_est > d.n_ic_papers) bad.push(`${d.name_cn}: 学生数(${d.n_students_est}) > 论文数(${d.n_ic_papers})`);
  if (d.composite < 0 || d.composite > 100) bad.push(`${d.name_cn}: 综合分越界 ${d.composite}`);
}
console.log(bad.length ? bad.slice(0, 10).join('\n') : '  无矛盾项');

console.log('\n=== 3. 引用数异常（篇均引用 > 500）===');
const hi = ranked.filter((d) => d.n_ic_papers >= 5 && d.citations / d.n_ic_papers > 500);
console.log(hi.length ? hi.slice(0, 8).map((d) => `  ${d.name_cn}(${d.school.slice(0, 4)}) 篇均 ${Math.round(d.citations / d.n_ic_papers)}`).join('\n') : '  无');

console.log('\n=== 4. 署名结构异常（导师一作占比 > 80% 且论文 ≥20）===');
const selfFirst = ranked.filter((d) => d.n_ic_papers >= 20 && d.advisor_first_ratio > 0.8);
console.log(selfFirst.length ? selfFirst.slice(0, 8).map((d) => `  ${d.name_cn}(${d.school.slice(0, 4)}) 一作占比 ${(d.advisor_first_ratio * 100).toFixed(0)}% / ${d.n_ic_papers} 篇`).join('\n') : '  无');

console.log('\n=== 5. 零记录但 S/A 非零（不应发生）===');
const z = ranked.filter((d) => d.n_ic_papers === 0 && (d.S + d.A + d.B) > 0);
console.log(z.length ? z.map((d) => `  ${d.name_cn} S${d.S} A${d.A} B${d.B}`).join('\n') : '  无');

console.log('\n=== 6. 数据完整性 ===');
const fields = ['name_cn', 'school', 'title', 'composite', 'rank', 'S', 'A', 'B', 'n_ic_papers', 'recent3', 'citations', 'primary_direction', 'confidence'];
const miss = {};
for (const d of ranked) for (const f of fields) if (d[f] === undefined) miss[f] = (miss[f] || 0) + 1;
console.log(Object.keys(miss).length ? JSON.stringify(miss) : '  全部字段完整');

console.log('\n=== 7. 综合分与各维度相关性（检查是否被单一维度主导）===');
const dims = ['strength', 'density', 'impact', 'active', 'ethics', 'team', 'title'];
for (const dm of dims) {
  const xs = ranked.map((d) => d.dim?.[dm] ?? 0), ys = ranked.map((d) => d.composite);
  const n = xs.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
  console.log(`  ${dm.padEnd(9)} r = ${(sxy / Math.sqrt(sxx * syy)).toFixed(3)}`);
}
