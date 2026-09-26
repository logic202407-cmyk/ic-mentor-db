// reenrich_topic.mjs — 针对低召回导师，按「作者名 × IC 核心期刊 ISSN」精确检索，绕开同校同名者挤占
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const MAILTO = 'ic-mentor-db@users.noreply.github.com';
const THRESH = Number(process.argv[2] || 2);
const CONC = Number(process.env.CONC || 10);
const SELECT = 'DOI,title,author,container-title,published,type,is-referenced-by-count,ISSN,short-container-title';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Crossref 机构串含 HTML 实体（如 Xi&#x2019;an Jiaotong University），需先解码再匹配
const ENT2 = /&(#x[0-9a-f]+|#\d+|amp|apos|quot|lt|gt|nbsp);/gi;
function decodeEnt(s) {
  return String(s || '').replace(ENT2, (m, g) => {
    if (g[0] === '#') {
      const code = g[1].toLowerCase() === 'x' ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10);
      try { return String.fromCodePoint(code); } catch { return ' '; }
    }
    return { amp: '&', apos: "'", quot: '"', lt: '<', gt: '>', nbsp: ' ' }[g.toLowerCase()] ?? ' ';
  });
}
const affText = (a) => (a.affiliation || []).map((x) => decodeEnt(x.name || '')).join(' | ');


// IC 领域核心期刊 ISSN（按方向相关性可扩展）
const ISSN = [
  '0018-9200', // JSSC
  '1549-8328', // TCAS-I
  '1549-7747', // TCAS-II
  '1063-8210', // TVLSI
  '0018-9383', // TED
  '0741-3106', // EDL
  '0018-9480', // MTT
  '0278-0070', // TCAD
  '1932-4545', // TBioCAS
  '0885-8993', // TPEL
];

const variantsRaw = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
// 可选：只处理指定学校，例如 `node reenrich_topic.mjs 2 cas hit buaa`
const ONLY = process.argv.slice(3).filter((x) => !/^\d+$/.test(x));
const variants = ONLY.length
  ? Object.fromEntries(Object.entries(variantsRaw).filter(([k]) => ONLY.includes(k)))
  : variantsRaw;
if (ONLY.length) console.log('限定学校:', ONLY.join(', '));
const compact = (s) => (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');
function compactSet(vs) {
  const set = new Set();
  for (const v of vs) { const c = compact(v); if (!c) continue; set.add(c); if (c.includes('v')) { set.add(c.replace(/v/g, 'u')); set.add(c.replace(/v/g, 'yu')); } }
  return set;
}
async function cr(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      if (r.status === 429 || r.status >= 500) { await sleep(2000 * (i + 1)); continue; }
      if (!r.ok) return { err: r.status };
      return await r.json();
    } catch (e) { if (i === tries - 1) return { err: e.message }; await sleep(1200); }
  }
  return { err: 'exhausted' };
}
const venueOf = (it) => ((it['container-title'] || [''])[0] || (it['short-container-title'] || [''])[0] || '').replace(/\s+/g, ' ').trim();

const jobs = [];
for (const [key, meta] of Object.entries(variants)) {
  const file = path.join(PROC, `enriched_${key}.json`);
  if (!fs.existsSync(file)) continue;
  const enriched = JSON.parse(fs.readFileSync(file, 'utf8'));
  const byName = new Map(enriched.people.map((p) => [p.name_cn, p]));
  for (const p of meta.people) {
    const e = byName.get(p.name_cn);
    if (!e || (e.papers || []).length > THRESH) continue;
    jobs.push({ key, meta, person: p, enriched, current: e });
  }
}
console.log(`按期刊精查: ${jobs.length} 人 × ${ISSN.length} 刊`);

const bySchool = {};
for (const j of jobs) (bySchool[j.key] = bySchool[j.key] || []).push(j);

let improved = 0, added = 0, done = 0, reqs = 0;
const t0 = Date.now();
for (const [key, list] of Object.entries(bySchool)) {
  const meta = list[0].meta;
  const inc = new RegExp(meta.include, 'i');
  const exc = meta.exclude ? new RegExp(meta.exclude, 'i') : null;
  let idx = 0;
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= list.length) return;
      const job = list[i];
      const p = job.person;
      const cset = compactSet(p.match_variants || p.variants);
      const found = new Map((job.current.papers || []).map((x) => [x.doi, x]));
      const v = p.variants[0];
      for (const issn of ISSN) {
        const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(v)}&filter=issn:${issn},from-pub-date:2005-01-01&rows=50&select=${SELECT}&mailto=${MAILTO}`;
        const j2 = await cr(url); reqs++;
        if (j2.err) continue;
        for (const it of j2.message?.items || []) {
          if (!it.DOI || found.has(it.DOI)) continue;
          const authors = it.author || [];
          let meIdx = -1;
          for (let k = 0; k < authors.length; k++) {
            const a = authors[k];
            const full = [a.given, a.family].filter(Boolean).join(' ') || a.name || '';
            if (!cset.has(compact(full))) continue;
            const aff = affText(a);
            if (aff ? (inc.test(aff) && !(exc && exc.test(aff))) : false) { meIdx = k; break; }
          }
          if (meIdx < 0) continue;
          const authors2 = authors.map((a, i2) => ({ name: [a.given, a.family].filter(Boolean).join(' ') || a.name || '', order: i2 + 1, aff: affText(a).slice(0, 160) }));
          found.set(it.DOI, {
            doi: it.DOI, title: (it.title || [''])[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
            year: it.published?.['date-parts']?.[0]?.[0] ?? null, venue: venueOf(it), type: it.type,
            cited: it['is-referenced-by-count'] ?? 0, my_order: meIdx + 1, n_authors: authors.length, coauthors: authors2,
          });
        }
        await sleep(60);
      }
      const before = job.current.papers.length;
      job.current.papers = [...found.values()].sort((a, b) => (b.year || 0) - (a.year || 0));
      job.current.paper_count = job.current.papers.length;
      if (job.current.papers.length > before) { improved++; added += job.current.papers.length - before; }
      done++;
      if (done % 40 === 0) console.log(`  ${done}/${jobs.length} (${((Date.now() - t0) / 1000).toFixed(0)}s, ${reqs} req) 提升 ${improved} 人 / 新增 ${added} 篇`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONC, list.length) }, worker));
  fs.writeFileSync(path.join(PROC, `enriched_${key}.json`), JSON.stringify(list[0].enriched, null, 1), 'utf8');
  console.log(`  => ${meta.school} 完成（${list.length} 人）`);
}
console.log(`\n完成：${done} 人，${improved} 人召回提升，新增 ${added} 篇（${reqs} 次请求，${((Date.now() - t0) / 1000).toFixed(0)}s）`);
