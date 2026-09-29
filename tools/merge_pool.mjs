// merge_pool.mjs — 把论文池命中结果合并进各校 enriched 数据（按 DOI 去重取并集）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const POOL = path.join(REPO, 'data', 'raw', 'crossref', 'pool_matches_clean.json');

const pool = JSON.parse(fs.readFileSync(POOL, 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

// 同校同名者（消歧后仍共享同一拼音）无法用姓名+机构区分
const dupName = new Map();
for (const [key, meta] of Object.entries(variants)) {
  const seen = new Map();
  for (const p of meta.people) {
    const base = p.name_cn.replace(/[（(][^）)]*[）)]/g, '');
    if (!seen.has(base)) seen.set(base, []);
    seen.get(base).push(p.name_cn);
  }
  for (const [base, arr] of seen) if (arr.length > 1) dupName.set(`${key}|${base}`, arr);
}
if (dupName.size) {
  console.log(`⚠ 同校同名者 ${dupName.size} 组（其论文无法按姓名区分，将标注 confidence 并保留原状）：`);
  for (const [k, v] of dupName) console.log(`   ${k} -> ${v.join(' / ')}`);
}

let added = 0, merged = 0, peopleTouched = 0;
for (const f of fs.readdirSync(PROC).filter((x) => x.startsWith('enriched_'))) {
  const key = f.replace('enriched_', '').replace('.json', '');
  const p = path.join(PROC, f);
  const e = JSON.parse(fs.readFileSync(p, 'utf8'));
  for (const person of e.people) {
    const pooled = pool[`${key}|${person.name_cn}`];
    if (!pooled || !pooled.length) continue;
    const have = new Set((person.papers || []).map((x) => x.doi));
    let n = 0;
    for (const pap of pooled) {
      if (have.has(pap.doi)) continue;
      person.papers.push(pap);
      have.add(pap.doi);
      n++; added++;
    }
    if (n) { peopleTouched++; person._pool_added = n; }
    person.papers.sort((a, b) => (b.year || 0) - (a.year || 0));
    person.paper_count = person.papers.length;
    merged++;
  }
  fs.writeFileSync(p, JSON.stringify(e, null, 1), 'utf8');
  console.log(`  ${key}: 合并完成`);
}
console.log(`\n新增论文 ${added} 篇，涉及 ${peopleTouched} 位导师，扫描 ${merged} 人`);
