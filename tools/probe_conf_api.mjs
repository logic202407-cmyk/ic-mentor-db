// probe_conf_api.mjs — 测试 Crossref 覆盖会议论文的可行路径
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function j(url) {
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    if (!r.ok) return { err: r.status };
    const t = await r.json();
    return { n: t.message['total-results'], items: t.message.items || [] };
  } catch (e) { return { err: e.message.slice(0, 40) }; }
}
const M = '&mailto=ic-mentor-db@users.noreply.github.com';
const T = 'ISSCC 2024';

const tests = [
  ['ISBN 过滤（ISSCC 2024 会议录 ISBN）', `https://api.crossref.org/works?filter=isbn:978-1-6654-5902-5&rows=3${M}`],
  ['container-title 检索', `https://api.crossref.org/works?query.container-title=${encodeURIComponent('International Solid-State Circuits Conference')}&rows=3${M}`],
  ['bibliographic 检索', `https://api.crossref.org/works?query.bibliographic=${encodeURIComponent('ISSCC 2024 IEEE International Solid-State Circuits Conference')}&rows=3${M}`],
  ['type:proceedings-article + 未限定', `https://api.crossref.org/works?filter=type:proceedings-article,from-pub-date:2024-01-01,until-pub-date:2024-12-31&rows=3${M}`],
  ['query.container-title + type', `https://api.crossref.org/works?query.container-title=${encodeURIComponent('Solid-State Circuits Conference')}&filter=type:proceedings-article,from-pub-date:2008-01-01&rows=3${M}`],
];
for (const [label, url] of tests) {
  const r = await j(url);
  if (r.err) { console.log(`✗ ${label}: ${r.err}`); continue; }
  console.log(`\n✓ ${label}: 总量 ${r.n?.toLocaleString?.() ?? r.n}`);
  for (const it of r.items.slice(0, 2)) {
    const au = (it.author || []).slice(0, 3).map((a) => [a.given, a.family].filter(Boolean).join(' ')).join(', ');
    const aff = (it.author?.[0]?.affiliation || []).map((x) => x.name).join('');
    console.log(`    ${(it['container-title'] || [''])[0].slice(0, 50)} | ${(it.title || [''])[0].slice(0, 40)}`);
    console.log(`      作者: ${au}${au ? '...' : ''} | 首作者机构: ${aff.slice(0, 50) || '(空)'}`);
  }
  await sleep(600);
}

// 查一个已知会议论文 DOI 看机构字段情况
console.log('\n=== 已知会议论文的机构字段情况 ===');
const dois = ['10.1109/isscc49657.2024.10454321', '10.1109/isscc42615.2023.10067835'];
for (const d of dois) {
  const r = await j(`https://api.crossref.org/works/${d}${M.replace('&', '?')}`);
  if (r.err || !r.items?.[0]) { console.log(`  ${d}: ${r.err || '未找到'}`); continue; }
  const it = r.items[0];
  const withAff = (it.author || []).filter((a) => (a.affiliation || []).length).length;
  console.log(`  ${d}: ${(it['container-title'] || [''])[0].slice(0, 44)} | 作者 ${(it.author || []).length} 人，其中 ${withAff} 人有机构串`);
  await sleep(500);
}
