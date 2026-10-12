// cim_final.mjs — 存算一体「深耕者」最终榜单（严格口径 + 证据）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const people = JSON.parse(fs.readFileSync(path.join(REPO, 'data', 'processed', 'cim_ranking.json'), 'utf8'));

// 深耕的判定标准（全部为可核实的数据条件）
const DEEP = (p) => p.nCIM >= 8 && p.distinctYears >= 4 && (p.sTier + p.aTier) >= 3 && p.recent >= 2;
const SOLID = (p) => p.nCIM >= 4 && p.distinctYears >= 3 && (p.sTier + p.aTier) >= 1;

const deep = people.filter(DEEP);
const solid = people.filter((p) => !DEEP(p) && SOLID(p) && p.nCIM >= 5);

console.log(`符合「深耕」硬指标（CIM≥8篇 且 跨≥4个年度 且 S/A≥3篇 且 近2年≥2篇）：${deep.length} 人\n`);
console.log('深  姓名      单位              CIM/总   占比  S  A 通讯 一作 跨年 近2年');
console.log('─'.repeat(88));
for (const p of deep.sort((a, b) => b.depth - a.depth)) {
  console.log(
    `${String(p.depth).padStart(3)}  ${p.name.replace(/（.*?）/g, '').padEnd(9)} ` +
    `${p.school.replace('中国科学院', '中科院').slice(0, 14).padEnd(15)} ` +
    `${String(p.nCIM).padStart(3)}/${String(p.nAll).padStart(3)} ${(p.share * 100).toFixed(0).padStart(4)}% ` +
    `${String(p.sTier).padStart(2)} ${String(p.aTier).padStart(2)} ${String(p.lastA).padStart(4)} ${String(p.firstA).padStart(4)} ` +
    `${String(p.distinctYears).padStart(4)} ${String(p.recent).padStart(5)}`
  );
}

console.log(`\n\n次级（CIM≥5篇 且 跨≥3年 且 有S/A）：${solid.length} 人`);
for (const p of solid.sort((a, b) => b.depth - a.depth).slice(0, 30)) {
  console.log(
    `${String(p.depth).padStart(3)}  ${p.name.replace(/（.*?）/g, '').padEnd(9)} ` +
    `${p.school.replace('中国科学院', '中科院').slice(0, 14).padEnd(15)} ` +
    `${String(p.nCIM).padStart(3)}/${String(p.nAll).padStart(3)} ${(p.share * 100).toFixed(0).padStart(4)}% ` +
    `${String(p.sTier).padStart(2)} ${String(p.aTier).padStart(2)} ${String(p.lastA).padStart(4)} ${String(p.recent).padStart(5)}`
  );
}

// 按学校汇总（深耕层）
console.log('\n\n深耕层按单位分布：');
const bySchool = {};
for (const p of deep) bySchool[p.school] = (bySchool[p.school] || 0) + 1;
for (const [s, c] of Object.entries(bySchool).sort((a, b) => b[1] - a[1])) console.log(`  ${String(c).padStart(2)} 人  ${s}`);

// 导出
fs.writeFileSync(path.join(REPO, 'data', 'processed', 'cim_deep.json'),
  JSON.stringify({ deep: deep.sort((a, b) => b.depth - a.depth), solid: solid.sort((a, b) => b.depth - a.depth) }, null, 1), 'utf8');
console.log('\n已导出 data/processed/cim_deep.json');
