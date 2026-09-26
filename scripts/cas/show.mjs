// show.mjs — 打印 JSON 摘要
import fs from 'node:fs';
const [file, ...cols] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(file, 'utf8'));
for (const r of data) {
  console.log(cols.map((c) => {
    let v = r[c];
    if (Array.isArray(v)) v = v.join('/');
    if (typeof v === 'string' && v.length > 150) v = v.slice(0, 150) + '…';
    return v == null ? '-' : v;
  }).join(' | '));
}
