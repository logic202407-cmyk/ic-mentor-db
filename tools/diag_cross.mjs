// diag_cross.mjs — 诊断交叉证据为何为 0
import fs from 'node:fs';
const PROC = 'data/processed';
const cv = JSON.parse(fs.readFileSync(`${PROC}/cv_extracted.json`, 'utf8'));
const variants = JSON.parse(fs.readFileSync(`${PROC}/name_variants.json`, 'utf8'));
const pairs = JSON.parse(fs.readFileSync(`${PROC}/_net_pair.json`, 'utf8'));

const byKey = {};
for (const [sk, m] of Object.entries(variants)) for (const p of m.people) byKey[`${sk}|${p.name_cn}`] = { key: `${sk}|${p.name_cn}`, sk, school: m.school, name: p.name_cn };

// 1) CV 记录的 key 能否对应到人
let cvOk = 0, cvBad = 0;
const cvPersonKeys = new Set();
for (const k of Object.keys(cv)) {
  const i = k.indexOf('_');
  const sk = k.slice(0, i), nm = k.slice(i + 1);
  const pk = `${sk}|${nm}`;
  if (byKey[pk]) { cvOk++; cvPersonKeys.add(pk); } else { cvBad++; }
}
console.log(`CV 记录 ${Object.keys(cv).length} 条 → 能对应到名录 ${cvOk}，无法对应 ${cvBad}`);

// 2) pairs 涉及的"学生"人数
const stuKeys = new Set(pairs.map((p) => p.k.split('||')[0]));
console.log(`论文配对中的"学生"角色人数: ${stuKeys.size}`);

// 3) 交集
const inter = [...cvPersonKeys].filter((k) => stuKeys.has(k));
console.log(`既有 CV 学历、又出现在论文配对中: ${inter.length} 人`);
console.log('  样例:', inter.slice(0, 12).map((k) => byKey[k].name).join('、'));

// 4) 对有学历的这批人，看其毕业机构与配对导师学校是否匹配
const HINT = [
  [/清华/, 'tsinghua'], [/北京航空|北航/, 'buaa'], [/北京大学|北大/, 'pku'], [/复旦/, 'fudan'],
  [/上海交通|上交/, 'sjtu'], [/浙江大学|浙大/, 'zju'], [/南京大学|南大/, 'nju'],
  [/中国科学技术大学|中国科大|中科大/, 'ustc'], [/东南大学/, 'seu'], [/西安电子|西电/, 'xidian'],
  [/电子科技大学|成电/, 'uestc'], [/哈尔滨工业|哈工大/, 'hit'], [/天津大学|天大/, 'tju'],
  [/华中科技|华科/, 'hust'], [/西安交通|西交/, 'xjtu'],
  [/微电子研究所/, 'cas_ime'], [/半导体研究所/, 'cas_semi'], [/上海微系统/, 'cas_simit'],
  [/计算技术研究所/, 'cas_ict'], [/自动化研究所/, 'cas_ia'], [/上海高等研究院/, 'cas_sari'],
  [/中国科学院|中科院/, 'cas_any'],
];
const instKeys = (t) => { const s = new Set(); for (const [re, k] of HINT) if (re.test(t || '')) s.add(k); return s; };

console.log('\n=== 逐个看有学历者的毕业机构 vs 其配对导师学校 ===');
let n = 0;
for (const pk of inter) {
  const rec = cv[`${byKey[pk].sk}_${byKey[pk].name}`];
  if (!rec || !rec.edu.length) continue;
  const insts = new Set();
  for (const e of rec.edu) for (const k of instKeys(e.inst)) insts.add(k);
  const myPairs = pairs.filter((p) => p.k.split('||')[0] === pk);
  if (!myPairs.length) continue;
  if (n++ >= 18) break;
  const mentorSchools = [...new Set(myPairs.map((p) => byKey[p.k.split('||')[1]]?.sk).filter(Boolean))];
  const match = mentorSchools.filter((s) => insts.has(s) || (insts.has('cas_any') && s.startsWith('cas_')));
  console.log(`  ${byKey[pk].name}(${byKey[pk].school.slice(0, 6)}) 毕业自[${[...insts].join(',')}] 导师校[${mentorSchools.join(',')}] ${match.length ? '★匹配 ' + match.join(',') : ''}`);
  console.log(`      学历原文: ${rec.edu.slice(0, 2).map((e) => (e.year || '?') + ' ' + e.deg + ' ' + e.inst).join(' | ').slice(0, 100)}`);
}
