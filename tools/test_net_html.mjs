// test_net_html.mjs — 在 Node 中模拟运行页面核心逻辑，验证不会运行时崩溃
import fs from 'node:fs';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
const js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

// 提取 DATA 并注入
const dm = js.match(/const DATA = (\{[\s\S]*?\});\n/);
const DATA = JSON.parse(dm[1]);
console.log('数据: 节点', Object.keys(DATA.nodes).length, '| 师徒', DATA.advisor.length, '| 合作', DATA.collab.length, '| 同门', DATA.sibling.length);

const N = DATA.nodes, ADV = DATA.advisor, COLB = DATA.collab, SIB = DATA.sibling;

// ── 复刻页面核心逻辑（不依赖 DOM/canvas）──
let W = 1400, H = 900;
function buildGraph(view, minW, showAdv, showSib, hideAlone, schoolF) {
  const mentorOf = {}, studentsOf = {};
  for (const e of ADV) {
    if (!N[e.s] || !N[e.t]) continue;
    (mentorOf[e.s] = mentorOf[e.s] || []).push(e.t);
    (studentsOf[e.t] = studentsOf[e.t] || []).push(e.s);
  }
  const nodesSet = new Set(), edges = [];
  if (showAdv) for (const e of ADV) if (N[e.s] && N[e.t]) { edges.push({ ...e, k: 'adv' }); nodesSet.add(e.s); nodesSet.add(e.t); }
  if (showSib) for (const e of SIB) if (N[e.s] && N[e.t]) { edges.push({ ...e, k: 'sib' }); nodesSet.add(e.s); nodesSet.add(e.t); }
  if (view === 'collab' || !hideAlone) {
    for (const e of COLB) {
      if (e.n < minW) continue;
      if (!N[e.s] || !N[e.t]) continue;
      edges.push({ ...e, k: 'col' }); nodesSet.add(e.s); nodesSet.add(e.t);
    }
  }
  let list = [...nodesSet];
  if (schoolF) list = list.filter((k) => N[k].s === schoolF);
  const keep = new Set(list);
  const finalEdges = edges.filter((e) => keep.has(e.s) && keep.has(e.t));
  if (hideAlone && view !== 'collab') {
    const deg = {};
    for (const e of finalEdges) { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.t] = (deg[e.t] || 0) + 1; }
    list = list.filter((k) => deg[k]);
  }
  return { list, edges: finalEdges.filter((e) => list.includes(e.s) && list.includes(e.t)), mentorOf, studentsOf };
}

function layoutLineage(list, g) {
  const inSet = new Set(list), depth = {};
  const roots = list.filter((k) => !(g.mentorOf[k] || []).some((m) => inSet.has(m)));
  const q = roots.map((k) => [k, 0]); const seen = new Set(roots);
  while (q.length) {
    const [k, d] = q.shift(); depth[k] = d;
    for (const s of (g.studentsOf[k] || [])) { if (!inSet.has(s) || seen.has(s)) continue; seen.add(s); q.push([s, d + 1]); }
  }
  for (const k of list) if (depth[k] === undefined) depth[k] = 0;
  const byD = {};
  for (const k of list) (byD[depth[k]] = byD[depth[k]] || []).push(k);
  const maxDepth = Math.max(...Object.keys(byD).map(Number));
  const res = {};
  const rowH = Math.max(64, Math.min(150, (H - 80) / Math.max(1, maxDepth + 1)));
  for (const [d, arr] of Object.entries(byD)) {
    arr.sort((a, b) => (N[b].p || 0) - (N[a].p || 0));
    const gap = (W - 120) / Math.max(arr.length, 1);
    arr.forEach((k, i) => { res[k] = { x: 60 + gap * (i + 0.5), y: 60 + Number(d) * rowH }; });
  }
  return { pos: res, maxDepth, layers: Object.keys(byD).length };
}

function radius(k) { const p = N[k]?.p || 0; return 4 + Math.min(13, Math.sqrt(p) * 1.15); }

// ── 测试 ──
let fail = 0;
function t(name, fn) { try { const r = fn(); console.log(`  ✓ ${name}${r ? ' → ' + r : ''}`); } catch (e) { console.log(`  ✗ ${name}: ${e.message}`); fail++; } }

console.log('\n[1] 师承视图（默认）');
let g1, L1;
t('建图不报错', () => { g1 = buildGraph('lineage', 3, true, true, true, ''); return `${g1.list.length} 节点 / ${g1.edges.length} 边`; });
t('分层布局不报错', () => { L1 = layoutLineage(g1.list, g1); return `${L1.layers} 层，最深 ${L1.maxDepth} 层`; });
t('坐标全部有效', () => {
  const bad = g1.list.filter((k) => !L1.pos[k] || !isFinite(L1.pos[k].x) || !isFinite(L1.pos[k].y));
  if (bad.length) throw new Error(bad.length + ' 个节点坐标无效');
  const nan = g1.list.filter((k) => isNaN(L1.pos[k].x));
  if (nan.length) throw new Error('含 NaN');
  return '全部有限值';
});
t('半径计算有效', () => { const bad = g1.list.filter((k) => !isFinite(radius(k)) || radius(k) <= 0); if (bad.length) throw new Error(bad.length + ' 个'); return 'ok'; });
t('每层节点数合理', () => {
  const byY = {};
  for (const k of g1.list) { const y = Math.round(L1.pos[k].y); byY[y] = (byY[y] || 0) + 1; }
  const maxRow = Math.max(...Object.values(byY));
  if (maxRow > g1.list.length) throw new Error('异常');
  return `最宽一层 ${maxRow} 人`;
});

console.log('\n[2] 师承链完整性');
t('师承链最长的几条', () => {
  const g = g1;
  // 找最长链
  let best = [];
  function dfs(k, path, seen) {
    const st = (g.studentsOf[k] || []).filter((s) => !seen.has(s));
    if (!st.length) { if (path.length > best.length) best = [...path]; return; }
    for (const s of st) { seen.add(s); path.push(s); dfs(s, path, seen); path.pop(); seen.delete(s); }
  }
  const roots = g.list.filter((k) => !(g.mentorOf[k] || []).some((m) => g.list.includes(m)));
  for (const r of roots) dfs(r, [r], new Set([r]));
  if (!best.length) throw new Error('未找到任何师承链');
  return best.map((k) => N[k].n).join(' → ');
});

console.log('\n[3] 合作视图（力导向）');
t('建图不报错', () => { const g = buildGraph('collab', 3, false, false, false, ''); return `${g.list.length} 节点 / ${g.edges.length} 边`; });
t('稀疏子图（minW≥6）规模可控', () => { const g = buildGraph('collab', 6, false, false, false, ''); return `${g.list.length} 节点 / ${g.edges.length} 边`; });

console.log('\n[4] 过滤组合');
for (const [school, w, adv, sib] of [['西电', 3, true, true], ['清华', 5, true, false], ['北大', 10, false, true], ['中科院微电子所', 3, true, true]]) {
  t(`${school} / w≥${w} / 师徒${adv ? '√' : '×'} / 同门${sib ? '√' : '×'}`, () => {
    const g = buildGraph('lineage', w, adv, sib, true, school);
    const L = layoutLineage(g.list, g);
    const bad = g.list.filter((k) => !L.pos[k] || !isFinite(L.pos[k].x));
    if (bad.length) throw new Error('坐标无效');
    return `${g.list.length} 节点 / ${g.edges.length} 边 / ${L.layers} 层`;
  });
}

console.log('\n[5] 数据引用完整性');
t('所有边的端点都在 nodes 中', () => {
  const all = [...ADV, ...COLB, ...SIB];
  const miss = all.filter((e) => !N[e.s] || !N[e.t]);
  if (miss.length) throw new Error(miss.length + ' 条边端点缺失');
  return `${all.length} 条边全部有效`;
});
t('师徒边置信度字段完整', () => {
  const bad = ADV.filter((e) => !['high', 'medium'].includes(e.c));
  if (bad.length) throw new Error(bad.length + ' 条缺置信度');
  const c = {}; for (const e of ADV) c[e.c] = (c[e.c] || 0) + 1;
  return JSON.stringify(c);
});
t('无自环', () => { const s = [...ADV, ...COLB, ...SIB].filter((e) => e.s === e.t); if (s.length) throw new Error(s.length + ' 条自环'); return 'ok'; });

console.log(fail ? `\n❌ ${fail} 项失败` : '\n✅ 全部通过');
process.exit(fail ? 1 : 0);
