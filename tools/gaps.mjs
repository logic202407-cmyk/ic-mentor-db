// gaps.mjs — 统计"未完善"的具体缺口
import fs from 'node:fs';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(`${PROC}\\mentor_ranked.json`, 'utf8'));
const curated = JSON.parse(fs.readFileSync(`${PROC}\\curated.json`, 'utf8'));
const labs = JSON.parse(fs.readFileSync(`${PROC}\\lab_pages.json`, 'utf8'));

const n = ranked.length;
const q = (f) => ranked.filter(f).length;
console.log('=== 全库 2114 人缺口统计 ===');
console.log('疑似漏检（正高但≤2篇）:', q((d) => d.recall_risk === 'yes'));
console.log('无任何论文记录:', q((d) => (d.n_ic_papers || 0) === 0));
console.log('论文<3:', q((d) => (d.n_ic_papers || 0) < 3));
console.log('低置信:', q((d) => d.confidence === 'low'));
console.log('无研究方向关键词:', q((d) => !(d.research_keywords || []).length));
console.log('关键词<3个:', q((d) => (d.research_keywords || []).length < 3));
console.log('无院系字段:', q((d) => !d.department));
console.log('无主页:', q((d) => !d.homepage));
console.log('有邮箱:', q((d) => d.email));

console.log('\n=== 主页抓取情况（推荐集候选 643 → 有主页 522）===');
const st = {};
for (const l of labs) st[l.status] = (st[l.status] || 0) + 1;
console.log('抓取状态分布:', JSON.stringify(st));
const failed = labs.filter((l) => !String(l.status).startsWith('ok'));
console.log('抓取失败/无文本:', failed.length);
console.log('样例:', failed.slice(0, 8).map((x) => `${x.name}(${x.school.slice(0, 4)}):${x.status}`).join(', '));

console.log('\n=== 推荐集 355 人 ===');
console.log('无招生信号:', curated.filter((d) => !d.recruit_signal_count).length);
console.log('无课题组名:', curated.filter((d) => !(d.lab_names || []).length).length);
console.log('无邮箱:', curated.filter((d) => !d.email).length);

console.log('\n=== 疑似漏检者样例（应重点补救）===');
for (const d of ranked.filter((x) => x.recall_risk === 'yes').slice(0, 15)) {
  console.log(`  ${d.name_cn}(${d.school.slice(0, 6)}) ${d.title} | 论文${d.n_ic_papers} | 关键词: ${(d.research_keywords || []).join('、').slice(0, 40)}`);
}
