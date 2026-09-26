# -*- coding: utf-8 -*-
"""patch_ent.py — 给补检脚本加上 Crossref 机构串的 HTML 实体解码"""
import io
import re
import os

HELPER = '''
// Crossref 机构串含 HTML 实体（如 Xi&#x2019;an Jiaotong University），需先解码再匹配
const ENT2 = /&(#x[0-9a-f]+|#\\d+|amp|apos|quot|lt|gt|nbsp);/gi;
function decodeEnt(s) {
  return String(s || '').replace(ENT2, (m, g) => {
    if (g[0] === '#') {
      const code = g[1].toLowerCase() === 'x' ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10);
      try { return String.fromCodePoint(code); } catch { return ' '; }
    }
    return { amp: '&', apos: "'", quot: '"', lt: '<', gt: '>', nbsp: ' ' }[g.toLowerCase()] ?? ' ';
  });
}
const affText = (a) => (a.affiliation || []).map((x) => decodeEnt(x.name || '')).join(' | ');
'''

for f in ['reenrich_low.mjs', 'reenrich_topic.mjs']:
    p = os.path.join(r'E:\ytm\mentor-db\tools', f)
    s = io.open(p, encoding='utf-8').read()
    if 'decodeEnt' in s:
        print('已含解码，跳过:', f)
        continue
    s = s.replace(
        'const sleep = (ms) => new Promise((r) => setTimeout(r, ms));',
        'const sleep = (ms) => new Promise((r) => setTimeout(r, ms));\n' + HELPER,
        1,
    )
    s = re.sub(
        r"const aff = \(a\.affiliation \|\| \[\]\)\.map\(\(x\) => x\.name \|\| ''\)\.join\(' \| '\);",
        "const aff = affText(a);", s)
    s = re.sub(
        r"\(a\.affiliation \|\| \[\]\)\.map\(\(x\) => x\.name \|\| ''\)\.join\(' \| '\)",
        "affText(a)", s)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
    print('已打补丁:', f)
