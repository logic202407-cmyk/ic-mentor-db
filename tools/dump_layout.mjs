// dump_layout.mjs — 导出页面脚本真实计算出的布局坐标，供可视化核对
import fs from 'node:fs';
import vm from 'node:vm';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];
// 注入：导出坐标与图结构（支持指定视图：lineage | collab）
const VIEW = process.argv[2] || 'lineage';
js = js.replace('resize();', '/* resize 推迟到注入代码里调用 */');
js += `
;(function(){
  try{
    // 手动设置视口尺寸（原脚本的 resize() 依赖 DOM 布局，桩件下取不到值）
    W = 1500; H = 950;
    view = '${VIEW}';
    if (view === 'force') minW = 5;
    rebuild(true);
    const P={}; for(const k of G.list){ const p=pos[k]; if(p) P[k]={x:p.x,y:p.y,r:(typeof radius==='function'?radius(k):6),n:NAME(k),s:SCH(k),pp:NP(k)}; }
    __DUMP={pos:P, edges:G.edges.map(e=>({s:e.s,t:e.t,k:e.k,lv:e.lv||0,cross:!!e.cross})), scale, ox, oy, W, H, view,
      panels: panels.filter(p=>p.mi===undefined).map(p=>({school:p.school,x:p.x,y:p.y,w:p.w,h:p.h,color:p.color,n:p.n})),
      matrix: (M&&M._schools)?{schools:M._schools,cell:M._cell,left:M._left,top:M._top,cells:panels.filter(c=>c.mi!==undefined)}:null};
  }catch(e){ __DUMP={err:e.message, stack:(e.stack||'').split('\\n').slice(0,2).join(' | ')}; }
})();
`;
const ctx2d = new Proxy({}, { get(_, p) { if (p === 'canvas') return { width: 1500, height: 950 }; if (p === 'measureText') return () => ({ width: 20 }); if (['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'textAlign', 'textBaseline'].includes(p)) return ''; return () => {}; }, set() { return true; } });
function el(id) {
  return {
    id, textContent: '', value: '', checked: true, style: {}, dataset: {}, width: 1500, height: 950,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild(c) { (this.c = this.c || []).push(c); return c; },
    addEventListener() {}, querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    getContext: () => ctx2d, set innerHTML(v) {}, get innerHTML() { return ''; },
  };
}
const store = {};
const sb = {
  document: { getElementById: (id) => (store[id] = store[id] || el(id)), createElement: () => el('x'), querySelectorAll: (s) => (s === '.tab' ? [Object.assign(el('t1'), { dataset: { v: 'lineage' } }), Object.assign(el('t2'), { dataset: { v: 'collab' } })] : []), addEventListener() {} },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Float32Array, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
sb.globalThis = sb;
vm.createContext(sb);
new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 120000 });
const D = sb.__DUMP;
if (D.err) { console.log('ERR', D.err); process.exit(1); }
const outFile = `data/processed/_layout_${VIEW}.json`;
fs.writeFileSync(outFile, JSON.stringify(D), 'utf8');
console.log(`导出 ${VIEW} 布局: ${Object.keys(D.pos).length} 节点 / ${D.edges.length} 边 / scale=${D.scale.toFixed(3)} → ${outFile}`);
