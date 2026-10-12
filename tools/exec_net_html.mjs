// exec_net_html.mjs — 用 DOM/Canvas 桩件真实执行页面脚本，抓运行时错误
import fs from 'node:fs';
import vm from 'node:vm';

const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
const js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

// ── 收集页面里出现的所有 id，供 getElementById 返回桩件 ──
const ids = [...new Set([...h.matchAll(/id="([\w-]+)"/g)].map((m) => m[1]))];
const calls = [];
function el(id) {
  const e = {
    id, _html: '', textContent: '', value: '', checked: true, style: {},
    dataset: {}, classList: { add() {}, remove() {}, contains: () => false },
    appendChild(c) { (this.children = this.children || []).push(c); return c; },
    addEventListener(t) { calls.push(`${id}:${t}`); },
    getBoundingClientRect: () => ({ width: 1400, height: 900, left: 0, top: 0 }),
    querySelectorAll: () => [],
    getContext: () => ctx2d,
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
    width: 1400, height: 900,
  };
  return e;
}
const store = {};
const ctxCalls = [];
const ctx2d = new Proxy({}, {
  get(_, p) {
    if (p === 'canvas') return el('cv');
    if (['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'textAlign'].includes(p)) return '';
    return (...a) => { ctxCalls.push(String(p)); if (p === 'measureText') return { width: 20 }; void a; };
  },
  set() { return true; },
});

const document = {
  getElementById: (id) => (store[id] = store[id] || el(id)),
  createElement: (t) => el('new-' + t),
  querySelectorAll: (sel) => {
    if (sel === '.tab') return [Object.assign(el('tab1'), { dataset: { v: 'lineage' } }), Object.assign(el('tab2'), { dataset: { v: 'collab' } })];
    return [];
  },
  addEventListener() {},
};
const window = { addEventListener() {}, devicePixelRatio: 1 };

const sandbox = {
  document, window, console,
  requestAnimationFrame: (f) => { void f; return 0; },
  setTimeout: (f) => { void f; return 0; },
  Math, JSON, Date, Object, Array, String, Number, Set, Map, Float32Array, isFinite, isNaN, parseInt, parseFloat,
};
sandbox.globalThis = sandbox;
let err = null;
try {
  vm.createContext(sandbox);
  new vm.Script(js, { filename: 'network-page.js' }).runInContext(sandbox, { timeout: 60000 });
} catch (e) { err = e; }

console.log('=== 脚本执行结果 ===');
if (err) { console.log('✗ 运行时错误:', err.message); console.log(err.stack?.split('\n').slice(0, 4).join('\n')); }
else console.log('✓ 脚本完整执行，无运行时错误');

console.log('\n=== 执行期间的活动 ===');
console.log('  注册的事件监听:', [...new Set(calls)].length, '个');
for (const c of [...new Set(calls)].slice(0, 16)) console.log('    ' + c);
console.log('  Canvas 绘制调用种类:', [...new Set(ctxCalls)].length, '种');
console.log('    常用:', [...new Set(ctxCalls)].filter((x) => ['beginPath', 'arc', 'fill', 'stroke', 'moveTo', 'lineTo', 'fillText', 'setTransform', 'clearRect', 'setLineDash'].includes(x)).join(', '));

// 关键 DOM 是否被写入
console.log('\n=== 关键 DOM 状态 ===');
for (const id of ['sN', 'sA', 'sC', 'sS', 'wv', 'qres']) {
  const e = store[id];
  console.log(`  #${id}: ${e ? `textContent="${e.textContent}"` : '（未访问）'}`);
}
const school = store['school'];
console.log(`  #school 下拉项: ${school?.children?.length ?? 0} 个`);

console.log(err ? '\n❌ 存在运行时错误' : '\n✅ 页面脚本可正常执行');
process.exit(err ? 1 : 0);
