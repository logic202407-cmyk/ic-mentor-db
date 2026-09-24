// test_conf.mjs — 验证会议论文能否通过 Crossref 按机构检索 + 修复 dblp API
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const j = async (url) => { const r = await fetch(url, { headers: { 'User-Agent': UA } }); return { status: r.status, data: await r.json().catch(() => null) }; };

console.log('===== A) Crossref: ISSCC 会议论文 + 机构 =====');
let r = await j('https://api.crossref.org/works?query.container-title=International+Solid-State+Circuits+Conference&query.affiliation=Fudan&filter=from-pub-date:2022-01-01&rows=3&select=DOI,title,author,container-title,published,type');
console.log('status', r.status, 'total', r.data?.message?.['total-results']);
for (const it of r.data?.message?.items || []) {
  console.log(`  ${it.published?.['date-parts']?.[0]?.[0]} | ${(it['container-title'] || [''])[0].slice(0, 50)} | ${(it.title || [''])[0].slice(0, 60)}`);
  console.log('     aff:', [...new Set((it.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name)))].slice(0, 2).join(' ; ').slice(0, 120));
}

console.log('\n===== B) Crossref: 按 proceedings 标题精确筛 ISSCC =====');
r = await j('https://api.crossref.org/works?query.bibliographic=ISSCC+2023+digest+of+technical+papers&query.affiliation=Tsinghua&rows=3&select=DOI,title,container-title,published');
console.log('status', r.status, 'total', r.data?.message?.['total-results']);
for (const it of r.data?.message?.items || []) console.log('  ', (it['container-title'] || [''])[0], '|', (it.title || [''])[0].slice(0, 60));

console.log('\n===== C) dblp 原始返回 =====');
const raw = await fetch('https://dblp.org/search/publ/api?q=isscc&h=2&format=json', { headers: { 'User-Agent': UA } });
console.log('status', raw.status);
console.log((await raw.text()).slice(0, 500));

console.log('\n===== D) dblp TOC 页面（正确路径探测） =====');
for (const u of ['https://dblp.org/db/conf/isscc/isscc2024.html', 'https://dblp.org/db/conf/isscc/index.html', 'https://dblp.org/db/conf/cicc/cicc2023.html']) {
  const rr = await fetch(u, { headers: { 'User-Agent': UA } });
  const t = await rr.text();
  console.log(`  [${rr.status}] len=${t.length} ${u}`);
}

console.log('\n===== E) Semantic Scholar（带退避） =====');
for (let i = 0; i < 3; i++) {
  const rr = await fetch('https://api.semanticscholar.org/graph/v1/paper/search?query=analog%20circuit&limit=1&fields=title,year', { headers: { 'User-Agent': UA } });
  console.log('  attempt', i + 1, 'status', rr.status);
  if (rr.ok) break;
  await new Promise((s) => setTimeout(s, 5000));
}
