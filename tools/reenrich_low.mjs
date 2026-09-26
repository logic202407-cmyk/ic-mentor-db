// reenrich_low.mjs — 对低召回导师做二次检索（作者名检索 + 机构后置校验），提升论文召回率
// 用法: node reenrich_low.mjs [阈值论文数，默认 2]
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const MAILTO = 'ic-mentor-db@users.noreply.github.com';
const THRESH = Number(process.argv[2] || 2);
const CONC = Number(process.env.CONC || 10);
const SELECT = 'DOI,title,author,container-title,published,type,is-referenced-by-count,ISSN,short-container-title';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

function compact(s) {
  return (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');
}
function compactSet(vs) {
  const set = new Set();
  for (const v of vs) {
    const c = compact(v);
    if (!c) continue;
    set.add(c);
    if (c.includes('v')) { set.add(c.replace(/v/g, 'u')); set.add(c.replace(/v/g, 'yu')); }
  }
  return set;
}
async function cr(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      if (r.status === 429 || r.status >= 500) { await sleep(2500 * (i + 1)); continue; }
      if (!r.ok) return { err: r.status };
      return await r.json();
    } catch (e) { if (i === tries - 1) return { err: e.message }; await sleep(1500); }
  }
  return { err: 'exhausted' };
}

const venueOf = (it) => ((it['container-title'] || [''])[0] || (it['short-container-title'] || [''])[0] || '').replace(/\s+/g, ' ').trim();
function toPaper(it, idx, meIdx) {
  const authors = it.author || [];
  return {
    doi: it.DOI,
    title: (it.title || [''])[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
    year: it.published?.['date-parts']?.[0]?.[0] ?? null,
    venue: venueOf(it),
    type: it.type,
    cited: it['is-referenced-by-count'] ?? 0,
    my_order: meIdx + 1,
    n_authors: authors.length,
    coauthors: authors.map((a, i) => ({ name: [a.given, a.family].filter(Boolean).join(' ') || a.name || '', order: i + 1, aff: (a.affiliation || []).map((x) => x.name || '').join(' | ').slice(0, 160) })),
  };
}

// 收集需要补救的人
const jobs = [];
for (const [key, meta] of Object.entries(variants)) {
  const file = path.join(PROC, `enriched_${key}.json`);
  if (!fs.existsSync(file)) continue;
  const enriched = JSON.parse(fs.readFileSync(file, 'utf8'));
  const byName = new Map(enriched.people.map((p) => [p.name_cn, p]));
  for (const p of meta.people) {
    const e = byName.get(p.name_cn);
    if (!e) continue;
    if ((e.papers || []).length > THRESH) continue;
    const isSenior = /教授|研究员|院士|杰青|讲席|特聘|副教授|副研究员/.test(String(p.title || ''));
    if (!isSenior) continue;
    jobs.push({ key, meta, person: p, enriched, current: e });
  }
}
console.log(`待二次检索: ${jobs.length} 人（论文数 ≤ ${THRESH} 的教授/研究员）`);

const bySchool = {};
for (const j of jobs) (bySchool[j.key] = bySchool[j.key] || []).push(j);

let improved = 0, added = 0, done = 0;
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
      // 策略：只用作者名检索（不限定机构），再逐条校验「姓名精确 + 本人机构命中」
      for (const v of (p.variants || []).slice(0, 3)) {
        const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(v)}` +
          `&filter=from-pub-date:2005-01-01&rows=200&select=${SELECT}&mailto=${MAILTO}`;
        const j2 = await cr(url);
        if (j2.err) continue;
        for (const it of j2.message?.items || []) {
          if (!it.DOI || found.has(it.DOI)) continue;
          const authors = it.author || [];
          let meIdx = -1;
          for (let k = 0; k < authors.length; k++) {
            const a = authors[k];
            const full = [a.given, a.family].filter(Boolean).join(' ') || a.name || '';
            if (!cset.has(compact(full))) continue;
            const aff = (a.affiliation || []).map((x) => x.name || '').join(' | ');
            if (aff ? (inc.test(aff) && !(exc && exc.test(aff))) : false) { meIdx = k; break; }
          }
          if (meIdx < 0) continue;
          const allAff = authors.flatMap((a) => (a.affiliation || []).map((x) => x.name || '')).join(' | ');
          if (!inc.test(allAff)) continue;
          if (exc && exc.test(allAff)) continue;
          found.set(it.DOI, toPaper(it, 0, meIdx));
        }
        await sleep(150);
      }
      const before = job.current.papers.length;
      job.current.papers = [...found.values()].sort((a, b) => (b.year || 0) - (a.year || 0));
      job.current.paper_count = job.current.papers.length;
      job.current._reenriched = true;
      if (job.current.papers.length > before) { improved++; added += job.current.papers.length - before; }
      done++;
      if (done % 50 === 0) console.log(`  ${done}/${jobs.length} (${((Date.now() - t0) / 1000).toFixed(0)}s) 已提升 ${improved} 人 / 新增 ${added} 篇`);
      await sleep(100);
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONC, list.length) }, worker));
  const enriched = list[0].enriched;
  fs.writeFileSync(path.join(PROC, `enriched_${key}.json`), JSON.stringify(enriched, null, 1), 'utf8');
  console.log(`  => ${meta.school} 完成（${list.length} 人）`);
}

console.log(`\n二次检索完成：${done} 人，其中 ${improved} 人召回提升，新增 ${added} 篇论文（${((Date.now() - t0) / 1000).toFixed(0)}s）`);
