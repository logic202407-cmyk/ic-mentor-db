// net_html.mjs — 生成关系网络可视化（单文件 HTML，离线可用）
//
// v2 重写布局引擎，修复三类问题：
//   ① 无自适应视口 —— 节点散落画布一角或溢出。现在每次布局后自动 fit-to-view
//   ② 力导向塌成糊 —— 近似斥力太弱。改为 Barnes-Hut 四叉树精确斥力
//   ③ 标签互相压叠 —— 改为分层显示 + 网格避让，只在缩放足够或节点重要时标名
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
const trim = (e) => ({ s: e.s, t: e.t, n: e.n, lv: e.lv, sp: e.span, nt: e.note || '', inst: e.inst || '', ty: e.type || '' });
const DATA = {
  meta: net.meta, nodes: N, colors: COLORS,
  advisor: net.advisor.map(trim),
  collab: net.collab.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: 4 })),
  sibling: net.sibling.map((e) => ({ s: e.s, t: e.t, v: e.via })),
  schoolCount: Object.keys(SHORT).length,
};

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>微电子导师关系网络</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{font:13px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#0b0e14;color:#e5e7eb}
#app{display:flex;height:100%}
#side{width:310px;flex:0 0 310px;background:#12161f;border-right:1px solid #232936;overflow-y:auto;padding:14px}
#main{flex:1;position:relative;overflow:hidden}
canvas{display:block;cursor:grab}
canvas.drag{cursor:grabbing}
h1{font-size:15px;margin:0 0 3px}
h2{font-size:11px;margin:15px 0 6px;color:#7c8ba1;letter-spacing:.6px;text-transform:uppercase}
.sub{font-size:11px;color:#5a6472;margin-bottom:11px}
.tabs{display:flex;gap:5px;margin-bottom:10px}
.tab{flex:1;padding:8px 4px;text-align:center;background:#1a1f2b;border:1px solid #232936;border-radius:7px;cursor:pointer;font-size:12px;color:#8b98a9;transition:.15s}
.tab:hover{background:#212736}
.tab.on{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
label{display:flex;align-items:center;gap:7px;padding:5px 0;cursor:pointer;font-size:12px;color:#c3ccd8}
input[type=checkbox]{accent-color:#2563eb;width:14px;height:14px;cursor:pointer}
input[type=range]{width:100%;accent-color:#2563eb;cursor:pointer}
input[type=text],select{width:100%;padding:7px 9px;background:#0b0e14;border:1px solid #232936;border-radius:6px;color:#e5e7eb;font-size:12px;margin-top:3px}
input[type=text]:focus,select:focus{outline:none;border-color:#2563eb}
.stat{display:flex;justify-content:space-between;padding:2px 0;font-size:12px;color:#8b98a9}
.stat b{color:#e5e7eb}
.lg{display:flex;align-items:center;gap:8px;padding:3px 0;color:#8b98a9;font-size:11px}
.sw{width:24px;height:0;border-top-width:2px;border-top-style:solid;flex:0 0 24px}
.dot{width:10px;height:10px;border-radius:50%;flex:0 0 10px}
#tip{position:absolute;background:#1a1f2bee;border:1px solid #2f3744;border-radius:8px;padding:8px 11px;font-size:12px;pointer-events:none;display:none;max-width:270px;z-index:20;line-height:1.55;box-shadow:0 6px 20px #0008}
#panel{position:absolute;right:0;top:0;width:340px;height:100%;background:#12161ff2;border-left:1px solid #232936;padding:14px;overflow-y:auto;display:none;backdrop-filter:blur(6px)}
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
</style></head><body>
<div id="app">
  <div id="side">
    <h1>微电子导师关系网络</h1>
    <div class="sub">基于 31,689 条共同署名记录的姓名+机构双校验结果</div>
    <div class="tabs">
      <div class="tab on" data-v="lineage">师承图谱</div>
      <div class="tab" data-v="collab">合作网络</div>
    </div>

    <h2>搜索</h2>
    <input type="text" id="q" placeholder="输入导师姓名…"/>
    <div id="qres" style="font-size:11px;color:#5a6472;margin-top:5px;line-height:1.9"></div>

    <h2>过滤</h2>
    <div style="font-size:11px;color:#7c8ba1">单位</div>
    <select id="school"><option value="">全部（22 校/单位）</option></select>
    <div style="font-size:11px;color:#7c8ba1;margin-top:9px">最小合作篇数：<b id="wv" style="color:#e5e7eb">3</b></div>
    <input type="range" id="w" min="2" max="20" value="3"/>
    <label><input type="checkbox" id="showAdv" checked> 显示师承关系</label>
    <label><input type="checkbox" id="showSib" checked> 显示同门关系</label>
    <label><input type="checkbox" id="minComp"> 只显示 ≥3 人的师承组</label>

    <h2>图例</h2>
    <div class="lg"><div class="sw" style="border-color:#fbbf24;border-top-width:3px"></div>L1 自述师承（页面明写）</div>
    <div class="lg"><div class="sw" style="border-color:#f59e0b;border-top-width:2px"></div>L2 学历×论文交叉证据</div>
    <div class="lg"><div class="sw" style="border-color:#a16207"></div>L3 署名推断（无学历佐证）</div>
    <div class="lg"><div class="sw" style="border-color:#3b82f6;border-top-style:dashed"></div>共同署名合作</div>
    <div class="lg"><div class="sw" style="border-color:#10b981;border-top-style:dotted"></div>同门（同一导师）</div>
    <div class="lg"><div class="dot" style="background:#2563eb"></div>节点大小 = 论文数</div>

    <h2>统计</h2>
    <div class="stat"><span>当前显示节点</span><b id="sN">0</b></div>
    <div class="stat"><span>师承关系</span><b id="sA">0</b></div>
    <div class="stat"><span>合作关系</span><b id="sC">0</b></div>
    <div class="stat"><span>同门关系</span><b id="sS">0</b></div>

    <div class="warn">
      <b>关系判定依据（按可靠性分四级）</b><br/>
      <b style="color:#fbbf24">L1</b>：本人页面<b>明写</b>「导师为／师从 XX」。<br/>
      <b style="color:#f59e0b">L2</b>：页面自述<b>毕业院校</b>＋该院校教授在其<b>早期论文中固定为末位作者</b>。<br/>
      <b style="color:#a16207">L3</b>：仅「早期一作＋固定末位作者」署名模式，<b>无学历佐证</b>。<br/>
      所有署名均经<b>姓名＋机构双重校验</b>；机构不符或无法判定者一律丢弃。<br/>
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
const SCHOOL = k => (N[k] ? N[k].s : '?');
const NP = k => (N[k] ? (N[k].p || 0) : 0);

const cv = $('cv'), ctx = cv.getContext('2d');
let W = 0, H = 0, DPR = 1;
let view = 'lineage', minW = 3, showAdv = true, showSib = true, minComp = false, schoolF = '';
let pos = {}, sel = null, hover = null, G = null;
let scale = 1, ox = 0, oy = 0;

// ══ 自适应视口：布局完成后把整图缩放到刚好填满画布 ══
function fitView(pad = 40) {
  const xs = [], ys = [];
  for (const k of G.list) { const p = pos[k]; if (p) { xs.push(p.x); ys.push(p.y); } }
  if (!xs.length) return;
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const gw = Math.max(x1 - x0, 1), gh = Math.max(y1 - y0, 1);
  const s = Math.min((W - pad * 2) / gw, (H - pad * 2) / gh, 3.2);
  scale = Math.max(0.05, s);
  ox = (W - gw * scale) / 2 - x0 * scale;
  oy = (H - gh * scale) / 2 - y0 * scale;
  $('zlv').textContent = Math.round(scale * 100) + '%';
}

// ══ Barnes-Hut 四叉树（力导向用，O(n log n) 而非 O(n²)）══
function buildTree(px, py, n) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) { if (px[i] < x0) x0 = px[i]; if (px[i] > x1) x1 = px[i]; if (py[i] < y0) y0 = py[i]; if (py[i] > y1) y1 = py[i]; }
  const size = Math.max(x1 - x0, y1 - y0, 1);
  const root = { x0: x0 - size * .05, y0: y0 - size * .05, s: size * 1.1, m: 0, cx: 0, cy: 0, c: null, i: -1 };
  const ins = (node, i) => {
    if (node.c === null) {
      if (node.m === 0) { node.i = i; node.m = 1; node.cx = px[i]; node.cy = py[i]; return; }
      // 拆分
      const oi = node.i; node.i = -1; node.c = [null, null, null, null];
      const half = node.s / 2;
      const q = (x, y) => (x >= node.x0 + half ? 1 : 0) + (y >= node.y0 + half ? 2 : 0);
      const oq = q(px[oi], py[oi]);
      node.c[oq] = { x0: node.x0 + (oq & 1 ? half : 0), y0: node.y0 + (oq & 2 ? half : 0), s: half, m: 1, cx: px[oi], cy: py[oi], c: null, i: oi };
      ins(node, i);
      return;
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
  acc(root);
  return root;
}
function bhForce(node, i, px, py, theta, out) {
  if (node.m === 0) return;
  const dx = px[i] - node.cx, dy = py[i] - node.cy;
  const d2 = dx * dx + dy * dy + 1e-6;
  if (node.c === null || (node.s * node.s) / d2 < theta * theta) {
    if (node.c === null && node.i === i) return;
    const d = Math.sqrt(d2);
    const f = node.m / d2;
    out.x += (dx / d) * f; out.y += (dy / d) * f;
    return;
  }
  for (const ch of node.c) if (ch) bhForce(ch, i, px, py, theta, out);
}

function layoutForce(list, edges) {
  const n = list.length;
  const px = new Float32Array(n), py = new Float32Array(n);
  const idx = {};
  list.forEach((k, i) => { idx[k] = i; });
  // 初始：黄金角螺旋，避免初始重叠
  const R = Math.sqrt(n) * 26;
  list.forEach((k, i) => {
    const a = i * 2.399963, r = R * Math.sqrt((i + .5) / n);
    px[i] = Math.cos(a) * r; py[i] = Math.sin(a) * r;
  });
  // 度数与权重
  const deg = new Float32Array(n), wsum = new Float32Array(n);
  const E = [];
  for (const e of edges) {
    const a = idx[e.s], b = idx[e.t];
    if (a === undefined || b === undefined) continue;
    const w = Math.min(4, 1 + (e.n || 1) * 0.25);
    E.push([a, b, w]); deg[a] += w; deg[b] += w; wsum[a] += w; wsum[b] += w;
  }
  // 理想边长随节点数缩放
  const k0 = Math.max(18, Math.min(90, 900 / Math.sqrt(n)));
  const ITER = n > 1500 ? 320 : 420;
  const out = { x: 0, y: 0 };
  let temp = k0 * 1.6;
  for (let it = 0; it < ITER; it++) {
    const tree = buildTree(px, py, n);
    const fx = new Float32Array(n), fy = new Float32Array(n);
    const theta = 0.9;
    for (let i = 0; i < n; i++) {
      out.x = 0; out.y = 0;
      bhForce(tree, i, px, py, theta, out);
      const rep = (k0 * k0) * out.x, repY = (k0 * k0) * out.y;
      const d = Math.sqrt(out.x * out.x + out.y * out.y) + 1e-9;
      const cap = 900;
      fx[i] += Math.max(-cap, Math.min(cap, rep / d * out.x / d * 0 + rep)) * 0;
      fy[i] += 0;
      fx[i] += Math.max(-cap, Math.min(cap, out.x / d * (k0 * k0)));
      fy[i] += Math.max(-cap, Math.min(cap, out.y / d * (k0 * k0)));
    }
    // 引力（沿边）
    for (const [a, b, w] of E) {
      let dx = px[a] - px[b], dy = py[a] - py[b];
      const d = Math.sqrt(dx * dx + dy * dy) + 1e-6;
      const f = (d * d) / (k0 * 1.1) * w * 0.55;
      fx[a] -= dx / d * f; fy[a] -= dy / d * f;
      fx[b] += dx / d * f; fy[b] += dy / d * f;
    }
    // 向心（孤立点别飞走）
    for (let i = 0; i < n; i++) {
      const d = Math.sqrt(px[i] * px[i] + py[i] * py[i]) + 1e-6;
      const g = deg[i] === 0 ? 0.06 : 0.012;
      fx[i] -= px[i] / d * d * g; fy[i] -= py[i] / d * d * g;
    }
    // 位移限幅
    for (let i = 0; i < n; i++) {
      const d = Math.sqrt(fx[i] * fx[i] + fy[i] * fy[i]) + 1e-9;
      const step = Math.min(d, temp);
      px[i] += fx[i] / d * step; py[i] += fy[i] / d * step;
    }
    // 每轮归一化到稳定尺度，避免整体漂移
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += px[i]; my += py[i]; }
    mx /= n; my /= n;
    for (let i = 0; i < n; i++) { px[i] -= mx; py[i] -= my; }
    temp = Math.max(k0 * 0.12, temp * 0.975);
  }
  const res = {};
  list.forEach((k, i) => { res[k] = { x: px[i], y: py[i] }; });
  void wsum;
  return res;
}

// ══ 师承图谱：每个连通分量做树形布局，分量按尺寸打包 ══
function layoutLineage(list, g) {
  const inSet = new Set(list);
  const adj = {};
  for (const k of list) adj[k] = new Set();
  for (const e of g.edges) if (inSet.has(e.s) && inSet.has(e.t)) { adj[e.s].add(e.t); adj[e.t].add(e.s); }
  const comp = {}, comps = [];
  for (const k of list) {
    if (comp[k] !== undefined) continue;
    const cid = comps.length, st = [k], mem = [];
    comp[k] = cid;
    while (st.length) { const x = st.pop(); mem.push(x); for (const y of adj[x]) if (comp[y] === undefined) { comp[y] = cid; st.push(y); } }
    comps.push(mem);
  }
  comps.sort((a, b) => b.length - a.length);
  const LABELPAD = 10;
  // 两档间距：
  //   大组（≥3 人）—— 有结构可看，用宽间距，标签清晰
  //   小组（2 人）  —— 数量多、形态雷同，压缩成密集「目录带」，避免霸占画面
  const BIG = { DX: 116, DY: 124, GAPX: 74, GAPY: 88 };
  const SMALL = { DX: 52, DY: 74, GAPX: 22, GAPY: 26 };

  const buildBlock = (mem, cfg) => {
    const mset = new Set(mem);
    const depth = {};
    const roots = mem.filter((k) => !(g.mentorOf[k] || []).some((m) => mset.has(m)));
    const q = (roots.length ? roots : [mem[0]]).map((k) => [k, 0]);
    const seen0 = new Set(q.map((x) => x[0]));
    while (q.length) {
      const [k, d] = q.shift(); depth[k] = d;
      for (const s of (g.studentsOf[k] || [])) if (mset.has(s) && !seen0.has(s)) { seen0.add(s); q.push([s, d + 1]); }
    }
    for (const k of mem) if (depth[k] === undefined) depth[k] = 0;
    // ⚠️ 师承图可能存在环（A↔B 互为导师），递归计数会栈溢出 —— 用带 visited 的迭代
    const sub = {};
    for (const k of mem) {
      const seen2 = new Set([k]);
      const stack = [...(g.studentsOf[k] || [])].filter((s) => mset.has(s));
      let c = 0;
      while (stack.length) {
        const x = stack.pop();
        if (seen2.has(x)) continue;
        seen2.add(x); c++;
        for (const y of (g.studentsOf[x] || [])) if (mset.has(y) && !seen2.has(y)) stack.push(y);
      }
      sub[k] = c;
    }
    const byD = {};
    for (const k of mem) (byD[depth[k]] = byD[depth[k]] || []).push(k);
    for (const d of Object.keys(byD)) byD[d].sort((a, b) => sub[b] - sub[a] || NP(b) - NP(a));
    const maxRow = Math.max(...Object.values(byD).map((a) => a.length));
    const maxD = Math.max(...Object.keys(byD).map(Number));
    return { mem, byD, cfg, w: Math.max(2, maxRow) * cfg.DX + cfg.GAPX * 2, h: (maxD + 1) * cfg.DY + LABELPAD };
  };
  const bigBlocks = comps.filter((c) => c.length >= 3).map((c) => buildBlock(c, BIG));
  const smallBlocks = comps.filter((c) => c.length < 3).map((c) => buildBlock(c, SMALL));

  const packBlocks = (blocks, MAXW, startY) => {
    const res = {};
    let cx = 0, cy = startY, rowH = 0, maxRowW = 0;
    for (const b of blocks) {
      if (cx > 0 && cx + b.w > MAXW) { maxRowW = Math.max(maxRowW, cx - b.cfg.GAPX); cx = 0; cy += rowH + b.cfg.GAPY; rowH = 0; }
      for (const d of Object.keys(b.byD)) {
        const arr = b.byD[d];
        const rowW = arr.length * b.cfg.DX;
        const x0 = cx + b.cfg.GAPX + (b.w - b.cfg.GAPX * 2 - rowW) / 2 + b.cfg.DX / 2;
        arr.forEach((k, i) => { res[k] = { x: x0 + i * b.cfg.DX, y: cy + LABELPAD + Number(d) * b.cfg.DY }; });
      }
      cx += b.w + b.cfg.GAPX; rowH = Math.max(rowH, b.h);
    }
    maxRowW = Math.max(maxRowW, cx - (blocks.length ? blocks[blocks.length - 1].cfg.GAPX : 0));
    return { res, w: maxRowW, h: cy + rowH - startY };
  };

  // 搜索大组的最优打包宽度（贴合画布长宽比）
  const target = (W && H) ? W / H : 1.58;
  const totalW = bigBlocks.reduce((a, b) => a + b.w + b.cfg.GAPX, 0) || 1;
  let best = null;
  for (let t = 0; t <= 44; t++) {
    const MAXW = Math.max(700, totalW * (0.05 + t * 0.024));
    const r = packBlocks(bigBlocks, MAXW, 0);
    const score = Math.abs(Math.log((r.w / Math.max(r.h, 1)) / target));
    if (!best || score < best.score) best = { score, MAXW, ...r };
  }
  // 小组作为「目录带」放在大组下方，用其自身的紧凑间距横向铺开
  const res = { ...best.res };
  const smallMaxW = Math.max(best.w, 1400);
  const small = packBlocks(smallBlocks, smallMaxW, 0);
  const yOffset = best.h + (smallBlocks.length ? 110 : 0);
  for (const [k, p] of Object.entries(small.res)) res[k] = { x: p.x, y: p.y + yOffset };
  return res;
}

// ══ 建图 ══
function buildGraph() {
  const mentorOf = {}, studentsOf = {};
  for (const e of ADV) { if (!N[e.s] || !N[e.t]) continue; (mentorOf[e.s] = mentorOf[e.s] || []).push(e.t); (studentsOf[e.t] = studentsOf[e.t] || []).push(e.s); }
  const set = new Set(), edges = [];
  if (showAdv) for (const e of ADV) if (N[e.s] && N[e.t]) { edges.push({ ...e, k: 'adv' }); set.add(e.s); set.add(e.t); }
  if (showSib) for (const e of SIB) if (N[e.s] && N[e.t]) { edges.push({ ...e, k: 'sib' }); set.add(e.s); set.add(e.t); }
  if (view === 'collab') {
    for (const e of COLB) { if (e.n < minW || !N[e.s] || !N[e.t]) continue; edges.push({ ...e, k: 'col' }); set.add(e.s); set.add(e.t); }
  }
  let list = [...set];
  if (schoolF) list = list.filter((k) => N[k].s === schoolF);
  const keep = new Set(list);
  let fe = edges.filter((e) => keep.has(e.s) && keep.has(e.t));
  // 连接度
  const deg = {};
  for (const e of fe) { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.t] = (deg[e.t] || 0) + 1; }
  if (view !== 'collab') list = list.filter((k) => deg[k]);          // 师承视图去掉孤立点
  if (minComp && view !== 'collab') {
    // 只保留 ≥3 人的连通分量
    const adj = {}; for (const k of list) adj[k] = new Set();
    for (const e of fe) if (adj[e.s] && adj[e.t]) { adj[e.s].add(e.t); adj[e.t].add(e.s); }
    const comp = {}; const big = new Set();
    for (const k of list) {
      if (comp[k] !== undefined) continue;
      const st = [k], mem = []; comp[k] = 1;
      while (st.length) { const x = st.pop(); mem.push(x); for (const y of adj[x]) if (comp[y] === undefined) { comp[y] = 1; st.push(y); } }
      if (mem.length >= 3) for (const m of mem) big.add(m);
    }
    list = list.filter((k) => big.has(k));
  }
  const ls = new Set(list);
  fe = fe.filter((e) => ls.has(e.s) && ls.has(e.t));
  return { list, edges: fe, mentorOf, studentsOf };
}

let rank = null;   // 标签优先级：论文数排名
function computeRank() {
  rank = {};
  const arr = G.list.slice().sort((a, b) => NP(b) - NP(a));
  arr.forEach((k, i) => { rank[k] = i; });
}

function rebuild(refit) {
  G = buildGraph();
  pos = view === 'collab' ? layoutForce(G.list, G.edges) : layoutLineage(G.list, G);
  computeRank();
  $('sN').textContent = G.list.length;
  $('sA').textContent = G.edges.filter((e) => e.k === 'adv').length;
  $('sC').textContent = G.edges.filter((e) => e.k === 'col').length;
  $('sS').textContent = G.edges.filter((e) => e.k === 'sib').length;
  if (refit) fitView();
  render();
}

const radius = (k) => 4.5 + Math.min(14, Math.sqrt(NP(k)) * 1.15);
const colorOf = (k) => COL[N[k] ? N[k].s : ''] || '#64748b';

// ══ 渲染 ══
function render() {
  if (!G) return;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, W, H);
  ctx.setTransform(DPR * scale, 0, 0, DPR * scale, DPR * ox, DPR * oy);

  // ── 边 ──
  for (const e of G.edges) {
    const a = pos[e.s], b = pos[e.t]; if (!a || !b) continue;
    if (e.k === 'adv') {
      ctx.strokeStyle = e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
      ctx.lineWidth = (e.lv === 1 ? 2.8 : e.lv === 2 ? 1.9 : 1.0) / Math.max(scale, .35) + Math.min(1.8, (e.n || 2) * .18);
      ctx.setLineDash([]);
      arrow(a, b, radius(e.t), e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207');
    } else if (e.k === 'col') {
      ctx.strokeStyle = 'rgba(59,130,246,' + Math.min(.55, .12 + e.n * .04) + ')';
      ctx.lineWidth = (.6 + Math.min(2.2, e.n * .15)) / Math.max(scale, .4);
      ctx.setLineDash([]); line(a, b);
    } else {
      ctx.strokeStyle = 'rgba(16,185,129,.32)';
      ctx.lineWidth = .8 / Math.max(scale, .4); ctx.setLineDash([3, 3]); line(a, b);
    }
  }
  ctx.setLineDash([]);

  // ── 节点（先画后标名，避免标签被节点盖住）──
  for (const k of G.list) {
    const p = pos[k]; if (!p) continue;
    const r = radius(k);
    if (k === sel || k === hover) {
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 7, 0, 7);
      ctx.fillStyle = k === sel ? 'rgba(251,191,36,.3)' : 'rgba(255,255,255,.14)'; ctx.fill();
    }
    ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 7);
    ctx.fillStyle = colorOf(k); ctx.fill();
    ctx.strokeStyle = 'rgba(11,14,20,.9)'; ctx.lineWidth = 1.3 / Math.max(scale, .4); ctx.stroke();
  }

  // ── 标签：在**屏幕坐标系**绘制，保证任意缩放级别下字号恒定可读 ──
  // （此前在图坐标系绘制，缩放到 0.23 时字只有 6px，完全看不清）
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);   // 回到屏幕坐标
  const CELL = 62;
  const FS = 11.5;
  ctx.font = FS + 'px -apple-system,"Microsoft YaHei",sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  const order = G.list.slice().sort((a, b) => {
    if (a === sel) return -2; if (b === sel) return 2;
    if (a === hover) return -1; if (b === hover) return 1;
    return (rank[a] || 0) - (rank[b] || 0);
  });
  const total = G.list.length;
  // 标签预算：屏幕格子数决定，避免密图糊成一片
  // 合作视图节点极密（2200+），普通标签需放大到 0.5 倍以上才显示，否则靠悬停查看
  const dense = view === 'collab';
  const CELL2 = dense ? 78 : 62;
  const budget = Math.max(12, Math.min(total, Math.round((W * H) / (CELL2 * CELL2 * (dense ? 8 : 5.5)))));
  const cells = new Set();
  let drawn = 0;
  for (const k of order) {
    const p = pos[k]; if (!p) continue;
    const sx = p.x * scale + ox, sy = p.y * scale + oy;
    if (sx < -60 || sx > W + 60 || sy < -30 || sy > H + 30) continue;
    const important = k === sel || k === hover || (rank[k] || 0) < total * (dense ? 0.04 : 0.1);
    if (!important) {
      if (dense && scale < 0.5) continue;        // 密图缩小时不标名
      if (drawn >= budget) continue;
    }
    const r = radius(k) * scale;
    const key = Math.floor(sx / CELL2) + ',' + Math.floor((sy - r - FS) / CELL2);
    if (cells.has(key) && !important) continue;
    cells.add(key);
    drawn++;
    const label = NAME(k);
    ctx.font = (k === sel || k === hover ? 'bold ' : '') + FS + 'px -apple-system,"Microsoft YaHei",sans-serif';
    const tw = ctx.measureText(label).width;
    const ty = sy - r - 5;
    ctx.fillStyle = 'rgba(11,14,20,.78)';
    ctx.fillRect(sx - tw / 2 - 3, ty - FS + 1, tw + 6, FS + 3);
    ctx.fillStyle = k === sel ? '#fbbf24' : (important ? '#e8edf5' : '#9aa7b8');
    ctx.fillText(label, sx, ty);
  }
}
function line(a, b) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
function arrow(a, b, tr, col) {
  const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
  const ux = dx / d, uy = dy / d;
  const ex = b.x - ux * (tr + 3), ey = b.y - uy * (tr + 3);
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(ex, ey); ctx.stroke();
  const L = 9 / Math.max(scale, .5), ang = Math.atan2(dy, dx);
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex - L * Math.cos(ang - .42), ey - L * Math.sin(ang - .42));
  ctx.lineTo(ex - L * Math.cos(ang + .42), ey - L * Math.sin(ang + .42));
  ctx.closePath(); ctx.fillStyle = col; ctx.fill();
}

// ══ 交互 ══
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
    tip.style.left = Math.min(e.clientX + 15, W - 280) + 'px';
    tip.style.top = (e.clientY + 15) + 'px';
    tip.innerHTML = '<b>' + NAME(k) + '</b><br/>' + SCHOOL(k) + ' · ' + (N[k].t || '—') + '<br/>论文 ' + NP(k) + ' 篇' + (N[k].c ? '<br/><span style="color:#7c8ba1">' + N[k].c.slice(0, 34) + '</span>' : '');
  } else tip.style.display = 'none';
});
window.addEventListener('mouseup', (e) => {
  cv.classList.remove('drag');
  if (drag && !drag.moved) { const k = pick(e); if (k) select(k); else { sel = null; $('panel').style.display = 'none'; render(); } }
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
cv.addEventListener('dblclick', () => fitView());
$('zin').onclick = () => { const f = 1.25; ox = W / 2 - (W / 2 - ox) * f; oy = H / 2 - (H / 2 - oy) * f; scale *= f; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); };
$('zout').onclick = () => { const f = 0.8; ox = W / 2 - (W / 2 - ox) * f; oy = H / 2 - (H / 2 - oy) * f; scale *= f; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); };

function pick(e) {
  const r = cv.getBoundingClientRect();
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
    const c = e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
    const t = e.lv === 1 ? 'L1 自述' : e.lv === 2 ? 'L2 交叉' : 'L3 推断';
    return '<span title="' + String(e.nt || '').replace(/"/g, '&quot;') + '" style="color:' + c + ';font-size:10px;margin-left:3px">' + t + '</span>';
  };
  const eduH = (P.edu && P.edu.length) ? P.edu.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '</div>').join('') : '';
  const pdH = (P.pd && P.pd.length) ? P.pd.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '（博士后）</div>').join('') : '';
  const jobH = (P.job && P.job.length) ? P.job.map((x) => '<div style="font-size:11.5px;color:#8b98a9">· ' + x + '</div>').join('') : '';
  const teamH = (P.team && P.team.length) ? P.team.map((x) => '<span class="tag">' + x + '</span>').join('') : '';
  $('panel').style.display = 'block';
  $('panel').innerHTML =
    '<h3>' + NAME(k) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">' + SCHOOL(k) + ' · ' + (P.t || '—') + '</div>' +
    '<div style="font-size:12px;color:#5a6472">' + (P.d || '') + '</div>' +
    '<div style="margin-top:7px"><span class="tag">论文 ' + NP(k) + ' 篇</span>' + (P.c ? '<span class="tag">' + P.c.slice(0, 40) + '</span>' : '') + '</div>' +
    (P.h ? '<div style="margin-top:6px"><a href="' + P.h + '" target="_blank" style="color:#60a5fa;font-size:12px">打开主页 ↗</a></div>' : '') +
    (eduH || pdH || jobH ? '<div class="rel"><b>学历与工作经历（页面自述）</b>' + eduH + pdH + jobH + '</div>' : '') +
    '<div class="rel"><b>导师（' + me.length + '）</b>' + L(me, (m) => '<a data-k="' + m + '">' + NAME(m) + '</a>' + lvTag(m, 'up')) + '</div>' +
    '<div class="rel"><b>学生（' + st.length + '）</b>' + L(st, (s) => '<a data-k="' + s + '">' + NAME(s) + '</a>' + lvTag(s, 'down')) + '</div>' +
    (sib.length ? '<div class="rel"><b>同门（' + sib.length + '）</b>' + L(sib.slice(0, 40), (x) => '<a data-k="' + x.s + '">' + NAME(x.s) + '</a>') + '</div>' : '') +
    (teamH ? '<div class="rel"><b>课题组名单（页面所列）</b>' + teamH + '</div>' : '') +
    '<div class="rel"><b>主要合作者（共同署名篇数）</b>' + L(cols, (c) => '<a data-k="' + c.k + '">' + NAME(c.k) + ' <span style="color:#5a6472">' + c.n + '</span></a>') + '</div>' +
    '<div style="margin-top:10px;font-size:10.5px;color:#3f4855;line-height:1.65">L1 自述师承＝本人页面明写；L2＝毕业院校与论文署名两条独立证据交叉；L3＝仅署名模式推断。悬停标签可看具体依据。</div>';
  $('panel').querySelectorAll('a[data-k]').forEach((a) => { a.onclick = () => select(a.dataset.k); });
}

// ══ 控件 ══
document.querySelectorAll('.tab').forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.remove('on'));
    t.classList.add('on'); view = t.dataset.v; rebuild(true);
  };
});
$('q').addEventListener('input', (e) => {
  const v = e.target.value.trim(), res = $('qres');
  if (!v) { res.textContent = ''; return; }
  const hits = Object.keys(N).filter((k) => NAME(k).includes(v)).slice(0, 8);
  res.innerHTML = hits.length ? hits.map((k) => '<a data-k="' + k + '" style="color:#60a5fa;cursor:pointer;margin-right:8px">' + NAME(k) + '(' + SCHOOL(k) + ')</a>').join('') : '<span style="color:#5a6472">无匹配</span>';
  res.querySelectorAll('a[data-k]').forEach((a) => {
    a.onclick = () => {
      // 若当前视图中没有该节点，切到它所在的视图
      if (!pos[a.dataset.k]) {
        sel = null;
        if (!G.list.includes(a.dataset.k)) {
          // 尝试放宽过滤以纳入
          minW = 2; $('w').value = 2; $('wv').textContent = 2; minComp = false; $('minComp').checked = false; schoolF = '';
          $('school').value = ''; view = 'collab';
          document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x.dataset.v === 'collab'));
          rebuild(false);
        }
      }
      select(a.dataset.k);
      const p = pos[a.dataset.k];
      if (p) { scale = Math.max(scale, 1.1); ox = W / 2 - p.x * scale; oy = H / 2 - p.y * scale; $('zlv').textContent = Math.round(scale * 100) + '%'; render(); }
    };
  });
});
const schools = [...new Set(Object.values(N).map((x) => x.s))].sort();
for (const s of schools) { const o = document.createElement('option'); o.value = s; o.textContent = s; $('school').appendChild(o); }
$('school').onchange = (e) => { schoolF = e.target.value; rebuild(true); };
$('w').oninput = (e) => { minW = +e.target.value; $('wv').textContent = minW; if (view === 'collab') rebuild(true); else render(); };
$('showAdv').onchange = (e) => { showAdv = e.target.checked; rebuild(true); };
$('showSib').onchange = (e) => { showSib = e.target.checked; rebuild(true); };
$('minComp').onchange = (e) => { minComp = e.target.checked; rebuild(true); };

resize();
</script></body></html>`;

fs.writeFileSync(path.join(REPO, 'reports', '导师关系网络.html'), html, 'utf8');
console.log('saved reports/导师关系网络.html', (html.length / 1024).toFixed(0) + 'KB');
console.log('节点', Object.keys(N).length, '| 师承', DATA.advisor.length, '| 合作', DATA.collab.length, '| 同门', DATA.sibling.length);
