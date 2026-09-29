// probe_missing.mjs — 对真正零命中的人，直接探测 Crossref 到底有没有他们的论文
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const compact = (s) => (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');

const CASES = [
  { cn: '童志国', en: ['zhiguo tong', 'tong zhiguo'], aff: /beihang|bu\s*aa|aeronautics/i },
  { cn: '曲伟峰', en: ['weifeng qu', 'qu weifeng'], aff: /tsinghua/i },
  { cn: '林楠', en: ['nan lin', 'lin nan'], aff: /beihang|aeronautics/i },
  { cn: '徐崇耀', en: ['chongyao xu', 'xu chongyao'], aff: /xidian/i },
  { cn: '仝金程', en: ['jincheng tong', 'tong jincheng'], aff: /southeast/i },
];

for (const c of CASES) {
  console.log(`\n===== ${c.cn} =====`);
  for (const v of c.en) {
    const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(v)}&rows=100&select=DOI,title,author,container-title,published&mailto=ic-mentor-db@users.noreply.github.com`;
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    const j = await r.json();
    const cs = new Set([compact(v)]);
    let nameHit = 0, affHit = 0;
    const samples = [];
    for (const it of j.message.items || []) {
      for (const a of it.author || []) {
        const full = [a.given, a.family].filter(Boolean).join(' ') || a.name || '';
        if (!cs.has(compact(full))) continue;
        nameHit++;
        const aff = (a.affiliation || []).map((x) => x.name || '').join(' | ');
        if (c.aff.test(aff)) { affHit++; if (samples.length < 3) samples.push(`${it.published?.['date-parts']?.[0]?.[0]} | ${(it['container-title'] || [''])[0].slice(0, 38)} | ${(it.title || [''])[0].slice(0, 42)}`); }
        break;
      }
    }
    console.log(`  "${v}": 前100条中 姓名命中 ${nameHit} | 机构也命中 ${affHit}`);
    for (const s of samples) console.log(`     ✓ ${s}`);
    await sleep(500);
  }
}
