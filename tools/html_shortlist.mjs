// html_shortlist.mjs — 生成可交互的「2027 推免导师推荐」HTML（含一键生成邮件草稿）
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\2027推免-导师推荐.html';
const scored = JSON.parse(fs.readFileSync(path.join(PROC, 'profile_fit.json'), 'utf8'));

const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };
const DIR = { analog: '模拟/混合/电源', rf: '射频/毫米波', digital_ai: '数字/AI芯片', eda: 'EDA', device: '器件/存储', photonics: '光电', mems: 'MEMS/生医', quantum: '量子', other: '其他', power: '电力电子' };

const isAnalog = (d) => d.primary_direction === 'analog' || (/模拟集成电路|模拟电路|混合信号|数模混合|电源管理|ADC|DAC|数据转换器|锁相环|PLL|基准源|放大器|电源芯片|DC-?DC|LDO|IVR|供电/i.test((d.research_keywords || []).join(' ')) && d.code_load <= 25);
const isDigital = (d) => !isAnalog(d) && /数字集成电路|数字电路|SoC|片上系统|处理器|微处理器|RISC-V|验证|后端|物理设计|可测性|DFT|存算一体|存内计算|近存计算|芯片设计|集成电路设计/i.test((d.research_keywords || []).join(' ')) && d.code_load <= 45;
const isAiChip = (d) => !isAnalog(d) && !isDigital(d) && d.ai_score >= 60 && d.code_load <= 58;
function trackOf(d) {
  if (isAnalog(d)) return 'A';
  if (isDigital(d)) return 'B';
  if (isAiChip(d)) return 'C';
  if (d.code_load >= 60) return 'D';
  if (d.primary_direction === 'device') return 'V';
  return 'C';
}
const TRACK_NAME = { A: '模拟/混合/电源（最稳）', B: '数字IC/SoC/存算（最推荐）', C: 'AI芯片/类脑（可冲）', V: '器件/工艺/存储（IC本体·偏实验）', D: '编程重（慎选）' };

const data = scored.map((d) => ({
  n: d.name_cn, s: SHORT[d.school] || d.school, sc: d.school, t: d.title || '', dp: d.department || '',
  d: DIR[d.primary_direction] || d.primary_direction, tr: trackOf(d),
  c: d.composite, S: d.S, A: d.A, ic: d.n_ic_papers, r3: d.recent3, stu: d.n_students_est,
  ai: d.ai_score, code: d.code_load, core: d.ic_core, fit: d.fit_profile, rec: d.recruit_final,
  rsc: d.recruit_signal_count || 0, email: d.email || '', hp: d.homepage || '',
  lab: (d.lab_names || [])[0] || '', kw: (d.research_keywords || []).join('、'),
  sig: (d.recruit_signals || []).slice(0, 2).map((x) => x.snippet.slice(0, 220)),
  tags: (d.cross_tags || []).join(' / '),
  pap: (d.recent_titles || []).slice(0, 2),
  nt: (d.notes || '').slice(0, 120),
  phd: d.is_phd_advisor === true,
}));

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>2027 推免 · 导师推荐（IC 设计 × AI）</title>
<style>
 *{box-sizing:border-box}
 body{font-family:"Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;margin:0;background:#f2f5f9;color:#16202e}
 header{background:linear-gradient(135deg,#0f2547,#2f5fa8 60%,#3f7fd0);color:#fff;padding:18px 24px 16px}
 header h1{margin:0;font-size:20px;letter-spacing:.3px}
 header p{margin:7px 0 0;font-size:12.5px;opacity:.92;line-height:1.6}
 .wrap{padding:14px 20px 40px}
 .bar{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:10px;background:#fff;padding:11px 13px;border-radius:10px;box-shadow:0 1px 4px rgba(16,32,64,.07)}
 input,select{padding:7px 10px;border:1px solid #c9d0da;border-radius:7px;font-size:13px;background:#fff;color:#16202e}
 input[type=text]{width:220px}
 label.f{font-size:12.5px;color:#41506b;display:flex;align-items:center;gap:5px}
 .stat{font-size:12.5px;color:#3c4a63;margin-left:auto;font-weight:600}
 table{width:100%;border-collapse:collapse;background:#fff;font-size:12.5px;box-shadow:0 1px 4px rgba(16,32,64,.08);border-radius:10px;overflow:hidden}
 th,td{padding:7px 8px;border-bottom:1px solid #eef1f6;text-align:left;vertical-align:top}
 th{background:#e6edf9;cursor:pointer;position:sticky;top:0;font-size:11.5px;white-space:nowrap;z-index:3;color:#1d3557}
 th:hover{background:#d7e3f7}
 tr.row{cursor:pointer}
 tr.row:hover{background:#f5f9ff}
 tr.detail td{background:#fbfcfe;padding:0}
 .num{text-align:right;font-variant-numeric:tabular-nums}
 .pill{padding:1.5px 8px;border-radius:10px;font-size:11px;font-weight:700;display:inline-block;color:#fff}
 .tA{background:#1e8e5a}.tB{background:#2f6fd0}.tC{background:#c47f16}.tD{background:#a63a3a}.tV{background:#7a5cc4}
 .rec{background:#0f8a4a;color:#fff;padding:1.5px 7px;border-radius:9px;font-size:10.5px;font-weight:700}
 .maybe{background:#e9eef7;color:#41506b;padding:1.5px 7px;border-radius:9px;font-size:10.5px}
 a{color:#2a5fa8}
 small{color:#63708a}
 .panel{padding:13px 16px;border-left:4px solid #2f6fd0;margin:6px 0 10px;background:#fff}
 .panel h4{margin:0 0 7px;font-size:13.5px;color:#1d3557}
 .quote{background:#fff9e9;border-left:3px solid #e0a83a;padding:8px 11px;margin:7px 0;font-size:12.5px;line-height:1.65;border-radius:0 6px 6px 0}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:6px 16px;font-size:12.5px;margin:8px 0}
 .btns{margin-top:9px;display:flex;gap:8px;flex-wrap:wrap}
 button{padding:7px 13px;border:0;border-radius:7px;background:#2f6fd0;color:#fff;font-size:12.5px;cursor:pointer;font-weight:600}
 button.alt{background:#eef2f9;color:#274b80;border:1px solid #cfdcf0}
 button:hover{filter:brightness(1.06)}
 .hint{font-size:11.5px;color:#7086a6;margin-top:6px}
 .foot{padding:16px 24px 34px;font-size:12px;color:#5a6880;line-height:1.8}
 .warn{color:#a63a3a;font-weight:700}
 .tag{display:inline-block;background:#eef4ff;color:#2a5fa8;border-radius:6px;padding:1px 7px;font-size:11px;margin:1px 3px 1px 0}
 textarea{width:100%;height:190px;font-family:ui-monospace,Consolas,monospace;font-size:12px;border:1px solid #c9d0da;border-radius:8px;padding:9px;display:none;margin-top:8px}
</style></head><body>
<header>
  <h1>2027 推免 · 导师推荐（集成电路设计 × AI 交叉）</h1>
  <p>定制口径：<b>IC 科班 + 编程一般 + AI 重度使用者</b> ｜ 已排除 射频/毫米波、光电/硅光、MEMS/生医 ｜ 11 校 2114 位导师 → 643 人候选池 → 231 人课题组主页实抓<br/>
  五赛道：<b>A 模拟/电源</b>（编程最低）· <b>B 数字IC/SoC/存算</b>（最推荐）· <b>C AI芯片/类脑</b>（可冲）· <b>V 器件/工艺/存储</b>（IC 本体，偏实验）· <b>D 编程重</b>（慎选）｜ 生成日期 2026-09-24</p>
</header>
<div class="wrap">
  <div class="bar">
    <input type="text" id="q" placeholder="搜索姓名 / 关键词 / 院系 / 课题组"/>
    <label class="f">赛道 <select id="tr"><option value="">全部</option><option value="A">A 模拟/电源</option><option value="B">B 数字IC/SoC/存算</option><option value="C">C AI芯片/类脑</option><option value="V">V 器件/工艺/存储</option><option value="D">D 编程重</option></select></label>
    <label class="f">学校 <select id="sc"><option value="">全部</option></select></label>
    <label class="f">方向 <select id="dr"><option value="">全部</option></select></label>
    <label class="f">在招 <select id="rc"><option value="">全部</option><option value="y">主页明确在招</option><option value="n">未明确</option></select></label>
    <label class="f">编程负担 ≤ <input type="range" id="code" min="5" max="100" step="5" value="100" style="width:110px"><span id="codeV">100</span></label>
    <label class="f">排序 <select id="sortSel">
      <option value="fit">综合契合度</option><option value="code">编程负担（低→高）</option><option value="core">IC 核心度</option>
      <option value="ai">AI 交叉度</option><option value="c">学术综合分</option><option value="S">顶刊顶会数</option>
      <option value="rsc">在招信号</option><option value="stu">组内学生数</option>
    </select></label>
    <span class="stat" id="stat"></span>
  </div>
  <table id="tb"><thead><tr>
    <th data-k="n">姓名</th><th data-k="s">学校</th><th data-k="t">职称</th><th data-k="d">方向</th>
    <th data-k="tr">赛道</th><th data-k="code" class="num">编程负担</th><th data-k="core" class="num">IC核心</th>
    <th data-k="ai" class="num">AI交叉</th><th data-k="c" class="num">学术分</th><th data-k="S" class="num">S/A</th>
    <th data-k="r3" class="num">近3年</th><th data-k="stu" class="num">学生</th><th data-k="rsc">在招</th><th>邮箱</th>
  </tr></thead><tbody></tbody></table>
</div>
<div class="foot">
  <b>编程负担</b>（0–100，越低越适合"不想天天写代码"）：由研究方向关键词 + 院系自动估计，不是导师亲口所述。<br/>
  <b>IC 核心度</b>：越高越贴近集成电路本体（相对纯 CS/AI 算法）。<b>AI 交叉度</b>：与 AI 的结合程度。<br/>
  <b class="warn">"未明确"≠ 不招</b>：很多导师不更新主页。建议按赛道顺序分批发信，先联系"主页明确在招"的。<br/>
  点击任意一行展开详情（课题组、招生原话、近期论文），并可<b>一键生成邮件草稿</b>。
</div>
<script>
const DATA = ${JSON.stringify(data)};
const TN = ${JSON.stringify(TRACK_NAME)};
const $ = (id) => document.getElementById(id);
[...new Set(DATA.map(d=>d.s))].sort().forEach(s=>$('sc').insertAdjacentHTML('beforeend', \`<option>\${s}</option>\`));
[...new Set(DATA.map(d=>d.d))].sort().forEach(s=>$('dr').insertAdjacentHTML('beforeend', \`<option>\${s}</option>\`));
let sortK='fit', asc=(sortK==='code');
let openRow = null;

function filtered(){
  const q=$('q').value.trim().toLowerCase(), tr=$('tr').value, sc=$('sc').value, dr=$('dr').value, rc=$('rc').value, cmax=+$('code').value;
  return DATA.filter(d=>{
    if(tr && d.tr!==tr) return false;
    if(sc && d.s!==sc) return false;
    if(dr && d.d!==dr) return false;
    if(rc==='y' && d.rsc===0) return false;
    if(rc==='n' && d.rsc>0) return false;
    if(d.code>cmax) return false;
    if(q){const hay=(d.n+' '+d.kw+' '+d.dp+' '+d.lab+' '+d.t+' '+d.nt+' '+d.tags).toLowerCase(); if(!hay.includes(q)) return false;}
    return true;
  });
}
function sorted(list){
  return list.slice().sort((a,b)=>{const x=a[sortK],y=b[sortK];
    if(typeof x==='number') return asc?x-y:y-x;
    return asc?String(x).localeCompare(String(y)):String(y).localeCompare(String(x));});
}
function detail(d){
  const sig = d.sig.length ? d.sig.map(s=>\`<div class="quote">\${s}</div>\`).join('') : '<div class="quote">主页未见明确招生表述 —— 建议邮件直接问"2027 级是否还有推免名额"。</div>';
  const pap = d.pap.length ? d.pap.map(p=>\`<li>\${p}</li>\`).join('') : '<li>（见主页）</li>';
  return \`<div class="panel">
    <h4>\${d.n} · \${d.sc} · \${d.t} <span class="pill t\${d.tr}">赛道 \${d.tr}</span></h4>
    <div class="grid">
      <div>院系：\${d.dp||'—'}</div><div>课题组：\${d.lab||'（未识别）'}</div>
      <div>邮箱：<b>\${d.email||'主页未公开'}</b></div><div>主页：\${d.hp?\`<a href="\${d.hp}" target="_blank">打开</a>\`:'—'}</div>
      <div>编程负担：<b>\${d.code}</b> ｜ IC核心：<b>\${d.core}</b> ｜ AI交叉：<b>\${d.ai}</b></div>
      <div>学术：综合分 \${d.c} ｜ S\${d.S} / A\${d.A} ｜ 论文 \${d.ic} 篇 ｜ 近3年 \${d.r3}</div>
      <div>组内学生(估)：\${d.stu||0} 人 ｜ 博导：\${d.phd?'是':'未标注'}</div>
      <div>交叉标签：\${(d.tags||'').split(' / ').map(t=>\`<span class="tag">\${t}</span>\`).join('')}</div>
    </div>
    <div><b>官方方向</b>：\${d.kw||'—'}</div>
    <div style="margin-top:8px"><b>主页招生原话</b></div>\${sig}
    <div style="margin-top:6px"><b>邮件可引用的近期论文</b><ul style="margin:5px 0 0 18px;padding:0">\${pap}</ul></div>
    <div class="btns">
      <button onclick="genMail('\${d.n}')">✉️ 生成邮件草稿</button>
      <button class="alt" onclick="window.open('\${d.hp||'#'}','_blank')">打开主页</button>
      <button class="alt" onclick="nav('up')">收起</button>
    </div>
    <div class="hint">邮件草稿会自动填入该导师的招生原话与近期论文，请按自己情况替换 [方括号] 内容后再发送。</div>
    <textarea id="mail_\${d.n}" readonly></textarea>
  </div>\`;
}
function genMail(name){
  const d = DATA.find(x=>x.n===name);
  const ta = $('mail_'+name);
  const sig = d.sig.length ? d.sig[0].slice(0,110) : '';
  const pap = d.pap.length ? d.pap[0] : '';
  const body = \`主题：2027 级推免咨询 - [你的学校] - [你的姓名] - 集成电路设计（\${d.d==='模拟/混合/电源'?'模拟':'数字'}方向）

尊敬的\${d.n}老师：

您好！我是[你的学校]集成电路设计与集成系统专业 2023 级本科生[你的姓名]，
专业排名 [X/Y]（前 X%），预计获得 2027 届推免资格。

我在您课题组主页看到「\${sig}」，非常希望有机会加入您的团队。

【我的 IC 基础】
- 修过课程：数字集成电路设计 / 模拟集成电路设计 / 半导体器件 / Verilog HDL（成绩 [X]）
- 项目经历：[项目名，例如"基于 Verilog 的 XXX 模块设计"，完成综合与仿真，面积/功耗 XXX]
- 熟悉工具：[Cadence Virtuoso / Synopsys DC / ModelSim / Vivado]

【我的差异化】我是 AI 工具的深度使用者，能用大模型辅助完成 testbench 生成、
脚本编写、时序报告分析、文献综述等重复性工作，可以把更多时间留给电路本身。

我关注到您近期的工作《\${pap}》，其中[用一句话说出你理解的技术点]让我很受启发，
这与我在[课程/项目]中的经历高度相关。

若您 2027 级还有推免名额，我非常希望能有机会进一步沟通，
也随时可以按您的要求提前做文献阅读或小任务。

感谢您的时间！

[你的姓名]
[电话] | [邮箱] | [GitHub/个人主页]\`;
  ta.value = body; ta.style.display='block'; ta.select();
  try{ navigator.clipboard.writeText(body); ta.previousElementSibling; alert('邮件草稿已生成并复制到剪贴板（若未复制成功，请手动全选文本框内容）'); }
  catch(e){ alert('邮件草稿已生成，请手动复制文本框内容'); }
}
function nav(){ render(); }
function render(){
  const list = sorted(filtered());
  const tb = $('tb').querySelector('tbody');
  let html='';
  list.forEach(d=>{
    const rc = d.rsc>0 ? '<span class="rec">在招 '+d.rsc+'</span>' : (d.rec>=90?'<span class="maybe">可能在招</span>':'<span class="maybe">未明</span>');
    html += \`<tr class="row" data-n="\${d.n}">
      <td><b>\${d.n}</b></td><td><small>\${d.s}</small></td><td><small>\${d.t||'—'}</small></td>
      <td><small>\${d.d}</small></td><td><span class="pill t\${d.tr}">\${d.tr}</span></td>
      <td class="num"><b>\${d.code}</b></td><td class="num">\${d.core}</td><td class="num">\${d.ai}</td>
      <td class="num">\${d.c}</td><td class="num">\${d.S}/\${d.A}</td><td class="num">\${d.r3||''}</td>
      <td class="num">\${d.stu||''}</td><td>\${rc}</td><td><small>\${d.email||'—'}</small></td></tr>\`;
    if(openRow===d.n) html += \`<tr class="detail"><td colspan="14">\${detail(d)}</td></tr>\`;
  });
  tb.innerHTML = html;
  tb.querySelectorAll('tr.row').forEach(r=>r.addEventListener('click',()=>{
    openRow = (openRow===r.dataset.n) ? null : r.dataset.n; render();
  }));
  $('stat').textContent = \`显示 \${list.length} / 全库 \${DATA.length} 人｜在招明确 \${list.filter(x=>x.rsc>0).length} 人\`;
}
['q','tr','sc','dr','rc'].forEach(id=>$(id).addEventListener('input',render));
$('code').addEventListener('input',()=>{$('codeV').textContent=$('code').value; render();});
$('sortSel').addEventListener('input',()=>{sortK=$('sortSel').value; asc=(sortK==='code'); render();});
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k; if(sortK===k) asc=!asc; else {sortK=k; asc=(k==='code'||k==='n'||k==='s');} render();
}));
render();
</script></body></html>`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, html, 'utf8');
const t = { A: 0, B: 0, C: 0, D: 0, V: 0 };
for (const d of data) t[d.tr]++;
console.log('saved', OUT, (html.length / 1024).toFixed(0) + 'KB', 'rows', data.length);
console.log('赛道分布', JSON.stringify(t), '| 在招明确', data.filter((d) => d.rsc > 0).length);
