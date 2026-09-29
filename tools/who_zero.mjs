// who_zero.mjs — 分析剩余零记录者的构成
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ranked = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'processed', 'mentor_ranked.json'), 'utf8'));
const zero = ranked.filter((d) => (d.n_ic_papers || 0) === 0);
console.log(`零记录 ${zero.length} 人\n`);

const byDir = {};
const bySchool = {};
for (const d of zero) {
  byDir[d.primary_direction] = (byDir[d.primary_direction] || 0) + 1;
  bySchool[d.school] = (bySchool[d.school] || 0) + 1;
}
console.log('按主方向:', JSON.stringify(byDir));
console.log('按学校:', JSON.stringify(bySchool));

console.log('\n样例（含研究方向与主页）:');
for (const d of zero.slice(0, 20)) {
  console.log(`  ${d.name_cn}(${d.school.slice(0, 4)}) ${(d.title || '—').slice(0, 8)} | ${d.primary_direction} | ${(d.research_keywords || []).join('、').slice(0, 42)}`);
}

// 有多少人连 enriched 原始论文也是 0
let noRaw = 0;
const rawCount = new Map();
for (const f of fs.readdirSync(path.join(REPO, 'data', 'processed')).filter((x) => x.startsWith('enriched_'))) {
  const e = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'processed', f), 'utf8'));
  for (const p of e.people) rawCount.set(`${p.school}|${p.name_cn}`, (p.papers || []).length);
}
for (const d of zero) if ((rawCount.get(`${d.school}|${d.name_cn}`) || 0) === 0) noRaw++;
console.log(`\n其中"完全没有任何原始论文"的: ${noRaw} 人 | "有原始论文但被 IC 过滤"的: ${zero.length - noRaw} 人`);
