// harvest_pool_match.mjs — 按 IC 核心期刊 ISSN 抓取全量论文池，并反向匹配名录人名
//
// 思路：此前"按人名检索"对常见中文名会失败（同名者挤占结果、相关性排序把本人排到 200 条之外）。
// 本脚本反转方向：把 IC 核心期刊 2008 年至今的全部论文拉下来（约 19 万篇），
// 再逐个作者与名录比对（姓名精确匹配 + 本人机构校验），从而绕开相关性排序。
//
// 用法: node harvest_pool_match.mjs [页码上限，默认不限]
// 输出: data/raw/crossref/pool_matches.json  ->  { "school|name": [paper, ...] }
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const OUTDIR = path.join(REPO, 'data', 'raw', 'crossref');
fs.mkdirSync(OUTDIR, { recursive: true });

const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const MAILTO = 'ic-mentor-db@users.noreply.github.com';
const SELECT = 'DOI,title,author,container-title,short-container-title,published,type,is-referenced-by-count,ISSN';
const PAGE_MAX = Number(process.argv[2] || 0) || Infinity;
const CONC = Number(process.env.CONC || 5);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── IC 核心期刊 ISSN（S/A/B 级期刊部分）──
const JOURNALS = [
  ['0018-9200', 'IEEE Journal of Solid-State Circuits'],
  ['1549-8328', 'IEEE Transactions on Circuits and Systems I'],
  ['1549-7747', 'IEEE Transactions on Circuits and Systems II'],
  ['1063-8210', 'IEEE Transactions on Very Large Scale Integration Systems'],
  ['0278-0070', 'IEEE Transactions on Computer-Aided Design'],
  ['0018-9383', 'IEEE Transactions on Electron Devices'],
  ['0741-3106', 'IEEE Electron Device Letters'],
  ['0018-9480', 'IEEE Transactions on Microwave Theory and Techniques'],
  ['0885-8993', 'IEEE Transactions on Power Electronics'],
  ['0018-9340', 'IEEE Transactions on Computers'],
  ['2573-9603', 'IEEE Solid-State Circuits Letters'],
  ['0733-8724', 'Journal of Lightwave Technology'],
  ['1932-4545', 'IEEE Transactions on Biomedical Circuits and Systems'],
  ['1531-1309', 'IEEE Microwave and Wireless Components Letters'],
  ['2156-3357', 'IEEE Journal on Emerging and Selected Topics in Circuits and Systems'],
  ['2644-1349', 'IEEE Open Journal of the Solid-State Circuits Society'],
  ['1041-1135', 'IEEE Photonics Technology Letters'],
  ['0018-926X', 'IEEE Transactions on Antennas and Propagation'],
  ['2520-1131', 'Nature Electronics'],
  ['1674-4926', 'Journal of Semiconductors'],
  ['0038-1101', 'Solid-State Electronics'],
  ['0026-2714', 'Microelectronics Reliability'],
  ['0167-9317', 'Microelectronic Engineering'],
  ['0003-6951', 'Applied Physics Letters'],
  // ── 第二批：器件/材料、光电、传感、量子、CS/EDA、生物电子 ──
  ['0021-8979', 'Journal of Applied Physics'],
  ['0935-9648', 'Advanced Materials'],
  ['1616-301X', 'Advanced Functional Materials'],
  ['1936-0851', 'ACS Nano'],
  ['1530-6984', 'Nano Letters'],
  ['1613-6810', 'Small'],
  ['1944-8244', 'ACS Applied Materials & Interfaces'],
  ['2041-1723', 'Nature Communications'],
  ['2375-2548', 'Science Advances'],
  ['2053-1583', '2D Materials'],
  ['1094-4087', 'Optics Express'],
  ['0146-9592', 'Optics Letters'],
  ['2327-9125', 'Photonics Research'],
  ['1863-8880', 'Laser & Photonics Reviews'],
  ['2330-4022', 'ACS Photonics'],
  ['2047-7538', 'Light: Science & Applications'],
  ['1530-437X', 'IEEE Sensors Journal'],
  ['0924-4247', 'Sensors and Actuators A'],
  ['1473-0197', 'Lab on a Chip'],
  ['2055-7434', 'Microsystems & Nanoengineering'],
  ['1057-7157', 'Journal of Microelectromechanical Systems'],
  ['0031-9007', 'Physical Review Letters'],
  ['2331-7019', 'Physical Review Applied'],
  ['0953-2048', 'Superconductor Science and Technology'],
  ['2056-6387', 'npj Quantum Information'],
  ['2058-9565', 'Quantum Science and Technology'],
  ['2156-342X', 'IEEE Transactions on Terahertz Science and Technology'],
  ['1536-1225', 'IEEE Antennas and Wireless Propagation Letters'],
  ['2168-6777', 'IEEE Journal of Emerging and Selected Topics in Power Electronics'],
  ['0278-0046', 'IEEE Transactions on Industrial Electronics'],
  ['1084-4309', 'ACM Transactions on Design Automation of Electronic Systems'],
  ['0272-1732', 'IEEE Micro'],
  ['0018-9294', 'IEEE Transactions on Biomedical Engineering'],
  ['0956-5663', 'Biosensors and Bioelectronics'],
];

// ── 构建姓名索引 ──
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const SCHOOL_META = {};
const compact = (s) => (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');
function compactSet(vs) {
  const set = new Set();
  for (const v of vs) {
    const c = compact(v);
    if (!c) continue;
    set.add(c);
    if (c.includes('v')) { set.add(c.replace(/v/g, 'u')); set.add(c.replace(/v/g, 'yu')); }
    if (c.includes('u')) set.add(c.replace(/u/g, 'v'));
  }
  return set;
}
const nameIndex = new Map();   // compactName -> [ {key, inc, exc} ]
let peopleCount = 0;
for (const [key, meta] of Object.entries(variants)) {
  SCHOOL_META[key] = { include: meta.include, exclude: meta.exclude };
  for (const p of meta.people) {
    peopleCount++;
    const set = compactSet(p.match_variants || p.variants);
    for (const c of set) {
      if (!nameIndex.has(c)) nameIndex.set(c, []);
      nameIndex.get(c).push({ key, name: p.name_cn });
    }
  }
}
// 姓名稀有度：某个 compact 形式在全库由多少人共享。
// 独享（rarity=1）时该拼写本身已足够区分，可放宽机构校验（用于收录其在前单位发表的论文）；
// 共享时（如 "xiao wang" 有 13 人）必须严格校验机构。
const rarity = new Map();
for (const [c, arr] of nameIndex) rarity.set(c, new Set(arr.map((h) => `${h.key}|${h.name}`)).size);
const uniqueKeys = [...rarity.values()].filter((n) => n === 1).length;
console.log(`姓名索引 ${nameIndex.size} 个键，其中独享 ${uniqueKeys}（${(uniqueKeys / nameIndex.size * 100).toFixed(0)}%）`);
console.log(`名录 ${peopleCount} 人，姓名索引 ${nameIndex.size} 个键`);

const decodeEnt = (s) => String(s || '')
  .replace(/&#x([0-9a-f]+);/gi, (_, h) => { try { return String.fromCodePoint(parseInt(h, 16)); } catch { return ' '; } })
  .replace(/&#(\d+);/g, (_, d) => { try { return String.fromCodePoint(Number(d)); } catch { return ' '; } })
  .replace(/&amp;/g, '&').replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ');
const affText = (a) => (a.affiliation || []).map((x) => decodeEnt(x.name || '')).join(' | ');
const venueOf = (it) => ((it['container-title'] || [''])[0] || (it['short-container-title'] || [''])[0] || '').replace(/\s+/g, ' ').trim();

async function cr(url, tries = 4) {
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

const matches = new Map();   // key -> Map(doi -> paper)
let scanned = 0, hitPapers = 0;
const t0 = Date.now();

async function harvestJournal(issn, label) {
  let cursor = '*', page = 0, n = 0;
  const incCache = new Map();
  const getInc = (key, src) => {
    if (!incCache.has(key)) {
      // 注意字段名是 include / exclude（曾因写成 src.inc/src.exc 导致 new RegExp(undefined) 匹配一切）
      incCache.set(key, [new RegExp(src.include, 'i'), src.exclude ? new RegExp(src.exclude, 'i') : null]);
    }
    return incCache.get(key);
  };
  while (page < PAGE_MAX) {
    const url = `https://api.crossref.org/works?filter=issn:${issn},from-pub-date:2008-01-01` +
      `&rows=1000&cursor=${encodeURIComponent(cursor)}&select=${SELECT}&mailto=${MAILTO}`;
    const j = await cr(url);
    if (j.err) { console.log(`  [${label}] 第 ${page + 1} 页失败: ${j.err}`); break; }
    const items = j.message.items || [];
    if (!items.length) break;
    for (const it of items) {
      scanned++;
      if (!it.DOI) continue;
      const authors = it.author || [];
      if (!authors.length) continue;
      const venue = venueOf(it);
      for (let i = 0; i < authors.length; i++) {
        const a = authors[i];
        const full = [a.given, a.family].filter(Boolean).join(' ') || a.name || '';
        const cname = compact(full);
        const hits = nameIndex.get(cname);
        if (!hits) continue;
        const aff = affText(a);
        // 必须有机构证据：宁可漏收（本库之外还有其他来源兜底），不可错收
        if (!aff) continue;
        for (const h of hits) {
          const [inc, exc] = getInc(h.key, SCHOOL_META[h.key]);
          if (!inc.test(aff)) continue;
          if (exc && exc.test(aff)) continue;
          const key = `${h.key}|${h.name}`;
          if (!matches.has(key)) matches.set(key, new Map());
          const m = matches.get(key);
          if (m.has(it.DOI)) continue;
          m.set(it.DOI, {
            doi: it.DOI,
            title: (it.title || [''])[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
            year: it.published?.['date-parts']?.[0]?.[0] ?? null,
            venue,
            type: it.type,
            cited: it['is-referenced-by-count'] ?? 0,
            my_order: i + 1,
            n_authors: authors.length,
            coauthors: authors.map((x, k) => ({
              name: [x.given, x.family].filter(Boolean).join(' ') || x.name || '', order: k + 1,
              aff: affText(x).slice(0, 400),
            })),
            _src: `pool:${issn}`,
          });
          hitPapers++;
        }
      }
    }
    n += items.length;
    cursor = j.message['next-cursor'];
    page++;
    if (!cursor) break;
    await sleep(200);
  }
  return n;
}

async function worker(queue) {
  while (queue.length) {
    const [issn, label] = queue.shift();
    const n = await harvestJournal(issn, label);
    console.log(`  ${label.slice(0, 46).padEnd(46)} ${String(n).padStart(6)} 篇 | 命中累计 ${hitPapers} | ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
}

const queue = [...JOURNALS];
await Promise.all(Array.from({ length: CONC }, () => worker(queue)));

// ── 落盘 ──
const out = {};
for (const [k, m] of matches) out[k] = [...m.values()].sort((a, b) => (b.year || 0) - (a.year || 0));
fs.writeFileSync(path.join(OUTDIR, 'pool_matches.json'), JSON.stringify(out, null, 1));

console.log(`\n扫描 ${scanned.toLocaleString()} 篇论文，命中 ${hitPapers} 条作者-论文记录`);
console.log(`覆盖 ${Object.keys(out).length} 位导师`);
const dist = {};
for (const v of Object.values(out)) { const b = v.length >= 10 ? '10+' : v.length >= 5 ? '5-9' : v.length >= 3 ? '3-4' : v.length >= 1 ? '1-2' : '0'; dist[b] = (dist[b] || 0) + 1; }
console.log('每人命中篇数分布:', JSON.stringify(dist));
console.log(`用时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
