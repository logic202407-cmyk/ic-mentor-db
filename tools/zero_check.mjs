// zero_check.mjs — 抽查 0 论文者，用「仅作者名」策略重试，评估漏检率
import fs from 'node:fs';
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const db = JSON.parse(fs.readFileSync('E:\\ytm\\mentor-db\\data\\processed\\mentor_db.json', 'utf8'));
const PROC = 'E:\\ytm\\mentor-db\\data\\processed';

// 重新读 variants
const variants = JSON.parse(fs.readFileSync(`${PROC}\\name_variants.json`, 'utf8'));
const vmap = {};
for (const [k, v] of Object.entries(variants)) for (const p of v.people) vmap[`${k}|${p.name_cn}`] = p;

const zeros = db.filter((r) => r.n_all_papers === 0).slice(0, Number(process.argv[2] || 12));
console.log('抽查 0 论文者', zeros.length, '人\n');

function compact(s) {
  return (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');
}
const INC = {
  fudan: /fudan/i, sjtu: /shanghai\s*jiao\s*tong|sjtu/i, zju: /zhejiang university/i,
  nju: /nanjing university(?!\s+of)/i, ustc: /university of science and technology of china|ustc/i, sigs: /tsinghua/i,
};

for (const r of zeros) {
  const p = vmap[`${r.school_key}|${r.name_cn}`];
  if (!p) { console.log('skip', r.name_cn); continue; }
  const cset = new Set(p.variants.map(compact).filter(Boolean));
  const inc = INC[r.school_key];
  // 策略：只用作者名检索（不限机构），再本地过滤机构
  const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(p.variants[0])}&filter=from-pub-date:2010-01-01&rows=100&select=DOI,title,author,container-title,published,type&mailto=mentor.db.builder@gmail.com`;
  let hit = 0, samples = [];
  try {
    const res = await fetch(url, { headers: { 'User-Agent': UA } });
    const j = await res.json();
    for (const it of j.message?.items || []) {
      const authors = it.author || [];
      for (const a of authors) {
        const nm = [a.given, a.family].filter(Boolean).join(' ');
        if (!cset.has(compact(nm))) continue;
        const aff = (a.affiliation || []).map((x) => x.name || '').join(' ');
        if (aff && inc.test(aff)) { hit++; if (samples.length < 2) samples.push(`${it.published?.['date-parts']?.[0]?.[0]} ${(it['container-title'] || [''])[0].slice(0, 40)} | ${(it.title || [''])[0].slice(0, 45)}`); }
        break;
      }
    }
  } catch (e) { samples.push('ERR ' + e.message); }
  console.log(`${r.school.slice(0, 4)} ${r.name_cn} (${p.variants[0]}) 原=0 → 仅作者名策略命中 ${hit}`);
  for (const s of samples) console.log('     ', s);
  await sleep(400);
}
