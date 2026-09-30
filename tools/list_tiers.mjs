// list_tiers.mjs — 列出所有被分到 S/A 级的 venue，人工核查是否有误分层
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ranked = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'processed', 'mentor_ranked.json'), 'utf8'));
const m = { S: new Map(), A: new Map(), B: new Map() };
for (const d of ranked) for (const p of d.papers || []) {
  if (!p.tier) continue;
  const v = (p.venue || '?').replace(/&amp;/g, '&').slice(0, 60);
  m[p.tier].set(v, (m[p.tier].get(v) || 0) + 1);
}
for (const t of ['S', 'A', 'B']) {
  const arr = [...m[t]].sort((a, b) => b[1] - a[1]);
  console.log(`\n===== ${t} 级（${arr.length} 个 venue，共 ${arr.reduce((s, x) => s + x[1], 0)} 篇）=====`);
  for (const [k, v] of arr) console.log(`  ${String(v).padStart(6)}  ${k}`);
}
