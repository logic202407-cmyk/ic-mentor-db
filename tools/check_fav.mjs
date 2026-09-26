// check_fav.mjs — 校验收藏功能相关代码是否都在生成的 HTML 中
import fs from 'node:fs';
const h = fs.readFileSync(process.argv[2], 'utf8');
const keys = ['favOnly', 'expBtn', 'FAV_KEY', '导出收藏', 'data-fav', 'saveFav', 'exportFav', 'colspan="14"', 'icmd_fav_v1', '只看收藏'];
let bad = 0;
for (const k of keys) {
  const ok = h.includes(k);
  if (!ok) bad++;
  console.log((ok ? '  ✓ ' : '  ✗ ') + k);
}
// 括号/标签基本平衡检查
const opens = (h.match(/<tr/g) || []).length, closes = (h.match(/<\/tr>/g) || []).length;
console.log(`  tr 标签（模板中）: ${opens}/${closes}`);
console.log(bad ? `❌ 缺失 ${bad} 项` : '✅ 收藏功能代码完整');
process.exit(bad ? 1 : 0);
