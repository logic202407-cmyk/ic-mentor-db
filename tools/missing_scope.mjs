// missing_scope.mjs — 盘点"找不到的"三类口径，供决定删除范围
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const curated = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));

const noPaper = (d) => (d.n_ic_papers || 0) === 0;
const noHome = (d) => !d.homepage;
const noTitle = (d) => !d.title;

const A = ranked.filter((d) => noPaper(d) && noHome(d));
const B = ranked.filter(noPaper);
const C = ranked.filter(noHome);

console.log(`全库 ${ranked.length} 人\n`);
console.log(`口径 A：既无论文、又无主页        ${A.length} 人  ← 完全没有可核实线索`);
console.log(`口径 B：无论文（可能有主页）      ${B.length} 人`);
console.log(`口径 C：无主页（可能有论文）      ${C.length} 人`);
console.log(`口径 D：既无论文、又无主页、又无职称  ${ranked.filter((d) => noPaper(d) && noHome(d) && noTitle(d)).length} 人`);

console.log('\n=== 口径 A 名单（按学校）===');
const bySchool = {};
for (const d of A) (bySchool[d.school] = bySchool[d.school] || []).push(d);
for (const [s, arr] of Object.entries(bySchool).sort((a, b) => b[1].length - a[1].length)) {
  console.log(`\n  ${s}（${arr.length} 人）`);
  console.log('    ' + arr.map((d) => `${d.name_cn}${d.title ? '(' + d.title + ')' : ''}`).join('、'));
}

console.log('\n=== 口径 A 的人是否有人进了推荐集？ ===');
const inCurated = A.filter((a) => curated.some((c) => c.school === a.school && c.name === a.name_cn));
console.log(`  ${inCurated.length} 人${inCurated.length ? ': ' + inCurated.map((d) => d.name_cn).join('、') : ''}`);

console.log('\n=== 口径 B 中「有主页但无论文」的 ${B.filter((d) => d.homepage).length} 人（这些人有招生价值）===');
const bWithHome = B.filter((d) => d.homepage);
console.log('  ' + bWithHome.slice(0, 30).map((d) => `${d.name_cn}(${d.school.slice(0, 4)})`).join('、') + (bWithHome.length > 30 ? ' …' : ''));

console.log('\n=== 口径 C 中「有论文但无主页」的 ' + C.filter((d) => !noPaper(d)).length + ' 人（论文证据充分，只是缺链接）===');
const cWithPaper = C.filter((d) => !noPaper(d));
console.log('  ' + cWithPaper.slice(0, 20).map((d) => `${d.name_cn}(${d.n_ic_papers}篇)`).join('、') + (cWithPaper.length > 20 ? ' …' : ''));
