// verify_html.mjs — 校验生成的 HTML：DATA 片段可解析、无个人化词、脚本标签闭合
import fs from 'node:fs';
const files = process.argv.slice(2);
const BAD = ['你的背景', '编程负担', 'IC 科班', 'AI 重度使用者', '按你的', '适合你', '我的背景'];
for (const f of files) {
  const h = fs.readFileSync(f, 'utf8');
  // DATA 既可能是数组（列表页），也可能是对象（关系网络页）
  const m = h.match(/const DATA = (\[[\s\S]*?\]|\{[\s\S]*?\});\n/);
  let rows = -1, ok = false;
  if (m) {
    try {
      const v = JSON.parse(m[1]);
      rows = Array.isArray(v) ? v.length : (v.nodes ? Object.keys(v.nodes).length : Object.keys(v).length);
      ok = true;
    } catch (e) { ok = false; }
  }
  const hits = BAD.filter((k) => h.includes(k));
  const scriptOpen = (h.match(/<script/g) || []).length;
  const scriptClose = (h.match(/<\/script>/g) || []).length;
  const size = (h.length / 1024).toFixed(0);
  console.log(`${f.split(/[\\/]/).pop()}`);
  console.log(`   ${size} KB ｜ DATA 可解析: ${ok ? '是 (' + rows + ' 条)' : '否'} ｜ script 标签: ${scriptOpen}/${scriptClose}`);
  console.log(`   个人化词残留: ${hits.length ? hits.join(', ') : '无'}`);
}
