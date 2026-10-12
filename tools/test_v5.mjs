// test_v5.mjs — 真实执行 v5 页面脚本，检查总览/展开/放射/热力图
import fs from 'node:fs';
import vm from 'node:vm';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

js += `
;(function(){
  let R = {};
  try{
    W = 1500; H = 950;
    // 总览
    focus = null; layoutTree(); fitView(70);
    R.ov = { n: nodes.length, e: edges.length, scale: +scale.toFixed(3),
      clipped: nodes.filter(n => { const x = n.x*scale+ox, y = n.y*scale+oy;
        return x - n.r*scale < 0 || x + n.r*scale > W || y - n.r*scale < 0 || y + n.r*scale > H; }).length };
    // 展开学生最多的人
    let best = null, bn = -1;
    for (const m of MENTORS) if (m.n > bn) { bn = m.n; best = m.k; }
    focus = best; layoutTree(); fitView(90);
    const ys = new Set(nodes.map(n => Math.round(n.y)));
    R.fo = { name: NAME(best), n: nodes.length, e: edges.length, scale: +scale.toFixed(3), rows: ys.size,
      maxW: Math.round(Math.max(...nodes.map(n=>n.x)) - Math.min(...nodes.map(n=>n.x))),
      clipped: nodes.filter(n => { const x = n.x*scale+ox, y = n.y*scale+oy;
        return x - n.r*scale < 0 || x + n.r*scale > W || y - n.r*scale < 0 || y + n.r*scale > H; }).length };
    // 阈值调整
    th = 1; focus = null; layoutTree();
    R.th1 = nodes.length;
    th = 8; layoutTree();
    R.th8 = nodes.length;
    // 放射
    view = 'radial'; th = 3; buildRadial(best);
    R.rad = { n: Object.keys(rPos).length };
    R.mentors = MENTORS.length;
  }catch(e){ R = { err: e.message, stack: (e.stack||'').split('\\n')[1] }; }
  __R = R;
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
    querySelectorAll: (s) => (s === '.tab' ? ['tree','radial','heat'].map((v,i)=>{const e=mkEl('t'+i);e.dataset={v};return e;}) : []), addEventListener() {} },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Boolean, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0 };
sb.globalThis = sb;
vm.createContext(sb);
let err = null;
try { new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 60000 }); } catch (e) { err = e; }
console.log('=== 执行 ===');
if (err) { console.log('✗ 运行时错误:', err.message, '\n  ', (err.stack||'').split('\n')[1]); process.exit(1); }
const R = sb.__R;
if (R.err) { console.log('✗ 探针错误:', R.err, R.stack||''); process.exit(1); }
console.log('✓ 脚本执行无错');
console.log('\n=== 总览 ===');
console.log(`  ${R.ov.n} 位导师 ｜ scale ${R.ov.scale} ｜ 超出画布 ${R.ov.clipped} 个`);
console.log('\n=== 展开（学生最多者）===');
console.log(`  「${R.fo.name}」 ${R.fo.n} 节点 / ${R.fo.e} 边 ｜ 行数 ${R.fo.rows} ｜ 宽 ${R.fo.maxW}px ｜ scale ${R.fo.scale} ｜ 超出画布 ${R.fo.clipped} 个`);
console.log(`\n阈值效果：≥1 名学生的导师 ${R.th1} 位 ｜ ≥8 名 ${R.th8} 位 ｜ 全部有学生的导师 ${R.mentors} 位`);
console.log(`放射视图节点数 ${R.rad.n}`);

let fail = 0;
const t = (ok, m) => { console.log(`  ${ok ? '✓' : '✗'} ${m}`); if (!ok) fail++; };
console.log('\n=== 判定 ===');
t(R.ov.n >= 15 && R.ov.n <= 25, `总览节点 15-25 个，画面干净（实际 ${R.ov.n}）`);
t(R.ov.clipped === 0, `总览无节点被画布切掉（超出 ${R.ov.clipped}）`);
t(R.fo.n >= 20 && R.fo.n <= 60, `展开节点 20-60 个（实际 ${R.fo.n}）`);
t(R.fo.clipped === 0, `展开无节点被切掉（超出 ${R.fo.clipped}）`);
t(R.fo.rows >= 2, `学生自动换行（实际 ${R.fo.rows} 行）`);
t(R.fo.scale > 0.8, `展开缩放 >0.8，元素够大（实际 ${R.fo.scale}）`);
t(R.th1 > R.th8, `阈值滑块有效（≥1 名 → ${R.th1} 位，≥8 名 → ${R.th8} 位）`);
t(R.rad.n > 3 && R.rad.n < 90, `放射节点不拥挤（实际 ${R.rad.n}）`);
console.log(fail ? `\n❌ ${fail} 项未通过` : '\n✅ 全部通过');
process.exit(fail ? 1 : 0);
