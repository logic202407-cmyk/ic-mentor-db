// test_collab.mjs — 验证合作网络视图的力导向布局质量
import fs from 'node:fs';
import vm from 'node:vm';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];
// 切到合作视图并注入诊断
js += `
;(function(){
  try{
    view='collab'; minW=3;
    rebuild(true);
    const xs=[],ys=[];
    for(const k of G.list){const p=pos[k]; if(p){xs.push(p.x);ys.push(p.y);}}
    const n=xs.length;
    const w=Math.max(...xs)-Math.min(...xs), hh=Math.max(...ys)-Math.min(...ys);
    const nn=[];
    for(let i=0;i<n;i++){let best=1e9;for(let j=0;j<n;j++){if(i===j)continue;const d=(xs[i]-xs[j])**2+(ys[i]-ys[j])**2;if(d<best)best=d;}nn.push(Math.sqrt(best));}
    nn.sort((a,b)=>a-b);
    let inView=0;
    for(let i=0;i<n;i++){const X=xs[i]*scale+ox,Y=ys[i]*scale+oy;if(X>=0&&X<=W&&Y>=0&&Y<=H)inView++;}
    __Q={n,w:Math.round(w),h:Math.round(hh),scale:+scale.toFixed(4),nnMed:+nn[Math.floor(n/2)].toFixed(1),nnMin:+nn[0].toFixed(1),inViewPct:Math.round(inView/n*100)};
  }catch(e){ __Q={err:e.message, stack:(e.stack||'').split('\\n')[1]}; }
})();
`;
const ctx2d = new Proxy({}, { get(_, p) { if (p === 'canvas') return { width: 1500, height: 950 }; if (p === 'measureText') return () => ({ width: 20 }); if (['font','fillStyle','strokeStyle','lineWidth','textAlign','textBaseline'].includes(p)) return ''; return () => {}; }, set() { return true; } });
function el(id) { return { id, textContent: '', value: '', checked: true, style: {}, dataset: {}, width: 1500, height: 950, classList: { add(){}, remove(){}, toggle(){}, contains: () => false }, appendChild(c){ (this.c=this.c||[]).push(c); return c; }, addEventListener(){}, querySelectorAll: () => [], getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }), getContext: () => ctx2d, set innerHTML(v){}, get innerHTML(){return '';} }; }
const store = {};
const sb = {
  document: { getElementById: (id) => (store[id] = store[id] || el(id)), createElement: () => el('x'), querySelectorAll: (s) => (s === '.tab' ? [Object.assign(el('t1'), { dataset: { v: 'lineage' } }), Object.assign(el('t2'), { dataset: { v: 'collab' } })] : []), addEventListener() {} },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Float32Array, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
sb.globalThis = sb;
vm.createContext(sb);
const t0 = Date.now();
new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 300000 });
const ms = Date.now() - t0;
const Q = sb.__Q;
console.log('=== 合作网络视图 ===');
if (Q.err) { console.log('✗ 运行时错误:', Q.err, Q.stack); process.exit(1); }
console.log(`  节点 ${Q.n} | 包围盒 ${Q.w}×${Q.h} | scale ${Q.scale}`);
console.log(`  最近邻：中位 ${Q.nnMed}，最小 ${Q.nnMin}`);
console.log(`  视口内节点 ${Q.inViewPct}% | 布局+渲染耗时 ${ms}ms`);
let fail = 0;
const t = (ok, m) => { console.log(`  ${ok ? '✓' : '✗'} ${m}`); if (!ok) fail++; };
console.log('\n=== 判定 ===');
t(Q.nnMed > 8, `最近邻中位 >8（实际 ${Q.nnMed}）——过大即「糊成一团」`);
t(Q.nnMin > 1, `无完全重叠（最小 ${Q.nnMin}）`);
t(Q.inViewPct >= 95, `≥95% 在视口内（实际 ${Q.inViewPct}%）`);
t(ms < 20000, `耗时 <20s（实际 ${ms}ms）`);
console.log(fail ? `\n❌ ${fail} 项未通过` : '\n✅ 合作视图布局通过');
process.exit(fail ? 1 : 0);
