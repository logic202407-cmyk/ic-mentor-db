// net_html.mjs — 关系网络可视化 v3：按院校分区
//
// 设计动机（用户反馈「太杂乱、关系不明确」）：
//   力导向图与全量树状图都把「跨校流动」这一最有价值的信息淹没在数百条校内关系中。
//   实测：师承子图 431 人分布在 20 所学校，但**跨校师承只有 8 条**。
//
// 新形式：
//   视图1 院校分区族谱 —— 每校一个面板，校内师承画在面板内，跨校师承用高亮曲线跨面板连接
//   视图2 院校关系矩阵 —— 20×20 矩阵，格值 = 两校之间的关系条数，一眼看出人员流动格局
//   视图3 合作网络     —— 保留力导向，但按院校着色聚团
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const net = JSON.parse(fs.readFileSync(path.join(PROC, 'network_final.json'), 'utf8'));

const SHORT = {
  '清华大学深圳国际研究生院': '清华深研院', '清华大学': '清华', '复旦大学': '复旦', '上海交通大学': '上交',
  '浙江大学': '浙大', '南京大学': '南大', '中国科学技术大学': '中科大', '北京大学': '北大',
  '东南大学': '东南', '西安电子科技大学': '西电', '电子科技大学': '成电', '哈尔滨工业大学': '哈工大',
  '天津大学': '天大', '华中科技大学': '华科', '北京航空航天大学': '北航', '西安交通大学': '西交',
  '中国科学院微电子研究所': '中科院微电子所', '中国科学院半导体研究所': '中科院半导体所',
  '中国科学院上海微系统与信息技术研究所': '中科院上海微系统所', '中国科学院计算技术研究所': '中科院计算所',
  '中国科学院自动化研究所': '中科院自动化所', '中国科学院上海高等研究院': '中科院上海高研院',
};
const COLORS = {
  '清华': '#8b5cf6', '清华深研院': '#a78bfa', '北大': '#ef4444', '复旦': '#3b82f6', '上交': '#06b6d4',
  '浙大': '#10b981', '南大': '#eab308', '中科大': '#ec4899', '东南': '#f97316', '西电': '#6366f1',
  '成电': '#14b8a6', '哈工大': '#a855f7', '天大': '#d97706', '华科': '#e11d48', '北航': '#2563eb',
  '西交': '#16a34a', '中科院微电子所': '#94a3b8', '中科院半导体所': '#a8a29e', '中科院上海微系统所': '#9ca3af',
  '中科院计算所': '#78716c', '中科院自动化所': '#6b7280', '中科院上海高研院': '#d4d4d8',
};

const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const paperOf = new Map();
for (const d of ranked) paperOf.set(`${d.school}|${d.name_cn}`, d.n_ic_papers || 0);

const N = {};
for (const [k, p] of Object.entries(net.nodes)) {
  const s = SHORT[p.school] || p.school;
  const pr = net.profile[k] || {};
  N[k] = {
    n: p.name, s, sc: p.school, t: p.title || '', d: p.dept || '', c: p.kw || '', h: p.homepage || '',
    p: paperOf.get(k) || 0,
    edu: (pr.edu || []).map((e) => `${e.year ? e.year + ' ' : ''}${/博士/.test(e.deg) ? '博士' : /硕士/.test(e.deg) ? '硕士' : /学士|本科/.test(e.deg) ? '学士' : '毕业'} ${e.inst}`),
    pd: (pr.postdoc || []).map((e) => `${e.y1}${e.y2 ? '–' + e.y2 : ''} ${e.inst}`),
    job: (pr.jobs || []).map((e) => `${e.year} ${e.org}`),
    team: (pr.roster || []).slice(0, 20),
  };
}
const DATA = {
  meta: net.meta, nodes: N, colors: COLORS, short: SHORT,
  advisor: net.advisor.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: e.lv, sp: e.span || '', nt: e.note || '', inst: e.inst || '', ty: e.type || '' })),
  collab: net.collab.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: 4 })),
  sibling: net.sibling.map((e) => ({ s: e.s, t: e.t, v: e.via })),
};

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>微电子导师关系网络 · 按院校分区</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{font:13px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#0b0e14;color:#e5e7eb}
#app{display:flex;height:100%}
#side{width:308px;flex:0 0 308px;background:#12161f;border-right:1px solid #232936;overflow-y:auto;padding:14px}
#main{flex:1;position:relative;overflow:hidden}
canvas{display:block;cursor:grab}
canvas.drag{cursor:grabbing}
h1{font-size:15px;margin:0 0 3px}
h2{font-size:11px;margin:15px 0 6px;color:#7c8ba1;letter-spacing:.6px;text-transform:uppercase}
.sub{font-size:11px;color:#5a6472;margin-bottom:11px}
.tabs{display:flex;gap:4px;margin-bottom:10px}
.tab{flex:1;padding:7px 2px;text-align:center;background:#1a1f2b;border:1px solid #232936;border-radius:7px;cursor:pointer;font-size:11.5px;color:#8b98a9;transition:.15s}
.tab:hover{background:#212736}
.tab.on{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
label{display:flex;align-items:center;gap:7px;padding:5px 0;cursor:pointer;font-size:12px;color:#c3ccd8}
input[type=checkbox]{accent-color:#2563eb;width:14px;height:14px;cursor:pointer}
input[type=range]{width:100%;accent-color:#2563eb}
input[type=text]{width:100%;padding:7px 9px;background:#0b0e14;border:1px solid #232936;border-radius:6px;color:#e5e7eb;font-size:12px;margin-top:3px}
input[type=text]:focus{outline:none;border-color:#2563eb}
.stat{display:flex;justify-content:space-between;padding:2px 0;font-size:12px;color:#8b98a9}
.stat b{color:#e5e7eb}
.lg{display:flex;align-items:center;gap:8px;padding:3px 0;color:#8b98a9;font-size:11px}
.sw{width:24px;height:0;border-top-width:2px;border-top-style:solid;flex:0 0 24px}
.dot{width:10px;height:10px;border-radius:50%;flex:0 0 10px}
#tip{position:absolute;background:#1a1f2bee;border:1px solid #2f3744;border-radius:8px;padding:8px 11px;font-size:12px;pointer-events:none;display:none;max-width:280px;z-index:20;line-height:1.55;box-shadow:0 6px 20px #0008}
#panel{position:absolute;right:0;top:0;width:342px;height:100%;background:#12161ff2;border-left:1px solid #232936;padding:14px;overflow-y:auto;display:none;backdrop-filter:blur(6px)}
#panel h3{margin:0 0 2px;font-size:15px}
.tag{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;margin:2px 3px 2px 0;background:#1e2430;color:#9aa7b8}
.rel{border-top:1px solid #1e2430;margin-top:9px;padding-top:7px;font-size:12px}
.rel b{color:#7c8ba1;font-weight:600;display:block;margin-bottom:4px;font-size:11px}
.rel a{color:#60a5fa;cursor:pointer;text-decoration:none;margin-right:9px;display:inline-block;line-height:1.9}
.rel a:hover{text-decoration:underline}
#bar{position:absolute;left:12px;bottom:11px;font-size:11px;color:#4b5563;background:#0b0e14cc;padding:5px 10px;border-radius:6px}
#zoom{position:absolute;right:12px;bottom:11px;display:flex;gap:6px;align-items:center;background:#12161fdd;border:1px solid #232936;border-radius:8px;padding:5px 9px;font-size:11px;color:#8b98a9}
#zoom button{background:#1e2430;border:1px solid #2f3744;color:#c3ccd8;border-radius:5px;width:24px;height:22px;cursor:pointer;font-size:13px;line-height:1}
#zoom button:hover{background:#2a3242}
.warn{background:#78350f1a;border:1px solid #92400e;border-radius:7px;padding:8px 10px;font-size:11px;color:#fbbf24;line-height:1.65;margin-top:9px}
.warn b{color:#fcd34d}
.cross{border-left:3px solid #f472b6;padding-left:8px;margin:8px 0;font-size:11.5px;color:#c3ccd8;line-height:1.75}
.cross i{color:#f472b6;font-style:normal}
</style></head><body>
<div id="app">
  <div id="side">
    <h1>微电子导师关系网络</h1>
    <div class="sub">31,689 条共同署名记录 · 姓名+机构双校验</div>
    <div class="tabs">
      <div class="tab on" data-v="school">院校分区</div>
      <div class="tab" data-v="matrix">关系矩阵</div>
      <div class="tab" data-v="force">合作网络</div>
    </div>

    <h2>搜索</h2>
    <input type="text" id="q" placeholder="输入导师姓名…"/>
    <div id="qres" style="font-size:11px;color:#5a6472;margin-top:5px;line-height:1.9"></div>

    <h2>过滤</h2>
    <label><input type="checkbox" id="onlyCross"> <b style="color:#f472b6">只看跨校关系</b></label>
    <label><input type="checkbox" id="showAdv" checked> 显示师承关系</label>
    <label><input type="checkbox" id="showSib" checked> 显示同门关系</label>
    <div id="wWrap" style="display:none">
      <div style="font-size:11px;color:#7c8ba1;margin-top:8px">最小合作篇数：<b id="wv" style="color:#e5e7eb">5</b></div>
      <input type="range" id="w" min="2" max="25" value="5"/>
    </div>

    <div id="crossBox"></div>

    <h2>图例</h2>
    <div class="lg"><div class="sw" style="border-color:#fbbf24;border-top-width:3px"></div>L1 自述师承（页面明写）</div>
    <div class="lg"><div class="sw" style="border-color:#f59e0b;border-top-width:2px"></div>L2 学历×论文交叉证据</div>
    <div class="lg"><div class="sw" style="border-color:#a16207"></div>L3 署名推断</div>
    <div class="lg"><div class="sw" style="border-color:#f472b6;border-top-width:3px"></div><b style="color:#f472b6">跨校师承</b></div>
    <div class="lg"><div class="sw" style="border-color:#10b981;border-top-style:dotted"></div>同门</div>

    <h2>统计</h2>
    <div class="stat"><span>当前显示节点</span><b id="sN">0</b></div>
    <div class="stat"><span>师承关系</span><b id="sA">0</b></div>
    <div class="stat"><span>其中跨校</span><b id="sX" style="color:#f472b6">0</b></div>
    <div class="stat"><span>同门关系</span><b id="sS">0</b></div>

    <div class="warn">
      <b>关系判定依据</b><br/>
      <b style="color:#fbbf24">L1</b>：本人页面<b>明写</b>「导师为／师从 XX」。<br/>
      <b style="color:#f59e0b">L2</b>：页面自述<b>毕业院校</b>＋该院校教授在其<b>早期论文中固定为末位作者</b>。<br/>
      <b style="color:#a16207">L3</b>：仅署名模式推断，<b>无学历佐证</b>。<br/>
      图上位置＝<b>现所在院校</b>；箭头由导师指向学生。<br/>
      本图只反映公开页面自述与论文署名可推断的关系，<b>不代表完整师承，也不构成任何评价</b>。
    </div>
  </div>
  <div id="main">
    <canvas id="cv"></canvas>
    <div id="tip"></div>
    <div id="panel"></div>
    <div id="bar">滚轮缩放 · 拖拽平移 · 点击节点看档案 · 双击适应窗口</div>
    <div id="zoom"><button id="zin">+</button><button id="zout">−</button><span id="zlv">100%</span></div>
  </div>
</div>
<script>
const DATA = ${JSON.stringify(DATA)};
const N = DATA.nodes, COL = DATA.colors, ADV = DATA.advisor, COLB = DATA.collab, SIB = DATA.sibling;
const $ = id => document.getElementById(id);
const NAME = k => (N[k] ? N[k].n : k);
const SCH = k => (N[k] ? N[k].s : '?');
const NP = k => (N[k] ? (N[k].p || 0) : 0);

const cv = $('cv'), ctx = cv.getContext('2d');
let W = 0, H = 0, DPR = 1;
let view = 'school', minW = 5, showAdv = true, showSib = true, onlyCross = false;
let pos = {}, panels = [], sel = null, hover = null, G = null, rank = {};
let scale = 1, ox = 0, oy = 0;

// ══════════ 通用：自适应视口 ══════════
function fitView(pad = 40) {
  const xs = [], ys = [];
  for (const k of G.list) { const p = pos[k]; if (p) { xs.push(p.x); ys.push(p.y); } }
  if (!xs.length) return;
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const gw = Math.max(x1 - x0, 1), gh = Math.max(y1 - y0, 1);
  scale = Math.max(0.05, Math.min((W - pad * 2) / gw, (H - pad * 2) / gh, 3));
  ox = (W - gw * scale) / 2 - x0 * scale;
  oy = (H - gh * scale) / 2 - y0 * scale;
  $('zlv').textContent = Math.round(scale * 100) + '%';
}

// ══════════ 建图 ══════════
function buildGraph() {
  const mentorOf = {}, studentsOf = {};
  const set = new Set(), edges = [];
  const isCross = (e) => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc;
  if (showAdv) {
    for (const e of ADV) {
      if (!N[e.s] || !N[e.t]) continue;
      if (onlyCross && !isCross(e)) continue;
      edges.push({ ...e, k: 'adv', cross: isCross(e) }); set.add(e.s); set.add(e.t);
      (mentorOf[e.s] = mentorOf[e.s] || []).push(e.t);
      (studentsOf[e.t] = studentsOf[e.t] || []).push(e.s);
    }
  }
  if (showSib) {
    for (const e of SIB) {
      if (!N[e.s] || !N[e.t]) continue;
      if (onlyCross && !isCross(e)) continue;
      edges.push({ ...e, k: 'sib', cross: isCross(e) }); set.add(e.s); set.add(e.t);
    }
  }
  if (view === 'force') {
    for (const e of COLB) {
      if (e.n < minW || !N[e.s] || !N[e.t]) continue;
      edges.push({ ...e, k: 'col', cross: isCross(e) }); set.add(e.s); set.add(e.t);
    }
  }
  let list = [...set];
  const deg = {};
  for (const e of edges) { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.t] = (deg[e.t] || 0) + 1; }
  list = list.filter((k) => deg[k]);
  const ls = new Set(list);
  return { list, edges: edges.filter((e) => ls.has(e.s) && ls.has(e.t)), mentorOf, studentsOf };
}

// ══════════ 视图1：院校分区族谱 ══════════
function layoutSchool(list, g) {
  const bySchool = {};
  for (const k of list) (bySchool[SCH(k)] = bySchool[SCH(k)] || []).push(k);
  // HEAD 需容纳「面板标题条」+ 首行节点标签（标签在节点上方约 17px）
  const HEAD = 52, PADX = 22, PADY = 16, LABELPAD = 22;
  const DX = 96, DY = 104, CGX = 44, CGY = 34;

  // 每个学校内部：求连通分量 -> 每分量做树形布局
  const blocks = [];
  for (const [school, mem] of Object.entries(bySchool)) {
    const mset = new Set(mem);
    const adj = {}; for (const k of mem) adj[k] = new Set();
    for (const e of g.edges) if (mset.has(e.s) && mset.has(e.t)) { adj[e.s].add(e.t); adj[e.t].add(e.s); }
    const comp = {}, comps = [];
    for (const k of mem) {
      if (comp[k] !== undefined) continue;
      const cid = comps.length, st = [k], m2 = []; comp[k] = cid;
      while (st.length) { const x = st.pop(); m2.push(x); for (const y of adj[x]) if (comp[y] === undefined) { comp[y] = cid; st.push(y); } }
      comps.push(m2);
    }
    comps.sort((a, b) => b.length - a.length);
    const local = [];
    let lx = 0, rowH = 0, maxX = 0;
    for (const cm of comps) {
      const cset = new Set(cm);
      const depth = {};
      const roots = cm.filter((k) => !(g.mentorOf[k] || []).some((m) => cset.has(m)));
      const q = (roots.length ? roots : [cm[0]]).map((k) => [k, 0]);
      const seen = new Set(q.map((x) => x[0]));
      while (q.length) { const [k, d] = q.shift(); depth[k] = d; for (const s of (g.studentsOf[k] || [])) if (cset.has(s) && !seen.has(s)) { seen.add(s); q.push([s, d + 1]); } }
      for (const k of cm) if (depth[k] === undefined) depth[k] = 0;
      // 环安全的后代数
      const sub = {};
      for (const k of cm) {
        const s2 = new Set([k]); const st = [...(g.studentsOf[k] || [])].filter((x) => cset.has(x)); let c = 0;
        while (st.length) { const x = st.pop(); if (s2.has(x)) continue; s2.add(x); c++; for (const y of (g.studentsOf[x] || [])) if (cset.has(y) && !s2.has(y)) st.push(y); }
        sub[k] = c;
      }
      const byD = {};
      for (const k of cm) (byD[depth[k]] = byD[depth[k]] || []).push(k);
      for (const d of Object.keys(byD)) byD[d].sort((a, b) => sub[b] - sub[a] || NP(b) - NP(a));
      const rows = Object.keys(byD).map(Number).sort((a, b) => a - b);
      const widest = Math.max(...rows.map((d) => byD[d].length));
      const cw = Math.max(1, widest) * DX;
      const chh = (rows[rows.length - 1] + 1) * DY;
      if (lx > 0 && lx + cw > 900) { lx = 0; }
      for (const d of rows) {
        const arr = byD[d], rw = arr.length * DX;
        const x0 = lx + (cw - rw) / 2 + DX / 2;
        arr.forEach((k, i) => local.push({ k, x: x0 + i * DX, y: LABELPAD + d * DY }));
      }
      lx += cw + CGX; maxX = Math.max(maxX, lx);
      rowH = Math.max(rowH, chh + CGY);
      void rowH;
    }
    const w = Math.max(maxX, DX) + PADX * 2;
    const h = (local.length ? Math.max(...local.map((p) => p.y)) + DY * 0.55 : DY) + PADY * 2 + HEAD;
    blocks.push({ school, mem, local, w, h, color: COL[school] || '#64748b' });
  }

  // 面板打包：按面积降序，shelf 排布，宽度搜索贴合画布
  blocks.sort((a, b) => b.w * b.h - a.w * a.h);
  const pack = (MAXW) => {
    let cx = 0, cy = 0, rowH = 0, maxRowW = 0;
    const place = [];
    for (const b of blocks) {
      if (cx > 0 && cx + b.w > MAXW) { maxRowW = Math.max(maxRowW, cx - 16); cx = 0; cy += rowH + 16; rowH = 0; }
      place.push({ b, x: cx, y: cy });
      cx += b.w + 16; rowH = Math.max(rowH, b.h);
    }
    maxRowW = Math.max(maxRowW, cx - 16);
    return { place, w: maxRowW, h: cy + rowH };
  };
  const target = (W && H) ? W / H : 1.58;
  const totalW = blocks.reduce((a, b) => a + b.w + 16, 0) || 1;
  let best = null;
  for (let t = 0; t <= 44; t++) {
    const MAXW = Math.max(900, totalW * (0.06 + t * 0.022));
    const r = pack(MAXW);
    const sc = Math.abs(Math.log((r.w / Math.max(r.h, 1)) / target)) + (r.w * r.h) / 4e7;
    if (!best || sc < best.sc) best = { sc, ...r };
  }
  const res = {};
  panels = [];
  for (const { b, x, y } of best.place) {
    for (const p of b.local) res[p.k] = { x: x + p.x, y: y + p.y + HEAD };
    panels.push({ school: b.school, x, y, w: b.w, h: b.h, color: b.color, n: b.mem.length });
  }
  return res;
}

// ══════════ 视图3：力导向（含 Barnes-Hut） ══════════
function buildTree(px, py, n) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) { if (px[i] < x0) x0 = px[i]; if (px[i] > x1) x1 = px[i]; if (py[i] < y0) y0 = py[i]; if (py[i] > y1) y1 = py[i]; }
  const size = Math.max(x1 - x0, y1 - y0, 1);
  const root = { x0: x0 - size * .05, y0: y0 - size * .05, s: size * 1.1, m: 0, cx: 0, cy: 0, c: null, i: -1 };
  const ins = (node, i) => {
    if (node.c === null) {
      if (node.m === 0) { node.i = i; node.m = 1; node.cx = px[i]; node.cy = py[i]; return; }
      const oi = node.i; node.i = -1; node.c = [null, null, null, null];
      const half = node.s / 2;
      const q = (x, y) => (x >= node.x0 + half ? 1 : 0) + (y >= node.y0 + half ? 2 : 0);
      const oq = q(px[oi], py[oi]);
      node.c[oq] = { x0: node.x0 + (oq & 1 ? half : 0), y0: node.y0 + (oq & 2 ? half : 0), s: half, m: 1, cx: px[oi], cy: py[oi], c: null, i: oi };
      ins(node, i); return;
    }
    const half = node.s / 2;
    const q = (px[i] >= node.x0 + half ? 1 : 0) + (py[i] >= node.y0 + half ? 2 : 0);
    if (!node.c[q]) node.c[q] = { x0: node.x0 + (q & 1 ? half : 0), y0: node.y0 + (q & 2 ? half : 0), s: half, m: 0, cx: 0, cy: 0, c: null, i: -1 };
    ins(node.c[q], i);
  };
  const acc = (node) => {
    if (node.c === null) { if (node.i >= 0) { node.m = 1; node.cx = px[node.i]; node.cy = py[node.i]; } return node.m; }
    let m = 0, sx = 0, sy = 0;
    for (const ch of node.c) if (ch) { const cm = acc(ch); m += cm; sx += ch.cx * cm; sy += ch.cy * cm; }
    node.m = m; if (m) { node.cx = sx / m; node.cy = sy / m; }
    return m;
  };
  for (let i = 0; i < n; i++) ins(root, i);
  acc(root); return root;
}
function bhForce(node, i, px, py, theta, out) {
  if (node.m === 0) return;
  const dx = px[i] - node.cx, dy = py[i] - node.cy;
  const d2 = dx * dx + dy * dy + 1e-6;
  if (node.c === null || (node.s * node.s) / d2 < theta * theta) {
    if (node.c === null && node.i === i) return;
    const d = Math.sqrt(d2); const f = node.m / d2;
    out.x += (dx / d) * f; out.y += (dy / d) * f; return;
  }
  for (const ch of node.c) if (ch) bhForce(ch, i, px, py, theta, out);
}
function layoutForce(list, edges) {
  const n = list.length;
  const px = new Float32Array(n), py = new Float32Array(n), idx = {};
  list.forEach((k, i) => { idx[k] = i; });
  // 初始按院校分簇，让同校自然聚在一起
  const byS = {};
  list.forEach((k) => (byS[SCH(k)] = byS[SCH(k)] || []).push(k));
  const schools = Object.keys(byS);
  const R0 = Math.sqrt(n) * 24;
  schools.forEach((s, si) => {
    const a = (si / schools.length) * Math.PI * 2, r = R0 * (0.35 + 0.65 * ((si * 2654435761 % 1000) / 1000));
    const cx0 = Math.cos(a) * r, cy0 = Math.sin(a) * r, arr = byS[s];
    arr.forEach((k, i) => {
      const ang = i * 2.399963, rr = 26 * Math.sqrt(i + 0.5);
      px[idx[k]] = cx0 + Math.cos(ang) * rr; py[idx[k]] = cy0 + Math.sin(ang) * rr;
    });
  });
  const E = [];
  for (const e of edges) { const a = idx[e.s], b = idx[e.t]; if (a === undefined || b === undefined) continue; E.push([a, b, Math.min(4, 1 + (e.n || 1) * 0.25)]); }
  const k0 = Math.max(16, Math.min(80, 820 / Math.sqrt(n)));
  const ITER = n > 1800 ? 190 : n > 900 ? 280 : 400;
  const out = { x: 0, y: 0 };
  let temp = k0 * 1.6;
  for (let it = 0; it < ITER; it++) {
    const tree = buildTree(px, py, n);
    const fx = new Float32Array(n), fy = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      out.x = 0; out.y = 0; bhForce(tree, i, px, py, 0.9, out);
      const d = Math.hypot(out.x, out.y) + 1e-9, cap = 900;
      fx[i] += Math.max(-cap, Math.min(cap, out.x / d * (k0 * k0)));
      fy[i] += Math.max(-cap, Math.min(cap, out.y / d * (k0 * k0)));
    }
    for (const [a, b, w] of E) {
      const dx = px[a] - px[b], dy = py[a] - py[b], d = Math.hypot(dx, dy) + 1e-6;
      const f = (d * d) / (k0 * 1.1) * w * 0.55;
      fx[a] -= dx / d * f; fy[a] -= dy / d * f; fx[b] += dx / d * f; fy[b] += dy / d * f;
    }
    for (let i = 0; i < n; i++) {
      const d = Math.hypot(px[i], py[i]) + 1e-6;
      fx[i] -= px[i] * 0.012; fy[i] -= py[i] * 0.012; void d;
    }
    for (let i = 0; i < n; i++) {
      const d = Math.hypot(fx[i], fy[i]) + 1e-9, step = Math.min(d, temp);
      px[i] += fx[i] / d * step; py[i] += fy[i] / d * step;
    }
    let mx = 0, my = 0; for (let i = 0; i < n; i++) { mx += px[i]; my += py[i]; }
    mx /= n; my /= n; for (let i = 0; i < n; i++) { px[i] -= mx; py[i] -= my; }
    temp = Math.max(k0 * 0.12, temp * 0.975);
  }
  const res = {}; list.forEach((k, i) => { res[k] = { x: px[i], y: py[i] }; });
  return res;
}

// ══════════ 视图2：院校关系矩阵 ══════════
let M = null;
function buildMatrix() {
  const schools = [...new Set(G.list.map(SCH))].sort();
  const cnt = {}, pairs = {};
  for (const e of G.edges) {
    const a = SCH(e.s), b = SCH(e.t);
    if (a === b) { cnt[a + '|' + a] = (cnt[a + '|' + a] || 0) + 1; continue; }
    const k = [a, b].sort().join('|');
    cnt[k] = (cnt[k] || 0) + 1;
    (pairs[k] = pairs[k] || []).push(e);
  }
  let maxOff = 1, maxDiag = 1;
  for (const [k, v] of Object.entries(cnt)) {
    const [a, b] = k.split('|');
    if (a === b) maxDiag = Math.max(maxDiag, v); else maxOff = Math.max(maxOff, v);
  }
  const CELL = Math.max(22, Math.min(40, 720 / Math.max(schools.length, 1)));
  const LEFT = 96, TOP = 96;
  const res = {};
  panels = [];
  for (let i = 0; i < schools.length; i++) {
    for (let j = 0; j < schools.length; j++) {
      const a = schools[i], b = schools[j];
      const k = [a, b].sort().join('|');
      const v = cnt[k] || 0;
      panels.push({ mi: i, mj: j, a, b, v, x: LEFT + j * CELL, y: TOP + i * CELL, s: CELL, diag: a === b, list: pairs[k] || [] });
    }
  }
  res._schools = schools; res._cell = CELL; res._left = LEFT; res._top = TOP;
  res._maxOff = maxOff; res._maxDiag = maxDiag;
  M = res;
  return res;
}

// ══════════ 重建 ══════════
function computeRank() {
  rank = {};
  G.list.slice().sort((a, b) => NP(b) - NP(a)).forEach((k, i) => { rank[k] = i; });
}
function rebuild(refit) {
  G = buildGraph();
  if (view === 'school') { pos = layoutSchool(G.list, G); }
  else if (view === 'force') { pos = layoutForce(G.list, G.edges); panels = []; }
  else { buildMatrix(); pos = {}; }
  computeRank();
  $('sN').textContent = view === 'matrix' ? (M ? M._schools.length : 0) : G.list.length;
  $('sA').textContent = G.edges.filter((e) => e.k === 'adv').length;
  $('sX').textContent = G.edges.filter((e) => e.k === 'adv' && e.cross).length;
  $('sS').textContent = G.edges.filter((e) => e.k === 'sib').length;
  if (refit) fitView(view === 'matrix' ? 30 : 40);
  render();
}

const radius = (k) => 5 + Math.min(13, Math.sqrt(NP(k)) * 1.12);
const colorOf = (k) => COL[SCH(k)] || '#64748b';

// ══════════ 渲染 ══════════
function render() {
  if (!G) return;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, W, H);
  if (view === 'matrix') { renderMatrix(); return; }
  ctx.setTransform(DPR * scale, 0, 0, DPR * scale, DPR * ox, DPR * oy);

  // 院校面板底板
  if (view === 'school') {
    for (const p of panels) {
      ctx.fillStyle = p.color + '12';
      ctx.strokeStyle = p.color + '55';
      ctx.lineWidth = 1.4 / Math.max(scale, .3);
      roundRect(p.x, p.y, p.w, p.h, 12); ctx.fill(); ctx.stroke();
    }
  }

  // 边
  // 跨校边数量不多但跨度大，默认淡显避免画面被长曲线割碎；
  // 选中某节点时，与它相关的跨校边恢复高亮。
  const selTouch = (e) => sel && (e.s === sel || e.t === sel);
  for (const e of G.edges) {
    const a = pos[e.s], b = pos[e.t]; if (!a || !b) continue;
    if (e.k === 'adv') {
      const isCross = e.cross;
      const lit = selTouch(e);
      const base = e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
      const col = isCross ? (lit ? '#f472b6' : 'rgba(244,114,182,.42)') : (sel && !lit ? 'rgba(120,113,108,.35)' : base);
      ctx.strokeStyle = col;
      const wBase = isCross ? (lit ? 2.8 : 1.5) : (e.lv === 1 ? 2.4 : e.lv === 2 ? 1.7 : 0.9);
      ctx.lineWidth = wBase / Math.max(scale, .3) + Math.min(1.6, (e.n || 2) * .16) * (isCross ? 0.4 : 1);
      ctx.setLineDash([]);
      arrow(a, b, radius(e.t) + (isCross && lit ? 3 : 0), col === 'rgba(244,114,182,.42)' ? '#f472b6' : col);
    } else if (e.k === 'col') {
      ctx.strokeStyle = 'rgba(99,102,241,' + Math.min(.5, .1 + e.n * .035) + ')';
      ctx.lineWidth = (.6 + Math.min(2, e.n * .14)) / Math.max(scale, .35);
      ctx.setLineDash([]); line(a, b);
    } else {
      // 同门边：跨校的稍微显一点，否则很淡
      ctx.strokeStyle = e.cross ? 'rgba(16,185,129,.4)' : 'rgba(16,185,129,.2)';
      ctx.lineWidth = .8 / Math.max(scale, .35); ctx.setLineDash([3, 3]); line(a, b);
    }
  }
  ctx.setLineDash([]);

  // 节点
  for (const k of G.list) {
    const p = pos[k]; if (!p) continue;
    const r = radius(k);
    if (k === sel || k === hover) {
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 7, 0, 7);
      ctx.fillStyle = k === sel ? 'rgba(251,191,36,.32)' : 'rgba(255,255,255,.15)'; ctx.fill();
    }
    ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 7);
    ctx.fillStyle = colorOf(k); ctx.fill();
    ctx.strokeStyle = 'rgba(11,14,20,.92)'; ctx.lineWidth = 1.3 / Math.max(scale, .35); ctx.stroke();
  }

  // 标签（屏幕坐标，恒定字号）
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  const FS = 11.5;
  ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';

  // 面板标题（在屏幕坐标画，保证可读）
  if (view === 'school') {
    for (const p of panels) {
      const x = p.x * scale + ox, y = p.y * scale + oy;
      const w = p.w * scale, h = p.h * scale;
      if (x + w < 0 || x > W || y + h < 0 || y > H) continue;
      // 标题条：不透明底 + 分隔线，确保标题与下方节点标签互不干扰
      ctx.fillStyle = '#0b0e14';
      ctx.fillRect(x, y, w, 27);
      ctx.fillStyle = p.color + '3a';
      ctx.fillRect(x, y, Math.min(w, 280), 27);
      ctx.strokeStyle = p.color + '70'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, y + 27); ctx.lineTo(x + w, y + 27); ctx.stroke();
      ctx.font = 'bold 13px -apple-system,"Microsoft YaHei",sans-serif';
      ctx.fillStyle = p.color;
      ctx.textAlign = 'left';
      ctx.fillText(p.school, x + 9, y + 19);
      ctx.font = '11px -apple-system,"Microsoft YaHei",sans-serif';
      ctx.fillStyle = '#7c8ba1';
      ctx.fillText(p.n + ' 人', x + 8 + ctx.measureText(p.school).width + 34, y + 16);
      ctx.textAlign = 'center';
    }
  }

  const order = G.list.slice().sort((a, b) => {
    if (a === sel) return -2; if (b === sel) return 2;
    if (a === hover) return -1; if (b === hover) return 1;
    return (rank[a] || 0) - (rank[b] || 0);
  });
  const total = G.list.length;
  const CELL2 = view === 'school' ? 58 : 74;
  const budget = Math.max(20, Math.min(total, Math.round((W * H) / (CELL2 * CELL2 * (view === 'school' ? 3.2 : 5.5)))));
  const cells = new Set();
  let drawn = 0;
  for (const k of order) {
    const p = pos[k]; if (!p) continue;
    const sx = p.x * scale + ox, sy = p.y * scale + oy;
    if (sx < -60 || sx > W + 60 || sy < -30 || sy > H + 30) continue;
    const important = k === sel || k === hover || (rank[k] || 0) < total * 0.12;
    if (!important && drawn >= budget) continue;
    const r = radius(k) * scale;
    const key = Math.floor(sx / CELL2) + ',' + Math.floor((sy - r - FS) / CELL2);
    if (cells.has(key) && !important) continue;
    cells.add(key); drawn++;
    const label = NAME(k);
    ctx.font = (k === sel || k === hover ? 'bold ' : '') + FS + 'px -apple-system,"Microsoft YaHei",sans-serif';
    const tw = ctx.measureText(label).width, ty = sy - r - 5;
    ctx.fillStyle = 'rgba(11,14,20,.8)';
    ctx.fillRect(sx - tw / 2 - 3, ty - FS + 1, tw + 6, FS + 3);
    ctx.fillStyle = k === sel ? '#fbbf24' : (important ? '#e8edf5' : '#9aa7b8');
    ctx.fillText(label, sx, ty);
  }
}

// 矩阵渲染
function renderMatrix() {
  if (!M) return;
  const { _schools: schools, _cell: CELL, _left: LEFT, _top: TOP, _maxOff: mo, _maxDiag: md } = M;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  const S = Math.min(scale, 2.4);
  ctx.save();
  ctx.translate(ox, oy); ctx.scale(S, S);
  const FS = 11.5;
  ctx.textBaseline = 'middle';
  // 单元格
  for (const c of panels) {
    const isSel = sel && (c.list.some((e) => e.s === sel || e.t === sel));
    let alpha;
    if (c.diag) alpha = c.v ? 0.14 + 0.5 * (c.v / md) : 0;
    else alpha = c.v ? 0.16 + 0.72 * (c.v / mo) : 0;
    if (c.v) {
      ctx.fillStyle = (c.diag ? 'rgba(99,102,241,' : 'rgba(244,114,182,') + alpha.toFixed(3) + ')';
      ctx.fillRect(c.x, c.y, c.s - 1.5, c.s - 1.5);
    } else {
      ctx.fillStyle = 'rgba(255,255,255,.025)';
      ctx.fillRect(c.x, c.y, c.s - 1.5, c.s - 1.5);
    }
    if (isSel) { ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 2; ctx.strokeRect(c.x, c.y, c.s - 1.5, c.s - 1.5); }
    if (c.v && c.s >= 26) {
      ctx.font = (c.diag ? 'bold ' : '') + Math.min(13, c.s * 0.42) + 'px -apple-system,sans-serif';
      ctx.fillStyle = c.diag ? '#c7d2fe' : '#fbcfe8';
      ctx.textAlign = 'center';
      ctx.fillText(String(c.v), c.x + c.s / 2, c.y + c.s / 2);
    }
  }
  // 行列标签
  ctx.font = FS + 'px -apple-system,"Microsoft YaHei",sans-serif';
  for (let i = 0; i < schools.length; i++) {
    ctx.textAlign = 'right'; ctx.fillStyle = COL[schools[i]] || '#94a3b8';
    ctx.fillText(schools[i], LEFT - 6, TOP + i * CELL + CELL / 2);
    ctx.save();
    ctx.translate(LEFT + i * CELL + CELL / 2, TOP - 8); ctx.rotate(-Math.PI / 3);
    ctx.textAlign = 'left';
    ctx.fillText(schools[i], 0, 0);
    ctx.restore();
  }
  ctx.restore();
  ctx.textAlign = 'left';
  ctx.font = 'bold 13px -apple-system,"Microsoft YaHei",sans-serif';
  ctx.fillStyle = '#e5e7eb';
  ctx.fillText('院校关系矩阵', 16, 22);
  ctx.font = '11.5px -apple-system,"Microsoft YaHei",sans-serif';
  ctx.fillStyle = '#7c8ba1';
  ctx.fillText('对角线（蓝）= 校内关系条数　非对角（粉）= 跨校关系条数　格内数字为条数，点击查看明细', 16, 42);
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function line(a, b) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
function arrow(a, b, tr, col) {
  const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d;
  const ex = b.x - ux * (tr + 3), ey = b.y - uy * (tr + 3);
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(ex, ey); ctx.stroke();
  const L = 9 / Math.max(scale, .45), ang = Math.atan2(dy, dx);
  ctx.beginPath(); ctx.moveTo(ex, ey);
  ctx.lineTo(ex - L * Math.cos(ang - .42), ey - L * Math.sin(ang - .42));
  ctx.lineTo(ex - L * Math.cos(ang + .42), ey - L * Math.sin(ang + .42));
  ctx.closePath(); ctx.fillStyle = col; ctx.fill();
}

// ══════════ 交互 ══════════
function resize() {
  DPR = window.devicePixelRatio || 1;
  const r = $('main').getBoundingClientRect();
  W = r.width; H = r.height;
  cv.width = W * DPR; cv.height = H * DPR;
  cv.style.width = W + 'px'; cv.style.height = H + 'px';
  rebuild(true);
}
window.addEventListener('resize', resize);
let drag = null;
cv.addEventListener('mousedown', (e) => { drag = { x: e.clientX, y: e.clientY, ox, oy, moved: false }; cv.classList.add('drag'); });
window.addEventListener('mousemove', (e) => {
  if (drag) {
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    ox = drag.ox + dx; oy = drag.oy + dy; render(); return;
  }
  const k = pick(e), tip = $('tip');
  if (k !== hover) { hover = k; render(); }
  if (k) {
    tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX + 15, W - 290) + 'px';
    tip.style.top = (e.clientY + 15) + 'px';
    tip.innerHTML = '<b>' + NAME(k) + '</b><br/>' + SCH(k) + ' · ' + (N[k].t || '—') + '<br/>论文 ' + NP(k) + ' 篇';
  } else tip.style.display = 'none';
});
window.addEventListener('mouseup', (e) => {
  cv.classList.remove('drag');
  if (drag && !drag.moved) {
    const k = pick(e);
    if (k) select(k);
    else if (view === 'matrix') { sel = null; $('panel').style.display = 'none'; render(); }
    else { sel = null; $('panel').style.display = 'none'; render(); }
  }
  drag = null;
});
cv.addEventListener('wheel', (e) => {
  e.preventDefault();
  const f = e.deltaY < 0 ? 1.14 : 0.88;
  const r = cv.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  ox = mx - (mx - ox) * f; oy = my - (my - oy) * f; scale *= f;
  $('zlv').textContent = Math.round(scale * 100) + '%';
  render();
}, { passive: false });
cv.addEventListener('dblclick', () => fitView(view === 'matrix' ? 30 : 40));
$('zin').onclick = () => { const f = 1.25; ox = W / 2 - (W / 2 - ox) * f; oy = H / 2 - (H / 2 - oy) * f; scale *= f; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); };
$('zout').onclick = () => { const f = 0.8; ox = W / 2 - (W / 2 - ox) * f; oy = H / 2 - (H / 2 - oy) * f; scale *= f; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); };

function pick(e) {
  const r = cv.getBoundingClientRect();
  if (view === 'matrix') {
    const x = (e.clientX - r.left - ox) / Math.min(scale, 2.4), y = (e.clientY - r.top - oy) / Math.min(scale, 2.4);
    for (const c of panels) if (x >= c.x && x <= c.x + c.s && y >= c.y && y <= c.y + c.s) return { matrix: c };
    return null;
  }
  const x = (e.clientX - r.left - ox) / scale, y = (e.clientY - r.top - oy) / scale;
  let best = null, bd = Infinity;
  for (const k of G.list) {
    const p = pos[k]; if (!p) continue;
    const rr = radius(k) + 5 / scale;
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d < rr * rr && d < bd) { bd = d; best = k; }
  }
  return best;
}

function select(k) {
  if (k && k.matrix) { selectCell(k.matrix); return; }
  sel = k; render();
  const st = G.studentsOf[k] || [], me = G.mentorOf[k] || [];
  const cols = COLB.filter((e) => (e.s === k || e.t === k) && e.n >= 2)
    .map((e) => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 30);
  const sib = [];
  for (const m of me) for (const s of (G.studentsOf[m] || [])) if (s !== k) sib.push({ s, m });
  const L = (arr, f) => arr.length ? arr.map(f).join('') : '<span style="color:#3f4855">—</span>';
  const P = N[k] || {};
  const lvTag = (other, dir) => {
    const e = ADV.find((x) => (dir === 'up' ? (x.s === k && x.t === other) : (x.t === k && x.s === other)));
    if (!e) return '';
    const c = e.cross ? '#f472b6' : e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
    const t = (e.cross ? '跨校 ' : '') + (e.lv === 1 ? 'L1' : e.lv === 2 ? 'L2' : 'L3');
    return '<span title="' + String(e.nt || '').replace(/"/g, '&quot;') + '" style="color:' + c + ';font-size:10px;margin-left:3px">' + t + '</span>';
  };
  const eduH = (P.edu && P.edu.length) ? P.edu.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '</div>').join('') : '';
  const pdH = (P.pd && P.pd.length) ? P.pd.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '（博士后）</div>').join('') : '';
  const jobH = (P.job && P.job.length) ? P.job.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '</div>').join('') : '';
  const teamH = (P.team && P.team.length) ? P.team.map((x) => '<span class="tag">' + x + '</span>').join('') : '';
  $('panel').style.display = 'block';
  $('panel').innerHTML =
    '<h3>' + NAME(k) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">' + SCH(k) + ' · ' + (P.t || '—') + '</div>' +
    '<div style="font-size:12px;color:#5a6472">' + (P.d || '') + '</div>' +
    '<div style="margin-top:7px"><span class="tag">论文 ' + NP(k) + ' 篇</span>' + (P.c ? '<span class="tag">' + P.c.slice(0, 40) + '</span>' : '') + '</div>' +
    (P.h ? '<div style="margin-top:6px"><a href="' + P.h + '" target="_blank" style="color:#60a5fa;font-size:12px">打开主页 ↗</a></div>' : '') +
    (eduH || pdH || jobH ? '<div class="rel"><b>学历与工作经历（页面自述）</b>' + eduH + pdH + jobH + '</div>' : '') +
    '<div class="rel"><b>导师（' + me.length + '）</b>' + L(me, (m) => '<a data-k="' + m + '">' + NAME(m) + '</a>' + lvTag(m, 'up')) + '</div>' +
    '<div class="rel"><b>学生（' + st.length + '）</b>' + L(st, (s) => '<a data-k="' + s + '">' + NAME(s) + '</a>' + lvTag(s, 'down')) + '</div>' +
    (sib.length ? '<div class="rel"><b>同门（' + sib.length + '）</b>' + L(sib.slice(0, 40), (x) => '<a data-k="' + x.s + '">' + NAME(x.s) + '</a>') + '</div>' : '') +
    (teamH ? '<div class="rel"><b>课题组名单（页面所列）</b>' + teamH + '</div>' : '') +
    '<div class="rel"><b>主要合作者（共同署名篇数）</b>' + L(cols, (c) => '<a data-k="' + c.k + '">' + NAME(c.k) + ' <span style="color:#5a6472">' + c.n + '</span></a>') + '</div>';
  $('panel').querySelectorAll('a[data-k]').forEach((a) => { a.onclick = () => select(a.dataset.k); });
}

function selectCell(c) {
  sel = null; render();
  $('panel').style.display = 'block';
  const rows = c.list.slice(0, 40).map((e) => {
    const lv = e.k === 'adv' ? (e.lv === 1 ? 'L1 自述' : e.lv === 2 ? 'L2 交叉' : 'L3 推断') : (e.k === 'sib' ? '同门' : '合作');
    const extra = e.k === 'adv' ? '（' + (e.sp || '') + (e.inst ? ' · ' + e.inst : '') + '）' : (e.n ? '（共同署名 ' + e.n + ' 篇）' : '');
    return '<div style="font-size:11.5px;line-height:1.9">' +
      '<a data-k="' + e.t + '" style="color:#60a5fa;cursor:pointer">' + NAME(e.t) + '</a> ← ' +
      '<a data-k="' + e.s + '" style="color:#60a5fa;cursor:pointer">' + NAME(e.s) + '</a> ' +
      '<span style="color:#5a6472">' + lv + extra + '</span></div>';
  }).join('');
  $('panel').innerHTML =
    '<h3>' + (c.diag ? c.a + ' 校内关系' : c.a + ' ↔ ' + c.b) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">共 ' + c.v + ' 条</div>' +
    '<div class="rel"><b>关系明细' + (c.list.length > 40 ? '（前 40 条）' : '') + '</b>' + (rows || '—') + '</div>';
  $('panel').querySelectorAll('a[data-k]').forEach((a) => {
    a.onclick = () => { const kk = a.dataset.k; if (view === 'matrix') { view = 'school'; document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x.dataset.v === 'school')); rebuild(true); } select(kk); };
  });
}

// ══════════ 控件 ══════════
document.querySelectorAll('.tab').forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.remove('on'));
    t.classList.add('on'); view = t.dataset.v;
    $('wWrap').style.display = view === 'force' ? 'block' : 'none';
    rebuild(true);
  };
});
$('q').addEventListener('input', (e) => {
  const v = e.target.value.trim(), res = $('qres');
  if (!v) { res.textContent = ''; return; }
  const hits = Object.keys(N).filter((k) => NAME(k).includes(v)).slice(0, 8);
  res.innerHTML = hits.length ? hits.map((k) => '<a data-k="' + k + '" style="color:#60a5fa;cursor:pointer;margin-right:8px">' + NAME(k) + '(' + SCH(k) + ')</a>').join('') : '<span style="color:#5a6472">无匹配</span>';
  res.querySelectorAll('a[data-k]').forEach((a) => {
    a.onclick = () => {
      const kk = a.dataset.k;
      if (view === 'matrix' || !pos[kk]) {
        view = 'school'; onlyCross = false; $('onlyCross').checked = false;
        document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x.dataset.v === 'school'));
        rebuild(false);
      }
      select(kk);
      const p = pos[kk];
      if (p) { scale = Math.max(scale, 1.1); ox = W / 2 - p.x * scale; oy = H / 2 - p.y * scale; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); }
    };
  });
});
$('onlyCross').onchange = (e) => { onlyCross = e.target.checked; rebuild(true); };
$('showAdv').onchange = (e) => { showAdv = e.target.checked; rebuild(true); };
$('showSib').onchange = (e) => { showSib = e.target.checked; rebuild(true); };
$('w').oninput = (e) => { minW = +e.target.value; $('wv').textContent = minW; if (view === 'force') rebuild(true); };

// 侧栏列出全部跨校师承（最有价值的信息，直接文字呈现）
(function fillCross() {
  const cross = ADV.filter((e) => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc);
  const box = $('crossBox');
  if (!cross.length) return;
  box.innerHTML = '<h2>跨校师承（全部 ' + cross.length + ' 条）</h2>' +
    cross.map((e) => '<div class="cross">' +
      '<a data-k="' + e.s + '" style="color:#60a5fa;cursor:pointer">' + NAME(e.s) + '</a>（' + SCH(e.s) + '）<br/>← 师从 ' +
      '<a data-k="' + e.t + '" style="color:#60a5fa;cursor:pointer">' + NAME(e.t) + '</a>（' + SCH(e.t) + '）' +
      '<i> · ' + (e.lv === 1 ? 'L1 页面明写' : e.lv === 2 ? 'L2 交叉证据' : 'L3 署名推断') + '</i></div>').join('');
  box.querySelectorAll('a[data-k]').forEach((a) => {
    a.onclick = () => {
      if (view === 'matrix') { view = 'school'; document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x.dataset.v === 'school')); rebuild(false); }
      select(a.dataset.k);
      const p = pos[a.dataset.k];
      if (p) { scale = Math.max(scale, 1.1); ox = W / 2 - p.x * scale; oy = H / 2 - p.y * scale; render(); }
    };
  });
})();

resize();
</script></body></html>`;

fs.writeFileSync(path.join(REPO, 'reports', '导师关系网络.html'), html, 'utf8');
console.log('saved reports/导师关系网络.html', (html.length / 1024).toFixed(0) + 'KB');
const cross = DATA.advisor.filter((e) => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc);
console.log('节点', Object.keys(N).length, '| 师承', DATA.advisor.length, '（跨校 ' + cross.length + '）| 合作', DATA.collab.length);
