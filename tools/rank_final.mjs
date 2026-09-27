// rank_final.mjs — 融合文献计量 + skill 分析（异常规则/诚信核查/署名伦理）的最终详细排名
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const PROC = path.join(REPO, 'data', 'processed');
const db = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_db.json'), 'utf8'));
const heurPath = path.join(PROC, 'heuristics_all.json');
const integPath = path.join(PROC, 'integrity_check.json');
const heur = fs.existsSync(heurPath) ? JSON.parse(fs.readFileSync(heurPath, 'utf8')) : [];
const integ = fs.existsSync(integPath) ? JSON.parse(fs.readFileSync(integPath, 'utf8')) : [];

const heurMap = new Map(heur.map((h) => [`${h.school}|${h.name_cn}`, h]));
const integByPerson = new Map();
for (const r of integ) {
  const k = `${r.school}|${r.name}`;
  if (!integByPerson.has(k)) integByPerson.set(k, { checked: 0, retracted: 0, corrected: 0, items: [] });
  const b = integByPerson.get(k);
  b.checked++;
  if (r.status === 'retracted') { b.retracted++; b.items.push({ doi: r.doi, title: r.title, year: r.year, status: r.status, updates: r.updates }); }
  if (r.status === 'corrected') { b.corrected++; b.items.push({ doi: r.doi, title: r.title, year: r.year, status: r.status, updates: r.updates }); }
}

const sat = (x, k) => 1 - Math.exp(-x / k);
const clamp = (x, a = 0, b = 100) => Math.max(a, Math.min(b, x));

// ── 学术头衔/平台分 ──
function titleScore(title, notes) {
  const t = `${title || ''} ${notes || ''}`;
  if (/院士|学部委员/.test(t)) return 100;
  if (/IEEE Fellow|Fellow, IEEE|长江学者|国家杰出青年|杰青|IET Fellow/.test(t)) return 82;
  if (/优青|优秀青年|海外优青|青年长江|青年千人|国家级青年人才|万人计划/.test(t)) return 66;
  if (/讲席|特聘教授|首席教授|长聘教授/.test(t)) return 62;
  if (/教授|研究员/.test(t)) return 55;
  if (/副教授|副研究员/.test(t)) return 40;
  if (/助理教授|讲师|助理研究员|博士后|百人计划/.test(t)) return 32;
  return 30;
}

const rows = [];
for (const r of db) {
  const key = `${r.school}|${r.name_cn}`;
  const h = heurMap.get(key);
  const ig = integByPerson.get(key);
  const nP = r.n_ic_papers || 0;
  const citations = r.citations || 0;
  const citePerPaper = nP ? citations / nP : 0;
  const densityRaw = nP >= 5 ? r.S / nP : 0;

  const sStrength = clamp(r.score);                       // 产出强度（原分）
  const sDensity = clamp(sat(densityRaw * 20, 1) * 100);  // 顶刊顶会密度
  const sImpact = clamp(sat(Math.log1p(citePerPaper), 2.2) * 100);  // 篇均引用
  const sActive = clamp(sat(r.recent3, 6) * 100);         // 近三年活跃
  const sEthics = r.student_led_ratio === null || r.student_led_ratio === undefined
    ? 45
    : clamp(sat(r.student_led_ratio, 0.35) * 100);        // 学生一作比例（越高越健康）
  const sTeam = clamp(sat(r.n_students_est || 0, 12) * 100);
  const sTitle = titleScore(r.title, r.notes);
  // 诚信分：有撤稿重罚，更正轻扣
  let sInteg = 100;
  if (ig) {
    if (ig.retracted > 0) sInteg = 15;
    else if (ig.corrected > 0) sInteg = 80;
  } else sInteg = null;

  const W = { strength: 0.40, density: 0.13, impact: 0.10, active: 0.10, ethics: 0.08, team: 0.06, title: 0.08, integrity: 0.05 };
  let total = W.strength * sStrength + W.density * sDensity + W.impact * sImpact + W.active * sActive +
    W.ethics * sEthics + W.team * sTeam + W.title * sTitle;
  if (sInteg === null) total += W.integrity * 85; else total += W.integrity * sInteg;
  total = +total.toFixed(1);

  const flags = h ? h.flags : [];
  rows.push({
    ...r,
    composite: total,
    dim: {
      strength: +sStrength.toFixed(1), density: +sDensity.toFixed(1), impact: +sImpact.toFixed(1),
      active: +sActive.toFixed(1), ethics: +sEthics.toFixed(1), team: +sTeam.toFixed(1),
      title: sTitle, integrity: sInteg,
    },
    heur_flags: flags,
    integrity: ig ? { checked: ig.checked, retracted: ig.retracted, corrected: ig.corrected, items: ig.items } : null,
  });
}

rows.sort((a, b) => b.composite - a.composite);
for (let i = 0; i < rows.length; i++) rows[i].rank = i + 1;

fs.writeFileSync(path.join(PROC, 'mentor_ranked.json'), JSON.stringify(rows, null, 1));

// CSV
const HDR = ['rank', 'composite', 'name_cn', 'school', 'title', 'department', 'primary_direction', 'S', 'A', 'B',
  'n_ic_papers', 'recent3', 'citations', 'cite_per_paper', 'advisor_first_ratio', 'student_led_ratio', 'n_students_est',
  'is_phd_advisor', 'confidence', 'recall_risk', 'dim_strength', 'dim_density', 'dim_impact', 'dim_active', 'dim_ethics',
  'dim_team', 'dim_title', 'retracted', 'corrected', 'top_venues', 'research_keywords', 'homepage', 'notes'];
const csv = [HDR.join(',')].concat(rows.map((r) => HDR.map((h) => {
  let v;
  if (h.startsWith('dim_')) v = r.dim[h.slice(4)];
  else if (h === 'cite_per_paper') v = r.n_ic_papers ? (r.citations / r.n_ic_papers).toFixed(1) : 0;
  else if (h === 'retracted') v = r.integrity ? r.integrity.retracted : '';
  else if (h === 'corrected') v = r.integrity ? r.integrity.corrected : '';
  else v = r[h];
  if (Array.isArray(v)) v = v.map((x) => (Array.isArray(x) ? x.join('×') : x)).join(' ');
  if (v && typeof v === 'object') v = JSON.stringify(v);
  return `"${String(v ?? '').replace(/"/g, '""')}"`;
}).join(','))).join('\n');
fs.writeFileSync(path.join(PROC, 'mentor_ranked.csv'), '\ufeff' + csv, 'utf8');

console.log('总人数', rows.length);
console.log('Top 30:');
for (const r of rows.slice(0, 30)) {
  console.log(`  #${String(r.rank).padStart(4)} 综合${String(r.composite).padStart(5)} | ${r.name_cn}(${r.school.replace('清华大学深圳国际研究生院', '清华深研院').replace('大学', '')}) ${r.title} | S${r.S} A${r.A} 论文${r.n_ic_papers} | 强度${r.dim.strength} 密度${r.dim.density} 影响${r.dim.impact} 活跃${r.dim.active} 伦理${r.dim.ethics}`);
}
const withFlags = rows.filter((r) => r.heur_flags.length);
const retr = rows.filter((r) => r.integrity && r.integrity.retracted > 0);
const corr = rows.filter((r) => r.integrity && r.integrity.corrected > 0);
console.log(`\n有启发式 flag: ${withFlags.length} 人 | 发现撤稿: ${retr.length} 人 | 更正/关注: ${corr.length} 人`);
for (const r of retr) console.log(`  ⚠️ ${r.name_cn}(${r.school}) 撤稿 ${r.integrity.retracted} 篇: ${r.integrity.items.map((i) => i.title.slice(0, 40)).join(' / ')}`);
for (const r of corr.slice(0, 10)) console.log(`  ℹ ${r.name_cn}(${r.school}) 更正/关注 ${r.integrity.corrected} 篇`);
