// find_missing.mjs — 找出 enriched 中缺失的名录人员
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');

const affected = new Set();
for (const key of fs.readdirSync(RAW)) {
  const rp = path.join(RAW, key, `roster_${key}.json`);
  const ep = path.join(PROC, `enriched_${key}.json`);
  if (!fs.existsSync(rp) || !fs.existsSync(ep)) continue;
  const roster = JSON.parse(fs.readFileSync(rp, 'utf8'));
  const e = JSON.parse(fs.readFileSync(ep, 'utf8'));
  const have = new Set(e.people.map((p) => p.name_cn));
  const miss = roster.faculty.filter((f) => !have.has(f.name_cn));
  if (miss.length) {
    affected.add(key);
    console.log(`${roster.school} 缺 ${miss.length} 人: ${miss.map((m) => m.name_cn).join('、')}`);
  }
}
console.log('\n受影响学校:', [...affected].join(' '));
