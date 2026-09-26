// probe_aff.mjs — 查询某机构在 Crossref 中的实际机构串写法
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const aff = process.argv[2] || "Xi'an Jiaotong University";
const reSrc = process.argv[3] || "xi\\s*'?an\\s*jiaotong";
const re = new RegExp(reSrc, 'i');
const url = 'https://api.crossref.org/works?query.affiliation=' + encodeURIComponent(aff) +
  '&rows=50&select=DOI,author&mailto=ic-mentor-db@users.noreply.github.com';
const r = await fetch(url, { headers: { 'User-Agent': UA } });
const j = await r.json();
const affs = new Map();
for (const it of j.message.items || []) {
  for (const a of it.author || []) {
    for (const af of a.affiliation || []) {
      const n = (af.name || '').replace(/\s+/g, ' ').trim();
      if (n) affs.set(n, (affs.get(n) || 0) + 1);
    }
  }
}
console.log(`查询机构 "${aff}"，返回 ${j.message.items.length} 条，样本中机构串 ${affs.size} 种`);
console.log(`含 jiaotong 的串: ${[...affs.keys()].filter((k) => /jiaotong/i.test(k)).length}`);
console.log('Top 20：');
for (const [k, v] of [...affs].sort((a, b) => b[1] - a[1]).slice(0, 20)) {
  console.log(`  ${re.test(k) ? '✓' : '✗'} ${String(v).padStart(3)}  ${k.slice(0, 100)}`);
}
