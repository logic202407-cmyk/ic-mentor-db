// Controlled response order reproduces fast selection changes without live networking.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../web/desk.html'), 'utf8');
function setup(...names) {
  const elements = new Map();
  const calls = [];
  const state = {queryVersion:0,selectionVersion:0,projectId:'',candidates:[],mentor:null,
                 includeNonEngineering:false};
  const context = {state, encodeURIComponent,
    $: id => { if (!elements.has(id)) elements.set(id,{value:'',innerHTML:'',textContent:'',disabled:false,checked:false}); return elements.get(id); },
    params: obj => new URLSearchParams(obj), esc: String,
    // The page scopes catalogue queries to engineering by default.
    scopeParams: () => state.includeNonEngineering ? {include_non_engineering:true} : {},
    clearDossier: () => {state.queryVersion++;state.selectionVersion++;state.mentor=null;},
    renderCandidates: () => {}, message: value => { context.lastMessage=value; },
    resetSelect: id => {context.$(id).innerHTML='';context.$(id).disabled=true;},
    api: (url, options) => new Promise((resolve,reject)=>calls.push({url,options,resolve,reject})),
    renderPapers: () => {context.rendered=true;}, renderNetwork: () => {},
    refreshAuthorWorks: () => {context.refreshed=true;},
    chooseInstitution: async () => {}, chooseDirection: async () => {},
  };
  vm.createContext(context);
  for (const name of names) {
    const line = html.split('\n').find(line=>line.startsWith(`async function ${name}(`));
    assert.ok(line, name);
    vm.runInContext(line,context);
  }
  return {context,state,calls,$:context.$};
}
test('choosing a discipline immediately lists mentors across schools',async()=>{
  const {context,$,calls,state}=setup('chooseDiscipline','chooseInstitution','chooseDirection');
  $('disciplineSelect').value='0833 城乡规划学';
  const pending=context.chooseDiscipline();
  calls[0].resolve([{name:'甲大学',count:1},{name:'乙大学',count:1}]);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(calls[1].url,/institution=__all__/);
  calls[1].resolve([{name:'规划',count:2}]);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(calls[2].url,/direction=__all__/);
  calls[2].resolve([{id:'a',institution:'甲大学'},{id:'b',institution:'乙大学'}]);
  await pending;
  assert.equal(state.candidates.length,2);
  assert.equal($('institutionSelect').value,'__all__');
  assert.equal($('directionSelect').value,'__all__');
});
test('old discipline response cannot replace a later selection',async()=>{
  const {context,$,calls}=setup('chooseDiscipline');
  $('disciplineSelect').value='学科甲'; const first=context.chooseDiscipline();
  $('disciplineSelect').value='学科乙'; const second=context.chooseDiscipline();
  calls[1].resolve([{name:'乙大学',count:1}]);await second;
  calls[0].resolve([{name:'甲大学',count:2}]);await first;
  assert.match($('institutionSelect').innerHTML,/乙大学/);
  assert.doesNotMatch($('institutionSelect').innerHTML,/甲大学/);
});
test('old institution response cannot replace current directions',async()=>{
  const {context,$,calls}=setup('chooseInstitution');
  $('institutionSelect').value='甲大学';const first=context.chooseInstitution();
  $('institutionSelect').value='乙大学';const second=context.chooseInstitution();
  calls[1].resolve([{name:'当前方向',count:1}]);await second;
  calls[0].resolve([{name:'过期方向',count:1}]);await first;
  assert.match($('directionSelect').innerHTML,/当前方向/);
  assert.doesNotMatch($('directionSelect').innerHTML,/过期方向/);
});
test('old direction cannot replace current mentor candidates',async()=>{
  const {context,$,calls,state}=setup('chooseDirection');
  $('directionSelect').value='甲';const first=context.chooseDirection();
  $('directionSelect').value='乙';const second=context.chooseDirection();
  calls[1].resolve([{id:'current'}]);await second;
  calls[0].resolve([{id:'old'}]);await first;
  assert.equal(state.candidates[0].id,'current');
});
test('old failed request cannot replace the current success message',async()=>{
  const {context,$,calls}=setup('chooseDiscipline');
  $('disciplineSelect').value='甲';const first=context.chooseDiscipline();
  $('disciplineSelect').value='乙';const second=context.chooseDiscipline();
  calls[1].resolve([{name:'乙大学',count:1}]);await second;
  calls[0].reject(Error('old error'));await first;
  assert.doesNotMatch(context.lastMessage,/old error/);
});
test('author association finishing after mentor switch does not refresh new mentor',async()=>{
  const {context,state,calls}=setup('linkAuthor');
  state.mentor={profile:{id:'original'},case:{}};
  const pending=context.linkAuthor('A123');
  const current={profile:{id:'current'},case:{}};state.mentor=current;
  calls[0].resolve({openalex_author_id:'A123'});await pending;
  assert.equal(context.refreshed,undefined);
  assert.equal(current.case.openalex_author_id,undefined);
  assert.match(calls[0].url,/original\/case$/);
});
test('completed works query does not render over another mentor',async()=>{
  const {context,state,calls}=setup('refreshAuthorWorks');
  state.mentor={profile:{id:'original'},case:{}};
  const pending=context.refreshAuthorWorks();
  state.mentor={profile:{id:'current'},case:{}};
  calls[0].resolve({openalex_snapshot:{papers:[]}});await pending;
  assert.equal(context.rendered,undefined);
});
