// find_dups.mjs — 全库扫描同校同名
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');
let total = 0;
for (const d of fs.readdirSync(RAW)) {
  const p = path.join(RAW, d, `roster_${d}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  const m = new Map();
  for (const f of j.faculty) {
    const base = String(f.name_cn).replace(/[（(][^）)]*[）)]/g, '');
    if (!m.has(base)) m.set(base, []);
    m.get(base).push(f);
  }
  const dups = [...m].filter(([, arr]) => arr.length > 1);
  if (!dups.length) continue;
  console.log(`${j.school}（${j.faculty.length} 人）:`);
  for (const [name, arr] of dups) {
    total += arr.length;
    console.log(`  ${name} ×${arr.length}:`);
    for (const f of arr) console.log(`     ${f.name_cn} | ${f.title} | ${f.department} | ${(f.research_keywords || []).join('、').slice(0, 34)}`);
  }
}
console.log(`\n合计 ${total} 条需消歧`);
