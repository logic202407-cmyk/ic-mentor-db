// test_sources.mjs — 验证 Crossref / dblp 在无 OpenAlex 情况下能否按机构+期刊检索
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';

async function j(url, headers = {}) {
  const r = await fetch(url, { headers: { 'User-Agent': UA, ...headers } });
  const t = await r.text();
  try { return { status: r.status, data: JSON.parse(t) }; } catch { return { status: r.status, text: t.slice(0, 200) }; }
}

console.log('===== 1) Crossref: JSSC + 机构检索 =====');
let r = await j('https://api.crossref.org/journals/0018-9200/works?query.affiliation=Fudan+University&rows=5&select=DOI,title,author,published,container-title');
console.log('status', r.status, 'total', r.data?.message?.['total-results']);
for (const it of r.data?.message?.items || []) {
  const affs = [...new Set((it.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name)))].slice(0, 3);
  console.log(`  ${it.published?.['date-parts']?.[0]?.[0]} | ${(it.title || [''])[0].slice(0, 70)}`);
  console.log(`     aff: ${affs.join(' ; ').slice(0, 160)}`);
}

console.log('\n===== 2) Crossref: 过滤器式（ISSN + 时间）按机构关键词筛 =====');
r = await j('https://api.crossref.org/works?filter=issn:0018-9200,from-pub-date:2023-01-01&query.affiliation=Tsinghua&rows=3&select=DOI,title,author,published');
console.log('status', r.status, 'total', r.data?.message?.['total-results']);

console.log('\n===== 3) dblp: 会议 TOC（ISSCC 2024） =====');
r = await j('https://dblp.org/search/publ/api?q=stream%3Astreams%2Fconf%2Fisscc%3A&h=5&format=json');
console.log('status', r.status, 'hits', r.data?.result?.hits?.['@total']);
for (const h of r.data?.result?.hits?.hit || []) console.log('  ', h.info?.year, '|', (h.info?.title || '').slice(0, 70), '|', (h.info?.authors?.author || []).map?.((a) => a.text || a).join(', ').slice(0, 80));

console.log('\n===== 4) dblp: 作者检索 =====');
r = await j('https://dblp.org/search/author/api?q=Hao+Zhang&h=3&format=json');
console.log('status', r.status, 'hits', r.data?.result?.hits?.['@total']);
for (const h of r.data?.result?.hits?.hit || []) console.log('  ', h.info?.author, '|', h.info?.url);

console.log('\n===== 5) dblp: 会议年份 TOC 页面（HTML） =====');
const toc = await fetch('https://dblp.org/db/conf/isscc/isscc2024.html', { headers: { 'User-Agent': UA } });
console.log('status', toc.status, 'len', (await toc.text()).length);

console.log('\n===== 6) Semantic Scholar 状态 =====');
r = await j('https://api.semanticscholar.org/graph/v1/paper/search?query=solid-state%20circuits&limit=2&fields=title,year,venue');
console.log('status', r.status, r.data?.total ?? r.text);
