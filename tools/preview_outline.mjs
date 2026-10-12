// preview_outline.mjs — 把大纲视图转成纯文本，用于核对可读性
import fs from 'node:fs';
import vm from 'node:vm';
const h = fs.readFileSync('reports/导师关系网络.html', 'utf8');
let js = h.match(/<script>([\s\S]*?)<\/script>/)[1];
js += ';(function(){ __O = $("outline").innerHTML; })();';

function mkEl(id) {
  return {
    id, _html: '', textContent: '', value: '', checked: false, style: {}, dataset: {}, children: [],
    width: 1500, height: 950, clientWidth: 1500, clientHeight: 950,
    classList: { add() {}, remove() {}, toggle() { return true; }, contains() { return false; } },
    appendChild(c) { this.children.push(c); return c; }, addEventListener() {},
    getBoundingClientRect: () => ({ width: 1500, height: 950, left: 0, top: 0 }),
    querySelectorAll: () => [], querySelector: () => null,
    getContext: () => new Proxy({}, { get(_, p) { if (p === 'measureText') return () => ({ width: 24 }); return () => {}; }, set() { return true; } }),
    scrollIntoView() {}, set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
  };
}
const store = {};
const sb = {
  document: { getElementById: (id) => (store[id] = store[id] || mkEl(id)), createElement: () => mkEl('x'), querySelectorAll: (s) => (s === '.tab' ? ['outline', 'radial', 'heat'].map((v) => { const e = mkEl('t'); e.dataset = { v }; return e; }) : []), addEventListener() {} },
  window: { addEventListener() {}, devicePixelRatio: 1 },
  console, Math, JSON, Object, Array, String, Number, Set, Map, Boolean, Infinity, isFinite, isNaN, parseInt, parseFloat,
  requestAnimationFrame: () => 0, setTimeout: () => 0,
};
sb.globalThis = sb;
vm.createContext(sb);
new vm.Script(js).runInContext(sb, { timeout: 60000 });

let t = sb.__O
  .replace(/<span class="tri">▶<\/span>/g, '▸ ')
  .replace(/<span class="tick"[^>]*>▼<\/span>/g, '\u2003▼ ')
  .replace(/<span class="tick"[^>]*>▶<\/span>/g, '\u2003▶ ')
  .replace(/<span class="tick"><\/span>/g, '\u2003\u2003')
  .replace(/<span class="badge b1"[^>]*>L1<\/span>/g, ' [L1]')
  .replace(/<span class="badge b2"[^>]*>L2<\/span>/g, ' [L2]')
  .replace(/<span class="badge b3"[^>]*>L3<\/span>/g, ' [L3]')
  .replace(/<span class="badge bx">跨校<\/span>/g, ' [跨校]')
  .replace(/<span class="cnt">/g, '  —— ')
  .replace(/<div class="crossItem">/g, '\n  ')
  .replace(/<div class="mentorBlk"[^>]*>/g, '\n')
  .replace(/<div class="school">/g, '\n\n')
  .replace(/<div class="schoolHd[^"]*"[^>]*>/g, '')
  .replace(/<div class="schoolBd">/g, '')
  .replace(/<div class="row"[^>]*>/g, '\n')
  .replace(/<div class="crossList">/g, '\n【跨校师承】')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ')
  .replace(/[ \t]+/g, ' ')
  .split('\n').map((x) => x.replace(/\s+$/, '')).filter((x) => x.trim()).join('\n');

const lines = t.split('\n');
console.log(lines.slice(0, 60).join('\n'));
console.log('\n... 共 ' + lines.length + ' 行');
