// html_recommend.mjs — 生成中性的「集成电路设计与 AI 交叉方向 · 导师推荐」交互页面
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const PROC = path.join(REPO, 'data', 'processed');
const OUT = path.join(REPO, 'reports', '导师推荐.html');
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));

const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };

const data = rows.map((d) => ({
  n: d.name, s: SHORT[d.school] || d.school, sc: d.school, t: d.title || '', dp: d.department || '',
  g: d.group, gn: d.group_names, tier: d.tier, scope: d.scope,
  c: d.composite, S: d.S, A: d.A, ic: d.n_ic_papers, rel: d.n_related_papers || d.n_ic_papers, r3: d.recent3, cite: d.citations, cpp: d.cite_per_paper,
  stu: d.n_students_est || 0, phd: d.is_phd_advisor === true,
  eth: d.student_led_ratio === null || d.student_led_ratio === undefined ? null : +(d.student_led_ratio * 100).toFixed(0),
  conf: d.confidence, rr: d.recall_risk === 'yes', retr: d.integrity_retracted || 0,
  hp: d.homepage || '', lab: d.lab_names[0] || '',
  rsc: d.recruit_signal_count || 0,
  kw: (d.research_keywords || []).join('、'),
  sig: (d.recruit_signals || []).slice(0, 2).map((x) => x.snippet.slice(0, 240)),
  pap: (d.recent_titles || []).slice(0, 3),
  v: (d.top_venues || []).map((x) => `${x[0]}×${x[1]}`).join(' / ').slice(0, 90),
}));

const allGroups = [...new Set(rows.flatMap((d) => d.group_names))].sort();

const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>集成电路设计与 AI 交叉方向 · 导师推荐与招生信息</title>
<style>
 *{box-sizing:border-box}
 body{font-family:"Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;margin:0;background:#f2f5f9;color:#16202e}
 header{background:linear-gradient(135deg,#0f2547,#2f5fa8 60%,#3f7fd0);color:#fff;padding:18px 24px 16px}
 header h1{margin:0;font-size:20px}
 header p{margin:7px 0 0;font-size:12.5px;opacity:.93;line-height:1.65}
 .wrap{padding:14px 20px 40px}
 .bar{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:10px;background:#fff;padding:11px 13px;border-radius:10px;box-shadow:0 1px 4px rgba(16,32,64,.07)}
 input,select{padding:7px 10px;border:1px solid #c9d0da;border-radius:7px;font-size:13px;background:#fff;color:#16202e}
 input[type=text]{width:230px}
 label.f{font-size:12.5px;color:#41506b;display:flex;align-items:center;gap:5px}
 .stat{font-size:12.5px;color:#3c4a63;margin-left:auto;font-weight:600}
 table{width:100%;border-collapse:collapse;background:#fff;font-size:12.5px;box-shadow:0 1px 4px rgba(16,32,64,.08);border-radius:10px;overflow:hidden}
 th,td{padding:7px 8px;border-bottom:1px solid #eef1f6;text-align:left;vertical-align:top}
 th{background:#e6edf9;cursor:pointer;position:sticky;top:0;font-size:11.5px;white-space:nowrap;z-index:3;color:#1d3557}
 th:hover{background:#d7e3f7}
 tr.row{cursor:pointer}tr.row:hover{background:#f5f9ff}
 tr.detail td{background:#fbfcfe;padding:0}
 .num{text-align:right;font-variant-numeric:tabular-nums}
 .pill{padding:1.5px 8px;border-radius:10px;font-size:11px;font-weight:700;display:inline-block;color:#fff}
 .T0{background:#c0392b}.T1{background:#e67e22}.T2{background:#2f8f57}.T3{background:#7f8c8d}.T4{background:#b3bcc7;color:#333}
 .rec{background:#0f8a4a;color:#fff;padding:1.5px 7px;border-radius:9px;font-size:10.5px;font-weight:700}
 .maybe{background:#eef2f9;color:#41506b;padding:1.5px 7px;border-radius:9px;font-size:10.5px}
 .tag{display:inline-block;background:#eef4ff;color:#2a5fa8;border-radius:6px;padding:1px 7px;font-size:11px;margin:1px 3px 1px 0}
 a{color:#2a5fa8}small{color:#63708a}
 .panel{padding:13px 16px;border-left:4px solid #2f6fd0;margin:6px 0 10px;background:#fff}
 .panel h4{margin:0 0 7px;font-size:13.5px;color:#1d3557}
 .quote{background:#fff9e9;border-left:3px solid #e0a83a;padding:8px 11px;margin:7px 0;font-size:12.5px;line-height:1.65;border-radius:0 6px 6px 0}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px 16px;font-size:12.5px;margin:8px 0}
 .btns{margin-top:9px;display:flex;gap:8px;flex-wrap:wrap}
 button{padding:7px 13px;border:0;border-radius:7px;background:#2f6fd0;color:#fff;font-size:12.5px;cursor:pointer;font-weight:600}
 button.alt{background:#eef2f9;color:#274b80;border:1px solid #cfdcf0}
 button:hover{filter:brightness(1.06)}
 .hint{font-size:11.5px;color:#7086a6;margin-top:6px}
 textarea{width:100%;height:210px;font-family:ui-monospace,Consolas,monospace;font-size:12px;border:1px solid #c9d0da;border-radius:8px;padding:9px;display:none;margin-top:8px}
 .foot{padding:16px 24px 34px;font-size:12px;color:#5a6880;line-height:1.8}
 .warn{color:#a63a3a;font-weight:700}
 .star{cursor:pointer;font-size:15px;color:#cfd6e0;user-select:none;line-height:1}
 .star.on{color:#e8a600}
 tr.row.faved{background:#fffcf0}
 tr.row.faved:hover{background:#fff7e0}
</style></head><body>
<header>
  <h1>集成电路设计与 AI 交叉方向 · 导师推荐与招生信息</h1>
  <p>覆盖 11 校 2114 位导师的全库排名 → 本页收录 <b>${rows.length} 位</b>：集成电路设计与 AI 交叉方向 ${rows.filter((d) => d.scope === 'focus').length} 位 ＋ 其他 IC 方向但<b>主页明确在招</b> ${rows.filter((d) => d.scope === 'recruiting').length} 位<br/>
  课题组主页实抓 ${rows.filter((d) => d.page_status.startsWith('ok')).length} 位，其中 <b>${rows.filter((d) => d.recruit_signal_count > 0).length} 位有明确招生表述</b> ｜ 数据源：各校官网师资页 + Crossref（2008–2026）+ 撤稿/更正核查 ｜ 截至 2026-09-24<br/>
  <span style="display:inline-block;margin-top:8px;background:rgba(255,255,255,.16);padding:6px 10px;border-radius:7px;font-size:12px;line-height:1.6">
  ⚠️ 本页为<b>公开文献计量证据的分层</b>，<b>不构成学术评价、人事评价或报考建议</b>。T3/T4 通常源于姓名重名、英文署名不一致或中文文献未覆盖等数据原因，<b>不代表导师水平或指导质量</b>。使用前请阅读 <a href="../DISCLAIMER.md" style="color:#ffe9a8">免责声明</a> 与 <a href="../docs/使用指南.md" style="color:#ffe9a8">使用指南</a>。</span></p>
</header>
<div class="wrap">
  <div class="bar">
    <input type="text" id="q" placeholder="搜索姓名 / 关键词 / 院系 / 课题组"/>
    <label class="f">范围 <select id="sp"><option value="">全部</option><option value="focus">集成电路设计与 AI 交叉</option><option value="recruiting">其他方向但在招</option></select></label>
    <label class="f">方向 <select id="g"><option value="">全部方向</option>${allGroups.map((g) => `<option>${g}</option>`).join('')}</select></label>
    <label class="f">学校 <select id="sc"><option value="">全部</option></select></label>
    <label class="f">梯队 <select id="ti"><option value="">全部</option><option>T0</option><option>T1</option><option>T2</option><option>T3</option><option>T4</option></select></label>
    <label class="f">招生 <select id="rc"><option value="">全部</option><option value="y">主页明确在招</option><option value="n">未明确</option></select></label>
    <label class="f">排序 <select id="sortSel">
      <option value="c">学术综合分</option><option value="S">顶刊顶会数</option><option value="r3">近三年产出</option>
      <option value="cite">总引用</option><option value="cpp">篇均引用</option><option value="rsc">招生信号</option><option value="stu">组内学生数</option>
    </select></label>
    <label class="f"><input type="checkbox" id="favOnly"/> 只看收藏 (<span id="favN">0</span>)</label>
    <button class="alt" id="expBtn" style="font-size:12px;padding:6px 11px">导出收藏</button>
    <span class="stat" id="stat"></span>
  </div>
  <table id="tb"><thead><tr>
    <th style="width:26px">★</th>
    <th data-k="n">姓名</th><th data-k="s">学校</th><th data-k="t">职称</th><th data-k="g">方向</th>
    <th data-k="c" class="num">综合分</th><th data-k="tier">梯队</th><th data-k="S" class="num">S/A</th>
    <th data-k="ic" class="num">论文</th><th data-k="r3" class="num">近3年</th><th data-k="cite" class="num">引用</th>
    <th data-k="stu" class="num">学生(估)</th><th data-k="rsc">招生</th><th>联系</th>
  </tr></thead><tbody></tbody></table>
</div>
<div class="foot">
  <b>★ 收藏</b>：点每行最左侧的星标可收藏，收藏记录保存在浏览器本地（换设备不同步）。<b>导出收藏</b>可生成一份 Markdown 候选清单，方便对比与记录。<br/>
  <b>梯队</b>（仅反映公开文献计量证据的多少）：T0 顶刊顶会密集（综合分≥72）｜T1 一流产出稳定（58–72）｜T2 有稳定产出（42–58）｜T3 公开证据较少（26–42）｜T4 公开证据不足（&lt;26 或论文&lt;3）。<br/>
  <b>学生(估)</b>：论文一作中非本校在职教师的去重人数，是团队规模的下限估计，非实际在读人数。<br/>
  <b class="warn">"公开证据不足"≠ 水平低</b>：多为英文名重名或拼写差异导致自动匹配失败（标 ⚠️ 者请以官方主页为准）。<br/>
  点击任意一行展开详情（课题组、招生原话、近期论文），可<b>一键生成联系邮件草稿</b>。<br/>
  <b>导师的指导风格、课题组氛围、补助与毕业去向无法从文献数据获得</b>，请务必通过在读/毕业学生核实。<br/><br/>
  <b>使用条款</b>：本页数据来自高校官网公开师资页与 Crossref 公开元数据，采用 <b>CC BY-NC-SA 4.0（非商业性使用）</b>许可。
  <b>禁止用于批量群发邮件或其他骚扰行为</b>；引用请注明来源与免责声明。
  如需更正或删除信息，请提 <a href="../CONTRIBUTING.md">Issue</a>，我们将在 7 个工作日内处理。<br/>
  完整说明见仓库 <code>DISCLAIMER.md</code>（免责与合规）、<code>docs/使用指南.md</code>（使用教程）、<code>LICENSE-DATA</code>（许可协议）。
</div>
<script>
const DATA = ${JSON.stringify(data)};
const $ = (id) => document.getElementById(id);
[...new Set(DATA.map(d=>d.s))].sort().forEach(s=>$('sc').insertAdjacentHTML('beforeend', \`<option>\${s}</option>\`));
let sortK='c', asc=false, openRow=null;
function filtered(){
  const q=$('q').value.trim().toLowerCase(), g=$('g').value, sc=$('sc').value, ti=$('ti').value, rc=$('rc').value, sp=$('sp').value;
  const favOnly = $('favOnly').checked;
  return DATA.filter(d=>{
    if(favOnly && !FAV.has(d.n)) return false;
    if(sp && d.scope!==sp) return false;
    if(g && !d.gn.includes(g)) return false;
    if(sc && d.s!==sc) return false;
    if(ti && d.tier!==ti) return false;
    if(rc==='y' && d.rsc===0) return false;
    if(rc==='n' && d.rsc>0) return false;
    if(q){const hay=(d.n+' '+d.kw+' '+d.dp+' '+d.lab+' '+d.t+' '+d.gn.join(' ')).toLowerCase(); if(!hay.includes(q)) return false;}
    return true;
  });
}
function detail(d){
  const sig = d.sig.length ? d.sig.map(s=>\`<div class="quote">\${s}</div>\`).join('')
    : '<div class="quote">主页未见明确招生表述 —— 建议邮件直接询问当年度是否还有名额。</div>';
  const pap = d.pap.length ? d.pap.map(p=>\`<li>\${p}</li>\`).join('') : '<li>（见主页）</li>';
  return \`<div class="panel">
    <h4>\${d.n} · \${d.sc} · \${d.t} <span class="pill \${d.tier}">\${d.tier}</span></h4>
    <div class="grid">
      <div>院系：\${d.dp||'—'}</div><div>课题组：\${d.lab||'（未识别）'}</div>
      <div>联系方式：<b>见官方主页</b>（本项目不收录邮箱，请从院系官网或课题组主页获取）</div><div>主页：\${d.hp?\`<a href="\${d.hp}" target="_blank">打开</a>\`:'—'}</div>
      <div>学术：综合分 \${d.c} ｜ S\${d.S} / A\${d.A} ｜ IC 相关论文 \${d.ic} 篇（全部相关 \${d.rel} 篇）｜ 近3年 \${d.r3} ｜ 引用 \${d.cite}</div>
      <div>组内学生(估)：\${d.stu} 人 ｜ 博导：\${d.phd?'是':'未标注'} ｜ 学生一作占比：\${d.eth===null?'—':d.eth+'%'}</div>
      <div>方向标签：\${d.gn.map(t=>\`<span class="tag">\${t}</span>\`).join('')}</div>
      <div>置信度：\${d.conf==='high'?'高':d.conf==='medium'?'中':'低'}\${d.rr?' ⚠️疑似漏检':''}\${d.retr?' ❗撤稿 '+d.retr:''}</div>
    </div>
    <div><b>官方研究方向</b>：\${d.kw||'—'}</div>
    <div style="margin-top:6px"><b>代表 venue</b>：<small>\${d.v||'—'}</small></div>
    <div style="margin-top:8px"><b>主页招生原话</b></div>\${sig}
    <div style="margin-top:6px"><b>邮件可引用的近期论文</b><ul style="margin:5px 0 0 18px;padding:0">\${pap}</ul></div>
    <div class="btns">
      <button onclick="genMail('\${d.n}')">✉️ 生成联系邮件草稿</button>
      <button class="alt" onclick="window.open('\${d.hp||'#'}','_blank')">打开主页</button>
      <button class="alt" onclick="openRow=null;render()">收起</button>
    </div>
    <div class="hint">草稿已自动填入该导师的招生原话与近期论文，请替换 [方括号] 内信息后发送。</div>
    <textarea id="mail_\${d.n}" readonly></textarea>
  </div>\`;
}
function genMail(name){
  const d = DATA.find(x=>x.n===name);
  const ta = $('mail_'+name);
  const sig = d.sig.length ? d.sig[0].slice(0,110) : '';
  const pap = d.pap.length ? d.pap[0] : '';
  const body = \`主题：研究生申请咨询 - [你的学校] - [你的姓名] - [目标方向]

尊敬的\${d.n}老师：

您好！我是[你的学校][你的专业]20XX级本科生[你的姓名]，专业排名 [X/Y]（前 X%），
预计获得推免资格 / 正在准备考研，希望申请您课题组的研究生。

我在您课题组主页看到「\${sig}」，非常希望有机会加入您的团队。

【我的基础】
- 修过课程：[数字集成电路设计 / 模拟集成电路设计 / 半导体器件 / Verilog HDL …]（成绩 [X]）
- 项目经历：[项目名称]，我负责 [具体工作]，完成了 [可量化结果]
- 熟悉工具：[Cadence Virtuoso / Synopsys DC / ModelSim / Vivado / Python …]

我关注到您近期的工作《\${pap}》，其中 [一句话说明你理解的技术点] 让我很受启发，
这与我 [课程/项目] 中的经历相关。

若您当年度还有招生名额，希望能有机会进一步沟通，也愿意提前做文献阅读或小任务。
附件为我的简历与成绩单。

感谢您的时间！

[你的姓名]
[电话] | [邮箱] | [个人主页/GitHub]\`;
  ta.value = body; ta.style.display='block'; ta.select();
  try{ navigator.clipboard.writeText(body); alert('邮件草稿已生成并复制到剪贴板（若未自动复制，请手动全选文本框内容）'); }
  catch(e){ alert('邮件草稿已生成，请手动复制文本框内容'); }
}
function render(){
  const list = filtered().slice().sort((a,b)=>{const x=a[sortK],y=b[sortK];
    if(typeof x==='number') return asc?x-y:y-x;
    return asc?String(x).localeCompare(String(y)):String(y).localeCompare(String(x));});
  const tb = $('tb').querySelector('tbody');
  let html='';
  list.forEach(d=>{
    const rc = d.rsc>0 ? '<span class="rec">在招 '+d.rsc+'</span>' : '<span class="maybe">未明</span>';
    const fv = FAV.has(d.n);
    html += \`<tr class="row\${fv?' faved':''}" data-n="\${d.n}">
      <td><span class="star\${fv?' on':''}" data-fav="\${d.n}" title="收藏/取消收藏">\${fv?'★':'☆'}</span></td>
      <td><b>\${d.n}</b></td><td><small>\${d.s}</small></td><td><small>\${d.t||'—'}</small></td>
      <td><small>\${d.gn[0]}\${d.gn.length>1?' +'+(d.gn.length-1):''}</small></td>
      <td class="num"><b>\${d.c}</b></td><td><span class="pill \${d.tier}">\${d.tier}</span></td>
      <td class="num">\${d.S}/\${d.A}</td><td class="num">\${d.ic}</td><td class="num">\${d.r3}</td>
      <td class="num">\${d.cite}</td><td class="num">\${d.stu}</td><td>\${rc}</td>
      <td><small>\${d.hp?'<a href="'+d.hp+'" target="_blank">主页</a>':'—'}</small></td></tr>\`;
    if(openRow===d.n) html += \`<tr class="detail"><td colspan="14">\${detail(d)}</td></tr>\`;
  });
  tb.innerHTML = html;
  tb.querySelectorAll('td .star').forEach(s=>s.addEventListener('click',(e)=>{
    e.stopPropagation();
    const n = s.dataset.fav;
    if(FAV.has(n)) FAV.delete(n); else FAV.add(n);
    saveFav(); render();
  }));
  tb.querySelectorAll('tr.row').forEach(r=>r.addEventListener('click',()=>{
    openRow = (openRow===r.dataset.n) ? null : r.dataset.n; render();
  }));
  $('favN').textContent = FAV.size;
  $('stat').textContent = \`显示 \${list.length} / 本页 \${DATA.length} 人 ｜ 主页明确在招 \${list.filter(x=>x.rsc>0).length} 人 ｜ 已收藏 \${FAV.size} 人\`;
}
function exportFav(){
  if(!FAV.size){ alert('还没有收藏任何导师。点击每行最左侧的 ☆ 即可收藏。'); return; }
  const rows = DATA.filter(d=>FAV.has(d.n)).sort((a,b)=>b.c-a.c);
  let out = '# 我的导师候选清单\\n\\n';
  out += '| 姓名 | 学校 | 职称 | 方向 | 综合分 | 梯队 | S/A | 论文 | 在招 | 主页 |\\n';
  out += '|:--|:--|:--|:--|--:|:--|:--|--:|:--|:--|\\n';
  rows.forEach(d=>{
    out += \`| \${d.n} | \${d.s} | \${d.t||'—'} | \${d.gn[0]} | \${d.c} | \${d.tier} | \${d.S}/\${d.A} | \${d.ic} | \${d.rsc>0?'✅':'—'} | \${d.hp||'—'} |\\n\`;
  });
  out += '\\n> 数据来源：集成电路 / AI 芯片 方向导师库（ic-mentor-db）。\\n';
  out += '> 本清单为公开文献计量证据的整理，不构成学术评价或报考建议；联系方式请通过主页获取。\\n\\n';
  rows.forEach(d=>{
    out += \`## \${d.n} · \${d.sc} · \${d.t||''}\\n\\n\`;
    out += \`- 方向：\${d.gn.join(' / ')}\\n- 院系：\${d.dp||'—'}\\n- 课题组：\${d.lab||'（未识别）'}\\n\`;
    out += \`- 综合分 \${d.c}（\${d.tier}）｜ S\${d.S} / A\${d.A} ｜ 论文 \${d.ic} 篇 ｜ 近3年 \${d.r3} ｜ 引用 \${d.cite}\\n\`;
    out += \`- 主页：\${d.hp||'—'}\\n\`;
    if(d.sig.length) out += \`- 主页招生原话：\${d.sig[0]}\\n\`;
    out += '\\n';
  });
  const blob = new Blob([out], {type:'text/markdown;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '我的导师候选清单.md';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(()=>URL.revokeObjectURL(a.href), 3000);
  if(confirm('已生成《我的导师候选清单.md》并开始下载。\\n\\n是否同时复制到剪贴板？')) {
    try{ navigator.clipboard.writeText(out); }catch(e){}
  }
}
const FAV_KEY = 'icmd_fav_v1';
let FAV = new Set();
try{ FAV = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]')); }catch(e){ FAV = new Set(); }
function saveFav(){ try{ localStorage.setItem(FAV_KEY, JSON.stringify([...FAV])); }catch(e){} }
$('favOnly').addEventListener('input',render);
$('expBtn').addEventListener('click',exportFav);
['q','g','sc','ti','rc','sp'].forEach(id=>$(id).addEventListener('input',render));
$('sortSel').addEventListener('input',()=>{sortK=$('sortSel').value; asc=(sortK==='cpp'); render();});
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k; if(sortK===k) asc=!asc; else {sortK=k; asc=(k==='n'||k==='s');} render();
}));
render();
</script></body></html>`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, html, 'utf8');
console.log('saved', OUT, (html.length / 1024).toFixed(0) + 'KB', 'rows', data.length);
console.log('有招生原话:', data.filter((d) => d.rsc > 0).length, '| 有主页链接:', data.filter((d) => d.hp).length);
