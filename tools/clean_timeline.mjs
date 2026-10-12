// clean_timeline.mjs — 时间线清洗与体检，输出可用的「驻留区间」
//
// 清洗项：
//   ① 机构名去掉动词/介词前缀（他就职于、前往、于、在、加入…）与后缀噪声
//   ② 同机构的相邻/重叠区间合并为一段（避免同一对关系被重复计算）
//   ③ 剔除不可能区间（早于 1955、晚于当前、跨度>12 年、含版权字样）
//   ④ 标记可疑项（区间起点早于当事人本科入学年龄推算的出生年等）供人工复核
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = JSON.parse(fs.readFileSync(path.join(PROC, 'timeline.json'), 'utf8'));

const CUR = 2026;

// ── ① 机构名清洗 ──
const LEAD_VERB = /^(?:他|她|其|本人)?(?:就职于|任职于|工作于|任教于|前往|加入|来到了?|进入|毕业于|毕业|就读于|受聘于|受聘|攻读|获得|获|取得|得|在|于|到|赴|从)+/;
const TRAIL = /(?:从事|开展|工作|研究|任职|任教|攻读|获得|获|担任|任|期间|学习|深造|做博士后|博士后|访问学者|联合培养|的|并)+$/;
// 二级单位（学院/系/实验室）单独出现时，无法定位到学校，标记待补全
const SUBUNIT = /^(?:[\u4e00-\u9fa5]{2,12})?(?:学院|系|实验室|研究院|研究所|中心)$/;
function cleanInst(s) {
  let x = String(s || '').trim();
  // HTML 实体与残留标记
  x = x.replace(/&nbsp;?|&amp;|&#\d+;|&[a-z]+;/gi, ' ');
  // 去掉夹带的年份与「至今/Present」
  x = x.replace(/(?:19|20)\d{2}\s*年?/g, ' ').replace(/[-–—~至]?\s*(?:至今|Present|present)\b/g, ' ');
  x = x.replace(/^\s*[-–—~]\s*/, '');
  for (let i = 0; i < 4; i++) { const y = x.replace(LEAD_VERB, '').trim(); if (y === x) break; x = y; }
  for (let i = 0; i < 4; i++) { const y = x.replace(TRAIL, '').trim(); if (y === x) break; x = y; }
  x = x.replace(/[（(].*?[)）]/g, '').replace(/[|｜].*$/, '').replace(/[，,。；;、\s]+/g, '').trim();
  // 英文校名恢复词间空格（UniversitéParis-Saclay -> Université Paris-Saclay）
  if (/^[A-Za-zÀ-ÿ.\-&' ]+$/.test(x) && !/ /.test(x) && x.length > 14) {
    x = x.replace(/([a-zà-ÿ])([A-ZÀ-Ý])/g, '$1 $2');
  }
  return x;
}
const BAD_INST = /^(?:大学|学院|研究所|研究院|实验室|中心|公司|企业|单位|学校|博士后|博士|硕士|学士|本科|研究生|工作|学习|研究|物理学院|信息学院|计算机系|电子系)$/;
// 机构名里不该出现的字（出现即说明抽取时把句子片段带进来了）
const INST_DIRTY = /(?:毕业于|获得|取得|攻读|学位|期间|从事|方向|先后|分别|年|月)/;

// ── ①b 二级学院 -> 所属大学：只在**紧邻**处找（校名必须紧跟在院系名之前），
//      不用全文词频——否则会贴错（如把「物理学院」贴成页面里出现最多的那所大学）
const UNIV = /([\u4e00-\u9fa5]{2,16}(?:大学|理工学院))/g;
function resolveSubunit(inst, fullText) {
  if (!SUBUNIT.test(inst)) return inst;
  if (FOREIGN_OR_FULL.test(inst)) return inst;
  if (inst.length > 12) return inst;
  const t = String(fullText || '');
  // 紧邻：大学名 + 可选连接词 + 院系名（中间最多 6 字）
  const re = new RegExp(`([\\u4e00-\\u9fa5]{2,16}(?:大学|理工学院))[\\u4e00-\\u9fa5]{0,6}?${inst.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`);
  const m = t.match(re);
  if (!m) return inst;                              // 找不到紧邻的校名 -> 不回填（后续会被丢弃）
  const merged = `${m[1]}${inst}`;
  if (hasTwoOrgs(merged)) return inst;
  return merged;
}
// 合并后含两个机构标识 -> 无效
function hasTwoOrgs(s) {
  const marks = s.match(/大学|学院|研究院|研究所|实验室|中心/g) || [];
  const univs = s.match(/大学/g) || [];
  if (univs.length > 1) return true;
  return marks.length > 2;
}

// 「裸二级学院」：只有院系名、既无大学也无国别标识，无法定位到具体学校 → 丢弃
const FOREIGN_OR_FULL = /大学|Universit|Institute|College|School|Academy|Laborator|瑞士|美国|英国|德国|法国|日本|韩国|新加坡|加拿大|澳大利亚|荷兰|瑞典|比利时|意大利|西班牙|国立|联邦|理工|科技|师范|医科|工业|交通|农业|财经|政法/;
function isBareSubunit(inst) {
  return SUBUNIT.test(inst) && !FOREIGN_OR_FULL.test(inst) && inst.length <= 12;
}

// ── ①d 中英文校名归一（避免同名机构被当成两处）──
const EN2CN = [
  [/Tsinghua\s*University/i, '清华大学'], [/Peking\s*University/i, '北京大学'],
  [/Harvard\s*University/i, '哈佛大学'], [/Stanford\s*University/i, '斯坦福大学'],
  [/University\s*of\s*Texas[^,;]*/i, '德克萨斯大学奥斯汀分校'],
  [/Massachusetts\s*Institute\s*of\s*Technology|MIT/i, '麻省理工学院'],
  [/University\s*of\s*California[^,;]*(Berkeley)?/i, '加州大学伯克利分校'],
  [/ETH\s*Zurich|Swiss\s*Federal\s*Institute\s*of\s*Technology/i, '苏黎世联邦理工学院'],
  [/EPFL|Ecole\s*Polytechnique/i, '洛桑联邦理工学院'],
  [/Delft\s*University/i, '代尔夫特理工大学'], [/KU\s*Leuven/i, '鲁汶大学'],
  [/Purdue\s*University/i, '普渡大学'], [/Nanyang\s*Technological/i, '南洋理工大学'],
  [/National\s*University\s*of\s*Singapore/i, '新加坡国立大学'],
  [/University\s*of\s*Cambridge/i, '剑桥大学'], [/University\s*of\s*Oxford/i, '牛津大学'],
  [/Technical\s*University\s*of\s*Munich|TU\s*Munich/i, '慕尼黑工业大学'],
  [/University\s*of\s*Maryland/i, '马里兰大学'], [/Imperial\s*College/i, '帝国理工学院'],
];
const unify = (s) => {
  let x = String(s || '');
  for (const [re, v] of EN2CN) if (re.test(x)) return v;
  return x.replace(/([A-Za-z])(?=[\u4e00-\u9fa5])/g, '$1 ').replace(/\s+/g, ' ').trim();
};

// ── ①c 单点（只有毕业年）按学位时长反推驻留区间，并标注 inferred ──
const DEG_SPAN = { 博士: 5, 硕士: 3, 学士: 4 };
function inferSpan(e) {
  if (e.y2 > e.y1) return e;                        // 已有区间
  const m = String(e.rawText || '').match(/(博士|硕士|学士|本科)/);
  const span = m ? (DEG_SPAN[m[1]] || 4) : 4;
  return { ...e, y1: Math.max(1955, e.y1 - span + 1), y2: e.y1, inferred: true };
}

// ── ② 合并同机构的相邻/重叠区间 ──
function mergeRanges(list, gap = 1) {
  const byInst = {};
  for (const e of list) (byInst[e.inst] = byInst[e.inst] || []).push(e);
  const out = [];
  for (const [inst, arr] of Object.entries(byInst)) {
    arr.sort((a, b) => a.y1 - b.y1);
    let cur = null;
    for (const e of arr) {
      if (!cur) { cur = { ...e }; continue; }
      if (e.y1 <= cur.y2 + gap) { cur.y2 = Math.max(cur.y2, e.y2); cur.kinds = [...new Set([...(cur.kinds || [cur.kind]), e.kind])]; }
      else { out.push(cur); cur = { ...e }; }
    }
    if (cur) out.push(cur);
  }
  return out.sort((a, b) => a.y1 - b.y1);
}

const cleaned = {};
const stats = { total: 0, kept: 0, dropped: 0, merged: 0, people: 0, inferred: 0, subunit: 0 };
const dropReasons = {};
for (const [k, arr] of Object.entries(RAW)) {
  stats.people++;
  // 页面全文（用于二级学院回填大学名）
  const [sk, ...rest] = k.split('_');
  let fullText = '';
  try { fullText = fs.readFileSync(path.join(REPO, 'data', 'raw', 'lab_pages', `${k}.txt`), 'utf8'); } catch { fullText = ''; }
  void sk; void rest;
  const stage = [];
  for (const e of arr) {
    stats.total++;
    let inst = cleanInst(e.inst);
    inst = resolveSubunit(inst, fullText);
    inst = unify(inst);
    if (inst !== cleanInst(e.inst)) stats.subunit++;
    if (!inst || inst.length < 2 || BAD_INST.test(inst) || INST_DIRTY.test(inst)) { stats.dropped++; dropReasons['机构名无效'] = (dropReasons['机构名无效'] || 0) + 1; continue; }
    if (isBareSubunit(inst)) { stats.dropped++; dropReasons['二级学院无大学名'] = (dropReasons['二级学院无大学名'] || 0) + 1; continue; }
    // 区间合理性：教育经历通常 ≤12 年；工作经历可以很长（长期任教），上限放到 45 年
    const maxSpan = e.kind === 'work' ? 45 : 12;
    if (e.y1 < 1955 || e.y2 > CUR + 1 || e.y2 < e.y1 || e.y2 - e.y1 > maxSpan) { stats.dropped++; dropReasons['区间不合理'] = (dropReasons['区间不合理'] || 0) + 1; continue; }
    if (/版权|ICP|Copyright|地址|邮编/.test(inst)) { stats.dropped++; dropReasons['页脚噪声'] = (dropReasons['页脚噪声'] || 0) + 1; continue; }
    const e2 = inferSpan({ ...e, inst, rawText: e.raw });
    if (e2.inferred) stats.inferred++;
    stage.push({ inst, y1: e2.y1, y2: e2.y2, kind: e.kind, inferred: !!e2.inferred });
  }
  const merged = mergeRanges(stage);
  stats.merged += Math.max(0, stage.length - merged.length);
  if (merged.length) { cleaned[k] = merged; stats.kept++; }
}

console.log('═══ 时间线清洗结果 ═══');
console.log(`  处理 ${stats.people} 人 / ${stats.total} 条原始区间`);
console.log(`  保留 ${stats.kept} 人，剔除 ${stats.dropped} 条，合并冗余 ${stats.merged} 条`);
console.log(`  其中 单点按学位时长反推区间 ${stats.inferred} 条 ｜ 二级学院回填大学名 ${stats.subunit} 条`);
console.log('  剔除原因:', JSON.stringify(dropReasons));
const tot = Object.values(cleaned).reduce((a, b) => a + b.length, 0);
console.log(`  清洗后区间 ${tot} 条，人均 ${(tot / Math.max(stats.kept, 1)).toFixed(1)} 条`);

fs.writeFileSync(path.join(PROC, 'timeline_clean.json'), JSON.stringify(cleaned, null, 1), 'utf8');

console.log('\n═══ 清洗前后对比（6 人）═══');
let n = 0;
for (const k of Object.keys(cleaned)) {
  if (n++ >= 6) break;
  console.log(`  ${k}`);
  console.log(`    前: ${(RAW[k] || []).map((e) => `${e.y1}-${e.y2} ${e.inst}`).join(' ｜ ').slice(0, 150)}`);
  console.log(`    后: ${cleaned[k].map((e) => `${e.y1}-${e.y2} ${e.inst}`).join(' ｜ ').slice(0, 150)}`);
}

// ── 体检：区间长度分布 ──
const lens = {};
for (const arr of Object.values(cleaned)) for (const e of arr) { const L = e.y2 - e.y1 + 1; const b = L <= 2 ? '1-2年' : L <= 4 ? '3-4年' : L <= 7 ? '5-7年' : '8年+'; lens[b] = (lens[b] || 0) + 1; }
console.log('\n区间长度分布:', JSON.stringify(lens));
const insts = {};
for (const arr of Object.values(cleaned)) for (const e of arr) insts[e.inst] = (insts[e.inst] || 0) + 1;
console.log('机构种类:', Object.keys(insts).length);
console.log('出现最多的机构:', Object.entries(insts).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, v]) => `${k}(${v})`).join('、'));
