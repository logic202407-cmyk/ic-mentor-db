// quality_report.mjs — 数据质量综合核查
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const schoolOf = {};
for (const [k, m] of Object.entries(variants)) schoolOf[m.school] = k;

console.log('=== 1. 综合分 Top 25（检查是否仍以 IC 设计为主）===');
for (const [i, d] of ranked.slice(0, 25).entries()) {
  console.log(`  ${String(i + 1).padStart(2)}. ${String(d.composite).padStart(5)} ${d.name_cn.padEnd(10)} ${d.school.slice(0, 7).padEnd(8)} S${String(d.S).padStart(3)} A${String(d.A).padStart(4)} 论文${String(d.n_ic_papers).padStart(4)} | ${(d.primary_direction || '').padEnd(10)}`);
}

console.log('\n=== 2. S/A 级 venue 分布（前 20）===');
const sv = new Map(), av = new Map();
for (const d of ranked) for (const p of d.papers || []) {
  if (p.tier === 'S') sv.set((p.venue || '?').slice(0, 46), (sv.get((p.venue || '?').slice(0, 46)) || 0) + 1);
  if (p.tier === 'A') av.set((p.venue || '?').slice(0, 46), (av.get((p.venue || '?').slice(0, 46)) || 0) + 1);
}
console.log('  S 级:');
for (const [k, v] of [...sv].sort((a, b) => b[1] - a[1]).slice(0, 10)) console.log(`    ${String(v).padStart(5)}  ${k}`);
console.log('  A 级:');
for (const [k, v] of [...av].sort((a, b) => b[1] - a[1]).slice(0, 10)) console.log(`    ${String(v).padStart(5)}  ${k}`);

console.log('\n=== 3. 机构一致性抽检（随机 300 条论文）===');
const all = [];
for (const d of ranked) {
  const sk = schoolOf[d.school];
  if (!sk) continue;
  all.push({ d, sk });
}
let checked = 0, ok = 0, bad = 0, noAff = 0;
const badSample = [];
const step = Math.max(1, Math.floor(all.length / 80));
for (let i = 0; i < all.length && checked < 80; i += step) {
  const { d, sk } = all[i];
  const skk = schoolOf[d.school];
  const inc = new RegExp(variants[skk].include, 'i');
  const e = JSON.parse(fs.readFileSync(path.join(PROC, `enriched_${skk}.json`), 'utf8'));
  const p = e.people.find((x) => x.name_cn === d.name_cn);
  for (const pap of (p?.papers || []).slice(0, 4)) {
    checked++;
    const me = (pap.coauthors || []).find((c) => c.order === pap.my_order) || {};
    const aff = me.aff || '';
    if (!aff) { noAff++; continue; }
    if (inc.test(aff)) ok++; else { bad++; if (badSample.length < 4) badSample.push(`${d.name_cn}(${d.school.slice(0, 4)}) ${(pap.venue || '').slice(0, 30)} | ${aff.slice(0, 55)}`); }
  }
}
console.log(`  抽检 ${checked} 条：机构符合 ${ok}（${(ok / Math.max(ok + bad, 1) * 100).toFixed(1)}%）| 不符 ${bad} | 无机构信息 ${noAff}`);
for (const s of badSample) console.log('    ✗ ' + s);

console.log('\n=== 4. 字段完整性 ===');
const noTitle = ranked.filter((d) => !d.title).length;
const noKw = ranked.filter((d) => !(d.research_keywords || []).length).length;
const noHp = ranked.filter((d) => !d.homepage).length;
console.log(`  无职称 ${noTitle} | 无方向关键词 ${noKw} | 无主页 ${noHp} | 共 ${ranked.length}`);
console.log(`  置信度分布: ${JSON.stringify(ranked.reduce((a, d) => { a[d.confidence] = (a[d.confidence] || 0) + 1; return a; }, {}))}`);
