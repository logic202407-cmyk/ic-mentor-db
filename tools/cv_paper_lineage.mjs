// cv_paper_lineage.mjs — 交叉「学历机构」与「论文末位作者」两条独立证据，构建师承
//
// 逻辑：A 的博士毕业单位 = X 大学（页面自述）
//       且 B 是 X 大学的教授（名录）
//       且 B 在 A 的早期一作论文中固定为末位作者（论文署名）
//       => B 极可能是 A 的导师。两条独立证据交叉，远比单靠署名推断可靠。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const cv = JSON.parse(fs.readFileSync(path.join(PROC, 'cv_extracted.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const pairs = JSON.parse(fs.readFileSync(path.join(PROC, '_net_pair.json'), 'utf8'));
const stateLin = JSON.parse(fs.readFileSync(path.join(PROC, 'cv_lineage.json'), 'utf8'));

// key -> person（注意：_net_people.json 的键用**学校中文名**，CV 文件名用 **school_key**，需双向映射）
const byKey = {};
const keyBySchoolName = {};   // "清华大学|孙楠" -> "tsinghua|孙楠"
const skBySchoolName = {};
for (const [sk, m] of Object.entries(variants)) {
  skBySchoolName[m.school] = sk;
  for (const p of m.people) {
    const netKey = `${m.school}|${p.name_cn}`;
    byKey[netKey] = { key: netKey, sk, school: m.school, name: p.name_cn, title: p.title || '', dept: p.department || '' };
    keyBySchoolName[`${sk}|${p.name_cn}`] = netKey;
  }
}

// 机构关键词 -> school_key
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
function instKeys(text) {
  const out = new Set();
  for (const [re, k] of HINT) if (re.test(text || '')) out.add(k);
  return out;
}
// 取最高学历（博士 > 硕士 > 学士）
function topDegree(rec) {
  const order = { 博士: 3, 硕士: 2, 学士: 1, 本科: 1, 毕业: 0 };
  let best = null, bestRank = -1;
  for (const e of rec.edu || []) {
    const text = `${e.deg} ${e.inst}`;
    const rank = /博士|Ph\.?D/i.test(text) ? 3 : /硕士|Master/i.test(text) ? 2 : /学士|本科|Bachelor/i.test(text) ? 1 : 0;
    if (rank > bestRank) { bestRank = rank; best = { ...e, rank, insts: instKeys(e.inst) }; }
  }
  return best;
}

const statedKeys = new Set(stateLin.edges.map((e) => `${e.s}||${e.t}`));
const papersByKey = JSON.parse(fs.readFileSync(path.join(PROC, '_net_papers_by_key.json'), 'utf8'));
const firstYear = {};
for (const [k, ps] of Object.entries(papersByKey)) { const ys = ps.map((p) => p.year).filter(Boolean); if (ys.length) firstYear[k] = Math.min(...ys); }

const out = [];
const rejected = [];
for (const pr of pairs) {
  const [s, t] = pr.k.split('||');
  if (!byKey[s] || !byKey[t]) continue;
  if (statedKeys.has(pr.k)) continue;                 // 已有直接证据，跳过
  if (pr.n < 2) continue;                             // 单篇证据太弱
  const rec = cv[`${byKey[s].sk}_${byKey[s].name}`]; if (!rec) continue;
  const top = topDegree(rec);
  if (!top) continue;
  // 交叉判定①：导师所在学校 恰是 学生的毕业院校
  const mentorSk = byKey[t].sk;
  const hit = top.insts.has(mentorSk) || (top.insts.has('cas_any') && mentorSk.startsWith('cas_'));
  if (!hit) continue;
  const ys = pr.papers.map((p) => p.year).filter(Boolean).sort();
  // 交叉判定②：论文须落在**学生生涯窗口**（毕业年 ±，或本人发表记录前 6 年）
  const fy = firstYear[s];
  const inWin = (y) => (top.year ? (y >= top.year - 7 && y <= top.year + 2) : (fy ? y <= fy + 6 : false));
  const early = ys.filter(inWin);
  if (early.length < 2) { rejected.push({ s, t, n: pr.n, why: '论文年份不在学生生涯窗口' }); continue; }
  if (early[early.length - 1] - early[0] > 8) { rejected.push({ s, t, n: pr.n, why: '窗口内跨度 >8 年' }); continue; }
  out.push({
    s, t, n: pr.n, basis: 'cv+paper',
    year: top.year, inst: top.inst,
    span: `${early[0]}–${early[early.length - 1]}`,
    note: `${byKey[s].name} 页面自述于「${top.inst}」获${top.rank === 3 ? '博士' : top.rank === 2 ? '硕士' : '学位'}${top.year ? '（' + top.year + '年）' : ''}；` +
      `其 ${early.length} 篇早期论文（${early[0]}–${early[early.length - 1]}）为第一作者，${byKey[t].name}（${byKey[t].school}）固定为末位作者`,
    confidence: early.length >= 3 ? 'high' : 'medium',
  });
}
console.log(`交叉证据新增师承边: ${out.length} 条 | 因时间窗口不符被拒: ${rejected.length} 条`);
for (const e of out.sort((a, b) => b.n - a.n)) {
  console.log(`  ${byKey[e.s].name}（${byKey[e.s].school.replace('中国科学院', '中科院').slice(0, 8)}）← ${byKey[e.t].name}（${byKey[e.t].school.replace('中国科学院', '中科院').slice(0, 8)}）| ${e.n}篇 ${e.span} | 毕业自 ${e.inst.slice(0, 20)}`);
}

// ── 合并：stated（直接自述）+ cv+paper（交叉证据）──
const merged = {
  meta: { builtAt: new Date().toISOString().slice(0, 10), stated: stateLin.edges.length, cross: out.length, external: stateLin.external.length },
  stated: stateLin.edges,
  cross: out,
  external: stateLin.external,
  people: byKey,
};
fs.writeFileSync(path.join(PROC, 'cv_network.json'), JSON.stringify(merged, null, 1), 'utf8');

console.log(`\n=== 合计 ===`);
console.log(`  自述师承（直接证据）: ${stateLin.edges.length} 条`);
console.log(`  交叉证据（学历×论文）: ${out.length} 条`);
console.log(`  外部导师（不在库内）: ${stateLin.external.length} 条`);
const involved = new Set();
for (const e of [...stateLin.edges, ...out]) { involved.add(e.s); involved.add(e.t); }
console.log(`  涉及节点: ${involved.size} 人`);
