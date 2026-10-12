// build_network.mjs — 构建微电子导师关系网络
//
// 关系类型与判定依据（全部基于可核实的公开论文署名，不臆测）：
//   ① 师徒 (advisor)：Q 在 ≥MIN_ADV 篇论文中担任**末位作者**，且这些论文中 P 是**第一作者**
//      —— 这是中文学术界最典型的「学生一作 + 导师通讯」模式，可核实、可复现
//   ② 合作 (collab)：P 与 Q 共同署名（不含已判为师徒的边）
//   ③ 同门 (sibling)：P1 与 P2 推断出同一位导师（由 ① 推导）
//   ④ 同机构 (same_org)：同一院系（弱关系，仅作背景）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');

const MIN_ADV = 3;        // 判定师徒所需的最少「学生一作 + 导师末位」论文数
const MIN_COLLAB = 2;     // 收录合作关系所需的最少共同署名论文数

// ── 姓名归一化 ──
const norm = (s) => String(s || '')
  .normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/[^a-z\u4e00-\u9fa5]/g, '');   // 去空格/连字符/点，只留字母与汉字

// ── 1. 建立人员索引 + 机构正则（用于同名消歧）──
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));
const people = {};          // key = school|name_cn
const nameIndex = new Map(); // 归一化英文名 -> Set(people keys)
const orgRe = new Map();     // school_key -> {include, exclude} 正则
for (const [sk, m] of Object.entries(variants)) {
  orgRe.set(sk, {
    inc: m.include ? new RegExp(m.include, 'i') : null,
    exc: m.exclude ? new RegExp(m.exclude, 'i') : null,
  });
  for (const p of m.people) {
    const key = `${m.school}|${p.name_cn}`;
    people[key] = {
      key, school: m.school, schoolKey: sk, name: p.name_cn, nameEn: p.name_en || '',
      title: p.title || '', dept: p.department || '', phd: !!p.is_phd_advisor,
      kw: (p.research_keywords || []).join('、'), hp: p.homepage || '',
    };
    for (const v of [...(p.variants || []), p.name_en].filter(Boolean)) {
      const n = norm(v);
      if (n.length < 4) continue;
      if (!nameIndex.has(n)) nameIndex.set(n, new Set());
      nameIndex.get(n).add(key);
    }
    if (p.name_en) {
      const c = norm(p.name_en);
      if (c.length >= 5) { if (!nameIndex.has(c)) nameIndex.set(c, new Set()); nameIndex.get(c).add(key); }
    }
  }
}
console.log(`人员索引: ${Object.keys(people).length} 人 | 英文名键 ${nameIndex.size} 个`);

// ── 姓名 + 机构双校验消歧（核心可靠性保障）──
// 三级判定：
//   ① 机构串存在且命中该校模式  -> 接受（high）
//   ② 机构串存在但不匹配        -> **拒绝**（这是最隐蔽的坑：姓名全库唯一也未必是同一个人，
//                                  例：复旦的"洪志良"与西电论文里的"Hong Zhiliang"同名不同人）
//   ③ 机构串缺失                -> 接受但标注 low（会议记录常缺机构串）
let okAff = 0, rejMismatch = 0, okNoAff = 0, rejAmbiguous = 0;
function resolveAuthor(cname, aff) {
  const cands = nameIndex.get(norm(cname)) || nameIndex.get(norm(cname).replace(/\s/g, ''));
  if (!cands || !cands.size) return null;
  const a = String(aff || '').trim();
  const test = (k) => {
    const r = orgRe.get(people[k].schoolKey);
    if (!r || !r.inc) return false;
    return r.inc.test(a) && !(r.exc && r.exc.test(a));
  };
  if (!a) { okNoAff++; return { key: [...cands][0], conf: 'low', multi: cands.size > 1 }; }
  const hits = [...cands].filter(test);
  if (hits.length === 1) { okAff++; return { key: hits[0], conf: 'high', multi: false }; }
  if (hits.length > 1) { rejAmbiguous++; return null; }
  // 机构串存在，但没有任何候选匹配 -> 拒绝，绝不将就
  rejMismatch++;
  return null;
}

// ── 2. 遍历全部论文，累计「共同署名」与「一作-末位」配对 ──
const collab = new Map();   // "A||B" (A<B 排序) -> {n, papers:[]}
const pairRole = new Map(); // "student||advisor" -> {n, papers:[]}
const papersByKey = {};
const seenPaper = new Set();   // DOI 去重：同一篇论文会在多个人的记录里出现，避免重复计数
let scanned = 0, matchedAuthors = 0, dupSkipped = 0;

for (const f of fs.readdirSync(PROC).filter((x) => /^enriched_.*\.json$/.test(x))) {
  const e = JSON.parse(fs.readFileSync(path.join(PROC, f), 'utf8'));
  for (const person of e.people) {
    const pkey = `${person.school}|${person.name_cn}`;
    if (!people[pkey]) continue;
    for (const pap of person.papers || []) {
      scanned++;
      const au = pap.coauthors || [];
      if (au.length < 2) continue;
      const nAuth = au.length;
      // 找出同论文中所有属于名录的作者（姓名 + 机构双校验）
      const ins = [];
      for (const c of au) {
        const r = resolveAuthor(c.name, c.aff);
        if (r) ins.push({ key: r.key, order: c.order, aff: c.aff || '', conf: r.conf });
      }
      const uniq = [...new Map(ins.map((x) => [x.key + '#' + x.order, x])).values()];
      if (!uniq.length) continue;
      matchedAuthors += uniq.length;

      // DOI 去重：同一篇论文在多人记录中重复出现，只计一次
      const dedupKey = pap.doi || `${pap.title}|${pap.year}`;
      const isDup = seenPaper.has(dedupKey);
      if (!isDup) seenPaper.add(dedupKey); else dupSkipped++;
      const meta = { doi: pap.doi, title: pap.title, year: pap.year, venue: pap.venue, tier: pap.tier, nAuth };
      if (isDup) continue;   // 重复论文不再累加边权

      // 记录该论文涉及的本人（可能一人多名录条目）
      (papersByKey[pkey] = papersByKey[pkey] || []).push({ ...meta, myOrder: pap.my_order });

      // 两两建边
      for (let i = 0; i < uniq.length; i++) {
        for (let j = i + 1; j < uniq.length; j++) {
          const a = uniq[i].key, b = uniq[j].key;
          if (a === b) continue;
          const [x, y] = a < b ? [a, b] : [b, a];
          const ck = `${x}||${y}`;
          if (!collab.has(ck)) collab.set(ck, { n: 0, papers: [] });
          const rec = collab.get(ck);
          rec.n++;
          if (rec.papers.length < 30) rec.papers.push(meta);
        }
      }
      // 「某人一作 + 另一人末位」→ 候选师徒
      const first = uniq.filter((u) => u.order === 1);
      const last = uniq.filter((u) => u.order === nAuth && nAuth >= 3);
      for (const s of first) {
        for (const t of last) {
          if (s.key === t.key) continue;
          const ak = `${s.key}||${t.key}`;
          if (!pairRole.has(ak)) pairRole.set(ak, { n: 0, papers: [] });
          const r = pairRole.get(ak);
          r.n++;
          if (r.papers.length < 20) r.papers.push({ ...meta, myOrder: 1, aff: s.aff, mentorAff: t.aff });
        }
      }
    }
  }
}
console.log(`扫描论文记录 ${scanned} 条 | 命中名录作者 ${matchedAuthors} 人次 | 重复论文跳过 ${dupSkipped} 条`);
console.log(`作者消歧: 机构匹配成功 ${okAff} | 机构缺失但接受 ${okNoAff} | 机构不匹配拒绝 ${rejMismatch} | 多候选无法判定拒绝 ${rejAmbiguous}`);
console.log(`共同署名边（去重前）: ${collab.size} | 一作-末位配对: ${pairRole.size}`);

fs.writeFileSync(path.join(PROC, '_net_collab.json'), JSON.stringify([...collab].map(([k, v]) => ({ k, ...v }))), 'utf8');
fs.writeFileSync(path.join(PROC, '_net_pair.json'), JSON.stringify([...pairRole].map(([k, v]) => ({ k, ...v }))), 'utf8');
fs.writeFileSync(path.join(PROC, '_net_people.json'), JSON.stringify(people), 'utf8');
fs.writeFileSync(path.join(PROC, '_net_papers_by_key.json'), JSON.stringify(papersByKey), 'utf8');
console.log('中间结果已落盘 _net_*.json');
