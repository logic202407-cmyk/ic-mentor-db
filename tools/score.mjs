// score.mjs — 汇总各校富化结果 → 指标计算 + 研究方向归类 + 证据强度评分
// 用法: node score.mjs
import fs from 'node:fs';
import path from 'node:path';
import { classifyPaper, DIRECTIONS, STRONG_KW } from './classify.mjs';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const CURRENT_YEAR = 2026;

// 明显不属于电子/信息/工程领域的期刊 → 判为同名污染，排除出计量口径
const OFF_FIELD = /virulence|infection|pathogen|\bdisease\b|epidemi|clinical|medicine|medical journal|surg|oncol|cancer|tumor|hepat|gastro|cardio|neurol|psychiat|nurs|dental|pharmac|toxicolog|\bfood\b|agricultur|veterinar|forest|fisher|geolog|mineral|petroleum|astronom|astrophys|cosmolog|meteorolog|atmospher|ocean|ecolog|zoolog|botan|\bplant\b|\bsoil\b|econom|finance|account|jurisprud|\blaw\b|educat|linguist|histor|philosoph|sociolog|politic|sport|tourism|hospitality|textile|leather|pulp|civil engineering|construction|transport|traffic|public health|nursing|\bcell\b|\bgene\b|genetic|genom|proteom|microbiolog|immunolog|virolog|biochem|organic chemistry|inorganic chemistry|analytical chemistry|polymer|food chemistry|journal of chemistry|energy & fuels|combustion/i;

function sat(x, k) { return 1 - Math.exp(-x / k); }   // 饱和函数，避免高产者线性碾压

const files = fs.readdirSync(PROC).filter((f) => /^enriched_.*\.json$/.test(f));
const people = [];
const FACULTY_NAMES = {};
for (const f of files) {
  const d = JSON.parse(fs.readFileSync(path.join(PROC, f), 'utf8'));
  const set = new Set();
  for (const p of d.people) for (const v of p.variants || []) set.add((v || '').toLowerCase().replace(/[^a-z\s]/g, ' ').replace(/\s+/g, ' ').trim());
  FACULTY_NAMES[d.school_key] = set;
  for (const p of d.people) people.push({ ...p, school: d.school, school_key: d.school_key });
}

const rows = [];
for (const p of people) {
  const papers = (p.papers || []).map((x) => ({ ...x, ...classifyPaper(x) }));
  // 先剔除明显的同名污染（非工科期刊）
  const offField = papers.filter((x) => OFF_FIELD.test(x.venue || ''));
  const papersInField = papers.filter((x) => !OFF_FIELD.test(x.venue || ''));
  // 只保留 IC/电子相关论文（venue 命中 tier 或方向命中非 other）
  const ic = papersInField.filter((x) => x.tier || (x.dirs.length && !(x.dirs.length === 1 && x.dirs[0] === 'other')));
  const byTier = { S: 0, A: 0, B: 0 };
  for (const x of ic) if (x.tier) byTier[x.tier]++;
  const recent3 = ic.filter((x) => (x.year || 0) >= CURRENT_YEAR - 2).length;
  const recent5 = ic.filter((x) => (x.year || 0) >= CURRENT_YEAR - 4).length;
  const citations = ic.reduce((s, x) => s + (x.cited || 0), 0);
  const firstAuthor = ic.filter((x) => x.my_order === 1).length;
  const lastAuthor = ic.filter((x) => x.n_authors > 1 && x.my_order === x.n_authors).length;

  // 方向统计：论文方向 + roster 关键词
  const dirCount = {};
  for (const x of ic) for (const dkey of x.dirs) dirCount[dkey] = (dirCount[dkey] || 0) + 1;
  const kwText = (p.research_keywords || []).join(' ');
  for (const d of DIRECTIONS) {
    if (!d.kw.test(kwText)) continue;
    let w = 2;
    if (STRONG_KW[d.key] && STRONG_KW[d.key].test(kwText)) w += 6;   // 高辨识度关键词加权
    dirCount[d.key] = (dirCount[d.key] || 0) + w;
  }
  const dirsSorted = Object.entries(dirCount).sort((a, b) => b[1] - a[1]);
  const primaryDir = dirsSorted.length ? dirsSorted[0][0] : 'other';

  const venueCount = {};
  for (const x of ic) if (x.venueKey) venueCount[x.venueKey] = (venueCount[x.venueKey] || 0) + 1;
  const topVenues = Object.entries(venueCount).sort((a, b) => b[1] - a[1]).slice(0, 6);

  // ── 署名结构：导师一作 / 学生一作 ──
  const facNames = FACULTY_NAMES[p.school_key] || new Set();
  const normN = (s) => (s || '').toLowerCase().replace(/[^a-z\s]/g, ' ').replace(/\s+/g, ' ').trim();
  const studentFirst = new Set();
  let advisorFirst = 0, studentLed = 0, counted = 0;
  for (const x of ic) {
    if (!x.coauthors || !x.coauthors.length) continue;
    counted++;
    if (x.my_order === 1) { advisorFirst++; continue; }
    const fa = x.coauthors[0];
    const faName = normN(fa.name);
    if (!faName) continue;
    const isFaculty = facNames.has(faName) || (p.variants || []).some((v) => normN(v) === faName);
    if (!isFaculty && /tsinghua|fudan|shanghai|zhejiang|nanjing|science and technology of china|shenzhen|peking|southeast|xidian|electronic science and technology|uestc/i.test(fa.aff || '')) {
      studentLed++;
      studentFirst.add(faName);
    }
  }
  const advisorFirstRatio = counted ? +(advisorFirst / counted).toFixed(3) : null;
  const studentLedRatio = counted ? +(studentLed / counted).toFixed(3) : null;

  // ── 证据强度评分（0–100）──
  const sTop = sat(byTier.S, 3) * 34;        // 顶刊顶会
  const sA = sat(byTier.A, 8) * 24;          // 一流
  const sB = sat(byTier.B, 10) * 8;          // 良好
  const sVol = sat(ic.length, 30) * 12;      // 总量
  const sCite = sat(Math.log1p(citations), 5) * 12;  // 引用（对数饱和）
  const sRecent = sat(recent3, 6) * 10;      // 近三年活跃度
  const score = +(sTop + sA + sB + sVol + sCite + sRecent).toFixed(1);

  // ── 置信度：姓名歧义风险 ──
  const nameSyll = (p.name_cn || '').length;
  const evidence = ic.length;
  let confidence = 'medium';
  if (evidence >= 8 && byTier.S + byTier.A >= 2) confidence = 'high';
  else if (evidence <= 2) confidence = 'low';
  const ambiguity = evidence >= 60 && byTier.S === 0 ? 'high' : (nameSyll <= 2 && evidence >= 40 ? 'medium' : 'low');
  // 召回风险：正高职称却几乎检索不到论文 → 极可能是英文名拼写差异导致漏检
  const recallRisk = (ic.length <= 2 && /教授|研究员|院士|杰青|讲席|特聘/.test(String(p.title || ''))) ? 'yes' : 'no';

  rows.push({
    school: p.school, school_key: p.school_key,
    name_cn: p.name_cn, title: p.title, department: p.department,
    is_phd_advisor: p.is_phd_advisor, research_keywords: p.research_keywords || [],
    homepage: p.homepage, notes: p.notes,
    primary_direction: primaryDir,
    direction_scores: Object.fromEntries(dirsSorted.slice(0, 4)),
    n_ic_papers: ic.length, n_all_papers: (p.papers || []).length, n_off_field: offField.length,
    n_related_papers: papersInField.length,
    S: byTier.S, A: byTier.A, B: byTier.B,
    recent3, recent5, citations, first_author: firstAuthor, last_author: lastAuthor,
    advisor_first_ratio: advisorFirstRatio, student_led_ratio: studentLedRatio, n_students_est: studentFirst.size,
    top_venues: topVenues, score, confidence, ambiguity, recall_risk: recallRisk,
    papers: ic.map((x) => ({ doi: x.doi, title: x.title, year: x.year, venue: x.venue, tier: x.tier, venueKey: x.venueKey, cited: x.cited, my_order: x.my_order, n_authors: x.n_authors, dirs: x.dirs })),
  });
}

rows.sort((a, b) => b.score - a.score);
fs.writeFileSync(path.join(PROC, 'mentor_db.json'), JSON.stringify(rows, null, 1));

const HDR = ['school', 'name_cn', 'title', 'department', 'primary_direction', 'score', 'S', 'A', 'B', 'n_ic_papers', 'recent3', 'citations', 'first_author', 'last_author', 'advisor_first_ratio', 'student_led_ratio', 'n_students_est', 'is_phd_advisor', 'confidence', 'top_venues', 'research_keywords', 'homepage', 'notes'];
const csv = [HDR.join(',')].concat(rows.map((r) => HDR.map((h) => {
  let v = r[h];
  if (Array.isArray(v)) v = v.join(' ');
  if (v && typeof v === 'object') v = JSON.stringify(v);
  return `"${String(v ?? '').replace(/"/g, '""')}"`;
}).join(','))).join('\n');
fs.writeFileSync(path.join(PROC, 'mentor_db.csv'), '\ufeff' + csv, 'utf8');

console.log('总人数', rows.length);
const bySchool = {};
for (const r of rows) { bySchool[r.school] = bySchool[r.school] || { n: 0, withPaper: 0, S: 0, A: 0 }; bySchool[r.school].n++; if (r.n_ic_papers) bySchool[r.school].withPaper++; bySchool[r.school].S += r.S; bySchool[r.school].A += r.A; }
console.log('分校:', JSON.stringify(bySchool, null, 1));
const byDir = {};
for (const r of rows) byDir[r.primary_direction] = (byDir[r.primary_direction] || 0) + 1;
console.log('方向分布:', JSON.stringify(byDir));
console.log('\nTop 25:');
for (const r of rows.slice(0, 25)) console.log(`  ${String(r.score).padStart(5)} | ${r.school.slice(0, 6)} | ${r.name_cn} | ${r.title} | S${r.S} A${r.A} B${r.B} | ${r.primary_direction} | 近3年${r.recent3}`);
