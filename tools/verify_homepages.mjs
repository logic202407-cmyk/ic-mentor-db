// verify_homepages.mjs — 抽查新补主页链接的可达性与域名合法性
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';

const OFFICIAL = /\.(edu\.cn|ac\.cn|cas\.cn|github\.io|google\.com|zhihu\.com|researchgate\.net)$/i;
const rows = [];
for (const key of ['sjtu', 'tju', 'cas', 'uestc']) {
  const p = path.join(RAW, key, `roster_${key}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  for (const f of j.faculty) if (f.homepage) rows.push({ key, name: f.name_cn, url: f.homepage });
}
console.log(`四校共有主页的教师 ${rows.length} 人`);

// 1) 域名合法性
const nonOfficial = rows.filter((r) => {
  try { const h = new URL(r.url).hostname; return !OFFICIAL.test(h); } catch { return true; }
});
console.log(`\n非白名单域名（需人工确认）: ${nonOfficial.length}`);
for (const r of nonOfficial.slice(0, 10)) console.log(`  ${r.key} ${r.name}: ${r.url.slice(0, 80)}`);

// 2) 抽样可达性（每校抽 12 个）
console.log('\n=== 抽样可达性检查 ===');
const byKey = {};
for (const r of rows) (byKey[r.key] = byKey[r.key] || []).push(r);
for (const [k, arr] of Object.entries(byKey)) {
  const sample = [];
  const step = Math.max(1, Math.floor(arr.length / 12));
  for (let i = 0; i < arr.length && sample.length < 12; i += step) sample.push(arr[i]);
  let ok = 0, bad = 0;
  const badList = [];
  for (const r of sample) {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 12000);
      const resp = await fetch(r.url, { headers: { 'User-Agent': UA }, signal: ctl.signal, redirect: 'follow' });
      clearTimeout(t);
      if (resp.ok) ok++; else { bad++; badList.push(`${r.name} HTTP ${resp.status}`); }
    } catch (e) { bad++; badList.push(`${r.name} ${e.name}`); }
    await new Promise((r2) => setTimeout(r2, 150));
  }
  console.log(`  ${k}: 抽 ${sample.length} 个 → 可达 ${ok}，异常 ${bad}${badList.length ? ' (' + badList.slice(0, 4).join(', ') + ')' : ''}`);
}

// 3) 重复 URL 检测
const byUrl = new Map();
for (const r of rows) { const u = r.url.replace(/\/$/, ''); if (!byUrl.has(u)) byUrl.set(u, []); byUrl.get(u).push(`${r.key}|${r.name}`); }
const dup = [...byUrl].filter(([, v]) => v.length > 1);
console.log(`\n同一 URL 被多人使用: ${dup.length} 组`);
for (const [u, v] of dup.slice(0, 6)) console.log(`  ${u.slice(0, 70)} -> ${v.join(' / ')}`);
