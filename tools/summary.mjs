// summary.mjs — 汇总最终数字，用于更新 README
import fs from 'node:fs';
const P = 'E:\\ytm\\mentor-db\\data\\processed\\';
const ranked = JSON.parse(fs.readFileSync(P + 'mentor_ranked.json', 'utf8'));
const curated = JSON.parse(fs.readFileSync(P + 'curated.json', 'utf8'));
const labs = JSON.parse(fs.readFileSync(P + 'lab_pages.json', 'utf8'));

const withPapers = ranked.filter((d) => d.n_ic_papers > 0).length;
const S = ranked.reduce((a, b) => a + b.S, 0);
const A = ranked.reduce((a, b) => a + b.A, 0);
const tier = {};
for (const d of curated) tier[d.tier] = (tier[d.tier] || 0) + 1;
console.log('全库人数:', ranked.length);
console.log('有论文记录:', withPapers, '| 零记录:', ranked.length - withPapers);
console.log('S 合计:', S, '| A 合计:', A);
console.log('有 S≥1 人数:', ranked.filter((d) => d.S > 0).length, '| S≥5:', ranked.filter((d) => d.S >= 5).length);
console.log('推荐集:', curated.length, '| 聚焦:', curated.filter((d) => d.scope === 'focus').length, '| 在招补充:', curated.filter((d) => d.scope === 'recruiting').length);
console.log('推荐集梯队:', JSON.stringify(tier));
console.log('主页抓取:', labs.length, '| 成功:', labs.filter((l) => String(l.status).startsWith('ok')).length);
console.log('明确在招:', curated.filter((d) => d.recruit_signal_count > 0).length);
console.log('识别到课题组名:', curated.filter((d) => (d.lab_names || []).length).length);
console.log('疑似漏检:', ranked.filter((d) => d.recall_risk === 'yes').length);
const dirs = {};
for (const d of ranked) dirs[d.primary_direction] = (dirs[d.primary_direction] || 0) + 1;
console.log('主方向分布:', JSON.stringify(dirs));
