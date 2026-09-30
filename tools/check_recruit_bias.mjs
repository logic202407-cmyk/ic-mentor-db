// check_recruit_bias.mjs — 检查招生信号是否存在"整站模板"式误判
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const curated = JSON.parse(fs.readFileSync(path.join(PROC, 'curated.json'), 'utf8'));

const bySchool = {};
for (const d of curated) {
  const s = (bySchool[d.school] = bySchool[d.school] || { n: 0, rec: 0, sigs: [] });
  s.n++;
  if (d.recruit_signal_count > 0) { s.rec++ ; s.sigs.push(...d.recruit_signals.map((x) => x.snippet.slice(0, 60))); }
}
console.log('各校/单位的"在招"占比：');
for (const [k, v] of Object.entries(bySchool).sort((a, b) => b[1].rec / b[1].n - a[1].rec / a[1].n)) {
  const pct = (v.rec / v.n * 100).toFixed(0);
  console.log(`  ${String(v.rec).padStart(3)}/${String(v.n).padStart(3)} (${pct.padStart(3)}%)  ${k}`);
}

// 检查高频重复的招生语句（模板文本的特征）
console.log('\n出现次数最多的招生语句片段（Top 15，重复度高说明是模板）：');
const freq = new Map();
for (const d of curated) for (const s of d.recruit_signals) {
  const key = s.snippet.slice(0, 50);
  freq.set(key, (freq.get(key) || 0) + 1);
}
for (const [k, v] of [...freq].sort((a, b) => b[1] - a[1]).slice(0, 15)) {
  console.log(`  ×${String(v).padStart(3)}  ${k}`);
}

// 具体看中科院微电子所的招生原话
console.log('\n中科院微电子所（cas_ime）的招生原话样例：');
const ime = curated.filter((d) => d.school.includes('微电子研究所'));
console.log(`  共 ${ime.length} 人，其中标注在招 ${ime.filter((d) => d.recruit_signal_count > 0).length} 人`);
for (const d of ime.filter((x) => x.recruit_signal_count > 0).slice(0, 4)) {
  console.log(`  ${d.name_cn}:`);
  for (const s of d.recruit_signals.slice(0, 2)) console.log(`     「${s.snippet.slice(0, 100)}」`);
}
