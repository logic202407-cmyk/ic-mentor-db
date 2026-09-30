// dbstats.mjs — 数据库质量体检
import fs from 'node:fs';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// mentor_db.json 是未入库的中间产物（跑完 score.mjs 后生成）。
// 全新克隆里没有它时，改用已入库的 mentor_ranked.json，保持脚本可用。
const DB_PATH = path.join(REPO, 'data', 'processed', 'mentor_db.json');
const FALLBACK = path.join(REPO, 'data', 'processed', 'mentor_ranked.json');
if (!fs.existsSync(DB_PATH) && !fs.existsSync(FALLBACK)) {
  console.log('⚠ 未找到 data/processed/mentor_db.json 或 mentor_ranked.json，无法体检。');
  console.log('  请先按 docs/维护指南.md 跑完数据生产流程，或从仓库获取已入库的 mentor_ranked.json。');
  process.exit(0);
}
const useFallback = !fs.existsSync(DB_PATH);
if (useFallback) console.log('提示：未找到 mentor_db.json，改用已入库的 mentor_ranked.json');
const db = JSON.parse(fs.readFileSync(useFallback ? FALLBACK : DB_PATH, 'utf8'));
const buckets = { 0: 0, '1-2': 0, '3-9': 0, '10-29': 0, '30+': 0 };
for (const r of db) {
  const n = r.n_ic_papers;
  if (n === 0) buckets[0]++; else if (n < 3) buckets['1-2']++; else if (n < 10) buckets['3-9']++; else if (n < 30) buckets['10-29']++; else buckets['30+']++;
}
console.log('IC 论文数分布:', JSON.stringify(buckets));
console.log('有 S 级产出人数:', db.filter((r) => r.S > 0).length);
console.log('有 A 级产出人数:', db.filter((r) => r.A > 0).length);
console.log('S>=5 人数:', db.filter((r) => r.S >= 5).length);
console.log('\n验证重点人物:');
for (const n of ['曾晓洋', '曾璇', '刘明', '周鹏', '程林', '闫娜', '杜力', '毛军发', '吴汉明', '卓成', '唐仙']) {
  const r = db.find((x) => x.name_cn === n);
  if (r) console.log(`  ${n}: ${r.school} ${r.title} | S${r.S} A${r.A} 论文${r.n_ic_papers} 引用${r.citations} | ${r.top_venues.map((v) => v[0] + '×' + v[1]).join(', ').slice(0, 70)}`);
  else console.log(`  ${n}: 未找到`);
}
console.log('\n方向分布:');
const d = {};
for (const r of db) d[r.primary_direction] = (d[r.primary_direction] || 0) + 1;
console.log(JSON.stringify(d));
