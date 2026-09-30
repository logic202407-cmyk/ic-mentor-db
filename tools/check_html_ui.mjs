// check_html_ui.mjs — 校验两个 HTML 的交互元素与脚本引用是否自洽
import fs from 'node:fs';

function check(file, expect) {
  const h = fs.readFileSync(file, 'utf8');
  const m = h.match(/<script>([\s\S]*?)<\/script>/);
  const js = m ? m[1] : '';
  const ids = [...new Set([...js.matchAll(/\$\('([\w-]+)'\)/g)].map((x) => x[1]))];
  const missIds = ids.filter((id) => !h.includes(`id="${id}"`));
  const ths = [...new Set([...h.matchAll(/data-k="(\w+)"/g)].map((x) => x[1]))];
  const missEl = expect.filter((id) => !h.includes(`id="${id}"`));
  const dm = js.match(/const DATA = (\[[\s\S]*?\]);\n/);
  const n = dm ? JSON.parse(dm[1]).length : 0;

  console.log(`\n=== ${file} ===`);
  console.log(`  内嵌数据           : ${n} 条`);
  console.log(`  脚本引用的 DOM id  : ${ids.length} 个 → ${missIds.length ? '✗ 缺失 ' + missIds.join(',') : '✓ 全部存在'}`);
  console.log(`  交互控件           : ${expect.map((i) => i + (h.includes(`id="${i}"`) ? '✓' : '✗')).join(' ')} → ${missEl.length ? '✗' : '✓'}`);
  console.log(`  可排序列           : ${ths.length} 个 (${ths.slice(0, 10).join(',')}${ths.length > 10 ? '…' : ''})`);
  console.log(`  render 调用        : ${(js.match(/render\(\)/g) || []).length} 次`);
  const hasNet = /fetch\s*\(|XMLHttpRequest|src="http/.test(js) || /<script src=/.test(h);
  console.log(`  离线自包含         : ${hasNet ? '✗ 存在外部请求' : '✓'}`);
  return missIds.length + missEl.length + (n ? 0 : 1);
}

let bad = 0;
bad += check('reports/导师推荐.html', ['q', 'sp', 'g', 'sc', 'ti', 'rc', 'sortSel', 'favOnly', 'expBtn']);
bad += check('reports/导师库.html', ['q', 'school', 'dir', 'tier', 'sortSel']);
console.log(bad ? `\n❌ ${bad} 项异常` : '\n✅ 两个页面结构自洽');
process.exit(bad ? 1 : 0);
