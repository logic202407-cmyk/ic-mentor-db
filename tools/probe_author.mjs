// probe_author.mjs — 验证「按作者名 + 机构」检索 Crossref 的召回率（以复旦 ISSCC 论文作者为例）
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const get = async (u) => { const r = await fetch(u, { headers: { 'User-Agent': UA } }); return await r.json().catch(() => null); };

// 先取一篇复旦 ISSCC 2026 论文，拿到作者名
const j = await get('https://api.crossref.org/works?query.container-title=International+Solid-State+Circuits+Conference&query.affiliation=Fudan&filter=from-pub-date:2024-01-01,type:proceedings-article&rows=8&select=DOI,title,author,container-title,published');
const items = (j?.message?.items || []).filter((it) => (it.author || []).some((a) => (a.affiliation || []).some((x) => /fudan/i.test(x.name || ''))));
console.log('找到复旦 ISSCC 论文', items.length, '篇');
const sample = items.slice(0, 4);
const testAuthors = [];
for (const it of sample) {
  const a = (it.author || []).find((x) => (x.affiliation || []).some((y) => /fudan/i.test(y.name || '')));
  if (a) testAuthors.push({ paper: (it.title || [''])[0].slice(0, 55), name: [a.given, a.family].filter(Boolean).join(' ') });
}
for (const t of testAuthors) console.log('  样本:', t.name, '|', t.paper);

console.log('\n== 按「作者名 + 机构」检索，看能否召回本人论文 ==');
for (const t of testAuthors) {
  const u = `https://api.crossref.org/works?query.author=${encodeURIComponent(t.name)}&query.affiliation=${encodeURIComponent('Fudan University')}&filter=from-pub-date:2015-01-01&rows=100&select=DOI,title,author,container-title,published,type`;
  const r = await get(u);
  const items2 = r?.message?.items || [];
  const norm = (s) => s.toLowerCase().replace(/[^a-z ]/g, '').replace(/\s+/g, ' ').trim();
  const target = norm(t.name);
  let exact = 0, isscc = 0;
  const venues = new Set();
  for (const it of items2) {
    const hit = (it.author || []).some((a) => norm([a.given, a.family].filter(Boolean).join(' ')) === target || norm(a.family || '') === norm(t.name.split(' ').slice(-1)[0]) && norm(a.given || '') === norm(t.name.split(' ')[0]));
    if (!hit) continue;
    const affOk = (it.author || []).some((a) => norm([a.given, a.family].filter(Boolean).join(' ')) === target && (a.affiliation || []).some((x) => /fudan/i.test(x.name || '')));
    if (affOk) exact++;
    const ct = (it['container-title'] || [''])[0] || '';
    if (/solid-state circuits conference/i.test(ct)) isscc++;
    venues.add(ct.slice(0, 40));
  }
  console.log(`  ${t.name}: 返回${items2.length}条 | 姓名+机构双匹配=${exact} | 其中ISSCC=${isscc} | venue种类=${venues.size}`);
  await new Promise((s) => setTimeout(s, 600));
}
