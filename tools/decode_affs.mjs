// decode_affs.mjs — 一次性清洗：把已入库的机构串里的 HTML 实体解码
//
// 背景：早期 enrich_crossref.mjs 直接存原始机构串，导致 6% 的记录里带
// `Xi&#x2019;an Jiaotong University` 这类实体，下游做正则匹配时会漏掉。
// 本脚本不改动论文集合，只把 coauthors[].aff 解码；不改动已解码的值。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const ENT = /&(#x[0-9a-f]+|#\d+|amp|apos|quot|lt|gt|nbsp);/gi;
function decodeEnt(s) {
  return String(s || '').replace(ENT, (m, g) => {
    if (g[0] === '#') {
      const code = g[1].toLowerCase() === 'x' ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10);
      try { return String.fromCodePoint(code); } catch { return ' '; }
    }
    return { amp: '&', apos: "'", quot: '"', lt: '<', gt: '>', nbsp: ' ' }[g.toLowerCase()] ?? ' ';
  });
}

let files = 0, recs = 0, changed = 0;
for (const f of fs.readdirSync(PROC).filter((x) => x.startsWith('enriched_') && x.endsWith('.json'))) {
  const p = path.join(PROC, f);
  const e = JSON.parse(fs.readFileSync(p, 'utf8'));
  let n = 0;
  for (const person of e.people) {
    for (const pap of person.papers || []) {
      for (const c of pap.coauthors || []) {
        recs++;
        if (c.aff && ENT.test(c.aff)) {
          ENT.lastIndex = 0;
          c.aff = decodeEnt(c.aff);
          changed++; n++;
        }
        ENT.lastIndex = 0;
      }
    }
  }
  if (n) { fs.writeFileSync(p, JSON.stringify(e, null, 1), 'utf8'); files++; console.log(`  ${f}: 解码 ${n} 条`); }
}
console.log(`\n扫描 ${recs} 条作者记录，解码 ${changed} 条（涉及 ${files} 个文件）`);
