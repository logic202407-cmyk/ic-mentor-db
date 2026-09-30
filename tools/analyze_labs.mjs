// analyze_labs.mjs — 精炼课题组主页的招生信号，并结合近期学生一作评估"在招/活跃"
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const PROC = path.join(REPO, 'data', 'processed');
const RAWDIR = path.join(REPO, 'data', 'raw', 'lab_pages');
const pages = JSON.parse(fs.readFileSync(path.join(PROC, 'lab_pages.json'), 'utf8'));
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const rankMap = new Map(ranked.map((r) => [`${r.school}|${r.name_cn}`, r]));
// 中文校名 -> school_key（lab_pages 文件按 school_key 命名）
const schoolKey = new Map();
for (const [k, m] of Object.entries(JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8')))) {
  schoolKey.set(m.school, m.school_key || k);
}

// 精确招生句式（避免导航栏 "招生信息" 菜单项）
const RECRUIT_STRONG = [
  /(长期|常年|每年|本年度|2026|2027)?\s*招(收|募)\s*(硕士|博士|研究生|推免|若干|1|2|3|4|5|\d)/g,
  /(欢迎|热忱欢迎|诚邀)\s*(报考|加入|申请|联系)/g,
  /推免(生|名额|指标)/g,
  /夏令营/g,
  /招生(名额|指标|计划|方向|要求|说明)/g,
  /(硕士|博士)(研究生)?招生/g,
  /join\s*(us|our\s*(group|lab|team))/gi,
  /(ph\.?d\.?|master|graduate)\s*(student)?\s*(positions?|openings?|recruit)/gi,
  /(postdoc|research\s*assistant)\s*(positions?|openings?)/gi,
  /有意(者|向)?(请)?(联系|邮件|发送简历)/g,
  /简历\s*(发送|投递|发至)/g,
];
const NAV_NOISE = /^(首页|学院概况|师资|教师名录|科学研究|人才培养|招生信息|招聘信息|党建工作|联系我们|English|按拼音|按职称)/;
// 导航栏特征：同时出现多个"栏目名"
const NAV_TERMS = ['本科生招生', '硕士研究生招生', '博士研究生招生', '招生就业', '人才培养', '科学研究', '党建工作', '通知公告', '师资队伍', '学科建设', '学生工作', '合作交流', '信息公开', '诚聘英才', '资料下载'];
function looksLikeNav(s) {
  let n = 0;
  for (const t of NAV_TERMS) if (s.includes(t)) n++;
  return n >= 2;
}

function cleanSnips(text, name) {
  const out = [];
  // 姓名在正文中的所有位置，用于判断招生语句是否与该人相关
  const namePos = [];
  if (name) { let i = text.indexOf(name); while (i >= 0) { namePos.push(i); i = text.indexOf(name, i + 1); } }
  for (const re of RECRUIT_STRONG) {
    for (const m of text.matchAll(re)) {
      const s = Math.max(0, m.index - 60), e = Math.min(text.length, m.index + 120);
      let snip = text.slice(s, e).replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
      if (snip.length < 12) continue;
      if (NAV_NOISE.test(snip)) continue;
      if (looksLikeNav(snip)) continue;
      if ((snip.match(/[|·]/g) || []).length >= 3) continue;
      if (snip.replace(/[^\u4e00-\u9fa5A-Za-z]/g, '').length < 14) continue;
      // 姓名是否落在该语句附近（±200 字）
      const near = namePos.some((p) => Math.abs(p - m.index) <= 200);
      out.push({ kw: m[0].trim(), snippet: snip, near });
    }
  }
  // 去重
  const seen = new Set(), uniq = [];
  for (const o of out) { const k = o.snippet.slice(0, 36); if (seen.has(k)) continue; seen.add(k); uniq.push(o); }
  return uniq.slice(0, 5);
}

const out = [];
for (const p of pages) {
  const key = `${p.school}|${p.name}`;
  const r = rankMap.get(key);
  let text = '';
  // 文件名用 school_key（旧数据兼容：退回「学校前 4 字」命名）
  const sk = p.school_key || schoolKey.get(p.school) || (p.school || '').slice(0, 4);
  const f = path.join(RAWDIR, `${sk}_${p.name}.txt`);
  if (fs.existsSync(f)) text = fs.readFileSync(f, 'utf8');
  else {
    const legacy = path.join(RAWDIR, `${(p.school || '').slice(0, 4)}_${p.name}.txt`);
    if (fs.existsSync(legacy)) text = fs.readFileSync(legacy, 'utf8');
  }

  const snips = text ? cleanSnips(text, p.name) : [];
  // 近两年学生一作（活跃度/组内是否真有学生在干活）：只要求"导师不是一作"
  const recentStu = new Set();
  let lastYear = 0;
  if (r) {
    for (const pp of r.papers || []) {
      if (pp.year > lastYear) lastYear = pp.year;
      if (pp.year >= 2024 && pp.my_order > 1 && pp.coauthors && pp.coauthors[0] && pp.coauthors[0].name) {
        recentStu.add(pp.coauthors[0].name.toLowerCase());
      }
    }
  }
  // 清洗课题组名：必须是干净的机构名，排除导航文字
  const LAB_OK = /(课题组|研究室|实验室|研究组|研究中心|创新中心|工程中心|联合实验室|研究院|Group|Lab|Laboratory)$/i;
  const labs = (p.lab_names || [])
    .map((x) => x.replace(/[\n\r]+/g, ' ').replace(/\s+/g, ' ').trim())
    .filter((x) => x.length >= 4 && x.length <= 30 && LAB_OK.test(x))
    .filter((x) => !NAV_TERMS.some((t) => x.includes(t)))
    .slice(0, 3);
  out.push({
    name: p.name, school: p.school, title: p.title, department: p.department,
    homepage: p.homepage, email: p.db_email || p.page_email, page_email: p.page_email,
    primary_direction: p.primary_direction, ai_score: p.ai_score, recruit_score: p.recruit_score, fit: p.fit,
    lab_names: labs,
    recruit_signals: snips,
    recruit_signal_count: snips.length,    recent_student_first_authors: recentStu.size,
    last_paper_year: lastYear,
    page_ok: p.status === 'ok',
    page_len: p.text_len || 0,
    composite: r ? r.composite : null, S: r ? r.S : null, A: r ? r.A : null,
    n_ic_papers: r ? r.n_ic_papers : null, recent3: r ? r.recent3 : null,
    n_students_est: r ? r.n_students_est : null,
    is_phd_advisor: r ? r.is_phd_advisor : null,
    research_keywords: r ? r.research_keywords : [],
    top_venues: r ? r.top_venues : [],
    recent_titles: r ? (r.papers || [])
      .filter((x) => (x.year || 0) >= 2025)
      .filter((x) => !/carcinoma|cancer|tumor|clinical|patient|medical|disease|surgery|endoscop|diagnosis|gene|protein|cell |mice|rat |in vivo|cohort|hospital/i.test(x.title || ''))
      .sort((a, b) => ((/AI|neural|accelerat|processor|architecture|in-memory|computing|learning|chip|SoC|FPGA|memory|circuit|design|EDA/i.test(b.title || '') ? 1 : 0) - (/AI|neural|accelerat|processor|architecture|in-memory|computing|learning|chip|SoC|FPGA|memory|circuit|design|EDA/i.test(a.title || '') ? 1 : 0)) || ((b.cited || 0) - (a.cited || 0)))
      .slice(0, 3)
      .map((x) => `${x.year} ${x.title}`) : [],
  });
}

// ── 站点模板过滤：同一句话若在**同一学校 ≥4 人**的页面上出现，即为该站点的
//    新闻栏/导航模板（例：中科院微电子所官网的「夏令营报名通知」「拟录取名单公示」
//    曾让该所 78/78 人全部被误判为"在招"），而非本人招生表述，一律剔除。
const prefixCount = new Map();
for (const d of out) {
  for (const s of d.recruit_signals) {
    const k = `${d.school}||${s.snippet.slice(0, 36)}`;
    prefixCount.set(k, (prefixCount.get(k) || 0) + 1);
  }
}
let droppedTemplate = 0;
for (const d of out) {
  const kept = d.recruit_signals.filter((s) => (prefixCount.get(`${d.school}||${s.snippet.slice(0, 36)}`) || 0) < 4);
  droppedTemplate += d.recruit_signals.length - kept.length;
  d.recruit_signals = kept;
  d.recruit_signal_count = kept.length;
}
console.log(`站点模板过滤：剔除 ${droppedTemplate} 条跨多人重复的招生语句`);

// 综合"在招可能性"
for (const d of out) {
  let s = d.recruit_score * 0.5;
  s += Math.min(20, d.recruit_signal_count * 7);
  s += Math.min(15, d.recent_student_first_authors * 1.5);
  if (d.last_paper_year >= 2026) s += 10; else if (d.last_paper_year >= 2025) s += 5;
  if (d.email) s += 6;
  if (d.page_ok) s += 3;
  d.recruit_final = Math.round(Math.min(100, s));
  d.fit_final = +(d.fit * 0.45 + d.recruit_final * 0.30 + (d.ai_score) * 0.25).toFixed(1);
}
out.sort((a, b) => b.fit_final - a.fit_final);
fs.writeFileSync(path.join(PROC, 'shortlist_final.json'), JSON.stringify(out, null, 1));

const withSig = out.filter((d) => d.recruit_signal_count > 0);
console.log('分析人数:', out.length);
console.log('主页明确出现招生语句:', withSig.length);
console.log('页面自带邮箱:', out.filter((d) => d.page_email).length, '| 有邮箱总计:', out.filter((d) => d.email).length);
console.log('识别出实验室名:', out.filter((d) => d.lab_names.length).length);
console.log('\n=== 明确有招生语句的导师（前 25）===');
for (const d of withSig.slice(0, 25)) {
  console.log(`${d.fit_final} | ${d.name}(${d.school.slice(0, 4)}) ${d.title} AI${d.ai_score} | ${d.lab_names[0] || '-'}`);
  console.log(`     ${d.recruit_signals[0].snippet.slice(0, 110)}`);
}
