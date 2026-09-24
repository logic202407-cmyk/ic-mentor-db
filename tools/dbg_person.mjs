// dbg_person.mjs — 查看某人的论文分层明细，核对 S/A/B 归类是否正确
import fs from 'node:fs';
const db = JSON.parse(fs.readFileSync('E:\\ytm\\mentor-db\\data\\processed\\mentor_db.json', 'utf8'));
const name = process.argv[2];
const r = db.find((x) => x.name_cn === name);
if (!r) { console.log('not found'); process.exit(0); }
console.log(`${r.school} ${r.name_cn} ${r.title} | S${r.S} A${r.A} B${r.B} 论文${r.n_ic_papers} 引用${r.citations}`);
console.log('代表venue:', JSON.stringify(r.top_venues));
const byTier = { S: [], A: [], B: [], none: [] };
for (const p of r.papers) (byTier[p.tier || 'none']).push(p);
for (const t of ['S', 'A', 'B', 'none']) {
  console.log(`\n--- ${t} (${byTier[t].length}) ---`);
  for (const p of byTier[t].slice(0, 12)) console.log(`  ${p.year} | ${(p.venue || '(无venue)').slice(0, 62)} | ${p.title.slice(0, 60)}`);
}
