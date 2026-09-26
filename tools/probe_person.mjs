// probe_person.mjs — 直接探测某人在 Crossref 里的真实返回情况
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const compact = (s) => (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');

const CASES = [
  { name: '刘晓贤', variants: ['xiaoxian liu', 'liu xiaoxian'], school: 'xidian', aff: /xidian/i, cur: 1 },
  { name: '吴汉明', variants: ['hanming wu', 'wu hanming'], school: 'zju', aff: /zhejiang university/i, cur: 2 },
  { name: '刘马良', variants: ['maliang liu', 'liu maliang'], school: 'xidian', aff: /xidian/i, cur: 2 },
];

for (const c of CASES) {
  console.log(`\n########## ${c.name}（当前计入 ${c.cur} 篇）##########`);
  const cset = new Set(c.variants.map(compact));
  for (const v of c.variants) {
    // 策略A：姓名 + 机构（当前做法）
    const uA = `https://api.crossref.org/works?query.author=${encodeURIComponent(v)}&query.affiliation=${encodeURIComponent(c.school === 'xidian' ? 'Xidian University' : 'Zhejiang University')}&filter=from-pub-date:2005-01-01&rows=100&select=DOI,title,author,container-title,published&mailto=ic-mentor-db@users.noreply.github.com`;
    // 策略B：只按姓名
    const uB = `https://api.crossref.org/works?query.author=${encodeURIComponent(v)}&filter=from-pub-date:2005-01-01&rows=100&select=DOI,title,author,container-title,published&mailto=ic-mentor-db@users.noreply.github.com`;
    for (const [tag, u] of [['A 姓名+机构', uA], ['B 仅姓名', uB]]) {
      const r = await fetch(u, { headers: { 'User-Agent': UA } });
      if (!r.ok) { console.log(`  [${tag}] ${v} -> HTTP ${r.status}`); continue; }
      const j = await r.json();
      const items = j.message?.items || [];
      let nameHit = 0, affHit = 0;
      const affSamples = new Set();
      for (const it of items) {
        for (const a of it.author || []) {
          const full = [a.given, a.family].filter(Boolean).join(' ');
          if (!cset.has(compact(full))) continue;
          nameHit++;
          const aff = (a.affiliation || []).map((x) => x.name || '').join(' | ');
          if (aff) affSamples.add(aff.slice(0, 60));
          if (c.aff.test(aff)) affHit++;
          break;
        }
      }
      console.log(`  [${tag}] "${v}": 返回 ${items.length} 条 | 姓名命中 ${nameHit} | 机构也命中 ${affHit}`);
      if (tag === 'B 仅姓名' && affSamples.size) {
        console.log('      本人机构串样例:', [...affSamples].slice(0, 3).join(' /// '));
      }
      await sleep(400);
    }
  }
}
