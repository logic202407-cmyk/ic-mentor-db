// cv_lineage.mjs — 把页面自述的师承与库内导师匹配，构建「直接证据」师承图
//
// 证据等级（写入每条边的 basis 字段，可视化时区分）：
//   stated   —— 页面明写「导师为 XX」「师从 XX」           ← 直接证据，最高可靠
//   inferred —— 页面写「20XX 年博士毕业于 XX 大学」且 XX 大学库内唯一同方向教授 ← 强推断
//   external —— 导师不在本库（多为海外/外校），仅记录不作边
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');

const cv = JSON.parse(fs.readFileSync(path.join(PROC, 'cv_extracted.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

// ── 建索引：key(lab_pages 文件名) -> 人名录条目 ──
// lab_pages 文件名是 <school_key>_<姓名>
const byKey = {};      // schoolKey|name -> person
const cnIndex = new Map();  // 中文名 -> [keys]
const enIndex = new Map();  // 归一化英文名 -> [keys]
const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z]/g, '');
for (const [sk, m] of Object.entries(variants)) {
  for (const p of m.people) {
    const k = `${sk}|${p.name_cn}`;
    byKey[k] = { key: k, sk, school: m.school, name: p.name_cn, nameEn: p.name_en || '', title: p.title || '', dept: p.department || '' };
    if (!cnIndex.has(p.name_cn)) cnIndex.set(p.name_cn, []);
    cnIndex.get(p.name_cn).push(k);
    for (const v of [...(p.variants || []), p.name_en].filter(Boolean)) {
      const n = norm(v);
      if (n.length >= 5) { if (!enIndex.has(n)) enIndex.set(n, []); enIndex.get(n).push(k); }
    }
  }
}
console.log(`索引: ${Object.keys(byKey).length} 人 | 中文名键 ${cnIndex.size} | 英文名键 ${enIndex.size}`);

// ── 机构关键词 -> school_key（用于同名消歧）──
const INST_HINT = [
  [/清华/, 'tsinghua'], [/北京航空|北航/, 'buaa'], [/北京邮电|北邮/, 'buaa'],
  [/北京大学|北大(?!.*深圳)/, 'pku'], [/复旦/, 'fudan'], [/上海交通|上交/, 'sjtu'],
  [/浙江大学|浙大/, 'zju'], [/南京大学|南大/, 'nju'], [/中国科学技术大学|中科大|USTC/i, 'ustc'],
  [/东南大学/, 'seu'], [/西安电子|西电/, 'xidian'], [/电子科技大学|成电/, 'uestc'],
  [/哈尔滨工业|哈工大/, 'hit'], [/天津大学|天大/, 'tju'], [/华中科技|华科/, 'hust'],
  [/西安交通|西交/, 'xjtu'], [/微电子研究所|中科院微电子/, 'cas_ime'], [/半导体研究所|中科院半导体/, 'cas_semi'],
  [/上海微系统/, 'cas_simit'], [/计算技术研究所|计算所/, 'cas_ict'], [/自动化研究所/, 'cas_auto'],
  [/上海高等研究院/, 'cas_sari'],
];
const hintOf = (s) => { for (const [re, k] of INST_HINT) if (re.test(s || '')) return k; return null; };

// ── 匹配导师名 -> 库内人 ──
let nStated = 0, nExt = 0, nAmb = 0;
const edges = [];
const external = [];
for (const [fileKey, rec] of Object.entries(cv)) {
  const [sk, ...rest] = fileKey.split('_');
  const stuName = rest.join('_');
  const stuKey = `${sk}|${stuName}`;
  const stu = byKey[stuKey];
  if (!stu) continue;
  // 该人的学历机构提示（用于消歧）
  const eduText = rec.edu.map((e) => e.inst).join(' ') + ' ' + rec.postdoc.map((p) => p.inst).join(' ');

  for (const mm of rec.mentors) {
    const nm = mm.name;
    let cands = [];
    if (cnIndex.has(nm)) cands = cnIndex.get(nm);
    else { const e = enIndex.get(norm(nm)); if (e) cands = e; }
    if (!cands.length) { external.push({ stu: stuKey, mentor: nm, kind: mm.kind }); nExt++; continue; }
    cands = cands.filter((c) => c !== stuKey);
    if (!cands.length) { nExt++; continue; }
    let pick = null;
    if (cands.length === 1) pick = cands[0];
    else {
      // 多名候选：用学历机构提示消歧
      const h = hintOf(eduText);
      const hit = h ? cands.filter((c) => byKey[c].sk === h) : [];
      if (hit.length === 1) pick = hit[0];
      else { nAmb++; continue; }   // 判不出来就丢弃
    }
    edges.push({
      s: stuKey, t: pick, basis: 'stated', kind: mm.kind,
      note: `${stu.name} 页面自述「${mm.kind === 'shicong' ? '师从' : '导师为'} ${nm}」`,
    });
    nStated++;
  }
}
console.log(`\n库内师承边（页面自述）: ${nStated} 条`);
console.log(`外部导师（不在本库，仅记录）: ${nExt} 条`);
console.log(`同名无法消歧而丢弃: ${nAmb} 条`);

// ── 去重（同一对可能多次提及）──
const uniq = new Map();
for (const e of edges) {
  const k = `${e.s}||${e.t}`;
  if (!uniq.has(k)) uniq.set(k, e);
  else uniq.get(k).note += '；' + e.note;
}
const list = [...uniq.values()];
console.log(`去重后: ${list.length} 条`);

console.log('\n=== 库内师承边（全部）===');
for (const e of list.sort((a, b) => a.t.localeCompare(b.t))) {
  const S = byKey[e.s], T = byKey[e.t];
  console.log(`  ${S.name}（${S.school.replace('中国科学院', '中科院').slice(0, 10)}）← ${T.name}（${T.school.replace('中国科学院', '中科院').slice(0, 10)}）`);
}

console.log('\n=== 外部导师分布（Top 25 被提及）===');
const extCount = new Map();
for (const e of external) extCount.set(e.mentor, (extCount.get(e.mentor) || 0) + 1);
for (const [n, c] of [...extCount].sort((a, b) => b[1] - a[1]).slice(0, 25)) console.log(`  ${String(c).padStart(2)} 次  ${n}`);

fs.writeFileSync(path.join(PROC, 'cv_lineage.json'), JSON.stringify({ edges: list, external, people: byKey }, null, 1), 'utf8');
console.log('\n已导出 data/processed/cv_lineage.json');
