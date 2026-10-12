// test_layout.mjs — 真实执行页面脚本，检验布局质量（间距、重叠、视口适配）
import fs from 'node:fs';
import vm from 'node:vm';

const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

// 在脚本末尾注入诊断：导出内部状态
js += `
;(function(){
  try {
    const st = { view, scale, ox, oy, n: G.list.length, edges: G.edges.length,
      sample: G.list.slice(0, 5).map(k => ({ k, x: pos[k] && Math.round(pos[k].x), y: pos[k] && Math.round(pos[k].y) })) };
    __DIAG = st;
  } catch(e) { __DIAG = { err: e.message }; }
})();
`;

const ids = [...new Set([...h.matchAll(/id="([\w-]+)"/g)].map((m) => m[1]))];
const calls = [];
const ctx2d = new Proxy({}, {
  get(_, p) {
    if (p === 'canvas') return el('cv');
    if (['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'textAlign'].includes(p)) return '';
    if (p === 'measureText') return () => ({ width: 22 });
    return () => {};
  }, set() { return true; },
});
function el(id) {
  return {
    id, _html: '', textContent: '', value: '', checked: true, style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild(c) { (this.children = this.children || []).push(c); return c; },
    addEventListener(t) { calls.push(id + ':' + t); },
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    querySelectorAll: () => [],
    getContext: () => ctx2d,
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
    width: 1500, height: 950,
  };
}
const store = {};
const sandbox = {
  document: {
    getElementById: (id) => (store[id] = store[id] || el(id)),
    createElement: (t) => el('new-' + t),
    querySelectorAll: (s) => (s === '.tab'
      ? [Object.assign(el('t1'), { dataset: { v: 'lineage' } }), Object.assign(el('t2'), { dataset: { v: 'collab' } })]
      : []),
    addEventListener() {},
  },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Date, Object, Array, String, Number, Set, Map,
  Float32Array, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
sandbox.globalThis = sandbox;
let err = null;
try { vm.createContext(sandbox); new vm.Script(js, { filename: 'page.js' }).runInContext(sandbox, { timeout: 120000 }); }
catch (e) { err = e; }

console.log('=== 执行 ===');
if (err) { console.log('✗ 运行时错误:', err.message, '\n', err.stack?.split('\n')[1]); process.exit(1); }
console.log('✓ 脚本执行无错');
const D = sandbox.__DIAG;
console.log('  视图:', D.view, '| 节点', D.n, '| 边', D.edges);
console.log('  自动视口: scale =', D.scale?.toFixed(3), '| 偏移', D.ox?.toFixed(0), D.oy?.toFixed(0));
console.log('  样例坐标:', JSON.stringify(D.sample));

// ── 布局质量：在沙箱内重算坐标统计 ──
const probe = `
;(function(){
  const xs=[],ys=[];
  for(const k of G.list){const p=pos[k]; if(p){xs.push(p.x);ys.push(p.y);}}
  const n=xs.length;
  const w=Math.max(...xs)-Math.min(...xs), hh=Math.max(...ys)-Math.min(...ys);
  // 最近邻距离中位数（判断是否挤在一起）
  const nn=[];
  for(let i=0;i<n;i++){let best=1e9;for(let j=0;j<n;j++){if(i===j)continue;const d=(xs[i]-xs[j])**2+(ys[i]-ys[j])**2;if(d<best)best=d;}nn.push(Math.sqrt(best));}
  nn.sort((a,b)=>a-b);
  // 被画布覆盖的比例（考虑 scale/offset 后是否落在视口内）
  let inView=0;
  for(let i=0;i<n;i++){const X=xs[i]*scale+ox,Y=ys[i]*scale+oy;if(X>=0&&X<=W&&Y>=0&&Y<=H)inView++;}
  __Q={n,w:Math.round(w),h:Math.round(hh),nnMed:+nn[Math.floor(n/2)].toFixed(1),nnMin:+nn[0].toFixed(1),inViewPct:Math.round(inView/n*100),W,H};
})();
`;
try { new vm.Script(probe).runInContext(sandbox); } catch (e) { console.log('质量探测失败:', e.message); }
const Q = sandbox.__Q;
console.log('\n=== 布局质量 ===');
console.log(`  包围盒 ${Q.w} × ${Q.h}（画布 ${Q.W} × ${Q.H}）`);
console.log(`  最近邻距离：中位 ${Q.nnMed}，最小 ${Q.nnMin}`);
console.log(`  落在视口内的节点：${Q.inViewPct}%`);

let fail = 0;
const t = (ok, msg) => { console.log(`  ${ok ? '✓' : '✗'} ${msg}`); if (!ok) fail++; };
console.log('\n=== 判定 ===');
t(D.scale > 0.1 && D.scale < 4, `scale 在合理区间（${D.scale?.toFixed(3)}）`);
t(Q.inViewPct >= 95, `≥95% 节点在视口内（实际 ${Q.inViewPct}%）`);
t(Q.nnMed > 20, `最近邻中位距离 >20（实际 ${Q.nnMed}，防重叠）`);
t(Q.nnMin > 3, `无完全重叠节点（最小 ${Q.nnMin}）`);
t(Q.w > Q.W * 0.5 || Q.h > Q.H * 0.5, `图形充分占据画布（${Q.w}×${Q.h} vs ${Q.W}×${Q.H}）`);
console.log(fail ? `\n❌ ${fail} 项未通过` : '\n✅ 布局质量全部通过');
process.exit(fail ? 1 : 0);
