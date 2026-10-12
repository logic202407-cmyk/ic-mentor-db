// net_html.mjs — 关系网络 v5：可展开的师承树
//
// 三轮反馈的取舍：
//   v1-v3 把 400-2200 个节点同时铺在画布上 → 无论怎么排都杂乱
//   v4 改成文字大纲 → 不杂乱了，但失去了「直观」
//   v5 保留图形，但**默认只画关键节点，点击才展开子树** —— 节点数由用户控制
//
// 数据依据：165 位导师有学生，但只有 20 位有 ≥3 名学生。
//   默认只画这 20 个 → 画面极干净
//   点开一位 → 该导师的完整师承树独占画布 → 仍然干净且是真正的图形
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
  };
}
const DATA = {
  nodes: N, colors: COLORS,
  advisor: net.advisor.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: e.lv, sp: e.span || '', nt: e.note || '', inst: e.inst || '' })),
  collab: net.collab.map((e) => ({ s: e.s, t: e.t, n: e.n })),
  sibling: net.sibling.map((e) => ({ s: e.s, t: e.t })),
};

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>微电子导师关系网络</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{font:13px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#0b0e14;color:#e5e7eb}
#app{display:flex;height:100%}
#side{width:296px;flex:0 0 296px;background:#12161f;border-right:1px solid #232936;overflow-y:auto;padding:14px}
#main{flex:1;position:relative;overflow:hidden}
canvas{display:block;cursor:grab}
canvas.drag{cursor:grabbing}
h1{font-size:15px;margin:0 0 3px}
h2{font-size:11px;margin:15px 0 6px;color:#7c8ba1;letter-spacing:.6px;text-transform:uppercase}
.sub{font-size:11px;color:#5a6472;margin-bottom:11px}
.tab{display:block;width:100%;text-align:left;padding:8px 11px;margin-bottom:5px;background:#1a1f2b;border:1px solid #232936;border-radius:7px;cursor:pointer;font-size:12.5px;color:#8b98a9;transition:.15s}
.tab:hover{background:#212736;color:#c3ccd8}
.tab.on{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
input[type=text]{width:100%;padding:8px 10px;background:#0b0e14;border:1px solid #232936;border-radius:6px;color:#e5e7eb;font-size:12.5px}
input[type=text]:focus{outline:none;border-color:#2563eb}
input[type=range]{width:100%;accent-color:#2563eb}
.stat{display:flex;justify-content:space-between;padding:2px 0;font-size:12px;color:#8b98a9}
.stat b{color:#e5e7eb}
.mentorItem{display:flex;align-items:baseline;gap:7px;padding:4px 7px;border-radius:5px;cursor:pointer;font-size:12.5px}
.mentorItem:hover{background:#1a212e}
.mentorItem.on{background:#1d2a45}
.mentorItem .nm{color:#c9d4e2}
.mentorItem .cs{margin-left:auto;font-size:10.5px;color:#5a6472}
.badge{display:inline-block;padding:0 5px;border-radius:3px;font-size:10px;line-height:15px;margin-left:5px;vertical-align:1px}
.b1{background:#fbbf2426;color:#fbbf24;border:1px solid #fbbf2455}
.bx{background:#f472b626;color:#f472b6;border:1px solid #f472b655}
.warn{background:#78350f1a;border:1px solid #92400e;border-radius:7px;padding:8px 10px;font-size:11px;color:#fbbf24;line-height:1.65;margin-top:9px}
.warn b{color:#fcd34d}
.legend{font-size:11px;color:#8b98a9;line-height:1.95}
.lg{display:flex;align-items:center;gap:8px;padding:2px 0}
.sw{width:22px;height:0;border-top-width:2px;border-top-style:solid;flex:0 0 22px}
.dot{width:10px;height:10px;border-radius:50%;flex:0 0 10px}
#crumb{position:absolute;left:14px;top:12px;display:none;align-items:center;gap:9px;background:#12161fee;border:1px solid #232936;border-radius:8px;padding:7px 12px;font-size:12.5px;z-index:10}
#crumb a{color:#60a5fa;cursor:pointer;text-decoration:none}
#crumb a:hover{text-decoration:underline}
#crumb b{color:#e5e7eb}
#hint{position:absolute;left:14px;bottom:12px;font-size:11px;color:#4b5563;background:#0b0e14cc;padding:5px 10px;border-radius:6px}
#tip{position:absolute;background:#1a1f2bee;border:1px solid #2f3744;border-radius:8px;padding:8px 11px;font-size:12px;pointer-events:none;display:none;max-width:290px;z-index:20;line-height:1.55;box-shadow:0 6px 20px #0008}
#drawer{position:absolute;right:0;top:0;width:338px;height:100%;background:#12161ff7;border-left:1px solid #232936;padding:15px;overflow-y:auto;display:none;backdrop-filter:blur(6px);z-index:30}
#drawer h3{margin:0 0 2px;font-size:15px}
.tag{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;margin:2px 3px 2px 0;background:#1e2430;color:#9aa7b8}
.rel{border-top:1px solid #1e2430;margin-top:9px;padding-top:7px;font-size:12px}
.rel b{color:#7c8ba1;font-weight:600;display:block;margin-bottom:4px;font-size:11px}
.rel a{color:#60a5fa;cursor:pointer;text-decoration:none;margin-right:9px;display:inline-block;line-height:1.9}
.rel a:hover{text-decoration:underline}
#close{position:absolute;right:12px;top:12px;background:#1e2430;border:1px solid #2f3744;color:#c3ccd8;border-radius:5px;width:24px;height:24px;cursor:pointer;line-height:1}
</style></head><body>
<div id="app">
  <div id="side">
    <h1>微电子导师关系网络</h1>
    <div class="sub">31,689 条共同署名记录 · 姓名+机构双校验</div>

    <div class="tab on" data-v="tree">师承树（点导师展开）</div>
    <div class="tab" data-v="radial">放射聚焦</div>
    <div class="tab" data-v="heat">合作热力图</div>

    <h2>搜索导师</h2>
    <input type="text" id="q" placeholder="输入姓名…"/>
    <div id="qres" style="margin-top:6px"></div>

    <h2>导师列表</h2>
    <div style="font-size:11px;color:#7c8ba1">显示学生数 ≥ <b id="tv" style="color:#e5e7eb">3</b> 的导师</div>
    <input type="range" id="th" min="1" max="24" value="3"/>
    <div id="mlist" style="margin-top:8px;max-height:270px;overflow-y:auto"></div>

    <h2>统计</h2>
    <div class="stat"><span>师承关系</span><b id="sA">0</b></div>
    <div class="stat"><span>其中跨校</span><b id="sX" style="color:#f472b6">0</b></div>
    <div class="stat"><span>有学生的导师</span><b id="sM">0</b></div>

    <h2>图例</h2>
    <div class="legend">
      <div class="lg"><div class="dot" style="background:#6366f1"></div>节点颜色 = 现所在院校</div>
      <div class="lg"><div class="dot" style="background:#0b0e14;border:2px solid #f472b6"></div>粉圈 = 有跨校学生</div>
      <div class="lg"><div class="sw" style="border-color:#fbbf24;border-top-width:3px"></div>L1 自述师承</div>
      <div class="lg"><div class="sw" style="border-color:#f59e0b;border-top-width:2px"></div>L2 学历×论文交叉</div>
      <div class="lg"><div class="sw" style="border-color:#a16207"></div>L3 署名推断</div>
      <div class="lg"><div class="sw" style="border-color:#f472b6;border-top-width:3px"></div>跨校师承</div>
    </div>

    <div class="warn">
      所有署名均经<b>姓名＋机构双重校验</b>，机构不符或无法判定者一律丢弃。
      本页只反映公开页面自述与论文署名可推断的关系，<b>不代表完整师承，也不构成任何评价</b>。
    </div>
  </div>

  <div id="main">
    <canvas id="cv"></canvas>
    <div id="crumb"></div>
    <div id="hint">滚轮缩放 · 拖拽平移 · 点击节点看档案 · 双击适应窗口</div>
    <div id="tip"></div>
    <div id="drawer"></div>
  </div>
</div>
<script>
const DATA = ${JSON.stringify(DATA)};
const N = DATA.nodes, COL = DATA.colors, ADV = DATA.advisor, COLB = DATA.collab;
const $ = id => document.getElementById(id);
const NAME = k => (N[k] ? N[k].n : k);
const SCH = k => (N[k] ? N[k].s : '?');
const NP = k => (N[k] ? (N[k].p || 0) : 0);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const isCross = e => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc;

const mentorOf = {}, studentsOf = {};
for (const e of ADV) {
  if (!N[e.s] || !N[e.t]) continue;
  (studentsOf[e.t] = studentsOf[e.t] || []).push(e);
  (mentorOf[e.s] = mentorOf[e.s] || []).push(e);
}
const CROSS = ADV.filter(isCross);
// 有学生的导师，按学生数降序
const MENTORS = Object.keys(studentsOf).map(k => ({ k, n: studentsOf[k].length })).sort((a, b) => b.n - a.n);

const cv = $('cv'), ctx = cv.getContext('2d');
let W = 0, H = 0, DPR = 1;
let view = 'tree', th = 3, focus = null, sel = null, hover = null;
let nodes = [], edges = [], panels = [];
let scale = 1, ox = 0, oy = 0;

// ══════════ 视图1：师承树 ══════════
// 总览：只画 MENTORS 中 n>=th 的导师，规则网格，画面极干净
// 聚焦：某导师的完整师承树独占画布
function layoutTree() {
  nodes = []; edges = []; panels = [];
  if (!focus) {
    const list = MENTORS.filter(m => m.n >= th);
    const n = list.length;
    const aspect = (W && H) ? W / H : 1.58;
    const cols = Math.max(1, Math.round(Math.sqrt(n * aspect * 1.15)));
    const rows = Math.ceil(n / cols);
    const GX = Math.min(250, (W - 90) / Math.max(cols, 1));
    const GY = Math.min(190, (H - 90) / Math.max(rows, 1));
    list.forEach((m, i) => {
      const r = Math.floor(i / cols), c = i % cols;
      const x = (c - (cols - 1) / 2) * GX;
      const y = (r - (rows - 1) / 2) * GY;
      const hasCross = studentsOf[m.k].some(isCross) || (mentorOf[m.k] || []).some(isCross);
      nodes.push({ k: m.k, x, y, r: 20 + Math.min(46, Math.sqrt(m.n) * 9), root: true, hasCross, cnt: m.n });
    });
    return;
  }
  // 聚焦模式：分层布局，**每层超过 MAXROW 个就换行**
  // （原来把 24 个学生排成一长排，宽度 2832px，缩放被压到 0.48，什么都看不清）
  const MAXROW = 8;
  const DX = 124, DY = 136;
  const levels = [[focus]];
  const seen = new Set([focus]);
  const parentOf = {};
  for (let d = 0; d < 8; d++) {
    const cur = levels[d];
    if (!cur || !cur.length) break;
    const next = [];
    for (const k of cur) {
      const ks = (studentsOf[k] || []).map(e => e.s).filter(s => N[s] && !seen.has(s));
      ks.sort((a, b) => NP(b) - NP(a));
      for (const s of ks) { seen.add(s); parentOf[s] = k; next.push(s); }
    }
    if (next.length) levels.push(next); else break;
  }
  // 逐层摆放：每层按 MAXROW 换行，层与层之间不重叠
  let yCur = 0;
  const posOf = {};
  const maxCols = Math.max(...levels.map(L => Math.min(L.length, MAXROW)));
  levels.forEach((L, d) => {
    const rows = Math.ceil(L.length / MAXROW);
    L.forEach((k, i) => {
      const r = Math.floor(i / MAXROW), c = i % MAXROW;
      const cnt = Math.min(L.length - r * MAXROW, MAXROW);
      // 行内居中
      const x = (c - (cnt - 1) / 2) * DX;
      const y = yCur + r * DY + (d === 0 ? 0 : DY);
      posOf[k] = { x, y, d };
    });
    yCur += rows * DY;
  });
  for (const k of Object.keys(posOf)) {
    const isRoot = k === focus;
    const hasCross = (mentorOf[k] || []).some(isCross) || (studentsOf[k] || []).some(isCross);
    nodes.push({ k, x: posOf[k].x, y: posOf[k].y, r: isRoot ? 24 : 13, root: isRoot, hasCross, cnt: (studentsOf[k] || []).length });
  }
  for (const k of Object.keys(posOf)) {
    if (k === focus) continue;
    const p = parentOf[k];
    if (p) {
      const e = (mentorOf[k] || []).find(x => x.t === p);
      edges.push({ a: p, b: k, e: e || { lv: 3 } });
    }
  }
  void maxCols;
}

// ══════════ 视图2：放射聚焦 ══════════
let rPos = {}, rList = [], center = null;
function buildRadial(k) {
  center = k; rPos = {}; rList = [];
  if (!k || !N[k]) return;
  const me = (mentorOf[k] || []).slice(0, 8);
  const st = (studentsOf[k] || []).slice(0, 40);
  const sibSet = new Set();
  for (const e of me) for (const e2 of (studentsOf[e.t] || [])) if (e2.s !== k) sibSet.add(e2.s);
  const sib = [...sibSet].slice(0, 20);
  const col = COLB.filter(e => (e.s === k || e.t === k) && e.n >= 3)
    .map(e => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 14);
  rPos[k] = { x: 0, y: 0, r: 15, kind: 'me' };
  rList.push(k);
  const ring = (arr, radius, kind, get) => {
    arr.forEach((item, i) => {
      const kk = get ? get(item).k : item;
      if (!kk || rPos[kk]) return;
      const a = (i / Math.max(arr.length, 1)) * Math.PI * 2 - Math.PI / 2;
      rPos[kk] = { x: Math.cos(a) * radius, y: Math.sin(a) * radius, r: 8, kind };
      rList.push(kk);
    });
  };
  ring(st.map(x => x.s), 190, 'student');
  ring(me.map(x => x.t), 330, 'mentor');
  ring(sib, 470, 'sib');
  ring(col, 620, 'collab', x => x);
}

// ══════════ 视图3：合作热力图 ══════════
function buildHeat() {
  const schools = [...new Set(Object.keys(N).map(k => SCH(k)))].sort();
  const idx = {}; schools.forEach((s, i) => idx[s] = i);
  const m = schools.map(() => schools.map(() => 0));
  const pairs = {};
  for (const e of COLB) {
    if (!N[e.s] || !N[e.t]) continue;
    const a = idx[SCH(e.s)], b = idx[SCH(e.t)];
    if (a === undefined || b === undefined) continue;
    if (a !== b) { m[a][b] += e.n; m[b][a] += e.n; const k = Math.min(a, b) + '-' + Math.max(a, b); (pairs[k] = pairs[k] || []).push(e); }
  }
  let maxOff = 1;
  for (let i = 0; i < schools.length; i++) for (let j = 0; j < schools.length; j++) if (i !== j) maxOff = Math.max(maxOff, m[i][j]);
  let h = '<div style="font-size:11.5px;color:#5a6472;margin-bottom:12px;line-height:1.8">格子＝两校之间的<b style="color:#c9d4e2">跨校合作总篇数</b>。颜色越深合作越多，<b style="color:#c9d4e2">点击格子</b>查看明细。</div>';
  h += '<table style="border-collapse:separate;border-spacing:2px;font-size:11px"><tr><th></th>';
  for (const s of schools) h += '<th style="font-weight:500;font-size:10.5px;color:' + (COL[s] || '#94a3b8') + ';writing-mode:vertical-rl;transform:rotate(180deg);height:72px;text-align:left;vertical-align:bottom;white-space:nowrap">' + esc(s) + '</th>';
  h += '</tr>';
  for (let i = 0; i < schools.length; i++) {
    h += '<tr><th style="text-align:right;font-weight:500;font-size:10.5px;color:' + (COL[schools[i]] || '#94a3b8') + ';white-space:nowrap;padding-right:4px">' + esc(schools[i]) + '</th>';
    for (let j = 0; j < schools.length; j++) {
      if (i === j) { h += '<td style="width:28px;height:24px;background:#ffffff06;border-radius:3px"></td>'; continue; }
      const v = m[i][j];
      const t = v ? Math.pow(v / maxOff, .45) : 0;
      const style = v ? 'background:rgba(244,114,182,' + (0.12 + 0.78 * t).toFixed(2) + ');color:' + (t > .5 ? '#fff' : '#fbcfe8') : 'background:#ffffff08;color:#3f4855';
      h += '<td data-i="' + i + '" data-j="' + j + '" style="width:28px;height:24px;text-align:center;border-radius:3px;cursor:pointer;' + style + '" title="' + esc(schools[i]) + ' ↔ ' + esc(schools[j]) + '：' + v + ' 篇">' + (v || '') + '</td>';
    }
    h += '</tr>';
  }
  h += '</table>';
  $('main').innerHTML = '<div id="heatWrap" style="height:100%;overflow:auto;padding:16px 20px">' + h + '</div><div id="drawer"></div><div id="tip"></div>';
  $('main')._schools = schools; $('main')._pairs = pairs;
  document.querySelectorAll('#main table td[data-i]').forEach(td => {
    td.onclick = () => {
      const i = +td.dataset.i, j = +td.dataset.j;
      const a = schools[i], b = schools[j];
      const list = (pairs[Math.min(i, j) + '-' + Math.max(i, j)] || []).sort((x, y) => y.n - x.n).slice(0, 60);
      showList(a + ' ↔ ' + b, list.map(e => ({ a: SCH(e.s) === a ? e.s : e.t, b: SCH(e.s) === a ? e.t : e.s, note: e.n + ' 篇' })));
    };
  });
}
function showList(title, items) {
  const d = $('drawer'); if (!d) return;
  d.style.display = 'block';
  d.innerHTML = '<button id="close">×</button><h3>' + esc(title) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">共 ' + items.length + ' 对（按篇数降序）</div>' +
    '<div class="rel"><b>明细</b>' + (items.length ? items.map(x =>
      '<div style="line-height:1.95"><a data-k="' + esc(x.a) + '">' + esc(NAME(x.a)) + '</a>' +
      '<span style="color:#4b5563"> ↔ </span><a data-k="' + esc(x.b) + '">' + esc(NAME(x.b)) + '</a>' +
      '<span style="color:#5a6472;font-size:11px"> ' + esc(x.note) + '</span></div>').join('') : '—') + '</div>';
  d.querySelectorAll('a[data-k]').forEach(a => { a.onclick = () => showPerson(a.dataset.k); });
  const c = $('close'); if (c) c.onclick = () => { d.style.display = 'none'; };
}

// ══════════ 渲染 ══════════
function fitView(pad) {
  if (view === 'radial') return;
  if (!nodes.length) return;
  // ⚠️ 必须把节点半径算进包围盒，否则大圆会被画布边缘切掉
  const x0 = Math.min(...nodes.map(n => n.x - n.r)), x1 = Math.max(...nodes.map(n => n.x + n.r));
  // 下方留出标签空间
  const y0 = Math.min(...nodes.map(n => n.y - n.r));
  const y1 = Math.max(...nodes.map(n => n.y + n.r + (n.root ? 44 : 26)));
  const gw = Math.max(x1 - x0, 1), gh = Math.max(y1 - y0, 1);
  const P = pad || 70;
  scale = Math.max(0.05, Math.min((W - P * 2) / gw, (H - P * 2) / gh, 2.2));
  ox = (W - gw * scale) / 2 - x0 * scale;
  oy = (H - gh * scale) / 2 - y0 * scale;
}
function render() {
  if (view === 'heat') return;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, W, H);
  if (view === 'radial') return renderRadial();
  ctx.setTransform(DPR * scale, 0, 0, DPR * scale, DPR * ox, DPR * oy);

  // 边
  for (const e of edges) {
    const a = nodes.find(n => n.k === e.a), b = nodes.find(n => n.k === e.b);
    if (!a || !b) continue;
    const cr = isCross(e.e);
    const col = cr ? '#f472b6' : (e.e.lv === 1 ? '#fbbf24' : e.e.lv === 2 ? '#f59e0b' : '#a16207');
    ctx.strokeStyle = col;
    ctx.lineWidth = (cr ? 2.6 : e.e.lv === 1 ? 2.4 : e.e.lv === 2 ? 1.7 : 1.0) / Math.max(scale, .3);
    ctx.beginPath(); ctx.moveTo(a.x, a.y + a.r); ctx.lineTo(b.x, b.y - b.r - 2); ctx.stroke();
    // 箭头
    const ang = Math.atan2(b.y - b.r - 6 - (a.y + a.r), b.x - a.x);
    const ex = b.x, ey = b.y - b.r - 3, L = 8 / Math.max(scale, .4);
    ctx.beginPath(); ctx.moveTo(ex, ey);
    ctx.lineTo(ex - L * Math.cos(ang - .45), ey - L * Math.sin(ang - .45));
    ctx.lineTo(ex - L * Math.cos(ang + .45), ey - L * Math.sin(ang + .45));
    ctx.closePath(); ctx.fillStyle = col; ctx.fill();
  }
  // 节点
  for (const n of nodes) {
    if (n.hasCross) {
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 4, 0, 7);
      ctx.strokeStyle = '#f472b6'; ctx.lineWidth = 2 / Math.max(scale, .4); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 7);
    ctx.fillStyle = COL[SCH(n.k)] || '#64748b'; ctx.fill();
    ctx.strokeStyle = (n.k === sel || n.k === hover) ? '#fbbf24' : 'rgba(11,14,20,.92)';
    ctx.lineWidth = (n.k === sel || n.k === hover ? 3 : 1.4) / Math.max(scale, .4);
    ctx.stroke();
  }
  // 标签（屏幕坐标恒字号）
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.textAlign = 'center';
  const placed = [];
  const order = nodes.slice().sort((a, b) => (b.root ? 1 : 0) - (a.root ? 1 : 0) || NP(b.k) - NP(a.k));
  for (const n of order) {
    const sx = n.x * scale + ox, sy = n.y * scale + oy;
    if (sx < -80 || sx > W + 80 || sy < -30 || sy > H + 30) continue;
    const r = Math.max(n.r * scale, 3);
    const fs = n.root ? 14 : 11.5;
    const label = NAME(n.k);
    ctx.font = (n.root ? 'bold ' : '') + fs + 'px -apple-system,"Microsoft YaHei",sans-serif';
    const tw = ctx.measureText(label).width;
    // 根节点较大：名字直接画在圆内，避免被节点盖住
    if (n.root && r * 2 > tw + 10 && r > 16) {
      ctx.fillStyle = 'rgba(11,14,20,.55)';
      ctx.fillText(label, sx, sy + fs * 0.36);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, sx, sy + fs * 0.36);
      const sub = n.cnt + ' 名学生';
      ctx.font = '10.5px -apple-system,"Microsoft YaHei",sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,.75)';
      ctx.fillText(sub, sx, sy + fs * 0.36 + 15);
      continue;
    }
    const ty = sy + r + fs + 1;
    let ok = true;
    for (const p of placed) if (sx - tw / 2 < p[1] && sx + tw / 2 > p[0] && ty - fs < p[3] && ty > p[2]) { ok = false; break; }
    if (!ok && !n.root) continue;
    placed.push([sx - tw / 2, sx + tw / 2, ty - fs, ty]);
    ctx.fillStyle = 'rgba(11,14,20,.82)';
    ctx.fillRect(sx - tw / 2 - 3, ty - fs, tw + 6, fs + 4);
    ctx.fillStyle = n.k === sel ? '#fbbf24' : '#e8edf5';
    ctx.fillText(label, sx, ty);
    if (n.root && n.cnt) {
      const sub = n.cnt + ' 名学生';
      ctx.font = '10.5px -apple-system,"Microsoft YaHei",sans-serif';
      const sw = ctx.measureText(sub).width;
      ctx.fillStyle = 'rgba(11,14,20,.8)';
      ctx.fillRect(sx - sw / 2 - 2, ty + 2, sw + 4, 14);
      ctx.fillStyle = '#7c8ba1';
      ctx.fillText(sub, sx, ty + 13);
    }
  }
}

function renderRadial() {
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, W, H);
  if (!center) {
    ctx.fillStyle = '#3f4855'; ctx.font = '13px -apple-system,"Microsoft YaHei",sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('请先选择一位导师', W / 2, H / 2);
    return;
  }
  const fit = Math.min(W / 1500, H / 1400), cx = W / 2, cy = H / 2;
  const P = (p) => ({ x: cx + p.x * fit, y: cy + p.y * fit });
  for (const [rr, lb] of [[190, '学生'], [330, '导师'], [470, '同门'], [620, '主要合作者']]) {
    ctx.beginPath(); ctx.arc(cx, cy, rr * fit, 0, 7);
    ctx.strokeStyle = 'rgba(255,255,255,.05)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = 'rgba(120,132,150,.5)'; ctx.font = '10px -apple-system,"Microsoft YaHei",sans-serif';
    ctx.textAlign = 'left'; ctx.fillText(lb, cx + 5, cy - rr * fit + 11);
  }
  for (const kk of rList) {
    if (kk === center) continue;
    const p = rPos[kk]; if (!p) continue;
    const a = { x: cx, y: cy }, b = P(p);
    const e = (mentorOf[center] || []).find(x => x.t === kk) || (studentsOf[center] || []).find(x => x.s === kk);
    ctx.strokeStyle = e ? (isCross(e) ? '#f472b6' : (e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207')) : 'rgba(99,102,241,.3)';
    ctx.lineWidth = e ? 2 : 1;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const q = P(p), rr = (kk === center ? 15 : 8) * Math.max(fit, .55);
    ctx.beginPath(); ctx.arc(q.x, q.y, rr, 0, 7);
    ctx.fillStyle = COL[SCH(kk)] || '#64748b'; ctx.fill();
    ctx.strokeStyle = kk === center ? '#fbbf24' : 'rgba(11,14,20,.9)';
    ctx.lineWidth = kk === center ? 2.5 : 1.3; ctx.stroke();
  }
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const q = P(p), rr = (kk === center ? 15 : 8) * Math.max(fit, .55);
    const fs = kk === center ? 14 : 11.5;
    ctx.font = (kk === center ? 'bold ' : '') + fs + 'px -apple-system,"Microsoft YaHei",sans-serif';
    const dx = q.x - cx, dy = q.y - cy, dd = Math.hypot(dx, dy) || 1;
    const ux = dd > 1 ? dx / dd : 0, uy = dd > 1 ? dy / dd : -1;
    const lx = q.x + ux * (rr + 8), ly = q.y + uy * (rr + 8);
    const label = NAME(kk), tw = ctx.measureText(label).width;
    ctx.textAlign = ux > .25 ? 'left' : ux < -.25 ? 'right' : 'center';
    ctx.fillStyle = 'rgba(11,14,20,.78)';
    ctx.fillRect(lx - (ctx.textAlign === 'center' ? tw / 2 : ctx.textAlign === 'right' ? tw : 0) - 2, ly - fs + 1, tw + 4, fs + 3);
    ctx.fillStyle = kk === center ? '#fbbf24' : '#dbe3ee';
    ctx.fillText(label, lx, ly);
  }
}

// ══════════ 个人档案 ══════════
function showPerson(k) {
  if (!k || !N[k]) return;
  const P = N[k];
  const me = (mentorOf[k] || []).map(e => e.t);
  const st = (studentsOf[k] || []).map(e => e.s);
  const sib = [];
  for (const e of (mentorOf[k] || [])) for (const e2 of (studentsOf[e.t] || [])) if (e2.s !== k) sib.push(e2.s);
  const cols = COLB.filter(e => (e.s === k || e.t === k) && e.n >= 3)
    .map(e => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 24);
  const lvTag = (other, up) => {
    const e = ADV.find(x => up ? (x.s === k && x.t === other) : (x.t === k && x.s === other));
    if (!e) return '';
    const c = isCross(e) ? '#f472b6' : e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
    return '<span class="badge" style="background:' + c + '22;color:' + c + ';border:1px solid ' + c + '55" title="' + esc(e.nt || '') + '">' + (isCross(e) ? '跨校 ' : '') + 'L' + e.lv + '</span>';
  };
  const L = (arr, f) => arr.length ? arr.map(f).join('') : '<span style="color:#3f4855">—</span>';
  const d = $('drawer'); if (!d) return;
  d.style.display = 'block';
  d.innerHTML = '<button id="close">×</button>' +
    '<h3>' + esc(NAME(k)) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">' + esc(SCH(k)) + (P.t ? ' · ' + esc(P.t) : '') + '</div>' +
    (P.d ? '<div style="font-size:12px;color:#5a6472">' + esc(P.d) + '</div>' : '') +
    '<div style="margin-top:7px"><span class="tag">论文 ' + NP(k) + ' 篇</span>' + (st.length ? '<span class="tag" style="background:#1d2a45;color:#93c5fd">' + st.length + ' 名学生</span>' : '') + (P.c ? '<span class="tag">' + esc(P.c.slice(0, 40)) + '</span>' : '') + '</div>' +
    (P.h ? '<div style="margin-top:6px"><a href="' + esc(P.h) + '" target="_blank" style="color:#60a5fa;font-size:12px">打开主页 ↗</a></div>' : '') +
    ((P.edu.length || P.pd.length || P.job.length) ? '<div class="rel"><b>学历与工作经历（页面自述）</b>' +
      P.edu.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '</div>').join('') +
      P.pd.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '（博士后）</div>').join('') +
      P.job.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '</div>').join('') + '</div>' : '') +
    '<div class="rel"><b>导师（' + me.length + '）</b>' + L(me, m => '<a data-k="' + esc(m) + '">' + esc(NAME(m)) + '</a>' + lvTag(m, true)) + '</div>' +
    '<div class="rel"><b>学生（' + st.length + '）</b>' + L(st, s => '<a data-k="' + esc(s) + '">' + esc(NAME(s)) + '</a>' + lvTag(s, false)) + '</div>' +
    (sib.length ? '<div class="rel"><b>同门（' + sib.length + '）</b>' + L(sib.slice(0, 40), x => '<a data-k="' + esc(x) + '">' + esc(NAME(x)) + '</a>') + '</div>' : '') +
    '<div class="rel"><b>主要合作者（共同署名篇数）</b>' + L(cols, c => '<a data-k="' + esc(c.k) + '">' + esc(NAME(c.k)) + ' <span style="color:#5a6472">' + c.n + '</span></a>') + '</div>' +
    (st.length ? '<div class="rel"><b>操作</b><a id="focusBtn" style="color:#fbbf24">以他为中心展开师承树 →</a></div>' : '');
  d.querySelectorAll('a[data-k]').forEach(a => { a.onclick = () => showPerson(a.dataset.k); });
  const c = $('close'); if (c) c.onclick = () => { d.style.display = 'none'; };
  const fb = $('focusBtn');
  if (fb) fb.onclick = () => { setFocus(k); };
}

// ══════════ 交互 ══════════
function setFocus(k) {
  focus = k; view = 'tree';
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.v === 'tree'));
  restoreCanvas();
  layoutTree(); fitView(90); render(); renderCrumb(); renderMentorList();
  const d = $('drawer'); if (d) d.style.display = 'none';
}
function renderCrumb() {
  const c = $('crumb');
  if (!c) return;
  if (!focus) { c.style.display = 'none'; return; }
  c.style.display = 'flex';
  const st = (studentsOf[focus] || []).length;
  c.innerHTML = '<a id="back">← 返回总览</a> <span style="color:#3f4855">|</span> <b>' + esc(NAME(focus)) + '</b>' +
    '<span style="color:#7c8ba1">' + esc(SCH(focus)) + ' · ' + st + ' 名学生 · 论文 ' + NP(focus) + ' 篇</span>';
  const b = $('back'); if (b) b.onclick = () => { focus = null; layoutTree(); fitView(70); render(); renderCrumb(); renderMentorList(); };
}
function renderMentorList() {
  const box = $('mlist'); if (!box) return;
  const list = MENTORS.filter(m => m.n >= th).slice(0, 80);
  box.innerHTML = list.length ? list.map(m =>
    '<div class="mentorItem' + (m.k === focus ? ' on' : '') + '" data-k="' + esc(m.k) + '">' +
    '<span class="dot" style="background:' + (COL[SCH(m.k)] || '#64748b') + '"></span>' +
    '<span class="nm">' + esc(NAME(m.k)) + '</span>' +
    '<span class="cs">' + m.n + ' 名</span></div>').join('') :
    '<div style="color:#3f4855;font-size:12px;padding:8px">无</div>';
  box.querySelectorAll('.mentorItem').forEach(el => { el.onclick = () => setFocus(el.dataset.k); });
}
function restoreCanvas() {
  if ($('cv')) return;
  $('main').innerHTML = '<canvas id="cv"></canvas><div id="crumb"></div>' +
    '<div id="hint">滚轮缩放 · 拖拽平移 · 点击节点看档案 · 双击适应窗口</div>' +
    '<div id="tip"></div><div id="drawer"></div>';
  bindCanvas();
}
let drag = null;
function bindCanvas() {
  const c = $('cv');
  c.addEventListener('mousedown', (e) => { drag = { x: e.clientX, y: e.clientY, ox, oy, moved: false }; c.classList.add('drag'); });
  c.addEventListener('wheel', (e) => {
    e.preventDefault();
    const f = e.deltaY < 0 ? 1.14 : 0.88;
    const r = c.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    ox = mx - (mx - ox) * f; oy = my - (my - oy) * f; scale *= f; render();
  }, { passive: false });
  c.addEventListener('dblclick', () => { fitView(90); render(); });
  c.addEventListener('mousemove', (e) => {
    if (drag) { ox = drag.ox + e.clientX - drag.x; oy = drag.oy + e.clientY - drag.y; render(); return; }
    const k = pick(e);
    if (k !== hover) { hover = k; render(); }
    const tip = $('tip');
    if (!tip) return;
    if (k) {
      const st = (studentsOf[k] || []).length;
      tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 15, W - 300) + 'px';
      tip.style.top = (e.clientY + 15) + 'px';
      tip.innerHTML = '<b>' + esc(NAME(k)) + '</b><br/>' + esc(SCH(k)) + (N[k].t ? ' · ' + esc(N[k].t) : '') +
        '<br/>论文 ' + NP(k) + ' 篇' + (st ? '<br/><span style="color:#93c5fd">' + st + ' 名学生（点击展开）</span>' : '');
    } else tip.style.display = 'none';
  });
  c.addEventListener('click', (e) => {
    if (drag && drag.moved) return;
    const k = pick(e);
    if (k) showPerson(k);
  });
}
window.addEventListener('mouseup', () => { if (drag) drag = null; });
window.addEventListener('mousemove', (e) => {
  if (!drag) return;
  const c = $('cv'); if (!c) return;
  ox = drag.ox + e.clientX - drag.x; oy = drag.oy + e.clientY - drag.y; render();
});
function pick(e) {
  const c = $('cv'); if (!c) return null;
  const r = c.getBoundingClientRect();
  if (view === 'radial') {
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const fit = Math.min(W / 1500, H / 1400), cx = W / 2, cy = H / 2;
    let best = null, bd = Infinity;
    for (const kk of rList) {
      const p = rPos[kk]; if (!p) continue;
      const dd = (cx + p.x * fit - mx) ** 2 + (cy + p.y * fit - my) ** 2;
      if (dd < 400 && dd < bd) { bd = dd; best = kk; }
    }
    return best;
  }
  const x = (e.clientX - r.left - ox) / scale, y = (e.clientY - r.top - oy) / scale;
  let best = null, bd = Infinity;
  for (const n of nodes) {
    const rr = n.r + 6 / scale;
    const d = (n.x - x) ** 2 + (n.y - y) ** 2;
    if (d < rr * rr && d < bd) { bd = d; best = n.k; }
  }
  return best;
}
function resize() {
  DPR = window.devicePixelRatio || 1;
  const r = $('main').getBoundingClientRect();
  W = r.width; H = r.height;
  const c = $('cv');
  if (c) { c.width = W * DPR; c.height = H * DPR; c.style.width = W + 'px'; c.style.height = H + 'px'; }
  if (view === 'tree') { layoutTree(); fitView(focus ? 90 : 70); render(); }
  else render();
}
window.addEventListener('resize', resize);

// ══════════ 视图切换 ══════════
function setView(v) {
  view = v;
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.v === v));
  if (v === 'heat') { buildHeat(); return; }
  restoreCanvas();
  if (v === 'tree') { layoutTree(); fitView(focus ? 90 : 70); }
  else { buildRadial(focus || (MENTORS[0] && MENTORS[0].k)); }
  resize();
  renderCrumb();
}
document.querySelectorAll('.tab').forEach(t => { t.onclick = () => setView(t.dataset.v); });
$('q').addEventListener('input', (e) => {
  const v = e.target.value.trim(), res = $('qres');
  if (!v) { res.innerHTML = ''; return; }
  const hits = Object.keys(N).filter(k => NAME(k).includes(v)).slice(0, 10);
  res.innerHTML = hits.length ? hits.map(k =>
    '<div class="mentorItem" data-k="' + esc(k) + '"><span class="dot" style="background:' + (COL[SCH(k)] || '#64748b') + '"></span>' +
    '<span class="nm">' + esc(NAME(k)) + '</span><span class="cs">' + esc(SCH(k)) + '</span></div>').join('')
    : '<div style="color:#3f4855;font-size:12px;padding:6px">无匹配</div>';
  res.querySelectorAll('.mentorItem').forEach(el => {
    el.onclick = () => {
      const k = el.dataset.k;
      if ((studentsOf[k] || []).length) setFocus(k);
      else { if (view !== 'tree') setView('tree'); showPerson(k); }
    };
  });
});
$('th').oninput = (e) => {
  th = +e.target.value; $('tv').textContent = th;
  renderMentorList();
  if (view === 'tree' && !focus) { layoutTree(); fitView(70); render(); }
};

$('sA').textContent = ADV.filter(e => N[e.s] && N[e.t]).length;
$('sX').textContent = CROSS.length;
$('sM').textContent = MENTORS.length;

renderMentorList();
restoreCanvas();
resize();
layoutTree();
fitView(70);
render();
renderCrumb();
</script></body></html>`;

fs.writeFileSync(path.join(REPO, 'reports', '导师关系网络.html'), html, 'utf8');
console.log('saved reports/导师关系网络.html', (html.length / 1024).toFixed(0) + 'KB');
const ment = new Set(net.advisor.map((e) => e.t));
console.log('导师', ment.size, '| 师承', DATA.advisor.length, '| 有学生的导师', [...ment].filter((k) => net.advisor.some((e) => e.t === k)).length);
