// diag_adv.mjs — 诊断师徒边为何从 1302 组降到 145 条
import fs from 'node:fs';
const pairs = JSON.parse(fs.readFileSync('data/processed/_net_pair.json', 'utf8'));
const people = JSON.parse(fs.readFileSync('data/processed/_net_people.json', 'utf8'));
const pbk = JSON.parse(fs.readFileSync('data/processed/_net_papers_by_key.json', 'utf8'));
const firstYear = {};
for (const [k, ps] of Object.entries(pbk)) { const ys = ps.map((p) => p.year).filter(Boolean); if (ys.length) firstYear[k] = Math.min(...ys); }

const MIN_ADV = 3, EARLY_WINDOW = 6;
const drop = { n少: 0, 无首年: 0, 早年不足: 0, 跨度大: 0, 通过: 0 };
const examples = { 早年不足: [], 跨度大: [] };
for (const pr of pairs) {
  const [s, t] = pr.k.split('||');
  if (!people[s] || !people[t]) { drop.无首年++; continue; }
  if (pr.n < MIN_ADV) { drop.n少++; continue; }
  const fy = firstYear[s];
  if (!fy) { drop.无首年++; continue; }
  const ys = pr.papers.map((p) => p.year).filter(Boolean).sort();
  const early = ys.filter((y) => y <= fy + EARLY_WINDOW);
  if (early.length < MIN_ADV) {
    drop.早年不足++;
    if (examples.早年不足.length < 10) examples.早年不足.push(`${people[s].name}(${people[s].school.slice(0,8)})←${people[t].name} | 共${pr.n}篇 首年${fy} 年份[${[...new Set(ys)].join(',')}] 早年${early.length}篇`);
    continue;
  }
  if (early[early.length - 1] - early[0] > EARLY_WINDOW) { drop.跨度大++; continue; }
  drop.通过++;
}
console.log('淘汰原因统计:', JSON.stringify(drop, null, 1));
console.log('\n「早年不足」样例:');
for (const e of examples.早年不足) console.log('  ' + e);

// 看 pairRole 的分布：n 的分布
const dist = {};
for (const pr of pairs) { const b = pr.n >= 10 ? '10+' : pr.n >= 5 ? '5-9' : pr.n >= 3 ? '3-4' : pr.n; dist[b] = (dist[b] || 0) + 1; }
console.log('\n一作-末位配对的篇数分布:', JSON.stringify(dist));
