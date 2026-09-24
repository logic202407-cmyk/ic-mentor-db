// probe_isbn.mjs — 探测能否用 ISBN 整本抓取会议论文集（ISSCC/CICC 等）
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const get = async (u) => { const r = await fetch(u, { headers: { 'User-Agent': UA } }); return await r.json().catch(() => null); };

console.log('== 1) 从已知 ISSCC 论文取 ISBN ==');
const j = await get('https://api.crossref.org/works?query.container-title=International+Solid-State+Circuits+Conference&filter=from-pub-date:2022-01-01,until-pub-date:2026-12-31,type:proceedings-article&rows=40&select=DOI,title,ISBN,container-title,published');
const isbns = new Map();
for (const it of j?.message?.items || []) {
  const ct = (it['container-title'] || [''])[0] || '';
  if (!/solid-state circuits conference/i.test(ct)) continue;
  const y = it.published?.['date-parts']?.[0]?.[0];
  for (const i of it.ISBN || []) if (!isbns.has(i)) isbns.set(i, { year: y, ct: ct.slice(0, 60) });
}
console.log('   取到 ISBN', isbns.size, '个');
for (const [k, v] of [...isbns].slice(0, 10)) console.log(`   ${k} | ${v.year} | ${v.ct}`);

console.log('\n== 2) 用 ISBN 抓整本论文集 ==');
for (const [isbn, meta] of [...isbns].slice(0, 2)) {
  const r = await get(`https://api.crossref.org/works?filter=isbn:${isbn}&rows=3&select=DOI,title,author,container-title,published`);
  console.log(`   isbn=${isbn} total=${r?.message?.['total-results']}`);
  for (const it of (r?.message?.items || []).slice(0, 2)) {
    const affs = [...new Set((it.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name)))];
    console.log(`      ${(it.title || [''])[0].slice(0, 60)} | aff=${affs.slice(0, 2).join(' ; ').slice(0, 100)}`);
  }
  await new Promise((s) => setTimeout(s, 500));
}

console.log('\n== 3) 遍历多个会议名收集 ISBN（用于后续整本抓取） ==');
const confs = [
  ['ISSCC', 'International Solid-State Circuits Conference'],
  ['CICC', 'Custom Integrated Circuits Conference'],
  ['A-SSCC', 'Asian Solid-State Circuits Conference'],
  ['VLSI', 'Symposium on VLSI Circuits'],
  ['ESSCIRC', 'European Solid-State Circuits Conference'],
  ['DAC', 'Design Automation Conference'],
  ['ICCAD', 'International Conference on Computer-Aided Design'],
  ['ISCA', 'International Symposium on Computer Architecture'],
  ['MICRO', 'International Symposium on Microarchitecture'],
  ['HPCA', 'International Symposium on High-Performance Computer Architecture'],
];
const all = {};
for (const [k, q] of confs) {
  const rr = await get(`https://api.crossref.org/works?query.container-title=${encodeURIComponent(q)}&filter=from-pub-date:2015-01-01,type:proceedings-article&rows=100&select=ISBN,container-title,published`);
  const m = new Map();
  for (const it of rr?.message?.items || []) {
    const ct = (it['container-title'] || [''])[0] || '';
    if (!new RegExp(q.split(' ').slice(0, 2).join(' '), 'i').test(ct)) continue;
    const y = it.published?.['date-parts']?.[0]?.[0];
    for (const i of it.ISBN || []) m.set(i, { year: y, ct: ct.slice(0, 70) });
  }
  all[k] = [...m.entries()].map(([isbn, v]) => ({ isbn, ...v }));
  console.log(`   ${k}: ISBN ${all[k].length} 个 -> ${all[k].slice(0, 3).map((x) => x.isbn + '(' + x.year + ')').join(', ')}`);
  await new Promise((s) => setTimeout(s, 400));
}
require('fs').writeFileSync('E:\\ytm\\mentor-db\\data\\raw\\conference_isbns.json', JSON.stringify(all, null, 1));
console.log('\n保存 conference_isbns.json');
