// why_still_zero.mjs — 排查仍为零记录的具体原因
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const pool = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'raw', 'crossref', 'pool_matches_clean.json'), 'utf8'));
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

const CASES = process.argv.slice(2);
for (const cn of CASES) {
  const d = ranked.find((x) => x.name_cn === cn);
  if (!d) { console.log(`${cn}: 未找到`); continue; }
  const key = `${d.name_cn}`;
  // 找到该校的 key
  let poolKey = null;
  for (const k of Object.keys(pool)) if (k.endsWith(`|${cn}`)) poolKey = k;
  // enriched 原始论文
  const schoolKey = Object.keys(JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8')))
    .find((sk) => JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'))[sk].school === d.school);
  let rawN = -1, rawSample = [];
  if (schoolKey) {
    const e = JSON.parse(fs.readFileSync(path.join(PROC, `enriched_${schoolKey}.json`), 'utf8'));
    const p = e.people.find((x) => x.name_cn === cn);
    if (p) { rawN = (p.papers || []).length; rawSample = (p.papers || []).slice(0, 5); }
  }
  console.log(`\n===== ${cn} (${d.school}) ${d.title} | IC 计入 ${d.n_ic_papers} | 相关 ${d.n_related_papers} =====`);
  console.log(`  池命中: ${poolKey ? pool[poolKey].length + ' 篇 (' + poolKey + ')' : '无'}`);
  console.log(`  enriched 原始论文: ${rawN}`);
  for (const p of rawSample) console.log(`     ${p.year} | ${(p.venue || '(无venue)').slice(0, 44).padEnd(44)} | ${(p.title || '').slice(0, 44)}`);
  if (poolKey) {
    console.log('  池命中样例:');
    for (const p of pool[poolKey].slice(0, 4)) console.log(`     ${p.year} | ${(p.venue || '').slice(0, 40)} | ${p.title.slice(0, 44)}`);
  }
}
