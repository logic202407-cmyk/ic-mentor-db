// assess_periods.mjs — 评估页面里「时间段」的可抽取程度
import fs from 'node:fs';
import path from 'node:path';
const LB = 'data/raw/lab_pages';
const clean = (s) => String(s || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();

const PATS = {
  '区间(2008-2012)': /(19|20)\d{2}\s*[-–—~至]\s*(19|20)\d{2}/g,
  '区间(2008年-2012年)': /(19|20)\d{2}\s*年\s*[-–—~至]+\s*(19|20)\d{2}\s*年/g,
  '至今(2018年至今)': /(19|20)\d{2}\s*年?\s*[-–—~至]?\s*至今/g,
  '进入/就读于': /(19|20)\d{2}\s*年[^。；;]{0,12}?(进入|就读|考入|入学|加入)/g,
  '毕业于': /(19|20)\d{2}\s*年[^。；;]{0,20}?毕业/g,
  '获学位于': /(19|20)\d{2}\s*年[^。；;]{0,16}?(获|取得)[^。；;]{0,8}?(博士|硕士|学士)/g,
};
const cnt = {}; for (const k of Object.keys(PATS)) cnt[k] = 0;
let files = 0, withAny = 0;
const samples = [];
for (const f of fs.readdirSync(LB).filter((x) => x.endsWith('.txt'))) {
  let t; try { t = clean(fs.readFileSync(path.join(LB, f), 'utf8')); } catch { continue; }
  files++;
  let hit = false;
  for (const [k, re] of Object.entries(PATS)) {
    re.lastIndex = 0;
    const m = t.match(re);
    if (m) { cnt[k]++; hit = true; if (samples.length < 6 && k === '区间(2008-2012)') { const i = t.search(re); samples.push(`${f.replace('.txt', '')}: …${t.slice(Math.max(0, i - 70), i + 90)}…`); } }
  }
  if (hit) withAny++;
}
console.log(`扫描 ${files} 份页面，含任一时间段模式: ${withAny} (${(withAny / files * 100).toFixed(1)}%)\n`);
for (const [k, v] of Object.entries(cnt)) console.log(`  ${k.padEnd(22)} ${String(v).padStart(5)} 份 (${(v / files * 100).toFixed(1)}%)`);
console.log('\n区间样例:');
for (const s of samples) console.log('  ' + s);
