// net_html.mjs — 生成关系网络可视化（单文件 HTML，离线可用）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const net = JSON.parse(fs.readFileSync(path.join(PROC, 'network_final.json'), 'utf8'));

// ── 精简数据（只带可视化需要的字段，控制体积）──
const SHORT = {
  '清华大学深圳国际研究生院': '清华深研院', '清华大学': '清华', '复旦大学': '复旦', '上海交通大学': '上交',
  '浙江大学': '浙大', '南京大学': '南大', '中国科学技术大学': '中科大', '北京大学': '北大',
  '东南大学': '东南', '西安电子科技大学': '西电', '电子科技大学': '成电', '哈尔滨工业大学': '哈工大',
  '天津大学': '天大', '华中科技大学': '华科', '北京航空航天大学': '北航', '西安交通大学': '西交',
  '中国科学院微电子研究所': '中科院微电子所', '中国科学院半导体研究所': '中科院半导体所',
  '中国科学院上海微系统与信息技术研究所': '中科院上海微系统所', '中国科学院计算技术研究所': '中科院计算所',
  '中国科学院自动化研究所': '中科院自动化所', '中国科学院上海高等研究院': '中科院上海高研院',
};

// 论文数（用于节点大小）：从 mentor_ranked 取
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const paperOf = new Map();
for (const d of ranked) paperOf.set(`${d.school}|${d.name_cn}`, d.n_ic_papers || 0);

const COLORS = {
  '清华': '#7c3aed', '清华深研院': '#a78bfa', '北大': '#dc2626', '复旦': '#2563eb', '上交': '#0891b2',
  '浙大': '#059669', '南大': '#ca8a04', '中科大': '#db2777', '东南': '#ea580c', '西电': '#4f46e5',
  '成电': '#0d9488', '哈工大': '#9333ea', '天大': '#b45309', '华科': '#be123c', '北航': '#1d4ed8',
  '西交': '#15803d', '中科院微电子所': '#64748b', '中科院半导体所': '#78716c', '中科院上海微系统所': '#71717a',
  '中科院计算所': '#52525b', '中科院自动化所': '#3f3f46', '中科院上海高研院': '#a1a1aa',
};

const nodes = {};
for (const [k, p] of Object.entries(net.nodes)) {
  const s = SHORT[p.school] || p.school;
  const pr = net.profile[k] || {};
  nodes[k] = {
    n: p.name, s, sc: p.school, t: p.title || '', d: p.dept || '', c: p.kw || '', h: p.homepage || '',
    p: paperOf.get(k) || paperOf.get(`${p.school}|${p.name}`) || 0,
    edu: (pr.edu || []).map((e) => `${e.year ? e.year + ' ' : ''}${/博士/.test(e.deg) ? '博士' : /硕士/.test(e.deg) ? '硕士' : /学士|本科/.test(e.deg) ? '学士' : '毕业'} ${e.inst}`),
    pd: (pr.postdoc || []).map((e) => `${e.y1}${e.y2 ? '–' + e.y2 : '–'} ${e.inst}`),
    job: (pr.jobs || []).map((e) => `${e.year} ${e.org}`),
    team: (pr.roster || []).slice(0, 24),
  };
}
const nameOf = (k) => nodes[k]?.n || k;

const trim = (e) => ({ s: e.s, t: e.t, n: e.n, lv: e.lv, sp: e.span, nt: e.note || '', inst: e.inst || '' });
const data = {
  meta: net.meta,
  nodes,
  colors: COLORS,
  advisor: net.advisor.map(trim),
  collab: net.collab.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: 4 })),
  sibling: net.sibling.map((e) => ({ s: e.s, t: e.t, v: e.via })),
  external: (net.external || []).slice(0, 400),
};

// ── 生成 HTML ──
const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>微电子导师关系网络 · 师承与合作</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:13px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#0f1117;color:#e5e7eb;overflow:hidden}
#app{display:flex;height:100vh}
#side{width:320px;flex:0 0 320px;background:#161a23;border-right:1px solid #2a2f3a;overflow-y:auto;padding:14px}
#main{flex:1;position:relative}
canvas{display:block;width:100%;height:100%}
h1{font-size:15px;margin:0 0 4px}
h2{font-size:12px;margin:16px 0 6px;color:#93a3b8;text-transform:uppercase;letter-spacing:.5px}
.sub{font-size:11px;color:#6b7280;margin-bottom:10px}
.tabs{display:flex;gap:4px;margin-bottom:10px}
.tab{flex:1;padding:7px 4px;text-align:center;background:#1e2430;border:1px solid #2a2f3a;border-radius:6px;cursor:pointer;font-size:12px;color:#9ca3af}
.tab.on{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
label{display:flex;align-items:center;gap:7px;padding:5px 0;cursor:pointer;font-size:12px;color:#cbd5e1}
input[type=checkbox]{accent-color:#2563eb;width:14px;height:14px}
input[type=range]{width:100%;accent-color:#2563eb}
input[type=text],select{width:100%;padding:6px 8px;background:#0f1117;border:1px solid #2a2f3a;border-radius:5px;color:#e5e7eb;font-size:12px;margin-top:3px}
.stat{display:flex;justify-content:space-between;padding:3px 0;font-size:12px;color:#9ca3af}
.stat b{color:#e5e7eb}
.legend{font-size:11px;margin-top:8px}
.lg{display:flex;align-items:center;gap:7px;padding:3px 0;color:#9ca3af}
.sw{width:26px;height:0;border-top-width:2px;border-top-style:solid;flex:0 0 26px}
.dot{width:11px;height:11px;border-radius:50%;flex:0 0 11px}
#tip{position:absolute;background:#1e2430ee;border:1px solid #374151;border-radius:7px;padding:8px 11px;font-size:12px;pointer-events:none;display:none;max-width:280px;z-index:20;line-height:1.5}
#panel{position:absolute;right:0;top:0;width:330px;height:100%;background:#161a23f2;border-left:1px solid #2a2f3a;padding:14px;overflow-y:auto;display:none}
#panel h3{margin:0 0 2px;font-size:15px}
.tag{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;margin:2px 3px 2px 0;background:#252b38;color:#9ca3af}
.rel{border-top:1px solid #262c38;margin-top:9px;padding-top:7px;font-size:12px}
.rel b{color:#93a3b8;font-weight:600;display:block;margin-bottom:3px;font-size:11px}
.rel a{color:#60a5fa;cursor:pointer;text-decoration:none;margin-right:8px;display:inline-block;line-height:1.9}
.rel a:hover{text-decoration:underline}
#hint{position:absolute;left:12px;bottom:10px;font-size:11px;color:#4b5563;background:#0f1117cc;padding:5px 9px;border-radius:5px}
.warn{background:#7c2d1222;border:1px solid #9a3412;border-radius:6px;padding:8px 10px;font-size:11px;color:#fdba74;line-height:1.6;margin-top:8px}
</style></head><body>
<div id="app">
  <div id="side">
    <h1>微电子导师关系网络</h1>
    <div class="sub">基于 31,689 条共同署名记录的机构校验结果</div>
    <div class="tabs">
      <div class="tab on" data-v="lineage">师承图谱</div>
      <div class="tab" data-v="collab">合作网络</div>
    </div>

    <h2>搜索</h2>
    <input type="text" id="q" placeholder="输入导师姓名…"/>
    <div id="qres" style="font-size:11px;color:#6b7280;margin-top:4px"></div>

    <h2>过滤</h2>
    <div style="font-size:11px;color:#9ca3af">单位</div>
    <select id="school"><option value="">全部（22 校/单位）</option></select>
    <div style="font-size:11px;color:#9ca3af;margin-top:8px">最小合作篇数：<b id="wv">3</b></div>
    <input type="range" id="w" min="2" max="15" value="3"/>
    <label><input type="checkbox" id="showAdv" checked> 显示师徒关系</label>
    <label><input type="checkbox" id="showSib" checked> 显示同门关系</label>
    <label><input type="checkbox" id="hideAlone" checked> 隐藏孤立节点</label>

    <h2>图例</h2>
    <div class="legend">
      <div class="lg"><div class="sw" style="border-color:#fbbf24;border-top-width:3px"></div>L1 自述师承（页面明写）</div>
      <div class="lg"><div class="sw" style="border-color:#f59e0b;border-top-width:2px"></div>L2 学历 × 论文交叉证据</div>
      <div class="lg"><div class="sw" style="border-color:#a16207"></div>L3 署名推断（无学历佐证）</div>
      <div class="lg"><div class="sw" style="border-color:#3b82f6;border-top-style:dashed"></div>共同署名合作</div>
      <div class="lg"><div class="sw" style="border-color:#10b981;border-top-style:dotted"></div>同门（同一导师）</div>
      <div class="lg"><div class="dot" style="background:#2563eb"></div>节点大小 = 论文数</div>
    </div>

    <h2>统计</h2>
    <div class="stat"><span>当前显示节点</span><b id="sN">0</b></div>
    <div class="stat"><span>师徒关系</span><b id="sA">0</b></div>
    <div class="stat"><span>合作关系</span><b id="sC">0</b></div>
    <div class="stat"><span>同门关系</span><b id="sS">0</b></div>

    <div class="warn">
      <b>关系判定依据（按可靠性分四级）</b><br/>
      <b style="color:#fbbf24">L1 自述师承</b>：本人页面<b>明写</b>「导师为／师从 XX」。<br/>
      <b style="color:#f59e0b">L2 交叉证据</b>：页面自述<b>毕业院校</b>＋该院校教授在其<b>早期论文中固定为末位作者</b>（两条独立证据交叉）。<br/>
      <b style="color:#a16207">L3 署名推断</b>：仅有「早期一作＋固定末位作者」的署名模式，<b>无学历佐证</b>。<br/>
      所有署名均经<b>姓名＋机构双重校验</b>；机构不符或无法判定者一律丢弃，不猜测。<br/>
      本图仅反映<b>公开页面自述与论文署名</b>可推断的关系，不代表完整师承，也不构成任何评价。
    </div>
  </div>
  <div id="main">
    <canvas id="cv"></canvas>
    <div id="tip"></div>
    <div id="panel"></div>
    <div id="hint">滚轮缩放 · 拖拽平移 · 点击节点查看关系 · 双击空白重置</div>
  </div>
</div>
<script>
const DATA = ${JSON.stringify(data)};
const N = DATA.nodes, COL = DATA.colors, ADV = DATA.advisor, COLB = DATA.collab, SIB = DATA.sibling;
const $ = id => document.getElementById(id);
const NAME = k => (N[k] ? N[k].n : k);
const SCHOOL = k => (N[k] ? N[k].s : '?');

let view = 'lineage';
let minW = 3, showAdv = true, showSib = true, hideAlone = true, schoolF = '';
let scale = 1, ox = 0, oy = 0;
let pos = {}, sel = null, hover = null;
const cv = $('cv'), ctx = cv.getContext('2d');
let W = 0, H = 0;

// ── 布局：师承用分层（根=无导师者），合作用力导向 ──
function buildGraph() {
  const mentorOf = {}, studentsOf = {};
  for (const e of ADV) {
    if (!N[e.s] || !N[e.t]) continue;
    if (!mentorOf[e.s]) mentorOf[e.s] = [];
    mentorOf[e.s].push(e.t);
    (studentsOf[e.t] = studentsOf[e.t] || []).push(e.s);
  }
  const nodesSet = new Set();
  const edges = [];
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
  if (schoolF) list = list.filter(k => N[k].s === schoolF);
  // 过滤后仍需保证边两端都在
  const keep = new Set(list);
  const finalEdges = edges.filter(e => keep.has(e.s) && keep.has(e.t));
  // 隐藏孤立
  if (hideAlone) {
    const deg = {};
    for (const e of finalEdges) { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.t] = (deg[e.t] || 0) + 1; }
    if (view !== 'collab') list = list.filter(k => deg[k]);
  }
  return { list, edges: finalEdges.filter(e => list.includes(e.s) && list.includes(e.t)), mentorOf, studentsOf };
}

// ── 分层布局（师承视图）：按连通分量分块打包，每棵师承树独立布局 ──
function layoutLineage(list, g) {
  const inSet = new Set(list);
  // 1) 求连通分量（把师承/同门边当作无向图）
  const adj = {};
  for (const k of list) adj[k] = new Set();
  for (const e of g.edges) { if (inSet.has(e.s) && inSet.has(e.t)) { adj[e.s].add(e.t); adj[e.t].add(e.s); } }
  const comp = {}, comps = [];
  for (const k of list) {
    if (comp[k] !== undefined) continue;
    const cid = comps.length, stack = [k], members = [];
    comp[k] = cid;
    while (stack.length) {
      const x = stack.pop(); members.push(x);
      for (const y of adj[x]) if (comp[y] === undefined) { comp[y] = cid; stack.push(y); }
    }
    comps.push(members);
  }
  // 2) 每个分量内部做层次划分
  const layoutOf = (members) => {
    const mset = new Set(members);
    const depth = {};
    const roots = members.filter((k) => !(g.mentorOf[k] || []).some((m) => mset.has(m)));
    const q = (roots.length ? roots : [members[0]]).map((k) => [k, 0]);
    const seen = new Set(q.map((x) => x[0]));
    while (q.length) {
      const [k, d] = q.shift(); depth[k] = d;
      for (const s of (g.studentsOf[k] || [])) {
        if (!mset.has(s) || seen.has(s)) continue;
        seen.add(s); q.push([s, d + 1]);
      }
    }
    for (const k of members) if (depth[k] === undefined) depth[k] = 0;
    const byD = {};
    for (const k of members) (byD[depth[k]] = byD[depth[k]] || []).push(k);
    for (const d of Object.keys(byD)) byD[d].sort((a, b) => (N[b].p || 0) - (N[a].p || 0));
    const maxDepth = Math.max(...Object.keys(byD).map(Number));
    const widest = Math.max(...Object.values(byD).map((a) => a.length));
    return { byD, maxDepth, widest };
  };
  const infos = comps.map((m) => ({ members: m, ...layoutOf(m) }));
  infos.sort((a, b) => b.members.length - a.members.length);

  // 3) 网格打包：大分量优先，按面积估算排布
  const PADX = 26, PADY = 40, COLW = 200, ROWH = 78;
  const res = {};
  const cols = Math.max(1, Math.floor(W / COLW));
  let cx = 20, cy = 40, rowH = 0;
  for (const info of infos) {
    const w = Math.min(W - 40, Math.max(COLW, info.widest * 74));
    const hgt = (info.maxDepth + 1) * ROWH;
    if (cx + w > W - 20) { cx = 20; cy += rowH + PADY; rowH = 0; }
    const gap = w / Math.max(info.widest, 1);
    for (const [d, arr] of Object.entries(info.byD)) {
      arr.forEach((k, i) => { res[k] = { x: cx + gap * (i + 0.5), y: cy + Number(d) * ROWH }; });
    }
    cx += w + PADX;
    rowH = Math.max(rowH, hgt);
  }
  return res;
}

// ── 力导向布局（合作视图）──
function layoutForce(list, edges) {
  const res = {};
  const R = Math.min(W, H) * 0.42;
  list.forEach((k, i) => {
    const a = (i / list.length) * Math.PI * 2;
    const r = R * (0.35 + 0.65 * ((i * 2654435761 % 1000) / 1000));
    res[k] = { x: W / 2 + r * Math.cos(a), y: H / 2 + r * Math.sin(a) };
  });
  const idx = {}; list.forEach((k, i) => idx[k] = i);
  const N2 = list.length;
  const eIdx = edges.map(e => [idx[e.s], idx[e.t], e.n || 1]).filter(x => x[0] !== undefined && x[1] !== undefined);
  const px = new Float32Array(N2), py = new Float32Array(N2);
  list.forEach((k, i) => { px[i] = res[k].x; py[i] = res[k].y; });
  const k1 = Math.sqrt((W * H) / Math.max(N2, 1)) * 0.55;
  for (let it = 0; it < 260; it++) {
    const dx = new Float32Array(N2), dy = new Float32Array(N2);
    // 斥力（均匀采样近似，避免 O(n²) 卡死）
    const step = Math.max(1, Math.floor(N2 / 420));
    for (let i = 0; i < N2; i++) for (let j = i + 1; j < N2; j += step) {
      let vx = px[i] - px[j], vy = py[i] - py[j];
      let d2 = vx * vx + vy * vy; if (d2 < 1) { d2 = 1; vx = 0.7; vy = 0.5; }
      const d = Math.sqrt(d2), f = (k1 * k1) / d;
      dx[i] += (vx / d) * f; dy[i] += (vy / d) * f;
      dx[j] -= (vx / d) * f; dy[j] -= (vy / d) * f;
    }
    // 引力
    for (const [a, b, w] of eIdx) {
      let vx = px[a] - px[b], vy = py[a] - py[b];
      const d = Math.sqrt(vx * vx + vy * vy) || 1;
      const f = (d * d) / (k1 * 2.2) * Math.min(2, 0.6 + w * 0.12);
      dx[a] -= (vx / d) * f; dy[a] -= (vy / d) * f;
      dx[b] += (vx / d) * f; dy[b] += (vy / d) * f;
    }
    const cool = 0.28 * (1 - it / 300);
    for (let i = 0; i < N2; i++) {
      px[i] += Math.max(-26, Math.min(26, dx[i] * cool));
      py[i] += Math.max(-26, Math.min(26, dy[i] * cool));
      px[i] = Math.max(30, Math.min(W - 30, px[i]));
      py[i] = Math.max(30, Math.min(H - 30, py[i]));
    }
  }
  list.forEach((k, i) => { res[k] = { x: px[i], y: py[i] }; });
  return res;
}

let G = null;
function rebuild(keepPos) {
  G = buildGraph();
  const fresh = view === 'collab' ? layoutForce(G.list, G.edges) : layoutLineage(G.list, G);
  if (keepPos && Object.keys(pos).length) {
    for (const k of G.list) if (!pos[k]) pos[k] = fresh[k];
  } else pos = fresh;
  $('sN').textContent = G.list.length;
  $('sA').textContent = G.edges.filter(e => e.k === 'adv').length;
  $('sC').textContent = G.edges.filter(e => e.k === 'col').length;
  $('sS').textContent = G.edges.filter(e => e.k === 'sib').length;
  render();
}

function radius(k) { const p = N[k]?.p || 0; return 4 + Math.min(13, Math.sqrt(p) * 1.15); }
function colorOf(k) { return COL[N[k]?.s] || '#64748b'; }

function render() {
  if (!G) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#0f1117'; ctx.fillRect(0, 0, W, H);
  ctx.setTransform(scale, 0, 0, scale, ox, oy);
  const inSet = new Set(G.list);

  // 边
  for (const e of G.edges) {
    const a = pos[e.s], b = pos[e.t]; if (!a || !b) continue;
    if (e.k === 'adv') {
      ctx.strokeStyle = e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
      ctx.lineWidth = (e.lv === 1 ? 2.6 : e.lv === 2 ? 1.8 : 1.0) + Math.min(2.0, (e.n || 2) * 0.2);
      ctx.setLineDash([]);
      arrow(a, b);
    } else if (e.k === 'col') {
      ctx.strokeStyle = 'rgba(59,130,246,' + Math.min(0.5, 0.1 + e.n * 0.035) + ')';
      ctx.lineWidth = 0.5 + Math.min(2.4, e.n * 0.16);
      ctx.setLineDash([]);
      line(a, b);
    } else {
      ctx.strokeStyle = 'rgba(16,185,129,0.3)';
      ctx.lineWidth = 0.7; ctx.setLineDash([3, 3]);
      line(a, b);
    }
  }
  ctx.setLineDash([]);

  // 节点
  for (const k of G.list) {
    const p = pos[k]; if (!p) continue;
    const r = radius(k);
    if (k === sel || k === hover) {
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 6, 0, 7);
      ctx.fillStyle = k === sel ? 'rgba(245,158,11,.28)' : 'rgba(255,255,255,.13)'; ctx.fill();
    }
    ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 7);
    ctx.fillStyle = colorOf(k); ctx.fill();
    ctx.strokeStyle = 'rgba(15,17,23,.85)'; ctx.lineWidth = 1.1; ctx.stroke();
    if (scale > 0.62 || k === sel || k === hover || (N[k]?.p || 0) > 60) {
      ctx.fillStyle = k === sel ? '#fbbf24' : '#cbd5e1';
      ctx.font = (k === sel || k === hover ? 'bold ' : '') + '11px -apple-system,"Microsoft YaHei",sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(NAME(k), p.x, p.y - r - 4);
    }
  }
  void inSet;
}
function line(a, b) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
function arrow(a, b) {
  // 由导师(a=mentor? 见 buildGraph: s=学生,t=导师) —— 这里 e.s=学生, e.t=导师
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  const ang = Math.atan2(b.y - a.y, b.x - a.x), L = 9;
  const ex = b.x - Math.cos(ang) * (radius(argOf(b)) + 3), ey = b.y - Math.sin(ang) * (radius(argOf(b)) + 3);
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex - L * Math.cos(ang - 0.4), ey - L * Math.sin(ang - 0.4));
  ctx.lineTo(ex - L * Math.cos(ang + 0.4), ey - L * Math.sin(ang + 0.4));
  ctx.closePath(); ctx.fillStyle = ctx.strokeStyle; ctx.fill();
}
function argOf(p) { for (const k in pos) if (pos[k] === p) return k; return null; }

// ── 交互 ──
function resize() {
  const dpr = window.devicePixelRatio || 1;
  const r = $('main').getBoundingClientRect();
  W = r.width; H = r.height;
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.width = W + 'px'; cv.style.height = H + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.scale(1, 1);
  rebuild(true);
}
window.addEventListener('resize', resize);
let drag = null;
cv.addEventListener('mousedown', e => { drag = { x: e.clientX, y: e.clientY, ox, oy, moved: false }; });
window.addEventListener('mousemove', e => {
  if (drag) {
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    ox = drag.ox + dx; oy = drag.oy + dy; render(); return;
  }
  const k = pick(e); const tip = $('tip');
  if (k !== hover) { hover = k; render(); }
  if (k) {
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY + 14) + 'px';
    tip.innerHTML = '<b>' + NAME(k) + '</b><br/>' + SCHOOL(k) + ' · ' + (N[k].t || '—') + '<br/>论文 ' + (N[k].p || 0) + ' 篇';
  } else tip.style.display = 'none';
});
window.addEventListener('mouseup', e => {
  if (drag && !drag.moved) { const k = pick(e); if (k) select(k); else { sel = null; $('panel').style.display = 'none'; render(); } }
  drag = null;
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const f = e.deltaY < 0 ? 1.12 : 0.89;
  const r = cv.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  ox = mx - (mx - ox) * f; oy = my - (my - oy) * f; scale *= f;
  render();
}, { passive: false });
cv.addEventListener('dblclick', () => { scale = 1; ox = 0; oy = 0; sel = null; $('panel').style.display = 'none'; rebuild(true); });

function pick(e) {
  const r = cv.getBoundingClientRect();
  const x = (e.clientX - r.left - ox) / scale, y = (e.clientY - r.top - oy) / scale;
  let best = null, bd = 1e9;
  for (const k of G.list) {
    const p = pos[k]; if (!p) continue;
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d < (radius(k) + 4) ** 2 && d < bd) { bd = d; best = k; }
  }
  return best;
}

function select(k) {
  sel = k; render();
  const st = G.studentsOf[k] || [], me = G.mentorOf[k] || [];
  const cols = COLB.filter(e => (e.s === k || e.t === k) && e.n >= 2)
    .map(e => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 30);
  const sib = [];
  for (const m of me) for (const s of (G.studentsOf[m] || [])) if (s !== k) sib.push({ s, m });
  const L = (arr, f) => arr.length ? arr.map(f).join('') : '<span style="color:#4b5563">—</span>';
  const N2 = N[k] || {};
  // 师徒边的证据等级标签
  const lvTag = (other, dir) => {
    const e = ADV.find(x => (dir === 'up' ? (x.s === k && x.t === other) : (x.t === k && x.s === other)));
    if (!e) return '';
    const c = e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
    const t = e.lv === 1 ? 'L1 自述' : e.lv === 2 ? 'L2 交叉' : 'L3 推断';
    const title = (e.nt || '').replace(/"/g, '&quot;');
    return '<span title="' + title + '" style="color:' + c + ';font-size:10px;margin-left:3px">' + t + '</span>';
  };
  const eduHtml = (N2.edu && N2.edu.length) ? N2.edu.map(x => '<div style="font-size:11.5px;color:#9ca3af">· ' + x + '</div>').join('') : '';
  const pdHtml = (N2.pd && N2.pd.length) ? N2.pd.map(x => '<div style="font-size:11.5px;color:#9ca3af">· ' + x + '（博士后）</div>').join('') : '';
  const jobHtml = (N2.job && N2.job.length) ? N2.job.map(x => '<div style="font-size:11.5px;color:#9ca3af">· ' + x + '</div>').join('') : '';
  const teamHtml = (N2.team && N2.team.length) ? N2.team.map(x => '<span class="tag">' + x + '</span>').join('') : '';
  $('panel').style.display = 'block';
  $('panel').innerHTML =
    '<h3>' + NAME(k) + '</h3>' +
    '<div style="font-size:12px;color:#9ca3af">' + SCHOOL(k) + ' · ' + (N2.t || '—') + '</div>' +
    '<div style="font-size:12px;color:#6b7280">' + (N2.d || '') + '</div>' +
    '<div style="margin-top:7px">' +
      '<span class="tag">论文 ' + (N2.p || 0) + ' 篇</span>' +
      (N2.c ? '<span class="tag">' + N2.c.slice(0, 40) + '</span>' : '') +
    '</div>' +
    (N2.h ? '<div style="margin-top:6px"><a href="' + N2.h + '" target="_blank" style="color:#60a5fa;font-size:12px">打开主页 ↗</a></div>' : '') +
    (eduHtml || pdHtml || jobHtml ? '<div class="rel"><b>学历与工作经历（页面自述）</b>' + eduHtml + pdHtml + jobHtml + '</div>' : '') +
    '<div class="rel"><b>导师（' + me.length + '）</b>' + L(me, m => '<a data-k="' + m + '">' + NAME(m) + '</a>' + lvTag(m, 'up')) + '</div>' +
    '<div class="rel"><b>学生（' + st.length + '）</b>' + L(st, s => '<a data-k="' + s + '">' + NAME(s) + '</a>' + lvTag(s, 'down')) + '</div>' +
    (sib.length ? '<div class="rel"><b>同门（' + sib.length + '）</b>' + L(sib.slice(0, 40), x => '<a data-k="' + x.s + '">' + NAME(x.s) + '</a>') + '</div>' : '') +
    (teamHtml ? '<div class="rel"><b>课题组名单（页面所列）</b>' + teamHtml + '</div>' : '') +
    '<div class="rel"><b>主要合作者（共同署名篇数）</b>' + L(cols, c => '<a data-k="' + c.k + '">' + NAME(c.k) + ' <span style="color:#6b7280">' + c.n + '</span></a>') + '</div>' +
    '<div style="margin-top:10px;font-size:10.5px;color:#4b5563;line-height:1.6">L1 自述师承＝本人页面明写；L2＝毕业院校与论文署名两条独立证据交叉；L3＝仅署名模式推断，无学历佐证。鼠标悬停标签可看具体依据。</div>';
  $('panel').querySelectorAll('a[data-k]').forEach(a => a.onclick = () => select(a.dataset.k));
}

// ── 控件 ──
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  t.classList.add('on'); view = t.dataset.v; pos = {}; rebuild(false);
});
$('q').addEventListener('input', e => {
  const v = e.target.value.trim();
  const res = $('qres');
  if (!v) { res.textContent = ''; return; }
  const hits = Object.keys(N).filter(k => NAME(k).includes(v)).slice(0, 8);
  res.innerHTML = hits.length ? hits.map(k => '<a data-k="' + k + '" style="color:#60a5fa;cursor:pointer;margin-right:8px">' + NAME(k) + '(' + SCHOOL(k) + ')</a>').join('') : '<span style="color:#6b7280">无匹配</span>';
  res.querySelectorAll('a[data-k]').forEach(a => a.onclick = () => { select(a.dataset.k); const p = pos[a.dataset.k]; if (p) { ox = W / 2 - p.x * scale; oy = H / 2 - p.y * scale; render(); } });
});
const schools = [...new Set(Object.values(N).map(x => x.s))].sort();
for (const s of schools) { const o = document.createElement('option'); o.value = s; o.textContent = s; $('school').appendChild(o); }
$('school').onchange = e => { schoolF = e.target.value; rebuild(true); };
$('w').oninput = e => { minW = +e.target.value; $('wv').textContent = minW; if (view === 'collab') rebuild(true); else render(); };
$('showAdv').onchange = e => { showAdv = e.target.checked; rebuild(true); };
$('showSib').onchange = e => { showSib = e.target.checked; rebuild(true); };
$('hideAlone').onchange = e => { hideAlone = e.target.checked; rebuild(true); };

resize();
</script></body></html>`;

fs.writeFileSync(path.join(REPO, 'reports', '导师关系网络.html'), html, 'utf8');
console.log('saved reports/导师关系网络.html', (html.length / 1024).toFixed(0) + 'KB');
console.log('节点', Object.keys(nodes).length, '| 师徒', data.advisor.length, '| 合作', data.collab.length, '| 同门', data.sibling.length);
