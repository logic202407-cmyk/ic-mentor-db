// harvest_crossref.mjs — 按「学校 × 期刊/会议」从 Crossref 抓取论文（含作者机构），并做机构后置校验
// 用法: node harvest_crossref.mjs [schoolKey ...]   （不传则跑全部）
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const OUT = path.join(REPO, 'data', 'raw', 'crossref');
fs.mkdirSync(OUT, { recursive: true });
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const YEARS = 'from-pub-date:2015-01-01,until-pub-date:2026-12-31';

// ── 学校与机构匹配规则 ─────────────────────────────
const SCHOOLS = {
  sigs: {
    name: '清华大学深圳国际研究生院',
    queries: ['Tsinghua University'],
    // 机构串必须命中 include，且不得命中 exclude
    include: /tsinghua/i,
    exclude: null,
    shenzhen: /shenzhen|SIGS|graduate school at shenzhen/i,
  },
  fudan: { name: '复旦大学', queries: ['Fudan University'], include: /fudan/i, exclude: null },
  sjtu: { name: '上海交通大学', queries: ['Shanghai Jiao Tong University', 'Shanghai Jiaotong University'], include: /shanghai\s*jiao\s*tong|SJTU/i, exclude: null },
  zju: { name: '浙江大学', queries: ['Zhejiang University'], include: /zhejiang university/i, exclude: /zhejiang university of (technology|science)/i },
  nju: { name: '南京大学', queries: ['Nanjing University'], include: /nanjing university/i, exclude: /nanjing university of/i },
  ustc: { name: '中国科学技术大学', queries: ['University of Science and Technology of China'], include: /university of science and technology of china|USTC/i, exclude: null },
  tsinghua: { name: '清华大学', queries: ['Tsinghua University'], include: /tsinghua/i, exclude: /shenzhen|SIGS|graduate school at shenzhen/i },
  pku: { name: '北京大学', queries: ['Peking University'], include: /peking university/i, exclude: null },
  seu: { name: '东南大学', queries: ['Southeast University'], include: /southeast university/i, exclude: null },
  xidian: { name: '西安电子科技大学', queries: ['Xidian University'], include: /xidian/i, exclude: null },
  uestc: { name: '电子科技大学', queries: ['University of Electronic Science and Technology of China'], include: /university of electronic science and technology of china|uestc/i, exclude: null },
};

// ── 期刊（ISSN） ────────────────────────────────────
const JOURNALS = [
  { key: 'JSSC', issn: '0018-9200', tier: 'S' },
  { key: 'SSC-L', issn: '2573-9603', tier: 'A' },
  { key: 'TCAS-I', issn: '1549-8328', tier: 'A' },
  { key: 'TCAS-II', issn: '1549-7747', tier: 'A' },
  { key: 'TVLSI', issn: '1063-8210', tier: 'A' },
  { key: 'TCAD', issn: '0278-0070', tier: 'A' },
  { key: 'TED', issn: '0018-9383', tier: 'A' },
  { key: 'EDL', issn: '0741-3106', tier: 'B' },
  { key: 'MTT', issn: '0018-9480', tier: 'A' },
  { key: 'MWCL', issn: '1531-1309', tier: 'B' },
  { key: 'TBioCAS', issn: '1932-4545', tier: 'A' },
  { key: 'TPEL', issn: '0885-8993', tier: 'A' },
  { key: 'JETCAS', issn: '2156-3357', tier: 'B' },
  { key: 'IEEE-MICRO', issn: '0272-1732', tier: 'B' },
  { key: 'TC', issn: '0018-9340', tier: 'A' },
  { key: 'OJSSCS', issn: '2644-1349', tier: 'B' },
  { key: 'NAT-ELECTRON', issn: '2520-1131', tier: 'S' },
];

// ── 会议（container-title 检索 + 后置校验） ──────────
const CONFERENCES = [
  { key: 'ISSCC', q: 'IEEE International Solid-State Circuits Conference', tier: 'S' },
  { key: 'CICC', q: 'IEEE Custom Integrated Circuits Conference', tier: 'A' },
  { key: 'A-SSCC', q: 'IEEE Asian Solid-State Circuits Conference', tier: 'A' },
  { key: 'VLSI-Symp', q: 'Symposium on VLSI Circuits', tier: 'S' },
  { key: 'ESSCIRC', q: 'European Solid-State Circuits Conference', tier: 'A' },
  { key: 'RFIC', q: 'IEEE Radio Frequency Integrated Circuits Symposium', tier: 'A' },
  { key: 'DAC', q: 'Design Automation Conference', tier: 'A' },
  { key: 'ICCAD', q: 'International Conference on Computer-Aided Design', tier: 'A' },
  { key: 'ISCA', q: 'International Symposium on Computer Architecture', tier: 'S' },
  { key: 'MICRO', q: 'International Symposium on Microarchitecture', tier: 'S' },
  { key: 'HPCA', q: 'International Symposium on High-Performance Computer Architecture', tier: 'S' },
  { key: 'ASPLOS', q: 'Architectural Support for Programming Languages and Operating Systems', tier: 'S' },
  { key: 'FPGA', q: 'ACM/SIGDA International Symposium on Field-Programmable Gate Arrays', tier: 'A' },
  { key: 'ISSCC-2', q: 'Digest of Technical Papers IEEE International Solid-State Circuits Conference', tier: 'S' },
];

const SELECT = 'DOI,title,author,container-title,published,type,is-referenced-by-count,short-container-title,ISSN,ISBN';

function affStrings(item) {
  return (item.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name || '')).filter(Boolean);
}
function matchSchool(item, school) {
  const affs = affStrings(item);
  const hit = affs.filter((s) => school.include.test(s) && !(school.exclude && school.exclude.test(s)));
  if (!hit.length) return null;
  const sz = school.shenzhen ? hit.some((s) => school.shenzhen.test(s)) : null;
  return { affs: [...new Set(hit)], shenzhen: sz };
}
function slim(item, venue, tier, schoolMatch) {
  return {
    doi: item.DOI,
    title: (item.title || [''])[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
    year: item.published?.['date-parts']?.[0]?.[0] ?? null,
    venue: (item['container-title'] || [''])[0],
    venue_key: venue,
    tier,
    type: item.type,
    cited: item['is-referenced-by-count'] ?? null,
    shenzhen: schoolMatch.shenzhen,
    matched_affs: schoolMatch.affs.slice(0, 3),
    authors: (item.author || []).map((a, i) => ({
      name: [a.given, a.family].filter(Boolean).join(' ') || a.name || '',
      order: i + 1,
      aff: (a.affiliation || []).map((x) => x.name).filter(Boolean).join(' | ').slice(0, 200),
    })),
  };
}

async function crossref(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      if (r.status === 429 || r.status >= 500) { await sleep(2000 * (i + 1)); continue; }
      if (!r.ok) return { err: r.status };
      return await r.json();
    } catch (e) { if (i === tries - 1) return { err: e.message }; await sleep(1500); }
  }
  return { err: 'exhausted' };
}

async function pageAll(baseUrl, maxPages, onItems) {
  let cursor = '*', pages = 0, total = 0, seen = 0;
  while (pages < maxPages) {
    const url = `${baseUrl}&rows=1000&cursor=${encodeURIComponent(cursor)}`;
    const j = await crossref(url);
    if (j.err) { console.log('    ERR', j.err); break; }
    const msg = j.message;
    total = msg['total-results'];
    const items = msg.items || [];
    seen += items.length;
    onItems(items);
    cursor = msg['next-cursor'];
    pages++;
    if (!items.length || seen >= total) break;
    await sleep(400);
  }
  return { total, seen, pages };
}

// ── 主流程 ─────────────────────────────────────────
const only = process.argv.slice(2);
const schoolKeys = only.length ? only : Object.keys(SCHOOLS);

for (const sk of schoolKeys) {
  const school = SCHOOLS[sk];
  const papers = [];
  const log = { school: school.name, school_key: sk, started_at: new Date().toISOString(), jobs: [] };
  console.log(`\n########## ${school.name} (${sk}) ##########`);

  for (const q of school.queries) {
    for (const jn of JOURNALS) {
      const base = `https://api.crossref.org/works?filter=issn:${jn.issn},${YEARS}&query.affiliation=${encodeURIComponent(q)}&select=${SELECT}`;
      let kept = 0, total = 0;
      const r = await pageAll(base, 3, (items) => {
        for (const it of items) {
          const m = matchSchool(it, school);
          if (m) { papers.push(slim(it, jn.key, jn.tier, m)); kept++; }
        }
      });
      total = r.total;
      log.jobs.push({ venue: jn.key, kind: 'journal', queried_total: total, scanned: r.seen, kept });
      console.log(`  [J] ${jn.key.padEnd(9)} total=${String(total).padStart(6)} scanned=${String(r.seen).padStart(5)} kept=${kept}`);
      await sleep(300);
    }
    for (const cf of CONFERENCES) {
      const base = `https://api.crossref.org/works?query.container-title=${encodeURIComponent(cf.q)}&query.affiliation=${encodeURIComponent(q)}&filter=${YEARS}&select=${SELECT}`;
      let kept = 0;
      const r = await pageAll(base, 2, (items) => {
        for (const it of items) {
          const ct = (it['container-title'] || [''])[0] || '';
          if (!new RegExp(cf.q.split(' ').slice(0, 3).join(' '), 'i').test(ct)) continue;
          const m = matchSchool(it, school);
          if (m) { papers.push(slim(it, cf.key, cf.tier, m)); kept++; }
        }
      });
      log.jobs.push({ venue: cf.key, kind: 'conference', queried_total: r.total, scanned: r.seen, kept });
      if (kept) console.log(`  [C] ${cf.key.padEnd(9)} total=${String(r.total).padStart(6)} scanned=${String(r.seen).padStart(5)} kept=${kept}`);
      await sleep(300);
    }
  }

  // 去重（同 DOI 可能被多个 query 命中）
  const byDoi = new Map();
  for (const p of papers) if (p.doi && !byDoi.has(p.doi)) byDoi.set(p.doi, p);
  const uniq = [...byDoi.values()];
  log.finished_at = new Date().toISOString();
  log.papers_raw = papers.length;
  log.papers_unique = uniq.length;
  fs.writeFileSync(path.join(OUT, `${sk}_papers.json`), JSON.stringify(uniq, null, 1));
  fs.writeFileSync(path.join(OUT, `${sk}_harvest_log.json`), JSON.stringify(log, null, 1));
  console.log(`  => ${school.name}: unique papers ${uniq.length} (raw ${papers.length})`);
}
console.log('\nALL DONE');
