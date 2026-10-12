// test_click.mjs — 回归测试：验证画布事件确实绑上、且点击能展开师承树
//
// 背景：v5 首次发布时 `restoreCanvas()` 里有「if ($('cv')) return;」，
// 而画布本就存在于初始 HTML 中，导致 bindCanvas() 从未执行、鼠标事件一个都没绑，
// 表现为「点击点不了」。此测试专门守住这条。
import fs from 'node:fs';
import vm from 'node:vm';

const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

// 注入探针：加载后立即检查绑定情况，并模拟点击
js += `
;(function(){
  let R = {};
  try{
    W = 1500; H = 950;
    const c = $('cv');
    const ev = (c && c._ev) || {};
    R.listeners = Object.keys(ev);
    R.hasClick = typeof ev.click === 'function';
    R.hasMove = typeof ev.mousemove === 'function';
    R.hasWheel = typeof ev.wheel === 'function';
    R.hasDown = typeof ev.mousedown === 'function';
    // 总览态：挑一个「学生也有学生」的根节点（这样能测到下钻），否则退而求其次
    focus = null; layoutTree(); fitView(70);
    let target = null, child = null;
    for (const n of nodes) {
      const ks = (studentsOf[n.k] || []).map(e => e.s);
      const withKids = ks.find(s => (studentsOf[s] || []).length > 0);
      if (withKids) { target = n; child = withKids; break; }
    }
    if (!target) {
      for (const n of nodes) if ((studentsOf[n.k] || []).length > 0) { target = n; break; }
    }
    R.targetName = NAME(target.k);
    R.targetStu = (studentsOf[target.k] || []).length;
    R.hasGrand = !!child;
    const sx = target.x * scale + ox, sy = target.y * scale + oy;
    R.screenPos = { x: Math.round(sx), y: Math.round(sy) };
    // 触发 mousedown -> click（模拟真实点击序列）
    ev.mousedown({ clientX: sx, clientY: sy });
    ev.click({ clientX: sx, clientY: sy });
    R.afterClickFocus = focus ? NAME(focus) : null;
    R.afterClickNodes = nodes.length;
    R.afterClickEdges = edges.length;
    // 再点一个画布空白处，应保持不变
    ev.click({ clientX: 5, clientY: 5 });
    R.afterBlankFocus = focus ? NAME(focus) : null;
    // 展开态下点击一个「有学生」的子节点，应以他为中心重绘
    const childNode = child ? nodes.find(n => n.k === child) : null;
    if (childNode) {
      R.childName = NAME(child);
      const cx2 = childNode.x * scale + ox, cy2 = childNode.y * scale + oy;
      ev.mousedown({ clientX: cx2, clientY: cy2 });
      ev.click({ clientX: cx2, clientY: cy2 });
      R.afterChildFocus = focus ? NAME(focus) : null;
    }
    // 拖动后不应被当成点击
    focus = null; layoutTree(); fitView(70);
    const t2 = nodes.find(n => (studentsOf[n.k] || []).length > 0);
    const tx = t2.x * scale + ox, ty = t2.y * scale + oy;
    ev.mousedown({ clientX: tx, clientY: ty });
    if (typeof ev.mousemove === 'function') ev.mousemove({ clientX: tx + 40, clientY: ty + 40 });
    ev.click({ clientX: tx, clientY: ty });
    R.afterDragFocus = focus ? NAME(focus) : null;
  }catch(e){ R = { err: e.message, stack: (e.stack||'').split('\\n')[1] }; }
  __R = R;
})();
`;

function mkEl(id) {
  const el = {
    id, _html: '', textContent: '', value: '3', checked: false, style: {}, dataset: {}, children: [],
    width: 1500, height: 950, clientWidth: 1500, clientHeight: 950,
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); }, toggle(c, f) { if (f === undefined) f = !this._s.has(c); f ? this._s.add(c) : this._s.delete(c); return f; }, contains(c) { return this._s.has(c); } },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (this._ev = this._ev || {})[t] = fn; },
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    querySelectorAll: () => [], querySelector: () => null,
    getContext: () => ctx2d, scrollIntoView() {},
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
  };
  return el;
}
const ctx2d = new Proxy({}, { get(_, p) { if (p === 'canvas') return { width: 1500, height: 950 }; if (p === 'measureText') return () => ({ width: 26 }); if (['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'textAlign', 'textBaseline'].includes(p)) return ''; return () => {}; }, set() { return true; } });
const store = {};
const sb = {
  document: {
    getElementById: (id) => (store[id] = store[id] || mkEl(id)),
    createElement: () => mkEl('x'),
    querySelectorAll: (s) => (s === '.tab' ? ['tree', 'radial', 'heat'].map((v, i) => { const e = mkEl('t' + i); e.dataset = { v }; return e; }) : []),
    addEventListener() {},
  },
  window: { addEventListener(t, fn) { (win._ev = win._ev || {})[t] = fn; }, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Boolean, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
const win = sb.window;
sb.globalThis = sb;
vm.createContext(sb);
let err = null;
try { new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 60000 }); } catch (e) { err = e; }

console.log('=== 执行 ===');
if (err) { console.log('✗ 运行时错误:', err.message, '\n  ', (err.stack || '').split('\n')[1]); process.exit(1); }
const R = sb.__R;
if (R.err) { console.log('✗ 探针错误:', R.err, R.stack || ''); process.exit(1); }
console.log('✓ 页面加载无错');

console.log('\n=== 事件绑定 ===');
console.log('  画布上已绑事件:', R.listeners.join(', ') || '（无！）');

console.log('\n=== 点击行为 ===');
console.log(`  总览下点击「${R.targetName}」（${R.targetStu} 名学生）于屏幕坐标 (${R.screenPos.x}, ${R.screenPos.y})`);
console.log(`  → 展开为「${R.afterClickFocus}」，${R.afterClickNodes} 节点 / ${R.afterClickEdges} 边`);
console.log(`  点击空白处 → 仍为「${R.afterBlankFocus}」`);
if (R.childName) console.log(`  展开态下点击子节点「${R.childName}」→ 中心变为「${R.afterChildFocus}」`);
console.log(`  拖动 40px 后释放 → 不触发展开（focus = ${R.afterDragFocus}）`);

let fail = 0;
const t = (ok, m) => { console.log(`  ${ok ? '✓' : '✗'} ${m}`); if (!ok) fail++; };
console.log('\n=== 判定 ===');
t(R.hasClick, '画布绑定了 click 事件（此前该 bug 就是这里没绑上）');
t(R.hasMove, '画布绑定了 mousemove 事件');
t(R.hasWheel, '画布绑定了 wheel 事件');
t(R.hasDown, '画布绑定了 mousedown 事件');
t(R.afterClickFocus === R.targetName, `点击导师可直接展开（${R.targetName}）`);
t(R.afterClickNodes > 1 && R.afterClickEdges > 0, `展开后有节点与连线（${R.afterClickNodes} 节点 / ${R.afterClickEdges} 边）`);
t(R.afterBlankFocus === R.targetName, '点击空白处不会误触发');
t(!R.childName || R.afterChildFocus === R.childName, `点击有学生的子节点可继续下钻（${R.childName || 'n/a'}）`);
t(R.afterDragFocus === null, '拖动后释放不被误判为点击');
console.log(fail ? `\n❌ ${fail} 项未通过` : '\n✅ 点击交互全部通过');
process.exit(fail ? 1 : 0);
