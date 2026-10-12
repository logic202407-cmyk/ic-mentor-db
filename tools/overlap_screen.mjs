// overlap_screen.mjs — 时间-机构重叠筛查（v2，使用清洗后的时间线）
//
// 用户方法论：
//   ① 从经历取时间段（哪几年在哪个机构）
//   ② 筛该时间段内发表的论文
//   ③ 找论文里的共同作者
//   ④ 判断两人时间段是否重叠（同期同机构）
//   ⑤ 有重叠 => 列为重点对象详查
//
// 本版修正：
//   · 使用 timeline_clean.json（机构名已清洗、同机构区间已合并）
//   · 共著篇数不再受 30 条截断影响（改用原始计数）
//   · 增加"署名角色"分析：重叠期内一方是否稳定为一作、另一方稳定为末位
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const timeline = JSON.parse(fs.readFileSync(path.join(PROC, 'timeline_clean.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

// ── fileKey(buaa_李赛) -> 库内 key(北京航空航天大学|李赛) ──
const fk2pk = {};
for (const [sk, m] of Object.entries(variants)) {
  for (const p of m.people) fk2pk[`${sk}_${p.name_cn}`] = `${m.school}|${p.name_cn}`;
}
// ── 全部论文（含共同作者），用于按时间段筛选 ──
const paperIndex = {};   // pk -> [{year, doi, title, venue, myOrder, nAuth, coauthorKeys:Set}]
const nameIdx = new Map();
for (const [sk, m] of Object.entries(variants)) {
  for (const p of m.people) {
    const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z]/g, '');
    for (const v of [...(p.variants || []), p.name_en].filter(Boolean)) {
      const n = norm(v);
      if (n.length < 4) continue;
      if (!nameIdx.has(n)) nameIdx.set(n, new Set());
      nameIdx.get(n).add(`${m.school}|${p.name_cn}`);
    }
  }
}
console.log(`人员索引 ${fk2pk ? Object.keys(fk2pk).length : 0} | 姓名键 ${nameIdx.size}`);

// 读 enriched 拿共同作者（含机构，用于校验）
const orgRe = new Map();
for (const [sk, m] of Object.entries(variants)) orgRe.set(sk, { inc: m.include ? new RegExp(m.include, 'i') : null, exc: m.exclude ? new RegExp(m.exclude, 'i') : null, school: m.school });
const school2sk = {};
for (const [sk, m] of Object.entries(variants)) school2sk[m.school] = sk;

// ── DOI -> venue 分层（tier 只在 mentor_ranked.json 里，enriched 没有，需回填）──
const doiTier = new Map();
try {
  const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
  for (const d of ranked) for (const p of d.papers || []) if (p.doi && p.tier) doiTier.set(p.doi, p.tier);
} catch { /* 忽略 */ }
console.log(`DOI->分层 映射 ${doiTier.size} 条`);

let scanned = 0, edges = 0;
const pairAgg = new Map();   // "A||B" -> {papers:[{year, firstSide, lastSide}]}
const seenDoi = new Set();
for (const f of fs.readdirSync(PROC).filter((x) => /^enriched_.*\.json$/.test(x))) {
  const e = JSON.parse(fs.readFileSync(path.join(PROC, f), 'utf8'));
  for (const person of e.people) {
    const pkey = `${person.school}|${person.name_cn}`;
    if (!paperIndex[pkey]) paperIndex[pkey] = [];
    for (const pap of person.papers || []) {
      scanned++;
      const key = `${pkey}|${pap.doi}`;
      if (seenDoi.has(key)) continue;
      seenDoi.add(key);
      const au = pap.coauthors || [];
      // 识别同论文中属于名录的其他作者（姓名+机构双校验）
      const others = [];
      for (const c of au) {
        const n = String(c.name || '').toLowerCase().replace(/[^a-z]/g, '');
        let cands = nameIdx.get(n);
        if (!cands) continue;
        if (cands.size > 1) {
          const aff = String(c.aff || '');
          if (!aff.trim()) continue;
          const hits = [...cands].filter((k) => { const r = orgRe.get(school2sk[k.split('|')[0]]); return r?.inc && r.inc.test(aff) && !(r.exc && r.exc.test(aff)); });
          if (hits.length !== 1) continue;
          cands = new Set(hits);
        }
        for (const k of cands) if (k !== pkey) others.push({ key: k, order: c.order });
      }
      if (!others.length) continue;
      const rec = { year: pap.year, doi: pap.doi, title: pap.title, venue: pap.venue, tier: doiTier.get(pap.doi) || null, myOrder: pap.my_order, nAuth: au.length, others };
      paperIndex[pkey].push(rec);
      edges += others.length;
    }
  }
}
console.log(`扫描论文记录 ${scanned} | 建立人员论文索引 ${Object.keys(paperIndex).length} 人 | 跨人名录作者引用 ${edges} 次`);

// ── 构建 pair 聚合：两人共同署名的论文 + 各自署名位置 ──
for (const [pk, arr] of Object.entries(paperIndex)) {
  for (const p of arr) {
    for (const o of p.others) {
      const [x, y] = pk < o.key ? [pk, o.key] : [o.key, pk];
      const k = `${x}||${y}`;
      if (!pairAgg.has(k)) pairAgg.set(k, []);
      pairAgg.get(k).push({ year: p.year, doi: p.doi, title: p.title, venue: p.venue, tier: p.tier, nAuth: p.nAuth, orders: { [pk]: p.myOrder, [o.key]: o.order } });
    }
  }
}
console.log(`两两共同署名配对: ${pairAgg.size}`);

// ── 职称层级（用于师徒判定的资历差校验）──
const RANK = (t) => {
  const s = String(t || '');
  if (/院士/.test(s)) return 6;
  if (/(教授|研究员)/.test(s) && !/副/.test(s) && !/助理/.test(s)) return /特聘|长聘|讲席|杰出|二级/.test(s) ? 5 : 4;
  if (/副教授|副研究员|高级工程师/.test(s)) return 3;
  if (/助理教授|助理研究员|讲师|博士后|工程师/.test(s)) return 2;
  return 1;
};
const titleOf = (pk) => {
  const [sch, nm] = pk.split('|');
  const sk = school2sk[sch];
  const p = sk ? variants[sk].people.find((x) => x.name_cn === nm) : null;
  return p?.title || '';
};

// ── 时间-机构重叠 ──
const perPerson = {};
for (const [fk, arr] of Object.entries(timeline)) {
  const pk = fk2pk[fk];
  if (pk) perPerson[pk] = arr;
}
const byInst = {};
for (const [pk, arr] of Object.entries(perPerson)) for (const e of arr) (byInst[e.inst] = byInst[e.inst] || []).push({ pk, ...e });

const out = [];
for (const [inst, arr] of Object.entries(byInst)) {
  if (arr.length < 2) continue;
  for (let i = 0; i < arr.length; i++) {
    for (let j = i + 1; j < arr.length; j++) {
      const a = arr[i], b = arr[j];
      if (a.pk === b.pk) continue;
      const y1 = Math.max(a.y1, b.y1), y2 = Math.min(a.y2, b.y2);
      if (y2 < y1) continue;
      const [x, y] = a.pk < b.pk ? [a.pk, b.pk] : [b.pk, a.pk];
      const k = `${x}||${y}`;
      const papers = pairAgg.get(k);
      if (!papers || !papers.length) continue;        // 同期同机构但从未共同署名 -> 不作关系
      const inWin = papers.filter((p) => p.year >= y1 && p.year <= y2);
      if (!inWin.length) continue;
      // 署名角色统计（1=一作，nAuth=末位）
      let xFirst = 0, xLast = 0, yFirst = 0, yLast = 0;
      for (const p of inWin) {
        const ox = p.orders[x], oy = p.orders[y];
        if (ox === 1) xFirst++; if (ox === p.nAuth && p.nAuth >= 3) xLast++;
        if (oy === 1) yFirst++; if (oy === p.nAuth && p.nAuth >= 3) yLast++;
      }
      // 关系判定：署名模式 + **资历差**
      // 只看署名会犯错——两位副教授长期合作也会出现「一方一作、另一方末位」。
      // 因此要求"导师"的职称层级严格高于"学生"。
      const xStuP = xFirst >= 2 && yLast >= 2 && yFirst === 0;
      const yStuP = yFirst >= 2 && xLast >= 2 && xFirst === 0;
      const rankX = RANK(titleOf(x)), rankY = RANK(titleOf(y));
      let type = '同组/同事', reason = '';
      if (xStuP && rankY > rankX) { type = '师徒（X为学生）'; reason = `${x.split('|')[1]} 一作 ${xFirst} 篇、${y.split('|')[1]} 末位 ${yLast} 篇；且 ${y.split('|')[1]} 职称层级更高`; }
      else if (yStuP && rankX > rankY) { type = '师徒（Y为学生）'; reason = `${y.split('|')[1]} 一作 ${yFirst} 篇、${x.split('|')[1]} 末位 ${xLast} 篇；且 ${x.split('|')[1]} 职称层级更高`; }
      else if (xStuP || yStuP) { type = '疑似师徒（资历相当）'; reason = '署名模式像师徒，但两人职称层级相同，可能是同事合作，需人工核'; }
      else if (xFirst + yFirst >= 2) { type = '共同指导/合作'; reason = '双方均有一作论文'; }
      out.push({
        a: x, b: y, inst, y1, y2, years: y2 - y1 + 1,
        nPapers: papers.length, nInWindow: inWin.length,
        xFirst, xLast, yFirst, yLast, type, reason,
        tierS: inWin.filter((p) => p.tier === 'S').length,
        tierA: inWin.filter((p) => p.tier === 'A').length,
        samples: inWin.slice(0, 3).map((p) => `${p.year} ${(p.venue || '').slice(0, 26)}: ${(p.title || '').slice(0, 56)}`),
      });
    }
  }
}
console.log(`重叠且同期有共同署名: ${out.length} 对`);
const tc = {};
for (const r of out) tc[r.type] = (tc[r.type] || 0) + 1;
console.log('分类:', JSON.stringify(tc));

out.sort((p, q) => (q.nInWindow * 3 + q.tierS * 5 + q.tierA * 2) - (p.nInWindow * 3 + p.tierS * 5 + p.tierA * 2));
console.log('\n══════ 重点筛查对象 Top 35 ══════');
console.log('评分  甲                       乙                       机构          重叠期      同期共著 S/A  关系类型');
for (const r of out.slice(0, 35)) {
  const sc = r.nInWindow * 3 + r.tierS * 5 + r.tierA * 2;
  const nm = (k) => `${k.split('|')[1]}(${k.split('|')[0].replace('中国科学院', '中科院').slice(0, 5)})`;
  console.log(`${String(sc).padStart(4)}  ${nm(r.a).padEnd(24)} ${nm(r.b).padEnd(24)} ${r.inst.slice(0, 12).padEnd(14)} ${String(r.y1 + '-' + r.y2).padEnd(11)} ${String(r.nInWindow).padStart(6)} ${r.tierS}/${r.tierA}  ${r.type}`);
}
fs.writeFileSync(path.join(PROC, 'overlap_screen.json'), JSON.stringify({ perPerson, results: out }, null, 1), 'utf8');
console.log('\n已导出 data/processed/overlap_screen.json');

console.log('\n══════ 师徒类候选（全部）══════');
for (const r of out.filter((x) => x.type.startsWith('师徒'))) {
  console.log(`  ${r.a.split('|')[1]} × ${r.b.split('|')[1]} | ${r.inst} ${r.y1}-${r.y2} | 同期共著 ${r.nInWindow} | ${r.reason}`);
}
