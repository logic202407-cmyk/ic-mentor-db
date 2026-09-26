// html_db.mjs — 生成可交互导师库 HTML（基于最终排名数据）
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\导师库.html';
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

const DIRNAME = {
  analog: '模拟/混合信号/电源IC', rf: '射频/毫米波/太赫兹', digital_ai: '数字/AI芯片/体系结构',
  eda: 'EDA/设计自动化', device: '器件/工艺/存储', photonics: '光电/硅光/光计算',
  mems: 'MEMS/传感器/生医电子', power: '电力电子/功率集成', quantum: '量子芯片/低温电子', other: '其他/交叉',
};
const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };
const tierOf = (d) => (d.n_ic_papers < 3 && d.S === 0) ? 'T4' : d.composite >= 55 ? 'T0' : d.composite >= 42 ? 'T1' : d.composite >= 28 ? 'T2' : d.composite >= 15 ? 'T3' : 'T4';

const data = rows.map((r) => ({
  rk: r.rank, n: r.name_cn, s: SHORT[r.school] || r.school, t: r.title || '', dp: r.department || '',
  d: DIRNAME[r.primary_direction] || r.primary_direction, c: r.composite, tier: tierOf(r),
  S: r.S, A: r.A, B: r.B, ic: r.n_ic_papers, r3: r.recent3, cite: r.citations,
  cpp: r.n_ic_papers ? +(r.citations / r.n_ic_papers).toFixed(1) : 0,
  stu: r.n_students_est || 0, stul: r.student_led_ratio, adv1: r.advisor_first_ratio,
  phd: r.is_phd_advisor === true ? '是' : (r.is_phd_advisor === false ? '否' : '?'),
  conf: r.confidence, rr: r.recall_risk, retr: r.integrity ? r.integrity.retracted : 0,
  v: (r.top_venues || []).map((x) => `${x[0]}×${x[1]}`).join(' / '),
  kw: (r.research_keywords || []).join('、'), hp: r.homepage || '',
  nt: r.notes || '', off: r.n_off_field || 0,
  dim: r.dim,
}));

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>集成电路/AI芯片 导师库（11校 · 详细排名）</title>
<style>
 body{font-family:"Microsoft YaHei",-apple-system,Segoe UI,sans-serif;margin:0;background:#f4f6f9;color:#1c2330}
 header{background:linear-gradient(135deg,#12294f,#2f5fa8);color:#fff;padding:16px 22px}
 header h1{margin:0;font-size:19px} header p{margin:6px 0 0;font-size:12px;opacity:.9}
 .wrap{padding:14px 22px}
 .bar{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
 input,select{padding:6px 9px;border:1px solid #c8ccd4;border-radius:6px;font-size:13px;background:#fff}
 input[type=text]{width:230px}
 .stat{font-size:12px;color:#555;margin-left:auto}
 table{width:100%;border-collapse:collapse;background:#fff;font-size:12.5px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
 th,td{padding:6px 7px;border-bottom:1px solid #eceff3;text-align:left;vertical-align:top}
 th{background:#e8eef7;cursor:pointer;position:sticky;top:0;font-size:11.5px;white-space:nowrap;z-index:2}
 tr:hover{background:#f7faff}
 .t0{background:#c0392b;color:#fff;padding:1px 7px;border-radius:9px;font-size:11px;font-weight:700}
 .t1{background:#e67e22;color:#fff;padding:1px 7px;border-radius:9px;font-size:11px}
 .t2{background:#27ae60;color:#fff;padding:1px 7px;border-radius:9px;font-size:11px}
 .t3{background:#7f8c8d;color:#fff;padding:1px 7px;border-radius:9px;font-size:11px}
 .t4{background:#bdc3c7;color:#333;padding:1px 7px;border-radius:9px;font-size:11px}
 .num{text-align:right;font-variant-numeric:tabular-nums}
 a{color:#2e5a9c} small{color:#6d7684}
 .foot{padding:12px 22px 30px;font-size:11.5px;color:#5b6472;line-height:1.75}
 .warn{color:#c0392b;font-weight:700}
</style></head><body>
<header>
  <h1>集成电路 / 微电子 / 电子信息 / AI 芯片 —— 导师库（11 校 · 详细排名）</h1>
  <p>清华 · 清华深研院 · 北大 · 复旦 · 上交 · 浙大 · 南大 · 中科大 · 东南 · 西电 · 成电 ｜ ${rows.length} 位导师 ｜ 数据源：各校官方师资页 + Crossref（2008–2026）+ 撤稿/更正核查 ｜ 2026-09-24<br/><span style="display:inline-block;margin-top:8px;background:rgba(255,255,255,.16);padding:6px 10px;border-radius:7px;font-size:12px;line-height:1.6">⚠️ 本页为<b>公开文献计量证据的分层</b>，<b>不构成学术评价、人事评价或报考建议</b>。T3/T4 通常源于姓名重名、英文署名不一致或中文文献未覆盖等数据原因，<b>不代表导师水平或指导质量</b>。使用前请阅读仓库 <code>DISCLAIMER.md</code> 与 <code>docs/使用指南.md</code>。</span></p>
</header>
<div class="wrap">
  <div class="bar">
    <input type="text" id="q" placeholder="搜索姓名 / 关键词 / 方向 / 院系"/>
    <select id="school"><option value="">全部学校</option></select>
    <select id="dir"><option value="">全部方向</option></select>
    <select id="tier"><option value="">全部梯队</option><option>T0 顶刊顶会密集</option><option>T1 一流产出稳定</option><option>T2 有稳定产出</option><option>T3 公开证据较少</option><option>T4 公开证据不足</option></select>
    <select id="sortSel">
      <option value="c">按综合分</option><option value="S">按顶刊顶会数</option><option value="A">按一流期刊会议数</option>
      <option value="ic">按论文总数</option><option value="r3">按近三年</option><option value="cite">按引用</option>
      <option value="cpp">按篇均引用</option><option value="stul">按学生一作占比</option><option value="stu">按组内学生数</option>
    </select>
    <span class="stat" id="stat"></span>
  </div>
  <table id="tb"><thead><tr>
    <th data-k="rk">#</th><th data-k="n">姓名</th><th data-k="s">学校</th><th data-k="t">职称</th><th data-k="d">主方向</th>
    <th data-k="c" class="num">综合分</th><th data-k="tier">梯队</th>
    <th data-k="S" class="num">顶刊顶会</th><th data-k="A" class="num">一流</th><th data-k="ic" class="num">论文</th>
    <th data-k="r3" class="num">近3年</th><th data-k="cpp" class="num">篇均引用</th><th data-k="stul" class="num">学生一作</th>
    <th data-k="stu" class="num">学生(估)</th><th data-k="v">代表venue</th><th data-k="kw">官方方向</th><th>主页</th>
  </tr></thead><tbody></tbody></table>
</div>
<div class="foot">
  <b>综合分</b>＝产出强度 40% + 顶刊顶会密度 13% + 篇均引用 10% + 近三年活跃 10% + 署名伦理 8% + 头衔平台 8% + 团队规模 6% + 诚信 5%。<br/>
  <b>梯队</b>（仅反映公开文献计量证据的多少）：T0 顶刊顶会密集 ≥72 ｜ T1 一流产出稳定 58–72 ｜ T2 有稳定产出 42–58 ｜ T3 公开证据较少 26–42 ｜ T4 公开证据不足 &lt;26 或论文&lt;3。<br/>
  <b class="warn">"公开证据不足" ≠ 水平低</b>：多为英文名重名/拼写差异导致漏检（标 ⚠️ 者请以官方主页为准）。同名污染论文（医学/化学等）已剔除并在"备注"标注数量。<br/><b>本页为公开文献计量证据的分层，不构成学术评价、人事评价或报考建议。</b>详见仓库 <code>DISCLAIMER.md</code>；数据采用 CC BY-NC-SA 4.0（非商业性使用），禁止用于批量群发。<br/>
  <b>文献数据回答不了的问题</b>：导师 push 程度、补助、毕业去向、是否允许实习 —— 务必找在读/毕业师兄师姐核实。
</div>
<script>
const DATA = ${JSON.stringify(data)};
const $ = (id) => document.getElementById(id);
[...new Set(DATA.map(d=>d.s))].sort().forEach(s=>$('school').insertAdjacentHTML('beforeend', \`<option>\${s}</option>\`));
[...new Set(DATA.map(d=>d.d))].sort().forEach(s=>$('dir').insertAdjacentHTML('beforeend', \`<option>\${s}</option>\`));
const TL={'T0':'T0 顶刊顶会密集','T1':'T1 一流产出稳定','T2':'T2 有稳定产出','T3':'T3 公开证据较少','T4':'T4 公开证据不足'};
const TC={T0:'t0',T1:'t1',T2:'t2',T3:'t3',T4:'t4'};
let sortK='c', asc=false;
function render(){
  const q=$('q').value.trim().toLowerCase(), sc=$('school').value, dr=$('dir').value, ti=$('tier').value;
  let list = DATA.filter(d=>{
    if(sc&&d.s!==sc) return false;
    if(dr&&d.d!==dr) return false;
    if(ti&&TL[d.tier]!==ti) return false;
    if(q){const hay=(d.n+' '+d.kw+' '+d.d+' '+d.dp+' '+d.v+' '+d.nt+' '+d.t).toLowerCase(); if(!hay.includes(q)) return false;}
    return true;
  });
  list.sort((a,b)=>{const x=a[sortK],y=b[sortK]; if(typeof x==='number') return asc?x-y:y-x; return asc?String(x).localeCompare(String(y)):String(y).localeCompare(String(x));});
  $('tb').querySelector('tbody').innerHTML = list.map(d=>{
    const eth = (d.stul===null||d.stul===undefined)?'—':(d.stul*100).toFixed(0)+'%';
    const marks = (d.rr==='yes'?' ⚠️':'') + (d.retr>0?' ❗':'') + (d.off>=5?' 剔'+d.off:'');
    return \`<tr>
      <td class="num">\${d.rk}</td><td><b>\${d.n}</b>\${marks}</td><td><small>\${d.s}</small></td><td><small>\${d.t}</small></td>
      <td><small>\${d.d}</small></td><td class="num"><b>\${d.c}</b></td><td><span class="\${TC[d.tier]}">\${TL[d.tier]}</span></td>
      <td class="num">\${d.S||''}</td><td class="num">\${d.A||''}</td><td class="num">\${d.ic||''}</td>
      <td class="num">\${d.r3||''}</td><td class="num">\${d.cpp||''}</td><td class="num">\${eth}</td><td class="num">\${d.stu||''}</td>
      <td><small>\${d.v}</small></td><td><small>\${d.kw}</small></td>
      <td>\${d.hp?\`<a href="\${d.hp}" target="_blank">主页</a>\`:''}</td></tr>\`;
  }).join('');
  $('stat').textContent = \`显示 \${list.length} / 全库 \${DATA.length} 人\`;
}
['q','school','dir','tier'].forEach(id=>$(id).addEventListener('input',render));
$('sortSel').addEventListener('input',()=>{sortK=$('sortSel').value; render();});
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k;
  if(k==='tier'){sortK='c';} else if(k==='rk'){sortK='rk'; asc=!asc;} else {sortK=k; asc=!asc;}
  render();
}));
render();
</script></body></html>`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, html, 'utf8');
console.log('saved', OUT, (html.length / 1024).toFixed(0) + 'KB', 'rows', data.length);
