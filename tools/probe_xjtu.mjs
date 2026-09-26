// probe_xjtu.mjs — 检查 Crossref 里西交作者的实际机构串写法
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const q = process.argv[2] || 'Lili Geng';
const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(q)}&rows=60&select=DOI,author,title,container-title,published&mailto=ic-mentor-db@users.noreply.github.com`;
const r = await fetch(url, { headers: { 'User-Agent': UA } });
const j = await r.json();
const affs = new Map();
for (const it of j.message.items || []) {
  for (const a of it.author || []) {
    for (const af of a.affiliation || []) {
      const n = (af.name || '').trim();
      if (/jiaotong|xi.?an/i.test(n)) affs.set(n, (affs.get(n) || 0) + 1);
    }
  }
}
console.log(`查询 "${q}"：含 jiaotong/xian 的机构串 ${affs.size} 种`);
for (const [k, v] of [...affs].sort((a, b) => b[1] - a[1]).slice(0, 25)) console.log(`  ${String(v).padStart(3)}  ${k.slice(0, 110)}`);
const re = /xi\s*'?an\s*jiaotong/i;
console.log('\n现有正则命中情况:');
for (const [k, v] of [...affs].sort((a, b) => b[1] - a[1]).slice(0, 25)) {
  console.log(`  ${re.test(k) ? '✓' : '✗'}  ${k.slice(0, 90)}`);
}
