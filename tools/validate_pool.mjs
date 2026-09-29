// validate_pool.mjs — 产出侧校验：逐条重核"匹配到的作者机构"是否真的属于该校
// 不依赖采集过程是否正确，只信任最终数据本身。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const poolPath = path.join(REPO, 'data', 'raw', 'crossref', 'pool_matches.json');
const pool = JSON.parse(fs.readFileSync(poolPath, 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'processed', 'name_variants.json'), 'utf8'));

const decodeEnt = (s) => String(s || '')
  .replace(/&#x([0-9a-f]+);/gi, (_, h) => { try { return String.fromCodePoint(parseInt(h, 16)); } catch { return ' '; } })
  .replace(/&#(\d+);/g, (_, d) => { try { return String.fromCodePoint(Number(d)); } catch { return ' '; } })
  .replace(/&amp;/g, '&').replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ');

const CACHE = new Map();
function re(key) {
  if (!CACHE.has(key)) {
    const m = variants[key];
    CACHE.set(key, [new RegExp(m.include, 'i'), m.exclude ? new RegExp(m.exclude, 'i') : null]);
  }
  return CACHE.get(key);
}

// 姓名独享集合（某 compact 形式在全库只对应一个人 → 拼写本身已足够区分）
const compact = (s) => (s || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter((t) => t.length > 1).join('');
const ownerOf = new Map();
for (const [sk, m] of Object.entries(variants)) {
  for (const p of m.people) {
    for (const v of (p.match_variants || p.variants)) {
      const c = compact(v);
      if (!c) continue;
      if (!ownerOf.has(c)) ownerOf.set(c, new Set());
      ownerOf.get(c).add(`${sk}|${p.name_cn}`);
    }
  }
}
const rare = new Set([...ownerOf].filter(([, s]) => s.size === 1).map(([c]) => c));

const clean = {};
let kept = 0, dropped = 0;
const dropByKey = {};
for (const [k, list] of Object.entries(pool)) {
  const [schoolKey, name] = k.split('|');
  if (!variants[schoolKey]) { dropped += list.length; continue; }
  const [inc, exc] = re(schoolKey);
  const ok = [];
  for (const p of list) {
    const me = (p.coauthors || []).find((c) => c.order === p.my_order);
    const aff = decodeEnt(me?.aff || '');
    // 与采集端同规则：机构命中即收；无机构信息时，仅当姓名在本库中独享才收
    if (!aff) { dropped++; dropByKey[k] = (dropByKey[k] || 0) + 1; continue; }
    if (!inc.test(aff) || (exc && exc.test(aff))) { dropped++; dropByKey[k] = (dropByKey[k] || 0) + 1; continue; }
    ok.push(p);
    kept++;
  }
  if (ok.length) clean[k] = ok;
}

console.log(`校验前: ${Object.keys(pool).length} 人 / ${kept + dropped} 条记录`);
console.log(`校验后: ${Object.keys(clean).length} 人 / ${kept} 条记录（剔除 ${dropped} 条，${(dropped / (kept + dropped) * 100).toFixed(1)}%）`);
const worst = Object.entries(dropByKey).sort((a, b) => b[1] - a[1]).slice(0, 12);
console.log('\n被剔除最多的条目:');
for (const [k, v] of worst) console.log(`  ${k}: 剔除 ${v} / 原 ${pool[k].length}`);

const dist = {};
for (const v of Object.values(clean)) { const b = v.length >= 10 ? '10+' : v.length >= 5 ? '5-9' : v.length >= 3 ? '3-4' : '1-2'; dist[b] = (dist[b] || 0) + 1; }
console.log('\n校验后每人篇数分布:', JSON.stringify(dist));

fs.writeFileSync(path.join(REPO, 'data', 'raw', 'crossref', 'pool_matches_clean.json'), JSON.stringify(clean, null, 1));
console.log('\n已写出 pool_matches_clean.json');
