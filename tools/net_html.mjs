// net_html.mjs — 关系网络 v4：大纲 + 聚焦 + 热力图
//
// v1-v3 的教训：反复优化布局算法（力导向→树状→按院校分区），但始终把
// 几百上千个节点同时铺在画布上。节点一多，任何布局都必然杂乱——
// **清晰来自于「少显示」，而不是「排得好」**。
//
// v4 彻底换形式：
//   ① 师承大纲 —— 用 HTML 缩进树代替画布绘图。文字天然可读、可折叠、可搜索，
//                  绝无重叠。跨校关系用徽标标出，并单列一节突出显示。
//   ② 放射聚焦 —— 画布上一次只画「一个人 + 他的直接关系」（20-40 个节点），
//                  点击任意节点即以它为中心重绘。逐层走图，永不拥挤。
//   ③ 合作热力图 —— 院校 × 院校矩阵。2000+ 条合作关系压成 20×20 格子，
//                  从根上不可能杂乱。
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
  advisor: net.advisor.map((e) => ({ s: e.s, t: e.t, n: e.n, lv: e.lv, sp: e.span || '', nt: e.note || '', inst: e.inst || '', ty: e.type || '' })),
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
#side{width:300px;flex:0 0 300px;background:#12161f;border-right:1px solid #232936;overflow-y:auto;padding:14px}
#main{flex:1;position:relative;overflow:hidden;display:flex;flex-direction:column}
h1{font-size:15px;margin:0 0 3px}
h2{font-size:11px;margin:15px 0 6px;color:#7c8ba1;letter-spacing:.6px;text-transform:uppercase}
.sub{font-size:11px;color:#5a6472;margin-bottom:11px}
.tabs{display:flex;flex-direction:column;gap:5px;margin-bottom:10px}
.tab{padding:8px 10px;background:#1a1f2b;border:1px solid #232936;border-radius:7px;cursor:pointer;font-size:12.5px;color:#8b98a9;transition:.15s;display:flex;align-items:center;gap:8px}
.tab:hover{background:#212736;color:#c3ccd8}
.tab.on{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
.tab .ic{font-size:14px;width:16px;text-align:center}
label{display:flex;align-items:center;gap:7px;padding:5px 0;cursor:pointer;font-size:12px;color:#c3ccd8}
input[type=checkbox]{accent-color:#2563eb;width:14px;height:14px;cursor:pointer}
input[type=text]{width:100%;padding:8px 10px;background:#0b0e14;border:1px solid #232936;border-radius:6px;color:#e5e7eb;font-size:12.5px}
input[type=text]:focus{outline:none;border-color:#2563eb}
.stat{display:flex;justify-content:space-between;padding:2px 0;font-size:12px;color:#8b98a9}
.stat b{color:#e5e7eb}
.warn{background:#78350f1a;border:1px solid #92400e;border-radius:7px;padding:8px 10px;font-size:11px;color:#fbbf24;line-height:1.65;margin-top:9px}
.warn b{color:#fcd34d}
.legend{font-size:11px;color:#8b98a9;line-height:1.9}
.badge{display:inline-block;padding:0 5px;border-radius:3px;font-size:10px;line-height:15px;margin-left:5px;vertical-align:1px}
.b1{background:#fbbf2426;color:#fbbf24;border:1px solid #fbbf2455}
.b2{background:#f59e0b26;color:#f59e0b;border:1px solid #f59e0b55}
.b3{background:#a1620726;color:#b8860b;border:1px solid #a1620755}
.bx{background:#f472b626;color:#f472b6;border:1px solid #f472b655}

/* ── 大纲视图 ── */
#outline{flex:1;overflow-y:auto;padding:16px 20px}
.school{margin-bottom:9px;border:1px solid #1e2430;border-radius:9px;overflow:hidden;background:#0e121a}
.schoolHd{display:flex;align-items:center;gap:9px;padding:9px 13px;cursor:pointer;user-select:none;background:#141924}
.schoolHd:hover{background:#181e2b}
.schoolHd .tri{color:#5a6472;font-size:10px;transition:transform .15s;display:inline-block}
.schoolHd.open .tri{transform:rotate(90deg)}
.schoolHd .nm{font-weight:600;font-size:13px}
.schoolHd .cnt{margin-left:auto;font-size:11px;color:#5a6472}
.schoolBd{display:none;padding:6px 0 10px 0}
.schoolHd.open + .schoolBd{display:block}
.row{display:flex;align-items:baseline;gap:8px;padding:3px 13px 3px 0;line-height:1.75;border-radius:4px}
.row:hover{background:#161c27}
.row .nm{color:#c9d4e2;cursor:pointer;font-size:12.5px}
.row .nm:hover{color:#60a5fa;text-decoration:underline}
.row .nm.mentor{font-weight:600;color:#e8edf5}
.row .meta{font-size:11px;color:#4b5563}
.row .pp{font-size:10.5px;color:#4b5563;margin-left:auto;flex:0 0 auto}
.row.dim{opacity:.35}
.mentorBlk{margin:3px 0 3px 6px;border-left:2px solid #1e2430;padding-left:2px}
.mentorBlk.hl{border-left-color:#2563eb}
.mentorBlk > .row{padding-left:8px}
.mentorBlk .mentorBlk{margin-left:20px}
.tick{color:#3f4855;user-select:none;cursor:pointer;width:13px;display:inline-block;text-align:center;font-size:9px;flex:0 0 13px}
.crossList{padding:12px 20px;border-bottom:1px solid #1e2430;background:#12161f}
.crossList h3{margin:0 0 8px;font-size:12px;color:#f472b6;letter-spacing:.4px}
.crossItem{display:flex;align-items:baseline;gap:8px;font-size:12.5px;padding:3px 0;line-height:1.7}
.crossItem .nm{color:#60a5fa;cursor:pointer}
.crossItem .nm:hover{text-decoration:underline}
.empty{color:#3f4855;padding:26px;text-align:center;font-size:12.5px}

/* ── 放射聚焦 ── */
#radWrap{flex:1;position:relative;overflow:hidden}
#rad{display:block;cursor:grab}
#rad.drag{cursor:grabbing}
#radHd{position:absolute;left:14px;top:12px;font-size:12px;color:#7c8ba1;background:#0b0e14d9;padding:7px 12px;border-radius:7px;border:1px solid #232936;line-height:1.7;max-width:420px}
#radHd b{color:#e5e7eb}
#radHd a{color:#60a5fa;cursor:pointer;text-decoration:none}

/* ── 热力图 ── */
#heatWrap{flex:1;overflow:auto;padding:18px 22px}
table.heat{border-collapse:separate;border-spacing:2px;font-size:11px}
table.heat th{font-weight:500;color:#7c8ba1;font-size:10.5px;padding:2px 4px;white-space:nowrap}
table.heat th.rot{writing-mode:vertical-rl;transform:rotate(180deg);height:74px;text-align:left;vertical-align:bottom}
table.heat td{width:28px;height:24px;text-align:center;border-radius:3px;color:#c9d4e2;cursor:pointer;transition:.12s}
table.heat td:hover{outline:2px solid #60a5fa}
table.heat td.d0{background:#ffffff08}
table.heat td.diag{background:#6366f12e;color:#c7d2fe;font-weight:600}
.hint{font-size:11.5px;color:#5a6472;margin-bottom:12px;line-height:1.8}

#drawer{position:absolute;right:0;top:0;width:340px;height:100%;background:#12161ff7;border-left:1px solid #232936;padding:15px;overflow-y:auto;display:none;backdrop-filter:blur(6px);z-index:30}
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
    <div class="tabs">
      <div class="tab on" data-v="outline"><span class="ic">☰</span>师承大纲</div>
      <div class="tab" data-v="radial"><span class="ic">◎</span>放射聚焦</div>
      <div class="tab" data-v="heat"><span class="ic">▦</span>合作热力图</div>
    </div>

    <h2>搜索</h2>
    <input type="text" id="q" placeholder="输入姓名，大纲自动展开定位…"/>

    <h2>统计</h2>
    <div class="stat"><span>师承关系</span><b id="sA">0</b></div>
    <div class="stat"><span>其中跨校</span><b id="sX" style="color:#f472b6">0</b></div>
    <div class="stat"><span>覆盖院校</span><b id="sS">0</b></div>
    <div class="stat"><span>合作对数</span><b id="sC">0</b></div>

    <h2>说明</h2>
    <div class="legend">
      本页刻意<b style="color:#e5e7eb">不把几百个节点同时画在图上</b>——
      那样无论怎么排都会杂乱。改为：<br/>
      · <b>大纲</b>用文字表达层级，天然可读可折叠<br/>
      · <b>放射</b>一次只看一个人的直接关系<br/>
      · <b>热力图</b>把 2000+ 条合作压成 20×20 格子
    </div>

    <h2>证据等级</h2>
    <div class="legend">
      <span class="badge b1">L1</span> 本人页面明写「导师为／师从 XX」<br/>
      <span class="badge b2">L2</span> 毕业院校 × 早期论文末位作者，两条独立证据<br/>
      <span class="badge b3">L3</span> 仅署名模式推断，无学历佐证<br/>
      <span class="badge bx">跨校</span> 导师与学生不在同一单位
    </div>

    <div class="warn">
      所有署名均经<b>姓名＋机构双重校验</b>，机构不符或无法判定者一律丢弃。
      本页只反映公开页面自述与论文署名可推断的关系，<b>不代表完整师承，也不构成任何评价</b>。
    </div>
  </div>

  <div id="main">
    <div id="outline"></div>
    <div id="radWrap" style="display:none">
      <canvas id="rad"></canvas>
      <div id="radHd"></div>
    </div>
    <div id="heatWrap" style="display:none"></div>
    <div id="drawer"></div>
  </div>
</div>
<script>
const DATA = ${JSON.stringify(DATA)};
const N = DATA.nodes, COL = DATA.colors, ADV = DATA.advisor, COLB = DATA.collab, SIB = DATA.sibling;
const $ = id => document.getElementById(id);
const NAME = k => (N[k] ? N[k].n : k);
const SCH = k => (N[k] ? N[k].s : '?');
const NP = k => (N[k] ? (N[k].p || 0) : 0);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const isCross = e => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc;

// ── 派生结构 ──
const mentorOf = {}, studentsOf = {};
for (const e of ADV) {
  if (!N[e.s] || !N[e.t]) continue;
  (studentsOf[e.t] = studentsOf[e.t] || []).push(e);
  (mentorOf[e.s] = mentorOf[e.s] || []).push(e);
}
const lvOf = (k, other, up) => {
  const e = ADV.find(x => up ? (x.s === k && x.t === other) : (x.t === k && x.s === other));
  return e || null;
};
const CROSS = ADV.filter(isCross);

// ══════════ 视图1：师承大纲 ══════════
let openState = {};
function buildOutline() {
  const bySchool = {};
  const involved = new Set();
  for (const e of ADV) { if (N[e.s] && N[e.t]) { involved.add(e.s); involved.add(e.t); } }
  for (const k of involved) (bySchool[SCH(k)] = bySchool[SCH(k)] || []).push(k);
  const schools = Object.keys(bySchool).sort((a, b) => bySchool[b].length - bySchool[a].length);

  let html = '<div class="crossList"><h3>跨校师承（' + CROSS.length + ' 条 · 全图最有价值的信息）</h3>';
  if (!CROSS.length) html += '<div class="empty">无</div>';
  for (const e of CROSS) {
    const lv = e.lv === 1 ? 'b1" title="页面明写' : e.lv === 2 ? 'b2" title="学历×论文交叉证据' : 'b3" title="署名推断';
    html += '<div class="crossItem">' +
      '<span class="nm" data-k="' + esc(e.t) + '">' + esc(NAME(e.t)) + '</span><span class="meta" style="color:#5a6472;font-size:11px">' + esc(SCH(e.t)) + '</span>' +
      '<span style="color:#f472b6">→</span>' +
      '<span class="nm" data-k="' + esc(e.s) + '">' + esc(NAME(e.s)) + '</span><span class="meta" style="color:#5a6472;font-size:11px">' + esc(SCH(e.s)) + '</span>' +
      '<span class="badge ' + lv + '">L' + e.lv + '</span></div>';
  }
  html += '</div>';

  for (const s of schools) {
    const mem = bySchool[s], mset = new Set(mem);
    // 顶层：在本校范围内没有导师的人
    const roots = mem.filter(k => !(mentorOf[k] || []).some(e => mset.has(e.t)));
    roots.sort((a, b) => (studentsOf[b] || []).length - (studentsOf[a] || []).length || NP(b) - NP(a));
    const open = openState['S:' + s] !== false;
    html += '<div class="school"><div class="schoolHd' + (open ? ' open' : '') + '" data-school="' + esc(s) + '">' +
      '<span class="tri">▶</span><span class="nm" style="color:' + (COL[s] || '#94a3b8') + '">' + esc(s) + '</span>' +
      '<span class="cnt">' + mem.length + ' 人 · ' + roots.length + ' 个师承起点</span></div><div class="schoolBd">';
    const seen = new Set();
    for (const r of roots) html += nodeBlock(r, 0, mset, seen);
    // 环或跨校挂靠导致未被访问的，补在末尾
    const rest = mem.filter(k => !seen.has(k));
    if (rest.length) {
      html += '<div class="row" style="padding-left:13px;color:#4b5563;font-size:11px">— 其他（互为导师或跨校挂靠）—</div>';
      for (const k of rest) html += nodeBlock(k, 0, mset, seen, true);
    }
    html += '</div></div>';
  }
  $('outline').innerHTML = html;
  bindOutline();
}

function nodeBlock(k, depth, mset, seen, orphan) {
  if (seen.has(k)) return '';
  seen.add(k);
  const kids = (studentsOf[k] || []).filter(e => mset.has(e.s) && !seen.has(e.s));
  const myMentors = (mentorOf[k] || []).filter(e => mset.has(e.t));
  const key = 'N:' + k;
  const open = openState[key] !== false;
  const kidCount = kids.length;
  const crossBadge = (mentorOf[k] || []).some(isCross) ? '<span class="badge bx">跨校</span>' : '';
  // 同校多位导师时，等级徽标去重（否则会出现 [L3] [L3]），并标注「双导师」
  const profMentors = (mentorOf[k] || []).filter(e => mset.has(e.t));
  const lvSet = [...new Set(profMentors.map(e => e.lv))].sort();
  const lvB = lvSet.map(l => '<span class="badge b' + l + '" title="' + esc(profMentors.filter(e => e.lv === l).map(e => NAME(e.t)).join('、')) + '">L' + l + '</span>').join('') +
    (profMentors.length > 1 ? '<span class="badge" style="background:#1e2430;color:#8b98a9;border:1px solid #2f3744" title="' + esc(profMentors.map(e => NAME(e.t)).join('、')) + '">' + profMentors.length + ' 位导师</span>' : '');
  const indent = 6 + depth * 20;
  let h = '<div class="mentorBlk' + (depth === 0 ? '' : '') + '"' + (kids.length ? '' : '') + '>' +
    '<div class="row" style="padding-left:' + indent + 'px">' +
    (kidCount ? '<span class="tick" data-toggle="' + esc(key) + '">' + (open ? '▼' : '▶') + '</span>' : '<span class="tick"></span>') +
    '<span class="nm mentor" data-k="' + esc(k) + '">' + esc(NAME(k)) + '</span>' +
    (N[k] && N[k].t ? '<span class="meta">' + esc(N[k].t) + '</span>' : '') +
    crossBadge + lvB +
    '<span class="pp">' + (kidCount ? kidCount + ' 名学生' : '') + (NP(k) ? (kidCount ? ' · ' : '') + NP(k) + ' 篇' : '') + '</span>' +
    '</div>';
  if (kidCount && open) {
    h += '<div class="mentorBlk" style="margin-left:' + (indent + 6) + 'px">';
    kids.sort((a, b) => NP(b.s) - NP(a.s));
    for (const e of kids) h += nodeBlock(e.s, 0, mset, seen, false);
    h += '</div>';
  }
  h += '</div>';
  void myMentors; void orphan;
  return h;
}

function bindOutline() {
  document.querySelectorAll('.schoolHd').forEach(h => {
    h.onclick = () => {
      const s = h.dataset.school;
      const now = h.classList.toggle('open');
      openState['S:' + s] = now;
    };
  });
  document.querySelectorAll('.tick[data-toggle]').forEach(t => {
    t.onclick = (ev) => {
      ev.stopPropagation();
      const key = t.dataset.toggle;
      openState[key] = openState[key] === false;
      buildOutline();
    };
  });
  document.querySelectorAll('.nm[data-k]').forEach(a => {
    a.onclick = () => showPerson(a.dataset.k);
  });
}

// ══════════ 视图2：放射聚焦 ══════════
const rad = $('rad'), rctx = rad.getContext('2d');
let RW = 0, RH = 0, center = null, rPos = {}, rList = [], hovR = null;

function buildRadial(k) {
  center = k;
  rPos = {}; rList = [];
  if (!k || !N[k]) { return; }
  const me = (mentorOf[k] || []).slice(0, 8);
  const st = (studentsOf[k] || []).slice(0, 40);
  const sibSet = new Set();
  for (const e of me) for (const e2 of (studentsOf[e.t] || [])) if (e2.s !== k) sibSet.add(e2.s);
  const sib = [...sibSet].slice(0, 20);
  const col = COLB.filter(e => (e.s === k || e.t === k) && e.n >= 3)
    .map(e => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 14);

  rPos[k] = { x: 0, y: 0, r: 15, kind: 'me' };
  rList.push(k);
  // ⚠️ studentsOf/mentorOf 里存的是**边对象**，必须取 .s / .t 才是人名键
  const ring = (arr, radius, kind, get) => {
    arr.forEach((item, i) => {
      const kk = get ? get(item).k : item;
      if (!kk || rPos[kk]) return;
      const a = (i / Math.max(arr.length, 1)) * Math.PI * 2 - Math.PI / 2;
      rPos[kk] = { x: Math.cos(a) * radius, y: Math.sin(a) * radius, r: 8, kind, w: get ? get(item).n : 0 };
      rList.push(kk);
    });
  };
  ring(st.map((x) => x.s), 190, 'student');
  ring(me.map((x) => x.t), 330, 'mentor');
  ring(sib, 470, 'sib');
  ring(col, 620, 'collab', (x) => x);
}

function layoutRad() {
  RW = $('radWrap').clientWidth; RH = $('radWrap').clientHeight;
  const d = window.devicePixelRatio || 1;
  rad.width = RW * d; rad.height = RH * d;
  rad.style.width = RW + 'px'; rad.style.height = RH + 'px';
  return d;
}
function renderRad() {
  const d = layoutRad();
  const ctx = rctx;
  ctx.setTransform(d, 0, 0, d, 0, 0);
  ctx.fillStyle = '#0b0e14'; ctx.fillRect(0, 0, RW, RH);
  if (!center) {
    ctx.fillStyle = '#3f4855'; ctx.font = '13px -apple-system,"Microsoft YaHei",sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('请先从「师承大纲」点击一位导师，或在上方搜索', RW / 2, RH / 2);
    $('radHd').innerHTML = '';
    return;
  }
  const fit = Math.min(RW / 1500, RH / 1400);
  const cx = RW / 2, cy = RH / 2;
  const P = (p) => ({ x: cx + p.x * fit, y: cy + p.y * fit });

  // 同心参考环
  for (const [rr, lb] of [[190, '学生'], [330, '导师'], [470, '同门'], [620, '主要合作者']]) {
    ctx.beginPath(); ctx.arc(cx, cy, rr * fit, 0, 7);
    ctx.strokeStyle = 'rgba(255,255,255,.045)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = 'rgba(120,132,150,.5)'; ctx.font = '10px -apple-system,"Microsoft YaHei",sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(lb, cx + 5, cy - rr * fit + 11);
  }
  // 连线
  for (const kk of rList) {
    if (kk === center) continue;
    const p = rPos[kk]; if (!p) continue;
    const a = P({ x: 0, y: 0 }), b = P(p);
    const e = (mentorOf[center] || []).find(x => x.t === kk) || (studentsOf[center] || []).find(x => x.s === kk);
    ctx.strokeStyle = e ? (isCross(e) ? '#f472b6' : (e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207')) : 'rgba(99,102,241,.3)';
    ctx.lineWidth = e ? 2 : 1;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  // 节点
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const q = P(p);
    const rr = (kk === center ? 15 : 8) * Math.max(fit, .55);
    ctx.beginPath(); ctx.arc(q.x, q.y, rr, 0, 7);
    ctx.fillStyle = COL[SCH(kk)] || '#64748b'; ctx.fill();
    if (kk === center) { ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 2.5; ctx.stroke(); }
    else { ctx.strokeStyle = 'rgba(11,14,20,.9)'; ctx.lineWidth = 1.3; ctx.stroke(); }
    if (hovR === kk) { ctx.beginPath(); ctx.arc(q.x, q.y, rr + 5, 0, 7); ctx.strokeStyle = '#60a5fa'; ctx.lineWidth = 1.6; ctx.stroke(); }
  }
  // 标签
  ctx.textAlign = 'center';
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const q = P(p);
    const rr = (kk === center ? 15 : 8) * Math.max(fit, .55);
    const fs = kk === center ? 14 : 11.5;
    ctx.font = (kk === center ? 'bold ' : '') + fs + 'px -apple-system,"Microsoft YaHei",sans-serif';
    const label = NAME(kk);
    const w = ctx.measureText(label).width;
    // 排在节点外侧，避免遮住中心
    const out = Math.hypot(q.x - cx, q.y - cy) > 1 ? { x: (q.x - cx) / Math.hypot(q.x - cx, q.y - cy), y: (q.y - cy) / Math.hypot(q.x - cx, q.y - cy) } : { x: 0, y: -1 };
    const lx = q.x + out.x * (rr + 8), ly = q.y + out.y * (rr + 8);
    ctx.textAlign = out.x > .25 ? 'left' : out.x < -.25 ? 'right' : 'center';
    ctx.fillStyle = 'rgba(11,14,20,.75)';
    ctx.fillRect(lx - (ctx.textAlign === 'center' ? w / 2 : ctx.textAlign === 'right' ? w : 0) - 2, ly - fs + 1, w + 4, fs + 3);
    ctx.fillStyle = kk === center ? '#fbbf24' : '#dbe3ee';
    ctx.fillText(label, lx, ly);
  }
  // 顶部说明
  const p0 = N[center];
  $('radHd').innerHTML = '<b style="font-size:14px">' + esc(NAME(center)) + '</b> · ' + esc(SCH(center)) +
    (p0 && p0.t ? ' · ' + esc(p0.t) : '') + '<br/>' +
    '学生 ' + (studentsOf[center] || []).length + ' · 导师 ' + (mentorOf[center] || []).length +
    ' · 论文 ' + NP(center) + ' 篇<br/>' +
    '<span style="color:#5a6472;font-size:11px">点击任意节点即以它为中心重绘</span>' +
    (mentorOf[center] && mentorOf[center].length ? ' · <a id="upOne">回到导师 ' + esc(NAME(mentorOf[center][0].t)) + '</a>' : '');
  const up = $('upOne');
  if (up) up.onclick = () => { buildRadial(mentorOf[center][0].t); renderRad(); };
}
rad.addEventListener('click', (e) => {
  if (!center) return;
  const r = rad.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const fit = Math.min(RW / 1500, RH / 1400), cx = RW / 2, cy = RH / 2;
  let best = null, bd = Infinity;
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const qx = cx + p.x * fit, qy = cy + p.y * fit;
    const dd = (qx - mx) ** 2 + (qy - my) ** 2;
    if (dd < 380 && dd < bd) { bd = dd; best = kk; }
  }
  if (best) { buildRadial(best); renderRad(); showPerson(best, true); }
});
rad.addEventListener('mousemove', (e) => {
  if (!center) return;
  const r = rad.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const fit = Math.min(RW / 1500, RH / 1400), cx = RW / 2, cy = RH / 2;
  let best = null, bd = Infinity;
  for (const kk of rList) {
    const p = rPos[kk]; if (!p) continue;
    const qx = cx + p.x * fit, qy = cy + p.y * fit;
    const dd = (qx - mx) ** 2 + (qy - my) ** 2;
    if (dd < 380 && dd < bd) { bd = dd; best = kk; }
  }
  if (best !== hovR) { hovR = best; renderRad(); }
  rad.style.cursor = best ? 'pointer' : 'default';
});

// ══════════ 视图3：合作热力图 ══════════
function buildHeat() {
  const schools = [...new Set(Object.keys(N).map(k => SCH(k)))].sort();
  const idx = {}; schools.forEach((s, i) => idx[s] = i);
  const m = schools.map(() => schools.map(() => 0));
  const pairs = {};
  for (const e of COLB) {
    if (!N[e.s] || !N[e.t]) continue;
    const a = idx[SCH(e.s)], b = idx[SCH(e.t)];
    m[a][b] += e.n; m[b][a] += e.n;
    if (a !== b) { const k = Math.min(a, b) + '-' + Math.max(a, b); (pairs[k] = pairs[k] || []).push(e); }
  }
  let maxOff = 1;
  for (let i = 0; i < schools.length; i++) for (let j = 0; j < schools.length; j++) if (i !== j) maxOff = Math.max(maxOff, m[i][j]);
  let h = '<div class="hint">格子＝两校之间的<b>合作总篇数</b>（共同署名篇数求和）。对角线为校内合作。颜色越深表示合作越多。<b>点击任意格子</b>查看该对院校的合作明细。</div>';
  h += '<table class="heat"><tr><th></th>';
  for (const s of schools) h += '<th class="rot" style="color:' + (COL[s] || '#94a3b8') + '">' + esc(s) + '</th>';
  h += '</tr>';
  for (let i = 0; i < schools.length; i++) {
    h += '<tr><th style="text-align:right;color:' + (COL[schools[i]] || '#94a3b8') + '">' + esc(schools[i]) + '</th>';
    for (let j = 0; j < schools.length; j++) {
      const v = m[i][j];
      const diag = i === j;
      let cls = 'd0', style = '';
      if (v && diag) { cls = 'diag'; style = 'background:rgba(99,102,241,' + (0.14 + 0.5 * Math.min(1, v / (m[i][i] || 1))).toFixed(2) + ')'; }
      else if (v) { const t = Math.pow(v / maxOff, .45); style = 'background:rgba(244,114,182,' + (0.12 + 0.78 * t).toFixed(2) + ');color:' + (t > .5 ? '#fff' : '#fbcfe8'); }
      h += '<td class="' + cls + '" style="' + style + '" data-i="' + i + '" data-j="' + j + '" title="' + esc(schools[i]) + ' ↔ ' + esc(schools[j]) + '：' + v + ' 篇">' + (v || '') + '</td>';
    }
    h += '</tr>';
  }
  h += '</table>';
  $('heatWrap').innerHTML = h;
  $('heatWrap')._schools = schools;
  $('heatWrap')._pairs = pairs;
  document.querySelectorAll('table.heat td[data-i]').forEach(td => {
    td.onclick = () => {
      const i = +td.dataset.i, j = +td.dataset.j;
      const a = schools[i], b = schools[j];
      if (a === b) {
        const list = COLB.filter(e => N[e.s] && N[e.t] && SCH(e.s) === a && SCH(e.t) === a)
          .sort((x, y) => y.n - x.n).slice(0, 60);
        showList(a + ' 校内合作', list.map(e => ({ a: e.s, b: e.t, note: e.n + ' 篇' })));
      } else {
        const list = (pairs[Math.min(i, j) + '-' + Math.max(i, j)] || []).sort((x, y) => y.n - x.n).slice(0, 60);
        showList(a + ' ↔ ' + b, list.map(e => ({ a: SCH(e.s) === a ? e.s : e.t, b: SCH(e.s) === a ? e.t : e.s, note: e.n + ' 篇' })));
      }
    };
  });
}
function showList(title, items) {
  $('drawer').style.display = 'block';
  $('drawer').innerHTML = '<button id="close">×</button><h3>' + esc(title) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">共 ' + items.length + ' 对（按篇数降序）</div>' +
    '<div class="rel"><b>明细</b>' + (items.length ? items.map(x =>
      '<div style="line-height:1.95"><a data-k="' + esc(x.a) + '">' + esc(NAME(x.a)) + '</a>' +
      '<span style="color:#4b5563"> ↔ </span><a data-k="' + esc(x.b) + '">' + esc(NAME(x.b)) + '</a>' +
      '<span style="color:#5a6472;font-size:11px"> ' + esc(x.note) + '</span></div>').join('') : '—') + '</div>';
  $('drawer').querySelectorAll('a[data-k]').forEach(a => { a.onclick = () => showPerson(a.dataset.k, true); });
  $('close').onclick = () => { $('drawer').style.display = 'none'; };
}

// ══════════ 个人档案抽屉 ══════════
function showPerson(k, keep) {
  if (!k || !N[k]) return;
  const P = N[k];
  const me = (mentorOf[k] || []).map(e => e.t);
  const st = (studentsOf[k] || []).map(e => e.s);
  const sib = [];
  for (const e of (mentorOf[k] || [])) for (const e2 of (studentsOf[e.t] || [])) if (e2.s !== k) sib.push(e2.s);
  const cols = COLB.filter(e => (e.s === k || e.t === k) && e.n >= 3)
    .map(e => ({ k: e.s === k ? e.t : e.s, n: e.n })).sort((a, b) => b.n - a.n).slice(0, 24);
  const lvTag = (other, up) => {
    const e = lvOf(k, other, up);
    if (!e) return '';
    const c = isCross(e) ? '#f472b6' : e.lv === 1 ? '#fbbf24' : e.lv === 2 ? '#f59e0b' : '#a16207';
    return '<span class="badge" style="background:' + c + '22;color:' + c + ';border:1px solid ' + c + '55" title="' + esc(e.nt || '') + '">' + (isCross(e) ? '跨校 ' : '') + 'L' + e.lv + '</span>';
  };
  const L = (arr, f) => arr.length ? arr.map(f).join('') : '<span style="color:#3f4855">—</span>';
  $('drawer').style.display = 'block';
  $('drawer').innerHTML = '<button id="close">×</button>' +
    '<h3>' + esc(NAME(k)) + '</h3>' +
    '<div style="font-size:12px;color:#8b98a9">' + esc(SCH(k)) + (P.t ? ' · ' + esc(P.t) : '') + '</div>' +
    (P.d ? '<div style="font-size:12px;color:#5a6472">' + esc(P.d) + '</div>' : '') +
    '<div style="margin-top:7px"><span class="tag">论文 ' + NP(k) + ' 篇</span>' + (P.c ? '<span class="tag">' + esc(P.c.slice(0, 40)) + '</span>' : '') + '</div>' +
    (P.h ? '<div style="margin-top:6px"><a href="' + esc(P.h) + '" target="_blank" style="color:#60a5fa;font-size:12px">打开主页 ↗</a></div>' : '') +
    ((P.edu.length || P.pd.length || P.job.length) ? '<div class="rel"><b>学历与工作经历（页面自述）</b>' +
      P.edu.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '</div>').join('') +
      P.pd.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '（博士后）</div>').join('') +
      P.job.map(x => '<div style="font-size:11.5px;color:#8b98a9">· ' + esc(x) + '</div>').join('') + '</div>' : '') +
    '<div class="rel"><b>导师（' + me.length + '）</b>' + L(me, m => '<a data-k="' + esc(m) + '">' + esc(NAME(m)) + '</a>' + lvTag(m, true)) + '</div>' +
    '<div class="rel"><b>学生（' + st.length + '）</b>' + L(st, s => '<a data-k="' + esc(s) + '">' + esc(NAME(s)) + '</a>' + lvTag(s, false)) + '</div>' +
    (sib.length ? '<div class="rel"><b>同门（' + sib.length + '）</b>' + L(sib.slice(0, 40), x => '<a data-k="' + esc(x) + '">' + esc(NAME(x)) + '</a>') + '</div>' : '') +
    '<div class="rel"><b>主要合作者（共同署名篇数）</b>' + L(cols, c => '<a data-k="' + esc(c.k) + '">' + esc(NAME(c.k)) + ' <span style="color:#5a6472">' + c.n + '</span></a>') + '</div>';
  $('drawer').querySelectorAll('a[data-k]').forEach(a => { a.onclick = () => showPerson(a.dataset.k, true); });
  $('close').onclick = () => { $('drawer').style.display = 'none'; };
  if (keep && view === 'radial') { buildRadial(k); renderRad(); }
  if (!keep && view === 'radial') { buildRadial(k); renderRad(); }
}

// ══════════ 视图切换与搜索 ══════════
let view = 'outline';
function setView(v) {
  view = v;
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.v === v));
  $('outline').style.display = v === 'outline' ? 'block' : 'none';
  $('radWrap').style.display = v === 'radial' ? 'block' : 'none';
  $('heatWrap').style.display = v === 'heat' ? 'block' : 'none';
  $('drawer').style.display = 'none';
  if (v === 'radial') { renderRad(); }
  if (v === 'heat') { buildHeat(); }
}
document.querySelectorAll('.tab').forEach(t => { t.onclick = () => setView(t.dataset.v); });

$('q').addEventListener('input', (e) => {
  const v = e.target.value.trim();
  if (view !== 'outline') { setView('outline'); }
  if (!v) { buildOutline(); return; }
  const hits = Object.keys(N).filter(k => NAME(k).includes(v));
  if (!hits.length) { $('outline').innerHTML = '<div class="empty">未找到「' + esc(v) + '」</div>'; return; }
  buildOutline();
  // 高亮命中的行
  const set = new Set(hits);
  document.querySelectorAll('#outline .row').forEach(r => {
    const nm = r.querySelector('.nm[data-k]');
    if (!nm) return;
    if (!set.has(nm.dataset.k)) r.classList.add('dim');
  });
  const first = document.querySelector('#outline .nm[data-k="' + hits[0] + '"]');
  if (first) first.scrollIntoView({ block: 'center' });
});
window.addEventListener('resize', () => { if (view === 'radial') renderRad(); });

// ── 统计 ──
$('sA').textContent = ADV.filter(e => N[e.s] && N[e.t]).length;
$('sX').textContent = CROSS.length;
$('sS').textContent = new Set(ADV.flatMap(e => [SCH(e.s), SCH(e.t)]).filter(s => s && s !== '?')).size;
$('sC').textContent = COLB.length;

buildOutline();
setView('outline');
</script></body></html>`;

fs.writeFileSync(path.join(REPO, 'reports', '导师关系网络.html'), html, 'utf8');
console.log('saved reports/导师关系网络.html', (html.length / 1024).toFixed(0) + 'KB');
console.log('节点', Object.keys(N).length, '| 师承', DATA.advisor.length, '（跨校 ' + DATA.advisor.filter((e) => N[e.s] && N[e.t] && N[e.s].sc !== N[e.t].sc).length + '）| 合作', DATA.collab.length);
