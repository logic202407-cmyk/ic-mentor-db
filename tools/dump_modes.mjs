// dump_modes.mjs — 导出三种分类方式下的总览布局，供渲染核对
import fs from 'node:fs';
import vm from 'node:vm';
const MODE = process.argv[2] || 'school';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];
js += `
;(function(){
  let R = {};
  try{
    W = 1500; H = 950;
    mode = '${MODE}'; focus = null; th = (mode === 'gen' ? 2 : 3);
    layoutTree(); fitView(70);
    const P = {};
    for (const n of nodes) P[n.k] = { x:n.x, y:n.y, r:n.r, root:true, cnt:n.cnt, tier:n.tier||'',
      ndir:n.ndir||0, multi:!!n.multi,
      n:NAME(n.k), s:SCH(n.k), pp:NP(n.k), color:(COL[SCH(n.k)]||'#64748b'), cross:!!n.hasCross };
    R = { pos:P, edges:[], scale, ox, oy, W, H, mode:'${MODE}', n:nodes.length,
      groups: groups.map(g=>({key:g.key, name:g.name, color:g.color, x:g.x, y:g.y, w:g.w, h:g.h, n:g.n})) };
  }catch(e){ R = { err:e.message, stack:(e.stack||'').split('\\n')[1] }; }
  __D = R;
})();
`;
function mkEl(id) {
  return { id, _html: '', textContent: '', value: '3', checked: false, style: {}, dataset: {}, children: [],
    width: 1500, height: 950, clientWidth: 1500, clientHeight: 950,
    classList: { add() {}, remove() {}, toggle() { return true; }, contains() { return false; } },
    appendChild(c) { this.children.push(c); return c; }, addEventListener() {},
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    querySelectorAll: () => [], querySelector: () => null, getContext: () => ctx2d, scrollIntoView() {},
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; } };
}
const ctx2d = new Proxy({}, { get(_, p) { if (p === 'canvas') return { width: 1500, height: 950 }; if (p === 'measureText') return () => ({ width: 26 }); if (['font','fillStyle','strokeStyle','lineWidth','textAlign','textBaseline'].includes(p)) return ''; return () => {}; }, set() { return true; } });
const store = {};
const sb = { document: { getElementById: (id) => (store[id] = store[id] || mkEl(id)), createElement: () => mkEl('x'),
    querySelectorAll: (s) => (s === '.tab' ? ['tree','radial','heat'].map((v,i)=>{const e=mkEl('t'+i);e.dataset={v};return e;})
      : s === '.mode' ? ['school','dir','gen'].map((v,i)=>{const e=mkEl('m'+i);e.dataset={m:v};return e;}) : []), addEventListener() {} },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Boolean, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0 };
sb.globalThis = sb;
vm.createContext(sb);
new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 60000 });
const D = sb.__D;
if (D.err) { console.log('ERR', D.err, D.stack || ''); process.exit(1); }
const out = `data/processed/_mode_${MODE}.json`;
fs.writeFileSync(out, JSON.stringify(D), 'utf8');
console.log(`[${MODE}] ${D.n} 节点 / ${D.groups.length} 组 / scale ${D.scale.toFixed(3)} → ${out}`);
console.log('   分组: ' + D.groups.map(g => g.name + '(' + g.n + ')').join(' ｜ '));
