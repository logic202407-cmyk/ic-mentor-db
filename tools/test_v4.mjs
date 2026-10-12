// test_v4.mjs — 真实执行 v4 页面脚本，检查三个视图是否都正确构建
// 关键：脚本内的 const 不会挂到 global，探针必须**内联注入到脚本作用域**
import fs from 'node:fs';
import vm from 'node:vm';

const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];

js += `
;(function(){
  try{
    const out = $('outline').innerHTML || '';
    __R = {
      outline: {
        len: out.length,
        schools: (out.match(/class="school"/g) || []).length,
        rows: (out.match(/class="row"/g) || []).length,
        badges: (out.match(/class="badge b[123]"/g) || []).length,
        crossBadges: (out.match(/class="badge bx"/g) || []).length,
        crossItems: (out.match(/class="crossItem"/g) || []).length,
        sA: String($('sA').textContent), sX: String($('sX').textContent),
        sS: String($('sS').textContent), sC: String($('sC').textContent)
      }
    };
    let bestK = null, bestN = -1;
    for (const k of Object.keys(studentsOf)) { const n = studentsOf[k].length; if (n > bestN) { bestN = n; bestK = k; } }
    view = 'radial';
    buildRadial(bestK); renderRad();
    __R.radial = { center: NAME(bestK), n: Object.keys(rPos).length,
      kinds: Object.values(rPos).reduce(function(a,p){a[p.kind]=(a[p.kind]||0)+1;return a;},{}),
      hd: String($('radHd').innerHTML || '').replace(/<[^>]+>/g,' ').trim().slice(0,110) };
    const nb = Object.keys(rPos).find(function(k){return k !== bestK;});
    buildRadial(nb); renderRad();
    __R.radial2 = { center: NAME(nb), n: Object.keys(rPos).length };
    view = 'heat'; buildHeat();
    const hh = $('heatWrap').innerHTML || '';
    __R.heat = { cells: (hh.match(/data-i=/g)||[]).length, len: hh.length };
  }catch(e){ __R = { err: e.message, stack: (e.stack||'').split('\\n')[1] }; }
})();
`;

function mkEl(id) {
  return {
    id, _html: '', textContent: '', value: '', checked: false, style: {}, dataset: {},
    children: [], width: 1500, height: 950, clientWidth: 1500, clientHeight: 950,
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); }, toggle(c, f) { if (f === undefined) f = !this._s.has(c); f ? this._s.add(c) : this._s.delete(c); return f; }, contains(c) { return this._s.has(c); } },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (this._ev = this._ev || {})[t] = fn; },
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    querySelectorAll: () => [], querySelector: () => null,
    getContext: () => ctx2d, scrollIntoView() {},
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
  };
}
const ctx2d = new Proxy({}, { get(_, p) { if (p === 'canvas') return { width: 1500, height: 950 }; if (p === 'measureText') return () => ({ width: 24 }); if (['font', 'fillStyle', 'strokeStyle', 'lineWidth', 'textAlign', 'textBaseline'].includes(p)) return ''; return () => {}; }, set() { return true; } });
const store = {};
const sb = {
  document: {
    getElementById: (id) => (store[id] = store[id] || mkEl(id)),
    createElement: (t) => mkEl('new-' + t),
    querySelectorAll: (sel) => (sel === '.tab' ? ['outline', 'radial', 'heat'].map((v, i) => { const e = mkEl('tab' + i); e.dataset = { v }; return e; }) : []),
    addEventListener() {},
  },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Boolean, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
sb.globalThis = sb;
vm.createContext(sb);
let err = null;
const t0 = Date.now();
try { new vm.Script(js, { filename: 'p.js' }).runInContext(sb, { timeout: 120000 }); } catch (e) { err = e; }
const ms = Date.now() - t0;

console.log('=== 执行 ===');
if (err) { console.log('✗ 运行时错误:', err.message, '\n  ', (err.stack || '').split('\n')[1]); process.exit(1); }
const R = sb.__R;
if (R.err) { console.log('✗ 探针错误:', R.err, R.stack || ''); process.exit(1); }
console.log('✓ 脚本执行无错，耗时', ms, 'ms');

const O = R.outline;
console.log('\n=== 视图1 师承大纲 ===');
console.log(`  生成 HTML ${(O.len / 1024).toFixed(1)} KB`);
console.log(`  院校分组 ${O.schools} 个 ｜ 师承行 ${O.rows} 行`);
console.log(`  证据徽标 L1/L2/L3 共 ${O.badges} 个 ｜ 跨校徽标 ${O.crossBadges} 个 ｜ 跨校清单 ${O.crossItems} 条`);
console.log(`  统计栏：师承 ${O.sA} ｜ 跨校 ${O.sX} ｜ 院校 ${O.sS} ｜ 合作 ${O.sC}`);

console.log('\n=== 视图2 放射聚焦 ===');
console.log(`  中心「${R.radial.center}」，共 ${R.radial.n} 个节点`);
console.log(`  节点构成：${JSON.stringify(R.radial.kinds)}`);
console.log(`  顶部：${R.radial.hd}`);
console.log(`  点击邻居后重绘为「${R.radial2.center}」，${R.radial2.n} 个节点`);

console.log('\n=== 视图3 合作热力图 ===');
console.log(`  矩阵 ${Math.sqrt(R.heat.cells) | 0} × ${Math.sqrt(R.heat.cells) | 0}，共 ${R.heat.cells} 格`);

let fail = 0;
const t = (ok, m) => { console.log(`  ${ok ? '✓' : '✗'} ${m}`); if (!ok) fail++; };
console.log('\n=== 判定 ===');
t(O.schools >= 15, `院校分组 ≥15（实际 ${O.schools}）`);
t(O.rows >= 300, `师承行 ≥300，覆盖全部 431 人（实际 ${O.rows}）`);
t(O.crossItems === 8, `跨校清单 =8 条（实际 ${O.crossItems}）`);
t(O.badges > 200, `证据徽标 >200（实际 ${O.badges}）`);
t(O.sA === '293' && O.sX === '8', `统计数字正确（师承 ${O.sA} / 跨校 ${O.sX}）`);
t(R.radial.n >= 5 && R.radial.n <= 90, `放射节点 5-90 个，不拥挤（实际 ${R.radial.n}）`);
t(R.radial.n > 0 && R.radial2.n > 0, `点击邻居可重绘（${R.radial.n} → ${R.radial2.n}）`);
t(R.heat.cells === 484, `热力图 22×22=484 格（实际 ${R.heat.cells}）`);
t(ms < 8000, `首屏耗时 <8s（实际 ${ms}ms）`);
console.log(fail ? `\n❌ ${fail} 项未通过` : '\n✅ 三视图全部通过');
process.exit(fail ? 1 : 0);
