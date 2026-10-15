const publicResearchPending = new Set();
const researchLabels = {papers:'论文与论著',relations:'师承记录',biography:'身份与任职记录',recruitment:'招生说明与年度名录',admission_notices:'院系招生公告'};
function researchRows(key, rows, limit=50) {
  return rows.slice(0,limit).map(row=>`<div class="paper-item"><p style="color:var(--ink);overflow-wrap:anywhere">${esc(row.text)}</p><small>${row.publication_type?`${esc(row.publication_type)} · `:''}${row.source_kind?`${esc(row.source_kind)} · `:''}${row.year?`${esc(row.year)} 年${['recruitment','admission_notices'].includes(key)&&row.year<new Date().getFullYear()?' · 往年招生记录':''} · `:''}${key==='admission_notices'?'院系公告，不代表个人名额 · ':key==='recruitment'&&!row.year?'未注明招生年份 · ':''}<a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer">查看出处 ↗</a>${row.identity_url?` · <a href="${esc(row.identity_url)}" target="_blank" rel="noopener noreferrer">身份核对出处 ↗</a>`:''}${row.work_url?` · <a href="${esc(row.work_url)}" target="_blank" rel="noopener noreferrer">打开论文 ↗</a>`:''}</small></div>`).join('');
}
function publicSection(key, preview=false) {
  const data=state.mentor?.public_research;
  if(!data)return '';
  const rows=data[key]||[];
  const empty=data.status==='catalog'?{papers:'论文尚未收录。',relations:'师承资料尚未收录。',biography:'教育与任职资料尚未收录。',recruitment:'招生目录暂未列出。',admission_notices:data.catalog_kind==='faculty_directory'?'尚未收录院系招生公告。':'请查看上方招生目录原文。'}:{papers:'这次读取未提取到论文目录。',relations:'已读取的页面没有明确的师承表述。',biography:'已读取的页面没有可提取的教育与任职记录。',recruitment:'尚未提取到这位导师的招生记录。',admission_notices:'暂无可展示的院系招生公告。'};
  return `<section class="section-block"><h3>${researchLabels[key]}</h3>${key==='relations'?'<p class="pane-intro">出处中明确提到的指导关系。</p>':''}${rows.length?(preview&&rows.length>3?researchRows(key,rows,3)+`<details><summary>展开其余 ${rows.length-3} 条</summary>${researchRows(key,rows.slice(3))}</details>`:researchRows(key,rows)):`<p class="quiet">${empty[key]}</p>`}${key==='admission_notices'&&!rows.length?(data.admission_links||[]).map(item=>`<p><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">打开${esc(item.text)} ↗</a></p>`).join(''):''}</section>`;
}
function previousResearchSummary(){
  const d=state.mentor;
  const papers=(d.papers?.length||0)+(d.case.manual_papers?.length||0)+(d.case.openalex_snapshot?.papers?.length||0);
  const relations=Object.entries(d.relations||{}).filter(([,v])=>Array.isArray(v)).reduce((n,[,v])=>n+v.length,0);
  const archive=d.previous_research;
  return `${papers||relations?`<section class="section-block"><h3>之前已收录的资料</h3><p>${papers} 条论文候选 · ${relations} 条关系线索</p><button type="button" class="button light slim" data-public-pane="papers">查看论文</button> <button type="button" class="button light slim" data-public-pane="network">查看关系</button></section>`:''}${archive?`<details class="section-block"><summary>以前的调查 · ${esc(archive.date)}</summary><p class="quiet">历史记录，尚未重新核实。</p>${archive.sections.map(item=>`<h4>${esc(item.title)}</h4>${renderArchiveText(item.text)}`).join('')}</details>`:''}`;
}
function publicResearchSummary() {
  const mentor=state.mentor,data=mentor?.public_research;
  const pending=publicResearchPending.has(mentor?.profile.id);
  const directory=data?.catalog_kind==='faculty_directory';
  if(!data)return `<section class="section-block"><h3>正在补充调查资料</h3><p class="quiet" role="status">正在读取导师主页中的论文、师承和招生信息。已有资料可以先看。</p></section>`;
  const totals=[['papers','论文记录'],['relations','师承表述'],['recruitment','招生记录'],['admission_notices','院系公告']];
  return `<section class="section-block"><h3>已有调查资料</h3><p class="pane-intro">${totals.map(([key,label])=>`${label} ${data[key]?.length||0} 条`).join(' · ')}</p><p class="micro">整理于 ${esc(data.status==='catalog'?new Date(data.checked_at).toLocaleDateString('zh-CN'):new Date(data.checked_at).toLocaleString('zh-CN',{hour12:false}))}。每条资料都附有出处。请留意招生年份，年度名录不代表仍有名额。</p>${data.status==='catalog'?`<p class="quiet">${directory?'已收录导师名录中的学科信息，尚无当年招生依据。':'已收录招生目录中的专业、方向和年份。'}论文与师承仍需补充。</p>`:''}${data.status==='unavailable'?'<p class="quiet">个人主页暂未读到正文，下面仍会列出已核对的其他来源。</p>':''}${data.refresh_error?'<p class="error">更新失败，保留上次读到的资料。</p>':''}<button type="button" class="button light slim" data-refresh-public ${!mentor.profile.homepage?'hidden':''} ${pending?'disabled':''}>${pending?'正在读取…':'更新资料'}</button><p class="micro" id="publicResearchStatus" role="status">${pending?'正在读取导师主页，已有资料可以先看。':data.errors?.length?'部分网页未能读取，已保留可用资料。':''}</p></section>${previousResearchSummary()}${directory?publicSection('biography',true):''}${data.status==='catalog'?publicSection('recruitment',true):''}${publicSection('papers',true)}${publicSection('relations',true)}${data.status!=='catalog'?publicSection('recruitment',true):''}${publicSection('admission_notices',true)}${directory?'':`<details class="section-block"><summary>身份与任职记录</summary>${publicSection('biography')}</details>`}`;
}
function updatePublicResearchView() {
  const box=$('publicResearchSummary');
  if(box)box.innerHTML=publicResearchSummary();
}
async function readPublicResearch(force=false) {
  const mentor=state.mentor,id=mentor?.profile.id;
  if(!id||publicResearchPending.has(id)||(!force&&mentor.public_research&&!mentor.public_research.needs_enrichment))return;
  publicResearchPending.add(id);updatePublicResearchView();
  try {
    const result=await api('/api/catalog/mentor/'+encodeURIComponent(id)+'/public-research',{method:'POST'});
    if(state.mentor?.profile.id!==id)return;
    state.mentor.public_research=result;
    renderOverview();renderEvidenceList();renderPapers();renderNetwork();
  } catch(error) {
    if(state.mentor?.profile.id===id){
      state.mentor.public_research=state.mentor.public_research||{status:'unavailable',checked_at:new Date().toISOString(),errors:[]};
      state.mentor.public_research.refresh_error=[error.message];
    }
  } finally {
    publicResearchPending.delete(id);
    if(state.mentor?.profile.id===id)updatePublicResearchView();
  }
}
document.addEventListener('click',event=>{if(event.target.closest('[data-refresh-public]'))readPublicResearch(true);const button=event.target.closest('[data-public-pane]');if(button)setPane(button.dataset.publicPane)});
