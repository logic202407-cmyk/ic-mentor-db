// diag_reject.mjs — 诊断「机构不匹配」的拒绝是否误杀
import fs from 'node:fs';
import path from 'node:path';
const PROC = 'data/processed';
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const norm = (s) => String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z\u4e00-\u9fa5]/g, '');
const people = {}, nameIndex = new Map(), orgRe = new Map();
for (const [sk, m] of Object.entries(variants)) {
  orgRe.set(sk, { inc: m.include ? new RegExp(m.include, 'i') : null, exc: m.exclude ? new RegExp(m.exclude, 'i') : null, school: m.school, inc$: m.include });
  for (const p of m.people) {
    const key = `${m.school}|${p.name_cn}`;
    people[key] = { key, school: m.school, schoolKey: sk, name: p.name_cn };
    for (const v of [...(p.variants || []), p.name_en].filter(Boolean)) {
      const n = norm(v); if (n.length < 4) continue;
      if (!nameIndex.has(n)) nameIndex.set(n, new Set()); nameIndex.get(n).add(key);
    }
  }
}
// 抽样：构造一批 (姓名, 机构) 看拒绝原因
const samples = [];
let total = 0, rejected = 0;
for (const f of fs.readdirSync(PROC).filter((x) => /^enriched_.*\.json$/.test(x))) {
  const e = JSON.parse(fs.readFileSync(path.join(PROC, f), 'utf8'));
  for (const person of e.people) {
    for (const pap of person.papers || []) {
      for (const c of pap.coauthors || []) {
        const cands = nameIndex.get(norm(c.name));
        if (!cands || !cands.size) continue;
        const a = String(c.aff || '').trim();
        if (!a) continue;
        total++;
        const hits = [...cands].filter((k) => { const r = orgRe.get(people[k].schoolKey); return r?.inc && r.inc.test(a) && !(r.exc && r.exc.test(a)); });
        if (hits.length) continue;
        rejected++;
        if (samples.length < 40) samples.push({ name: c.name, aff: a.slice(0, 110), cands: [...cands].map((k) => people[k].name + '@' + people[k].school).slice(0, 3) });
      }
    }
  }
}
console.log(`含机构串的候选 ${total} 条，被拒 ${rejected} 条（${(rejected / total * 100).toFixed(1)}%）\n`);
console.log('被拒样本（姓名 | 机构串 | 名录中的同名候选）:');
for (const s of samples) console.log(`  ${s.name.padEnd(22)} | ${s.aff.padEnd(60)} | ${s.cands.join(' / ')}`);
