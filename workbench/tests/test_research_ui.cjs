const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function setup(){
  const calls=[];
  const ctx={state:{mentor:{profile:{id:'a'},case:{notes:'keep'}}},$:()=>null,
    document:{addEventListener(){}},encodeURIComponent,Date,esc:String,
    api:()=>new Promise(resolve=>calls.push(resolve)),
    renderOverview(){},renderEvidenceList(){},renderPapers(){},renderNetwork(){}};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/assets/public-research.js'),'utf8'),ctx);
  return {ctx,calls};
}
test('switching mentor keeps late public research out of the new dossier',async()=>{
  const {ctx,calls}=setup();const pending=ctx.readPublicResearch();
  ctx.state.mentor={profile:{id:'b'},case:{notes:'new'}};
  calls[0]({status:'ready',papers:[]});await pending;
  assert.equal(ctx.state.mentor.public_research,undefined);
  assert.equal(ctx.state.mentor.case.notes,'new');
});
test('returning to same mentor receives results without overwriting notes',async()=>{
  const {ctx,calls}=setup();const pending=ctx.readPublicResearch();
  ctx.state.mentor={profile:{id:'a'},case:{notes:'edited while loading'}};
  calls[0]({status:'ready',papers:[{text:'paper'}]});await pending;
  assert.equal(ctx.state.mentor.public_research.papers.length,1);
  assert.equal(ctx.state.mentor.case.notes,'edited while loading');
});

test('faculty roster is visible and is not described as an annual admission catalog',()=>{
  const {ctx}=setup();
  ctx.state.mentor.public_research={status:'catalog',catalog_kind:'faculty_directory',
    checked_at:'2026-10-14',biography:[{text:'转载导师名录列有测试甲，尚未取得学校原始导师页。',url:'https://example.com'}],
    papers:[],relations:[],recruitment:[],admission_notices:[],errors:[]};
  const html=ctx.publicResearchSummary();
  assert.ok(html.includes('尚无当年招生依据'));
  assert.ok(html.includes('转载导师名录列有测试甲'));
  assert.ok(!html.includes('已收录学校招生目录'));
  assert.ok(!html.includes('请查看上方招生目录原文'));
});

test('opening an unread catalog card starts once and keeps its admissions while loading',async()=>{
  const {ctx,calls}=setup();
  ctx.state.mentor.public_research={status:'catalog',needs_enrichment:true,checked_at:'2026-10-14',
    recruitment:[{text:'Existing admission record',url:'https://example.com/catalog'}]};
  const pending=ctx.readPublicResearch();
  assert.equal(calls.length,1);
  assert.ok(ctx.publicResearchSummary().includes('Existing admission record'));
  assert.ok(ctx.publicResearchSummary().includes('正在读取导师主页'));
  await ctx.readPublicResearch();
  assert.equal(calls.length,1);
  calls[0]({status:'catalog',needs_enrichment:false,recruitment:[],errors:['Unreadable']});
  await pending;
  await ctx.readPublicResearch();
  assert.equal(calls.length,1);
});
