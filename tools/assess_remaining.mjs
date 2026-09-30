// assess_remaining.mjs — 盘点剩余可补的缺口
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const labs = fs.existsSync(path.join(PROC, 'lab_pages.json')) ? JSON.parse(fs.readFileSync(path.join(PROC, 'lab_pages.json'), 'utf8')) : [];
const gotLab = new Set(labs.map((l) => `${l.school}|${l.name}`));

console.log('=== 1. 主页抓取缺口 ===');
const withHp = ranked.filter((d) => d.homepage);
console.log(`有主页的导师: ${withHp.length} / ${ranked.length}`);
const notFetched = withHp.filter((d) => !gotLab.has(`${d.school}|${d.name_cn}`));
console.log(`有主页但未抓取: ${notFetched.length} 人`);
const byPaper = {};
for (const d of notFetched) { const b = d.n_ic_papers === 0 ? '0篇' : d.n_ic_papers <= 2 ? '1-2篇' : '3+篇'; byPaper[b] = (byPaper[b] || 0) + 1; }
console.log('  按论文数分布:', JSON.stringify(byPaper));
console.log('  样例:', notFetched.slice(0, 6).map((d) => `${d.name_cn}(${d.n_ic_papers}篇)`).join('、'));

console.log('\n=== 2. 名录字段缺失 ===');
for (const key of fs.readdirSync(RAW)) {
  const p = path.join(RAW, key, `roster_${key}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  const noTitle = j.faculty.filter((f) => !f.title).length;
  const noKw = j.faculty.filter((f) => !(f.research_keywords || []).length).length;
  const noHp = j.faculty.filter((f) => !f.homepage).length;
  if (noTitle || noKw || noHp) console.log(`  ${j.school}: 无职称 ${noTitle} | 无关键词 ${noKw} | 无主页 ${noHp}（共 ${j.faculty.length}）`);
}

console.log('\n=== 3. 疑似漏检（正高但 ≤2 篇）===');
const lowRecall = ranked.filter((d) => (d.n_ic_papers || 0) <= 2 && /教授|研究员|院士|杰青|讲席|特聘/.test(d.title || ''));
console.log(`共 ${lowRecall.length} 人`);
const byDir = {};
for (const d of lowRecall) byDir[d.primary_direction] = (byDir[d.primary_direction] || 0) + 1;
console.log('  方向分布:', JSON.stringify(byDir));
console.log('  样例:', lowRecall.slice(0, 8).map((d) => `${d.name_cn}(${d.n_ic_papers})`).join('、'));

console.log('\n=== 4. 论文 venue 无名的 ===');
let noVenue = 0;
for (const d of ranked) for (const p of d.papers || []) if (!p.venue) noVenue++;
console.log(`venue 为空的论文: ${noVenue} 篇`);

console.log('\n=== 5. 课题组合并情况 ===');
const curated = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));
console.log(`推荐集 ${curated.length} 人 | 识别到课题组名 ${curated.filter((d) => (d.lab_names || []).length).length} | 有招生原话 ${curated.filter((d) => d.recruit_signal_count > 0).length}`);
