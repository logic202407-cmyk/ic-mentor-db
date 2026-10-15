function renderManualPapers() {
  const mentor = state.mentor;
  const items = mentor.case.manual_papers || [];
  $('pane-papers').insertAdjacentHTML('afterbegin', `<section class="section-block"><h3>自己补充的论文</h3>${items.map(p=>`<div class="paper-item"><strong>${esc(p.title)}</strong><p>${esc(p.year || '年份未填')} · 作者归属待核对</p><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">论文链接</a> <button class="button ghost slim" type="button" data-remove-paper="${esc(p.id)}">移除</button></div>`).join('')}<details class="paper-add"><summary>添加论文</summary><form id="manualPaperForm"><p class="quiet">填标题和 DOI 或链接即可。保存后可在“资料汇总”里核对 DOI。</p><label class="field-label" for="paperTitle">论文标题</label><input class="field" id="paperTitle" required maxlength="350"><label class="field-label" for="paperDoi">DOI（有的话填写）</label><input class="field" id="paperDoi" maxlength="250" placeholder="10.… 或 https://doi.org/…"><label class="field-label" for="paperUrl">论文链接（没有 DOI 时必填）</label><input class="field" id="paperUrl" type="url" maxlength="1000" placeholder="https://…"><label class="field-label" for="paperYear">发表年份（选填）</label><input class="field" id="paperYear" type="number" min="1800" max="2100"><div class="dossier-actions"><button class="button slim" type="submit">保存论文</button></div></form></details><p id="paperSaveStatus" class="quiet" role="status"></p></section>`);
  $('manualPaperForm').onsubmit = async event => {
    event.preventDefault();
    const button=event.target.querySelector('button');button.disabled=true;
    const payload={title:$('paperTitle').value,doi:$('paperDoi').value,url:$('paperUrl').value,year:$('paperYear').value};
    $('paperSaveStatus').textContent='正在保存…';
    try {
      mentor.case=await api('/api/catalog/mentor/'+encodeURIComponent(mentor.profile.id)+'/papers',{method:'POST',body:JSON.stringify(payload)});
      if(state.mentor!==mentor)return;
      renderPapers();$('paperSaveStatus').textContent='已保存。';
    } catch(error) {if(state.mentor===mentor)$('paperSaveStatus').textContent=error.message;}
    finally {button.disabled=false;}
  };
  document.querySelectorAll('[data-remove-paper]').forEach(button=>button.onclick=async()=>{
    button.disabled=true;
    try {
      mentor.case=await api('/api/catalog/mentor/'+encodeURIComponent(mentor.profile.id)+'/papers/'+button.dataset.removePaper,{method:'DELETE'});
      if(state.mentor===mentor)renderPapers();
    } catch(error){if(state.mentor===mentor)$('paperSaveStatus').textContent=error.message;button.disabled=false;}
  });
}

function setupAddMentor() {
  $('addMentorBox').innerHTML=`<summary>没找到？添加导师</summary><form id="addMentorForm"><p class="quiet">保存到自己的资料夹，之后可按姓名或学科找到。</p><label class="field-label" for="newMentorName">姓名</label><input class="field" id="newMentorName" maxlength="100" required><label class="field-label" for="newMentorDiscipline">一级学科</label><select class="field" id="newMentorDiscipline" required></select><label class="field-label" for="newMentorSchool">高校 / 机构</label><input class="field" id="newMentorSchool" list="schoolSuggestions" required maxlength="160" placeholder="选择已有学校，或输入名称"><datalist id="schoolSuggestions"></datalist><label class="field-label" for="newMentorDepartment">院系（选填）</label><input class="field" id="newMentorDepartment" maxlength="160"><label class="field-label" for="newMentorDirection">研究方向（选填）</label><input class="field" id="newMentorDirection" maxlength="160" placeholder="如：宋代史、机器学习"><label class="field-label" for="newMentorHomepage">导师主页（选填）</label><input class="field" id="newMentorHomepage" type="url" maxlength="1000" placeholder="https://…"><button class="button slim" type="submit">保存并查看</button><p class="quiet" id="newMentorStatus" role="status"></p></form>`;
  $('newMentorDiscipline').innerHTML=$('disciplineSelect').innerHTML;
  let schoolRequest=0;
  $('newMentorDiscipline').onchange=async()=>{
    const request=++schoolRequest;
    $('schoolSuggestions').innerHTML='';
    try {
      const schools=await api('/api/catalog/institutions?'+params({discipline:$('newMentorDiscipline').value,project_id:state.projectId}));
      if(request!==schoolRequest)return;
      $('schoolSuggestions').innerHTML=schools.map(item=>`<option value="${esc(item.name)}"></option>`).join('');
    }catch(error){if(request===schoolRequest)$('newMentorStatus').textContent='学校列表暂时没加载出来，也可以直接输入。';}
  };
  $('addMentorBox').addEventListener('toggle',()=>{
    if($('addMentorBox').open && !$('newMentorName').value)$('newMentorName').value=$('nameInput').value.trim();
  });
  $('addMentorForm').onsubmit=async event=>{
    event.preventDefault();
    const button=event.target.querySelector('button');button.disabled=true;
    const profile={name:$('newMentorName').value,institution:$('newMentorSchool').value,
      first_level_discipline:$('newMentorDiscipline').value,discipline:$('newMentorDiscipline').value,
      department:$('newMentorDepartment').value,interests:$('newMentorDirection').value,homepage:$('newMentorHomepage').value};
    $('newMentorStatus').textContent='正在保存…';
    try {
      let projectId=state.projectId;
      if(!projectId){
        const projects=await api('/api/projects');
        projectId=projects.find(p=>p.name==='我的导师')?.id;
        if(!projectId)projectId=(await api('/api/projects',{method:'POST',body:JSON.stringify({name:'我的导师'})})).id;
      }
      const saved=await api('/api/projects/'+projectId+'/profiles',{method:'POST',body:JSON.stringify(profile)});
      clearDossier();state.projectId=projectId;state.candidates=[];renderCandidates();
      await refreshProjects();await loadDisciplines();
      await openMentor('project-'+projectId+'-'+saved.id);
      $('newMentorStatus').textContent='已保存到当前资料夹。';event.target.reset();$('addMentorBox').open=false;
    }catch(error){$('newMentorStatus').textContent=error.message;}
    finally{button.disabled=false;}
  };
}
