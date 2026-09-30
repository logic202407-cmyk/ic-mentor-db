// assess_filter.mjs — 量化"有原始论文但被 IC 过滤"的规模与被过滤的 venue
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
// name_variants.json 是未入库的中间产物（python tools/prepare_names.py 生成）。
// 全新克隆里没有它时，退化为只按 school 名统计，不中断。
const NV = path.join(PROC, 'name_variants.json');
const variants = fs.existsSync(NV) ? JSON.parse(fs.readFileSync(NV, 'utf8')) : null;
if (!variants) console.log('提示：未找到 name_variants.json，本次仅按 school 字段统计（跑 python tools/prepare_names.py 可生成）');
const schoolOf = {};
if (variants) for (const [k, m] of Object.entries(variants)) schoolOf[m.school] = k;

const zero = ranked.filter((d) => (d.n_ic_papers || 0) === 0);
let trulyZero = 0, filteredOut = 0;
const venues = new Map();
for (const d of zero) {
  const sk = schoolOf[d.school];
  if (!sk) continue;
  const e = JSON.parse(fs.readFileSync(path.join(PROC, `enriched_${sk}.json`), 'utf8'));
  const p = e.people.find((x) => x.name_cn === d.name_cn);
  const n = (p?.papers || []).length;
  if (!n) { trulyZero++; continue; }
  filteredOut++;
  for (const pap of p.papers) venues.set((pap.venue || '(无 venue)').slice(0, 52), (venues.get((pap.venue || '(无 venue)').slice(0, 52)) || 0) + 1);
}
console.log(`零 IC 记录者 ${zero.length} 人：`);
console.log(`  真正没有任何原始论文: ${trulyZero} 人`);
console.log(`  有原始论文但被过滤  : ${filteredOut} 人`);
console.log('\n被过滤论文的 venue Top 25:');
for (const [v, n] of [...venues].sort((a, b) => b[1] - a[1]).slice(0, 25)) console.log(`  ${String(n).padStart(4)}  ${v}`);

// 全库范围内，被过滤的 venue 分布（这些人只是 0 篇的那批）
console.log('\n=== 全库被 IC 过滤掉的论文 venue Top 25（含已有记录者的未计入论文）===');
const allVenues = new Map();
let totalPapers = 0, countedPapers = 0;
for (const d of ranked) {
  const sk = schoolOf[d.school];
  if (!sk) continue;
  const e = JSON.parse(fs.readFileSync(path.join(PROC, `enriched_${sk}.json`), 'utf8'));
  const p = e.people.find((x) => x.name_cn === d.name_cn);
  if (!p) continue;
  const countedDois = new Set((d.papers || []).map((x) => x.doi));
  for (const pap of p.papers || []) {
    totalPapers++;
    if (countedDois.has(pap.doi)) { countedPapers++; continue; }
    allVenues.set((pap.venue || '(无 venue)').slice(0, 52), (allVenues.get((pap.venue || '(无 venue)').slice(0, 52)) || 0) + 1);
  }
}
console.log(`全库原始论文 ${totalPapers} 篇，其中计入 IC ${countedPapers} 篇（${(countedPapers / totalPapers * 100).toFixed(0)}%）`);
for (const [v, n] of [...allVenues].sort((a, b) => b[1] - a[1]).slice(0, 25)) console.log(`  ${String(n).padStart(5)}  ${v}`);
