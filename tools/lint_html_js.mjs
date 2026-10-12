// lint_html_js.mjs — 抽取 HTML 内嵌脚本做语法检查与基本合理性校验
import fs from 'node:fs';
import vm from 'node:vm';

const files = process.argv.slice(2);
let bad = 0;
for (const f of files) {
  const h = fs.readFileSync(f, 'utf8');
  const m = h.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { console.log(`✗ ${f}: 未找到 <script> 块`); bad++; continue; }
  const js = m[1];
  console.log(`\n=== ${f.split(/[\\/]/).pop()} ===`);
  console.log(`  脚本长度 ${(js.length / 1024).toFixed(0)} KB`);

  // 1) 语法检查
  try {
    new vm.Script(js, { filename: f });
    console.log('  ✓ JS 语法正确');
  } catch (e) {
    console.log('  ✗ JS 语法错误:', e.message.slice(0, 160));
    bad++;
    continue;
  }

  // 2) 关键函数是否存在
  const need = ['render', 'filtered', 'detail'];
  const missFn = need.filter((n) => !new RegExp(`function\\s+${n}\\s*\\(`).test(js) && !new RegExp(`const\\s+${n}\\s*=`).test(js));
  console.log(missFn.length ? `  ✗ 缺少函数: ${missFn.join(', ')}` : '  ✓ 关键函数齐全（render/filtered/detail）');

  // 3) DOM id 引用是否都在 HTML 中存在
  const ids = [...js.matchAll(/\$\('([a-zA-Z_][\w-]*)'\)/g)].map((x) => x[1]);
  const uniq = [...new Set(ids)];
  const missing = uniq.filter((id) => !new RegExp(`id="${id}"`).test(h));
  console.log(missing.length ? `  ✗ 引用了不存在的 DOM id: ${missing.join(', ')}` : `  ✓ 引用的 ${uniq.length} 个 DOM id 均存在`);

  // 4) 危险写法
  const dangers = [];
  if (/innerHTML\s*=\s*[^`'"]*\$\{/.test(js)) dangers.push('innerHTML 直接插入未转义变量');
  if (/eval\s*\(/.test(js)) dangers.push('使用了 eval');
  if (/document\.write/.test(js)) dangers.push('使用了 document.write');
  if (/fetch\s*\(|XMLHttpRequest/.test(js)) dangers.push('存在网络请求（应为离线单文件）');
  console.log(dangers.length ? `  ⚠ ${dangers.join('; ')}` : '  ✓ 无网络请求/eval/document.write（保持离线单文件）');

  // 5) 数据（DATA 可能是数组，也可能是对象）
  const dm = js.match(/const DATA = (\[[\s\S]*?\]|\{[\s\S]*?\});\n/);
  if (dm) {
    try {
      const v = JSON.parse(dm[1]);
      const n = Array.isArray(v) ? v.length : (v.nodes ? Object.keys(v.nodes).length : Object.keys(v).length);
      console.log(`  ✓ 内嵌数据可解析（${Array.isArray(v) ? '数组' : '对象'}，${n} 条/键）`);
    } catch { console.log('  ✗ 内嵌数据 JSON 解析失败'); bad++; }
  } else { console.log('  ⚠ 未找到 DATA（该页若不用内嵌数据可忽略）'); }
}
console.log(bad ? `\n❌ ${bad} 项未通过` : '\n✅ 全部通过');
process.exit(bad ? 1 : 0);
