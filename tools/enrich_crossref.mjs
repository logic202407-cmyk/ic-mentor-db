// enrich_crossref.mjs — 逐位导师：Crossref「作者名 + 机构」检索 → 精确匹配其论文（含会议）
// 用法: node enrich_crossref.mjs [schoolKey ...]
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const MAILTO = 'ic-mentor-db@users.noreply.github.com';
const CONCURRENCY = Number(process.env.CONC || 8);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SELECT = 'DOI,title,author,container-title,published,type,is-referenced-by-count,ISSN,short-container-title';

const rosters = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

// —— 姓名归一化 ——
function compact(s) {
  const toks = (s || '').toLowerCase()
    .replace(/[^a-z\s-]/g, ' ')
    .split(/[\s-]+/)
    .filter((t) => t.length > 1);           // 去掉单个字母（中间名缩写）
  return toks.join('');
}
function compactSet(variants) {
  const set = new Set();
  for (const v of variants) {
    const c = compact(v);
    if (!c) continue;
    set.add(c);
    if (c.includes('v')) { set.add(c.replace(/v/g, 'u')); set.add(c.replace(/v/g, 'yu')); }  // lv -> lu / lyu
    if (c.includes('u')) set.add(c.replace(/u/g, 'v'));
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

function venueOf(item) {
  const ct = (item['container-title'] || [''])[0] || (item['short-container-title'] || [''])[0] || '';
  return ct.replace(/\s+/g, ' ').trim();
}

async function enrichPerson(p, meta) {
  const cset = compactSet(p.match_variants || p.variants);
  const q = meta.crossref_query;
  const inc = meta.include ? new RegExp(meta.include, 'i') : null;
  const exc = meta.exclude ? new RegExp(meta.exclude, 'i') : null;

  const queryVariant = async (variant) => {
    const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(variant)}` +
      `&query.affiliation=${encodeURIComponent(q)}&filter=from-pub-date:2008-01-01` +
      `&rows=200&select=${SELECT}&mailto=${MAILTO}`;
    const j = await cr(url);
    if (j.err) return { err: j.err, papers: [], fetched: 0 };
    const items = j.message?.items || [];
    const papers = [];
    for (const it of items) {
      const authors = it.author || [];
      let me = null;
      for (let i = 0; i < authors.length; i++) {
        const a = authors[i];
        const full = [a.given, a.family].filter(Boolean).join(' ') || a.name || '';
        if (!cset.has(compact(full))) continue;
        const aff = (a.affiliation || []).map((x) => x.name || '').join(' | ');
        if (aff ? (inc.test(aff) && !(exc && exc.test(aff))) : false) { me = { i, a }; break; }
        if (!aff) { me = me || { i, a, affUnknown: true }; }
      }
      if (!me) continue;
      const allAff = authors.flatMap((a) => (a.affiliation || []).map((x) => x.name || '')).join(' | ');
      if (!inc.test(allAff)) continue;
      if (exc && exc.test(allAff)) continue;
      papers.push({
        doi: it.DOI,
        title: (it.title || [''])[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
        year: it.published?.['date-parts']?.[0]?.[0] ?? null,
        venue: venueOf(it),
        type: it.type,
        cited: it['is-referenced-by-count'] ?? 0,
        my_order: me.i + 1,
        n_authors: authors.length,
        aff_unknown: !!me.affUnknown,
        coauthors: authors.map((a, idx) => ({ name: [a.given, a.family].filter(Boolean).join(' ') || a.name || '', order: idx + 1, aff: (a.affiliation || []).map((x) => x.name || '').join(' | ').slice(0, 160) })),
      });
    }
    return { papers, fetched: items.length, err: null };
  };

  const byDoi = new Map();
  let fetched = 0, err = null, attempts = 0;
  for (const v of p.variants.slice(0, 3)) {
    attempts++;
    const r = await queryVariant(v);
    fetched = Math.max(fetched, r.fetched);
    if (r.err) err = r.err;
    for (const x of r.papers) if (x.doi && !byDoi.has(x.doi)) byDoi.set(x.doi, x);
    if (byDoi.size >= 6 || attempts >= 2) break;   // 已够多则不再试第二种写法
    await sleep(250);
  }
  const uniq = [...byDoi.values()].sort((a, b) => (b.year || 0) - (a.year || 0));
  return { papers: uniq, fetched, error: err };
}

const only = process.argv.slice(2);
for (const key of Object.keys(rosters)) {
  if (only.length && !only.includes(key)) continue;
  const meta = rosters[key];
  const outFile = path.join(PROC, `enriched_${key}.json`);
  if (fs.existsSync(outFile) && !process.env.FORCE) { console.log(`skip ${key} (exists)`); continue; }
  console.log(`\n#### ${meta.school} (${key}) people=${meta.people.length} concurrency=${CONCURRENCY}`);
  const out = new Array(meta.people.length);
  let done = 0;
  let idx = 0;
  const t0 = Date.now();
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= meta.people.length) return;
      const p = meta.people[i];
      let r;
      try { r = await enrichPerson(p, meta); } catch (e) { r = { papers: [], error: e.message }; }
      out[i] = { ...p, paper_count: r.papers.length, papers: r.papers, _fetched: r.fetched, _error: r.error || null };
      done++;
      if (done % 20 === 0) {
        const el = ((Date.now() - t0) / 1000).toFixed(0);
        console.log(`  [${done}/${meta.people.length}] ${el}s 最近: ${p.name_cn}->${r.papers.length}篇`);
      }
      await sleep(120);
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, meta.people.length) }, worker));
  fs.writeFileSync(outFile, JSON.stringify({ school: meta.school, school_key: key, people: out }, null, 1));
  const withPapers = out.filter((x) => x && x.paper_count > 0).length;
  console.log(`  => ${meta.school}: 有论文记录 ${withPapers}/${out.length} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
console.log('\nENRICH DONE');
