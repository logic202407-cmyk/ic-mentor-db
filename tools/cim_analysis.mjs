// cim_analysis.mjs — 存算一体（Computing-in-Memory）方向：热度趋势 + 深耕度识别
//
// 核心方法：**不看教师简介里的关键词，只看论文标题做了什么**。
// 简介可以写"研究兴趣包括存算一体"，但论文标题不会撒谎。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

// ── 存算一体的标题特征（分强/弱两档，避免"memory"这种泛词误伤）──
const CIM_STRONG = [
  /comput(?:ing|e)[\s-]?in[\s-]?memory/i,
  /in[\s-]?memory\s+comput/i,
  /processing[\s-]?in[\s-]?memory/i,
  /near[\s-]?memory\s+comput/i,
  /memory[\s-]?centric/i,
  /\bCIM\b/,
  /\bPIM\b/,
  /compute[\s-]?in[\s-]?(?:sram|reram|rram|mram|pcm|flash|dram)/i,
  /(?:sram|reram|rram|mram|pcm)[\s-]?based\s+(?:comput|accelerat|macro|engine)/i,
  /dot[\s-]?product\s+engine/i,
  /multiply[\s-]?accumulate\s+(?:macro|engine|array|circuit)/i,
  /\bMAC\s+(?:macro|array|unit|engine)/i,
  /analog\s+(?:comput|MAC|matrix)/i,
  /memrist(?:or|ive)/i,
  /in[\s-]?situ\s+comput/i,
  /logic[\s-]?in[\s-]?memory/i,
];
const CIM_WEAK = [
  /\bCIM\b|\bIMC\b/,
  /neural\s+(?:network|net)\s+(?:accelerator|processor|engine)/i,
  /deep[\s-]?learning\s+accelerator/i,
  /AI\s+(?:accelerator|chip|processor)/i,
  /tensor\s+(?:core|processor|accelerator)/i,
  /systolic\s+array/i,
];
const isCIM = (t) => CIM_STRONG.some((re) => re.test(t));
const isAccel = (t) => CIM_WEAK.some((re) => re.test(t));

// ── 1. 全库趋势 ──
console.log('='.repeat(74));
console.log('一、存算一体在研究产出中的热度趋势（全库 3179 位导师的论文池）');
console.log('='.repeat(74));
const yearCIM = {}, yearAll = {};
let totalCIM = 0, totalAll = 0;
const cimPeople = new Set();
for (const d of ranked) {
  for (const p of d.papers || []) {
    const y = p.year; if (!y) continue;
    yearAll[y] = (yearAll[y] || 0) + 1; totalAll++;
    if (isCIM(p.title || '')) {
      yearCIM[y] = (yearCIM[y] || 0) + 1; totalCIM++;
      cimPeople.add(`${d.school}|${d.name_cn}`);
    }
  }
}
console.log(`全库论文总数 ${totalAll} ｜ 存算一体主题 ${totalCIM} 篇（占 ${(totalCIM / totalAll * 100).toFixed(2)}%）`);
console.log(`涉及导师 ${cimPeople.size} 人\n`);
console.log('年份  CIM篇数  全库篇数  占比   趋势');
for (const y of Object.keys(yearCIM).map(Number).sort()) {
  if (y < 2015) continue;
  const c = yearCIM[y] || 0, a = yearAll[y] || 1;
  const bar = '█'.repeat(Math.min(60, Math.round(c / 2)));
  console.log(`${y}  ${String(c).padStart(6)}  ${String(a).padStart(8)}  ${(c / a * 100).toFixed(1).padStart(4)}%  ${bar}`);
}

// ── 2. 会议/期刊分布（看这个方向发在哪）──
console.log('\n' + '='.repeat(74));
console.log('二、存算一体论文的发表阵地 Top 15');
console.log('='.repeat(74));
const venueCIM = new Map();
for (const d of ranked) for (const p of d.papers || []) {
  if (!isCIM(p.title || '')) continue;
  const v = (p.venue || '?').replace(/&amp;/g, '&').replace(/^\d{4}\s*/, '').slice(0, 62);
  venueCIM.set(v, (venueCIM.get(v) || 0) + 1);
}
for (const [v, c] of [...venueCIM].sort((a, b) => b[1] - a[1]).slice(0, 15)) console.log(`  ${String(c).padStart(4)}  ${v}`);

// ── 3. 深耕度打分 ──
console.log('\n' + '='.repeat(74));
console.log('三、深耕度评估：谁是真的在做存算一体');
console.log('='.repeat(74));
const people = [];
for (const d of ranked) {
  const ps = d.papers || [];
  if (!ps.length) continue;
  const cim = ps.filter((p) => isCIM(p.title || ''));
  if (!cim.length) continue;
  const years = cim.map((p) => p.year).filter(Boolean).sort();
  const span = years.length ? years[years.length - 1] - years[0] + 1 : 0;
  const distinctYears = new Set(years).size;
  const sTier = cim.filter((p) => p.tier === 'S').length;
  const aTier = cim.filter((p) => p.tier === 'A').length;
  const lead = cim.filter((p) => p.my_order === 1 || (p.my_order === p.n_authors && (p.n_authors || 0) >= 3)).length;
  const firstA = cim.filter((p) => p.my_order === 1).length;
  const lastA = cim.filter((p) => p.my_order === p.n_authors && (p.n_authors || 0) >= 3).length;
  const recent = cim.filter((p) => (p.year || 0) >= 2024).length;
  const share = cim.length / ps.length;
  // 深耕度：持续性(跨年数) × 主导性(一作/通讯占比) × 产出量 × 质量，再要求近期仍活跃
  const depth = Math.round(
    Math.min(30, cim.length * 1.6) +          // 量
    Math.min(22, distinctYears * 3.6) +        // 持续性
    Math.min(18, sTier * 3.2 + aTier * 1.1) +  // 质量
    Math.min(16, lead * 1.5) +                 // 本人主导
    Math.min(14, recent * 2.2)                 // 近期活跃
  );
  people.push({
    name: d.name_cn, school: d.school, title: d.title, dept: d.department,
    homepage: d.homepage, nCIM: cim.length, nAll: ps.length, share,
    sTier, aTier, lead, firstA, lastA, recent, span, distinctYears, depth,
    kw: (d.research_keywords || []).join('、'),
    kwMentionsCIM: /存算|存内|忆阻|in-memory|computing-in-memory/i.test((d.research_keywords || []).join('、') + (d.primary_direction || '')),
    top: cim.sort((a, b) => (b.tier === 'S') - (a.tier === 'S') || (b.year || 0) - (a.year || 0)).slice(0, 3).map((p) => `${p.year} ${(p.venue || '').slice(0, 22)}: ${(p.title || '').slice(0, 62)}`),
  });
}
people.sort((a, b) => b.depth - a.depth);
console.log(`有存算一体主题论文的导师：${people.length} 人\n`);

console.log('【A. 简介写了 + 论文里也确实在做】(名副其实)');
const both = people.filter((p) => p.kwMentionsCIM && p.nCIM >= 2);
console.log(`  共 ${both.length} 人，取深耕度前 25：\n`);
console.log('  深耕度 姓名      单位            CIM篇/总篇  占比  S/A  一作 通讯 近2年 跨年');
for (const p of both.slice(0, 25)) {
  console.log(`  ${String(p.depth).padStart(4)}  ${p.name.padEnd(9)} ${p.school.replace('中国科学院', '中科院').slice(0, 13).padEnd(14)} ${String(p.nCIM).padStart(3)}/${String(p.nAll).padStart(3)}  ${(p.share * 100).toFixed(0).padStart(4)}%  ${p.sTier}/${p.aTier}  ${String(p.firstA).padStart(3)} ${String(p.lastA).padStart(3)}  ${String(p.recent).padStart(4)}  ${String(p.distinctYears).padStart(3)}`);
}

console.log('\n\n【B. 论文里在做，但简介没怎么提】(低调实干)');
const silent = people.filter((p) => !p.kwMentionsCIM && p.nCIM >= 3);
console.log(`  共 ${silent.length} 人，取深耕度前 15：\n`);
console.log('  深耕度 姓名      单位            CIM篇/总篇  占比  S/A  一作 通讯 近2年 跨年');
for (const p of silent.slice(0, 15)) {
  console.log(`  ${String(p.depth).padStart(4)}  ${p.name.padEnd(9)} ${p.school.replace('中国科学院', '中科院').slice(0, 13).padEnd(14)} ${String(p.nCIM).padStart(3)}/${String(p.nAll).padStart(3)}  ${(p.share * 100).toFixed(0).padStart(4)}%  ${p.sTier}/${p.aTier}  ${String(p.firstA).padStart(3)} ${String(p.lastA).padStart(3)}  ${String(p.recent).padStart(4)}  ${String(p.distinctYears).padStart(3)}`);
}

console.log('\n\n【C. 简介提了存算，但论文里几乎没有】(可能浮于表面)');
const shallow = people.filter((p) => p.kwMentionsCIM && p.nCIM <= 1);
console.log(`  共 ${shallow.length} 人（其中只有 1 篇 CIM 论文的：${shallow.filter((p) => p.nCIM === 1).length} 人）`);
console.log('  样例前 12：');
for (const p of shallow.slice(0, 12)) console.log(`  ${p.name}（${p.school.slice(0, 10)}）CIM ${p.nCIM} 篇 / 总 ${p.nAll} 篇 | 简介：${p.kw.slice(0, 60)}`);

// ── D. 简介写了存算，但论文池里一篇 CIM 都找不到（最典型的「浮于表面」）──
const zero = ranked.filter((d) => {
  const kws = (d.research_keywords || []).join('、') + (d.primary_direction || '');
  if (!/存算|存内|忆阻|in-memory|computing-in-memory/i.test(kws)) return false;
  return !(d.papers || []).some((x) => isCIM(x.title || ''));
});
console.log(`\n\n【D. 简介写了存算一体、但论文池里一篇都找不到】共 ${zero.length} 人`);
for (const z of zero.slice(0, 25)) {
  console.log(`  ${z.name_cn}（${z.school.replace('中国科学院', '中科院').slice(0, 12)}）论文 ${String(z.n_ic_papers).padStart(3)} 篇 | 简介：${(z.research_keywords || []).join('、').slice(0, 52)}`);
}

fs.writeFileSync(path.join(PROC, 'cim_ranking.json'), JSON.stringify(people, null, 1), 'utf8');
console.log('\n完整结果已存 data/processed/cim_ranking.json');
