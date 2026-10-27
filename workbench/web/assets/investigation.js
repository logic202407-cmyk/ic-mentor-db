let investigationRequest = 0;
let investigationData = null;
const runningInvestigations = new Set();
const investigationTime = value => new Date(value).toLocaleString('zh-CN', {hour12:false});
const moduleName = id => ({identity:'基本信息',papers:'论文',relations:'学术关系',archive:'以前的调查',crossref:'核对 DOI'})[id] || id;
function shortSummary(module) {
  const d=module.details;
  if(module.id==='identity')return `共有 ${d.sources?.length || 0} 个参考网页。`;
  if(module.id==='papers')return `整理了 ${d.sample_count || 0} 篇论文，作者归属待核对。`;
  if(module.id==='relations')return '下面是已收录的关系。合著不等于师承。';
  if(module.id==='archive')return d.date ? '这是之前保存的记录，内容可能已变化。' : '还没有这位导师的旧记录。';
  if(module.id==='crossref')return d.checks?.length ? `查了 ${d.checks.length} 篇，找到 ${d.checks.filter(c=>c.status==='found').length} 条 DOI 记录。` : '先选择要核对的论文。';
  return module.summary;
}

function renderArchiveText(text) {
  const lines = text.split('\n');
  const tableRows = lines.filter(line => line.trim().startsWith('|'));
  if (tableRows.length > 1 && lines.every(line => !line.trim() || line.trim().startsWith('|'))) {
    const cells = line => line.trim().replace(/^\||\|$/g,'').split('|').map(cell=>cell.trim());
    const rows = tableRows.filter(line => !cells(line).every(cell=>/^:?-+:?$/.test(cell)));
    return '<div class="archive-table"><table>' + rows.map((line,i)=>'<tr>'+cells(line).map(cell=>`<${i?'td':'th'}>${esc(cell)}</${i?'td':'th'}>`).join('')+'</tr>').join('') + '</table></div>';
  }
  return `<div class="archive-excerpt">${esc(text)}</div>`;
}

async function renderInvestigation() {
  const mentor = state.mentor;
  const request = ++investigationRequest;
  const pane = $('investigationTools');
  if (!pane || !mentor) return;
  investigationData = null;
  pane.innerHTML = '<p class="quiet" role="status">正在加载…</p>';
  try {
    const data = await api('/api/catalog/mentor/' + encodeURIComponent(mentor.profile.id) + '/investigation');
    if (request !== investigationRequest || state.mentor !== mentor) return;
    investigationData = data;
    const descriptions = {
      identity: '导师主页和保存的网页', papers: '已有论文和发表年份',
      relations: '师承、同门与合作关系', archive: '之前保存的调查资料',
      crossref: '核对论文标题、作者和年份',
    };
    const selected = (data.last_run?.selected || data.modules.filter(m => m.default).map(m => m.id)).filter(id=>id!=='crossref');
    const papers = data.papers.filter(p => p.doi);
    pane.innerHTML = `
      <div id="publicResearchSummary">${publicResearchSummary()}</div><details class="section-block"><summary>整理已有记录与核对 DOI</summary><section class="section-block"><h3>整理这位导师的资料</h3>
        <p class="pane-intro">选择要整理的内容。论文信息可另外联网核对。</p>
        <div class="investigation-options">${data.modules.map(m => `<label class="investigation-option"><input type="checkbox" name="investigation-module" value="${esc(m.id)}" ${selected.includes(m.id) ? 'checked' : ''}><span><strong>${esc(moduleName(m.id))}</strong><small>${esc(descriptions[m.id])}</small></span></label>`).join('')}</div>
        <div id="doiChoices" ${selected.includes('crossref') ? '' : 'hidden'}><h4>选论文（每次最多 3 篇）</h4><p class="quiet">通过 Crossref 查询 DOI，作者是否为这位导师仍需确认。</p>
          ${papers.length ? papers.map(p => `<label class="doi-choice"><input type="checkbox" name="investigation-paper" value="${esc(p.id)}"><span><strong>${esc(p.title)}</strong><small>${esc(p.year || '年份未知')} · ${esc(p.doi)}</small></span></label>`).join('') : '<p class="quiet">还没有带 DOI 的论文，可以在“论文”页补充。</p>'}
        </div>
        <div class="dossier-actions"><button class="button slim" id="runInvestigation" type="button">整理资料</button><button class="button light slim" id="investigatePapers" type="button">添加或查找论文</button><span class="micro" id="investigationStatus" role="status"></span></div>
        <div class="source-actions">${data.research_links.map(link => `<a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer">${esc(link.label)} ↗</a>`).join('')}</div>
      </section></details><section class="section-block" id="investigationResults"></section><section class="section-block" id="reviewGuide"></section>`;
    pane.querySelector('[value="crossref"]').onchange = event => { $('doiChoices').hidden = !event.target.checked; };
    pane.querySelectorAll('[name="investigation-paper"]').forEach(input => input.onchange = () => {
      if (pane.querySelectorAll('[name="investigation-paper"]:checked').length > 3) {
        input.checked = false;
        $('investigationStatus').textContent = '每次最多选择 3 篇。可以分批核对。';
      }
    });
    $('investigatePapers').onclick = () => setPane('papers');
    $('runInvestigation').onclick = runInvestigation;
    $('runInvestigation').disabled = runningInvestigations.has(mentor.profile.id);
    if (runningInvestigations.has(mentor.profile.id)) $('investigationStatus').textContent = '正在整理…';
    renderInvestigationResults(data.last_run, data.stale);
    renderReviewGuide(data.review_guide);
  } catch (error) {
    if (request === investigationRequest && state.mentor === mentor)
      pane.innerHTML = `<p class="error" role="status">${esc(error.message)}</p>`;
  }
}

function renderReviewGuide(guide) {
  const container = $('reviewGuide');
  if (!container) return;
  const pending = guide.items.filter(item=>['待核查','需补证据'].includes(item.status));
  const completed = guide.items.filter(item=>!['待核查','需补证据'].includes(item.status));
  const paneFor = item => item.pane === 'overview'
    ? ({'身份与任职':'identity','研究方向':'identity','招生与培养':'admission'}[item.section] || 'investigation') : item.pane;
  const row = item => `<div class="review-task"><div><strong>${esc(item.section)}</strong><span class="review-task-status">${esc(item.status)}</span><p>${esc(item.instruction)}</p><small>${esc(item.available)}。</small></div><div class="review-task-actions"><button class="button ghost slim" type="button" data-review-pane="${esc(paneFor(item))}">${esc(item.action)}</button><button class="button light slim" type="button" data-review-category="${esc(item.category)}">保存网页</button></div></div>`;
  container.innerHTML = `<h3>还要确认的事</h3><p class="pane-intro">已核对 ${guide.reviewed} 项，还有 ${guide.pending} 项待确认。</p>${pending.length ? pending.slice(0,3).map(row).join('') : '<p class="quiet">已完成当前核对。资料有更新时可以再查。</p>'}${pending.length>3 ? `<details class="remaining-review"><summary>还有 ${pending.length-3} 项</summary>${pending.slice(3).map(row).join('')}</details>` : ''}${completed.length ? `<details class="remaining-review"><summary>已处理 ${completed.length} 项</summary>${completed.map(row).join('')}</details>` : ''}<button class="button ghost slim" type="button" data-review-pane="check">修改进度</button>`;
  container.querySelectorAll('[data-review-pane]').forEach(button=>button.onclick=()=>setPane(button.dataset.reviewPane));
  container.querySelectorAll('[data-review-category]').forEach(button=>button.onclick=()=>{
    setPane('check');
    $('evidenceCategory').value=button.dataset.reviewCategory;
    $('evidenceTitle').focus();
  });
}

function renderInvestigationResults(run, stale) {
  const container = $('investigationResults');
  if (!run) {
    container.innerHTML = '<h3>整理结果</h3><p class="quiet">整理后会显示在这里。</p>';
    return;
  }
  const labels = {advisor:'师承候选',overlap:'经历重叠',collab:'共同署名',sibling:'同门派生线索',external:'外部师承线索'};
  container.innerHTML = `<h3>整理结果</h3><p class="run-meta">${esc(investigationTime(run.created_at))} · 资料中的任职、论文和招生信息仍需核对。</p>${stale ? '<div class="notice">资料有更新，点击“整理资料”即可刷新。</div>' : ''}` + run.modules.map(module => {
    const d = module.details;
    let details = '';
    if (module.id === 'identity') details = (d.sources || []).map(s => `<div class="source-item"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || '来源页面')}</a><p>${esc(s.claim || '需打开来源核对')} · ${esc(s.status || '待人工核查')}</p></div>`).join('');
    if (module.id === 'papers' && d.by_year) {
      const years = Object.entries(d.by_year), maximum = Math.max(1,...years.map(([,n])=>n));
      details = `<div class="year-bars" aria-label="当前论文候选样本年份分布">${years.map(([year,n]) => `<div class="year-bar">${n}<i style="height:${Math.max(3,Math.round(n/maximum*65))}px"></i>${esc(year)}</div>`).join('')}</div><button class="button ghost slim" data-investigation-pane="papers" type="button">查看论文</button>`;
    }
    if (module.id === 'relations') details = `<p class="quiet">${Object.entries(d.counts || {}).map(([kind,n])=>`${labels[kind]} ${n} 条`).join(' · ')}</p><button class="button ghost slim" data-investigation-pane="network" type="button">查看关系</button>`;
    if (module.id === 'archive' && d.date) details = `<p class="quiet">记录日期：${esc(d.date)}</p>${(d.source_urls || []).map(url=>`<p><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">查看原网页</a></p>`).join('')}${(d.sections || []).map(section=>`<details><summary>${esc(section.title)}</summary>${renderArchiveText(section.text)}</details>`).join('')}${d.collaborators?.length ? `<details><summary>之前记录的合作者</summary><p>${d.collaborators.map(p=>esc(p.name)+'（'+p.years.join('、')+'）').join('；')}</p><p class="quiet">年份为旧调查记录，未重新核对；共同署名不表示指导关系。</p></details>` : ''}`;
    if (module.id === 'crossref') details = (d.checks || []).map(check=>`<div class="doi-result"><strong>${esc(check.doi)}</strong><p>${esc(check.message)}</p>${check.status === 'found' ? `<p>登记标题：${esc(check.title)}<br>年份：${esc(check.year || '未知')} · ${esc(check.venue || '刊会未登记')}<br>作者：${esc(check.authors.join('、') || '未登记')}</p><p class="quiet">${check.title_exact_match ? '标题一致。' : '标题有差异，请查看原文。'}仍需核对作者身份。</p>` : ''}<p><a href="${esc(check.api_url)}" target="_blank" rel="noopener noreferrer">查看元数据来源</a> · ${esc(check.checked_at)}</p></div>`).join('');
    return `<div class="run-result"><div class="run-heading"><h3>${esc(moduleName(module.id))}</h3><span class="run-label ${module.status.includes('待') || module.status.includes('未') ? 'run-warning' : ''}">${esc(module.status)}</span></div><p>${esc(shortSummary(module))}</p>${details}</div>`;
  }).join('');
  container.querySelectorAll('[data-investigation-pane]').forEach(button=>button.onclick=()=>setPane(button.dataset.investigationPane));
}

async function runInvestigation() {
  const mentor = state.mentor;
  if (runningInvestigations.has(mentor.profile.id)) return;
  const modules = Array.from(document.querySelectorAll('[name="investigation-module"]:checked'), input=>input.value);
  const papers = Array.from(document.querySelectorAll('[name="investigation-paper"]:checked'), input=>input.value);
  if (!modules.length) { $('investigationStatus').textContent='请至少选一项。'; return; }
  runningInvestigations.add(mentor.profile.id);
  const button = $('runInvestigation');
  button.disabled = true;
  $('investigationStatus').innerHTML='<span class="investigation-busy" aria-hidden="true"></span>正在整理…';
  try {
    const run = await api('/api/catalog/mentor/' + encodeURIComponent(mentor.profile.id) + '/investigation', {
      method:'POST', body:JSON.stringify({modules,paper_ids:modules.includes('crossref') ? papers : []}),
    });
    if (state.mentor?.profile.id !== mentor.profile.id) return;
    mentor.case.investigation_run = run;
    const current = await api('/api/catalog/mentor/' + encodeURIComponent(mentor.profile.id) + '/investigation');
    if (state.mentor?.profile.id !== mentor.profile.id) return;
    investigationData = current;
    renderReviewGuide(current.review_guide);
    if ($('investigationResults')) renderInvestigationResults(run,current.stale);
    if ($('investigationStatus')) $('investigationStatus').textContent='已保存。';
  } catch(error) {
    if (state.mentor?.profile.id === mentor.profile.id && $('investigationStatus')) $('investigationStatus').textContent=error.message;
  } finally {
    button.disabled=false;
    runningInvestigations.delete(mentor.profile.id);
    if (state.mentor?.profile.id === mentor.profile.id && $('runInvestigation')) $('runInvestigation').disabled=false;
  }
}
