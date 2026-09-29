// verify_merged.mjs — 合并后的数据质量抽查
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const schoolOf = {};
for (const [k, m] of Object.entries(variants)) schoolOf[m.school] = k;

console.log('=== 全库 Top 20 ===');
for (const [i, d] of ranked.slice(0, 20).entries()) {
  console.log(`  ${String(i + 1).padStart(2)}. ${String(d.composite).padStart(5)} ${d.name_cn.padEnd(4)} ${d.school.slice(0, 5).padEnd(6)} S${String(d.S).padStart(3)} A${String(d.A).padStart(4)} 论文${String(d.n_ic_papers).padStart(4)}`);
}

// 高产出者的论文是否机构一致
console.log('\n=== 论文数最多的 15 人：抽查其论文的"本人机构"是否都属本校 ===');
const top = [...ranked].sort((a, b) => b.n_ic_papers - a.n_ic_papers).slice(0, 15);
for (const d of top) {
  const sk = schoolOf[d.school];
  const e = JSON.parse(fs.readFileSync(path.join(PROC, `enriched_${sk}.json`), 'utf8'));
  const p = e.people.find((x) => x.name_cn === d.name_cn);
  const inc = new RegExp(variants[sk].include, 'i');
  let ok = 0, bad = 0;
  for (const pap of p.papers || []) {
    const me = (pap.coauthors || []).find((c) => c.order === pap.my_order) || {};
    const aff = me.aff || '';
    if (!aff) continue;
    if (inc.test(aff)) ok++; else bad++;
  }
  console.log(`  ${d.name_cn}(${d.school.slice(0, 4)}) IC${String(d.n_ic_papers).padStart(4)} 篇 | 原始${String((p.papers || []).length).padStart(4)} | 机构符合 ${ok} / 不符 ${bad}${bad > ok ? '  ← 需核查' : ''}`);
}

// 疑似同名污染：论文数异常高
const huge = ranked.filter((d) => d.n_ic_papers >= 300);
console.log(`\n论文数 ≥300 的导师: ${huge.length} 人`);
for (const d of huge.slice(0, 10)) console.log(`  ${d.name_cn}(${d.school.slice(0, 4)}) ${d.n_ic_papers} 篇 | ${d.title}`);
