// check_doc_numbers.mjs — 校验文档中出现的统计数字是否与实际数据一致
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const curated = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));
const labs = JSON.parse(fs.readFileSync(path.join(PROC, 'lab_pages.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

const FACT = {
  全库人数: ranked.length,
  校单位数: new Set(ranked.map((d) => d.school)).size,
  有论文人数: ranked.filter((d) => d.n_ic_papers > 0).length,
  零记录人数: ranked.filter((d) => d.n_ic_papers === 0).length,
  S合计: ranked.reduce((a, b) => a + b.S, 0),
  A合计: ranked.reduce((a, b) => a + b.A, 0),
  有S人数: ranked.filter((d) => d.S > 0).length,
  推荐集: curated.length,
  在招: curated.filter((d) => d.recruit_signal_count > 0).length,
  有主页人数: ranked.filter((d) => d.homepage).length,
  抓取主页人数: labs.length,
};
console.log('=== 实际数据 ===');
for (const [k, v] of Object.entries(FACT)) console.log(`  ${k.padEnd(12)} ${v}`);
console.log(`  主页覆盖率   ${(FACT.有主页人数 / FACT.全库人数 * 100).toFixed(1)}%`);
console.log(`  论文覆盖率   ${(FACT.有论文人数 / FACT.全库人数 * 100).toFixed(1)}%`);

// 文档里"声称"的关键数字
const CLAIM = [
  ['README.md', /\*\*(\d+) 人\*\*（(\d+) 校\/单位）/, ['全库人数', '校单位数']],
  ['README.md', /检索到可核实论文 \| \*\*(\d+) 人（([\d.]+)%）\*\*/, ['有论文人数', null]],
  ['README.md', /S 级）合计 \| \*\*(\d+) 篇\*\*（(\d+) 位导师有 S 级产出）/, ['S合计', '有S人数']],
  ['README.md', /A 级）合计 \| \*\*(\d+) 篇\*\*/, ['A合计']],
  ['README.md', /主页明确写了在招\*\* \| \*\*(\d+) 位/, ['在招']],
  ['README.md', /抓取个人\/课题组主页 \| \*\*(\d+) 位\*\*（成功 (\d+)）/, ['抓取主页人数', null]],
];

let bad = 0;
console.log('\n=== 文档声称值 vs 实际值 ===');
for (const [file, re, keys] of CLAIM) {
  const t = fs.readFileSync(path.join(REPO, file), 'utf8');
  const m = t.match(re);
  if (!m) { console.log(`  ⚠ ${file}: 未匹配到「${re.source.slice(0, 40)}…」`); continue; }
  m.slice(1).forEach((val, i) => {
    const key = keys[i];
    if (!key) return;
    const actual = FACT[key];
    const claimed = Number(String(val).replace(/,/g, ''));
    const ok = claimed === actual;
    if (!ok) bad++;
    console.log(`  ${ok ? '✓' : '✗'} ${file} ${key}: 文档 ${claimed} / 实际 ${actual}`);
  });
}

// 百分比核对
const t = fs.readFileSync(path.join(REPO, 'README.md'), 'utf8');
const pctM = t.match(/检索到可核实论文 \| \*\*\d+ 人（([\d.]+)%）/);
if (pctM) {
  const actual = FACT.有论文人数 / FACT.全库人数 * 100;
  const ok = Math.abs(Number(pctM[1]) - actual) < 0.2;
  if (!ok) bad++;
  console.log(`  ${ok ? '✓' : '✗'} README 论文覆盖率: 文档 ${pctM[1]}% / 实际 ${actual.toFixed(1)}%`);
}
const hpM = t.match(/共 (\d+) 位导师有可访问的个人主页（占 ([\d.]+)%）/);
if (hpM) {
  const ok = Number(hpM[1]) === FACT.有主页人数 && Math.abs(Number(hpM[2]) - FACT.有主页人数 / FACT.全库人数 * 100) < 0.2;
  if (!ok) bad++;
  console.log(`  ${ok ? '✓' : '✗'} README 主页覆盖: ${hpM[1]} 位 / ${hpM[2]}%`);
}

console.log(bad ? `\n❌ ${bad} 处不一致` : '\n✅ 文档数字与实际数据全部一致');
process.exit(bad ? 1 : 0);
