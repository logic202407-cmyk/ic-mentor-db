// contamination_scan.mjs — 逐人计算"论文机构一致率"，找出可能仍有同名混入的人
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');

// 本脚本依赖两个**未入库的中间产物**（可由 tools/ 重跑生成）：
//   data/processed/name_variants.json   ← python tools/prepare_names.py
//   data/processed/enriched_<key>.json  ← node tools/enrich_crossref.mjs
// 全新克隆的仓库里没有这两类文件，此时给出提示而不是抛栈。
const NV = path.join(PROC, 'name_variants.json');
if (!fs.existsSync(NV)) {
  console.log('⚠ 未找到 data/processed/name_variants.json —— 本脚本需要完整的中间产物。');
  console.log('  请先按 docs/维护指南.md 的「全量重建流程」跑完第 1–3 步：');
  console.log('    node tools/clean_rosters.mjs && python tools/prepare_names.py');
  console.log('    node tools/enrich_crossref.mjs && node tools/harvest_pool_match.mjs && node tools/merge_pool.mjs');
  console.log('  若只想核验已入库数据的文档一致性，请改用 node tools/check_doc_numbers.mjs');
  process.exit(0);
}
const variants = JSON.parse(fs.readFileSync(NV, 'utf8'));
const incCache = new Map();
const re = (k) => {
  if (!incCache.has(k)) {
    const m = variants[k];
    incCache.set(k, [new RegExp(m.include, 'i'), m.exclude ? new RegExp(m.exclude, 'i') : null]);
  }
  return incCache.get(k);
};

const suspicious = [];
let total = 0, checkedPapers = 0, okPapers = 0;
for (const key of Object.keys(variants)) {
  const p = path.join(PROC, `enriched_${key}.json`);
  if (!fs.existsSync(p)) continue;
  const e = JSON.parse(fs.readFileSync(p, 'utf8'));
  const [inc, exc] = re(key);
  for (const person of e.people) {
    total++;
    let ok = 0, bad = 0, noaff = 0;
    const badSample = [];
    for (const pap of person.papers || []) {
      const me = (pap.coauthors || []).find((c) => c.order === pap.my_order) || {};
      const aff = me.aff || '';
      if (!aff) { noaff++; continue; }
      if (inc.test(aff) && !(exc && exc.test(aff))) ok++;
      else { bad++; if (badSample.length < 2) badSample.push(`${pap.year} ${(pap.venue || '').slice(0, 26)} | ${aff.slice(0, 45)}`); }
      checkedPapers++;
      if (inc.test(aff) && !(exc && exc.test(aff))) okPapers++;
    }
    const withAff = ok + bad;
    if (withAff >= 5 && bad / withAff >= 0.3) {
      suspicious.push({ key, name: person.name_cn, title: person.title, ok, bad, noaff, rate: bad / withAff, sample: badSample });
    }
  }
}
console.log(`扫描 ${total} 人 / ${checkedPapers} 条论文记录；机构一致 ${okPapers} 条（${(okPapers / checkedPapers * 100).toFixed(1)}%）`);
suspicious.sort((a, b) => b.bad - a.bad);
console.log(`\n机构一致率 <70% 且论文 ≥5 条的人: ${suspicious.length} 人`);
for (const s of suspicious.slice(0, 25)) {
  console.log(`  ${s.key}|${s.name} (${s.title || '—'}) 符合 ${s.ok} / 不符 ${s.bad} (${(s.rate * 100).toFixed(0)}%)`);
  for (const x of s.sample) console.log(`      ${x}`);
}
