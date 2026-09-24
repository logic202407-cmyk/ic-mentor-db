// probe_conf.mjs — 会议论文检索策略对比（哪种能稳定捞到某校的 ISSCC/CICC 论文）
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (u) => { const r = await fetch(u, { headers: { 'User-Agent': UA } }); return { status: r.status, data: await r.json().catch(() => null) }; };

const SCHOOL = 'Nanjing University';
const MATCH = /nanjing university(?!\s+of)/i;
const CONF = { key: 'ISSCC', q: 'IEEE International Solid-State Circuits Conference' };

async function scan(label, base, pages) {
  let cursor = '*', hits = 0, scanned = 0, total = 0, firstName = null;
  for (let p = 0; p < pages; p++) {
    const j = await get(`${base}&rows=1000&cursor=${encodeURIComponent(cursor)}`);
    if (j.data?.status === 'failed' || !j.data) { console.log(`  ${label}: ERR`, j.status); break; }
    const msg = j.data.message;
    total = msg['total-results'];
    const items = msg.items || [];
    scanned += items.length;
    items.forEach((it, idx) => {
      const affs = (it.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name || ''));
      if (affs.some((s) => MATCH.test(s))) {
        hits++;
        if (!firstName) firstName = `pos=${p * 1000 + idx + 1} | ${(it['container-title'] || [''])[0].slice(0, 40)} | ${(it.title || [''])[0].slice(0, 50)}`;
      }
    });
    cursor = msg['next-cursor'];
    if (!items.length || scanned >= total) break;
    await sleep(400);
  }
  console.log(`  ${label}: total=${total} scanned=${scanned} hits=${hits}`);
  if (firstName) console.log(`      first hit: ${firstName}`);
}

console.log('== 策略 1: query.container-title + query.affiliation ==================');
await scan('S1', `https://api.crossref.org/works?query.container-title=${encodeURIComponent(CONF.q)}&query.affiliation=${encodeURIComponent(SCHOOL)}&filter=from-pub-date:2015-01-01`, 3);

console.log('== 策略 2: query.bibliographic(会议名+学校) ==========================');
await scan('S2', `https://api.crossref.org/works?query.bibliographic=${encodeURIComponent(CONF.q + ' ' + SCHOOL)}&filter=from-pub-date:2015-01-01`, 2);

console.log('== 策略 3: query.affiliation 单独 + 容器名后置过滤 ====================');
await scan('S3', `https://api.crossref.org/works?query.affiliation=${encodeURIComponent(SCHOOL)}&query.container-title=${encodeURIComponent('Solid-State Circuits Conference')}&filter=from-pub-date:2015-01-01,type:proceedings-article`, 3);

console.log('== 策略 4: 加 select 缩小响应（对照 S1） =============================');
await scan('S4', `https://api.crossref.org/works?query.container-title=${encodeURIComponent('Solid-State Circuits Conference')}&query.affiliation=${encodeURIComponent(SCHOOL)}&filter=from-pub-date:2015-01-01,type:proceedings-article`, 3);
