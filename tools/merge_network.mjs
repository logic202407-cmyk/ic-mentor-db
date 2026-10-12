// merge_network.mjs — 合并四个证据等级，生成最终关系网络
//
// 证据等级（可视化中区分显示）：
//   L1 自述师承  —— 页面明写「导师为/师从 XX」                     最高
//   L2 交叉证据  —— 页面学历机构 × 早期一作 × 该机构教授任末位作者   高
//   L3 署名推断  —— 早期一作 + 固定末位作者（无学历佐证）            中
//   L4 合作      —— 共同署名（仅作背景，不主张师承）                参考
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const net = JSON.parse(fs.readFileSync(path.join(PROC, 'network.json'), 'utf8'));
const cvNet = JSON.parse(fs.readFileSync(path.join(PROC, 'cv_network.json'), 'utf8'));
const cvRaw = JSON.parse(fs.readFileSync(path.join(PROC, 'cv_extracted.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

// ── 人名 -> 档案（含学历/工作经历）──
const profile = {};
for (const [sk, m] of Object.entries(variants)) {
  for (const p of m.people) {
    const rec = cvRaw[`${sk}_${p.name_cn}`];
    profile[`${m.school}|${p.name_cn}`] = {
      edu: rec ? rec.edu.slice(0, 5) : [],
      postdoc: rec ? rec.postdoc.slice(0, 3) : [],
      jobs: rec ? rec.jobs.slice(0, 4) : [],
      roster: rec && rec.roster ? rec.roster.slice(0, 20) : [],
    };
  }
}
const withEdu = Object.values(profile).filter((p) => p.edu.length).length;
console.log(`含学历档案: ${withEdu} 人 | 含博士后经历: ${Object.values(profile).filter((p) => p.postdoc.length).length} 人`);

// ── 键格式统一：部分脚本用 school_key（buaa|李赛），部分用校名（北京航空航天大学|李赛）──
// 最终统一为**校名格式**，与 network.json 一致。
const sk2school = {};
for (const [sk, m] of Object.entries(variants)) sk2school[sk] = m.school;
const NORM = (k) => {
  const i = k.indexOf('|');
  if (i < 0) return k;
  const a = k.slice(0, i), b = k.slice(i + 1);
  return sk2school[a] ? `${sk2school[a]}|${b}` : k;
};
const normEdge = (e) => ({ ...e, s: NORM(e.s), t: NORM(e.t) });

// ── 合并节点 ──
const nodes = { ...net.people };
for (const [k, v] of Object.entries(cvNet.people)) { const nk = NORM(k); if (!nodes[nk]) nodes[nk] = v; }
for (const e of [...cvNet.stated, ...cvNet.cross]) {
  for (const k of [NORM(e.s), NORM(e.t)]) if (!nodes[k]) nodes[k] = cvNet.people[e.s] || cvNet.people[e.t] || { name: k.split('|')[1], school: k.split('|')[0] };
}
console.log(`合并后节点: ${Object.keys(nodes).length}`);

// ── 边分级（全部规范化键）──
const L1 = cvNet.stated.map((e) => ({ ...normEdge(e), lv: 1, n: null, span: '', kind: e.kind }));
const L2 = cvNet.cross.map((e) => normEdge({ ...e, lv: 2 }));
const covered = new Set([...L1, ...L2].map((e) => `${e.s}||${e.t}`));
const L3 = net.advisor.filter((e) => !covered.has(`${e.s}||${e.t}`))
  .map((e) => ({ s: NORM(e.s), t: NORM(e.t), lv: 3, n: e.n, span: e.span, note: `早期 ${e.early} 篇一作论文中固定末位作者（${e.span}）`, conf: e.confidence }));
const L4 = net.collab.map((e) => ({ s: NORM(e.s), t: NORM(e.t), lv: 4, n: e.n }));

// ── L0：时间-机构重叠 + 同期共同署名（用户方法论）──
// 两人在同一机构的时间段有重叠，且重叠期内有共同署名 => 直接的关系证据
let ovData = null;
try { ovData = JSON.parse(fs.readFileSync(path.join(PROC, 'overlap_screen.json'), 'utf8')); } catch { /* 可选 */ }
const ovEdges = [];
if (ovData) {
  for (const r of ovData.results) {
    const s = NORM(r.a), t = NORM(r.b);
    if (!NORM(r.a) || !NORM(r.b)) continue;
    ovEdges.push({
      s, t, lv: 0,
      n: r.nInWindow, inst: r.inst, span: `${r.y1}–${r.y2}`,
      type: r.type, reason: r.reason, tierS: r.tierS, tierA: r.tierA,
      note: `两人在「${r.inst}」的时间段重叠（${r.y1}–${r.y2}，共 ${r.years} 年），重叠期内共同署名 ${r.nInWindow} 篇。判定：${r.type}${r.reason ? '（' + r.reason + '）' : ''}`,
    });
  }
}
console.log(`\n时间-机构重叠边: ${ovEdges.length}（其中师徒候选 ${ovEdges.filter((e) => /师徒/.test(e.type)).length}）`);
// 用重叠证据给已有师徒边加权
const ovKey = new Set(ovEdges.map((e) => `${e.s}||${e.t}`).concat(ovEdges.map((e) => `${e.t}||${e.s}`)));
let boosted = 0;
for (const e of [...L1, ...L2, ...L3]) if (ovKey.has(`${e.s}||${e.t}`)) { e.ov = ovEdges.find((o) => (o.s === e.s && o.t === e.t) || (o.s === e.t && o.t === e.s)); boosted++; }
console.log(`已有师徒边中，有重叠佐证的: ${boosted} 条`);

console.log(`\n边分级:`);
console.log(`  L1 自述师承   ${L1.length}`);
console.log(`  L2 交叉证据   ${L2.length}`);
console.log(`  L3 署名推断   ${L3.length}`);
console.log(`  L4 合作       ${L4.length}`);
console.log(`  同门（由师徒派生） ${net.sibling.length}`);

const out = {
  meta: {
    builtAt: new Date().toISOString().slice(0, 10),
    nodes: Object.keys(nodes).length,
    L1: L1.length, L2: L2.length, L3: L3.length, L4: L4.length, overlap: ovEdges.length,
    siblings: net.sibling.length, externalMentors: cvNet.external.length,
    withEdu,
  },
  nodes, profile,
  advisor: [...L1, ...L2, ...L3],
  overlap: ovEdges,
  collab: L4,
  sibling: net.sibling,
  external: cvNet.external,
};
fs.writeFileSync(path.join(PROC, 'network_final.json'), JSON.stringify(out, null, 1), 'utf8');
console.log('\n已导出 data/processed/network_final.json');

// ── 打印 L1 + L2 全量（这是最可靠的部分）──
console.log('\n══════ L1 自述师承（页面明写，全部）══════');
const nm = (k) => nodes[k]?.name || k;
const sc = (k) => (nodes[k]?.school || '?').replace('中国科学院', '中科院').slice(0, 9);
for (const e of [...L1].sort((a, b) => sc(a.t).localeCompare(sc(b.t)))) {
  console.log(`  ${nm(e.s)}（${sc(e.s)}） ← ${nm(e.t)}（${sc(e.t)}）`);
}
console.log('\n══════ L2 学历×论文交叉证据（全部）══════');
for (const e of L2) {
  console.log(`  ${nm(e.s)}（${sc(e.s)}） ← ${nm(e.t)}（${sc(e.t)}） | ${e.n}篇 ${e.span} | 毕业自 ${(e.inst || '').slice(0, 22)}`);
}
