// shortlist.mjs — 面向 2027 推免的候选筛选：排除射频/光电/MEMS，突出 AI 相关，评估"在招可能性"
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

// ── 1) 方向排除 ──
const EXCLUDE_DIRS = new Set(['rf', 'photonics', 'mems']);

// 细分排除：主方向虽不是 rf/photonics/mems，但本人方向关键词明显属于这些领域的也要剔除
const EXCLUDE_KW = /毫米波|太赫兹|射频|微波|天线|相控阵|雷达|功放|低噪声放大|混频|频率综合|硅光|光子|光计算|光互连|激光|光电探测|光纤|光学|LED|显示技术|micro-?LED|MEMS|微机电|陀螺|微流控|柔性电子|可穿戴|生物医学电子|植入|超声换能|传感器芯片|压电|声学器件/i;

// ── 2) AI 相关度 ──
const AI_KW = /人工智能|AI芯片|AI 芯片|智能芯片|神经网络|深度学习|机器学习|大模型|大语言模型|加速器|存算一体|存内计算|近存计算|忆阻|类脑|神经形态|脉冲神经网络|智能计算|边缘智能|边缘计算|具身智能|自动驾驶|机器人芯片|算力|体系结构|架构|处理器|微处理器|RISC-V|SoC|片上系统|数字集成电路|数字电路|芯片设计|EDA|设计自动化|智能感知|智能系统|FPGA|可重构|稀疏|量化|Transformer|CNN|DNN|GPGPU|NPU|芯片架构|智能硬件|硬件加速/i;
const AI_STRONG = /AI芯片|人工智能芯片|智能芯片|神经网络|深度学习|大模型|加速器|存算一体|存内计算|近存计算|忆阻|类脑|神经形态|智能计算|算力|具身智能|体系结构|处理器|GPGPU|NPU|RISC-V|硬件加速|AI-?EDA/i;

// ── 3) 在招可能性 ──
function recruitScore(d) {
  let s = 50;
  const t = `${d.title || ''} ${d.notes || ''}`;
  if (/助理教授|准聘|青年研究员|特任|百人计划|助理研究员|博士后/.test(t)) s += 28;
  else if (/副教授|副研究员/.test(t)) s += 18;
  else if (/教授|研究员/.test(t)) s += 6;
  if (/院士|校长|副校长|院长|副院长|系主任|所长|党委书记|学部主任/.test(t)) s -= 18;
  if (/院士/.test(t)) s -= 12;
  if (d.recent3 >= 8) s += 20; else if (d.recent3 >= 4) s += 14; else if (d.recent3 >= 1) s += 6; else s -= 12;
  if ((d.n_students_est || 0) >= 10) s += 14; else if ((d.n_students_est || 0) >= 5) s += 9; else if ((d.n_students_est || 0) >= 2) s += 4;
  if (d.email) s += 8;
  if (d.homepage) s += 4;
  if (d.is_phd_advisor === true) s += 4;
  if (d.recall_risk === 'yes') s -= 10;
  if (d.confidence === 'low') s -= 6;
  return Math.max(0, Math.min(100, s));
}

const list = [];
for (const d of rows) {
  if (EXCLUDE_DIRS.has(d.primary_direction)) continue;
  const kwText = `${(d.research_keywords || []).join(' ')} ${d.notes || ''}`;
  if (EXCLUDE_KW.test(kwText) && !AI_KW.test(kwText)) continue;      // 明显是射频/光电/MEMS且不沾AI → 剔除
  if (d.n_ic_papers < 3) continue;                                    // 证据太少，无法判断

  // AI 相关度
  let ai = 0;
  if (d.primary_direction === 'digital_ai') ai += 30;
  if (d.primary_direction === 'eda') ai += 18;
  if (AI_STRONG.test(kwText)) ai += 26;
  else if (AI_KW.test(kwText)) ai += 12;
  const paperHits = (d.papers || []).filter((p) => AI_KW.test(p.title || '')).length;
  ai += Math.min(20, paperHits * 1.2);
  // 数字/AI 类顶会顶刊加成
  const aiVenues = (d.papers || []).filter((p) => ['ISCA', 'MICRO', 'HPCA', 'ASPLOS', 'DAC', 'ICCAD', 'ISSCC', 'JSSC', 'TVLSI', 'TC', 'TCAD', 'FPGA'].includes(p.venueKey)).length;
  ai += Math.min(16, aiVenues * 1.5);
  ai = Math.min(100, Math.round(ai));

  const rec = recruitScore(d);
  list.push({
    ...d,
    ai_score: ai,
    recruit_score: rec,
    fit: +(d.composite * 0.45 + ai * 0.35 + rec * 0.20).toFixed(1),
  });
}

list.sort((a, b) => b.fit - a.fit);
fs.writeFileSync(path.join(PROC, 'shortlist_2027.json'), JSON.stringify(list, null, 1));

const csv = ['rank_in_list,name,school,title,department,primary_direction,ai_score,recruit_score,fit,composite,S,A,n_ic_papers,recent3,citations,n_students_est,is_phd_advisor,email,homepage,research_keywords,notes']
  .concat(list.map((d, i) => [i + 1, d.name_cn, d.school, d.title, d.department, d.primary_direction, d.ai_score, d.recruit_score, d.fit, d.composite, d.S, d.A, d.n_ic_papers, d.recent3, d.citations, d.n_students_est, d.is_phd_advisor, d.email, d.homepage, (d.research_keywords || []).join('、'), (d.notes || '').replace(/\n/g, ' ')]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')))
  .join('\n');
fs.writeFileSync(path.join(PROC, 'shortlist_2027.csv'), '\ufeff' + csv, 'utf8');

console.log('候选池:', list.length, '人');
const byDir = {};
for (const d of list) byDir[d.primary_direction] = (byDir[d.primary_direction] || 0) + 1;
console.log('方向分布:', JSON.stringify(byDir));
console.log('AI 相关度 ≥60 的:', list.filter((d) => d.ai_score >= 60).length);
console.log('\nTop 40（fit 排序）:');
for (const d of list.slice(0, 40)) {
  console.log(`  fit${String(d.fit).padStart(5)} AI${String(d.ai_score).padStart(3)} 招${String(d.recruit_score).padStart(3)} | ${d.name_cn}(${d.school.replace('清华大学深圳国际研究生院', '清华深研院').replace('大学', '')}) ${d.title} | S${d.S} A${d.A} 论文${d.n_ic_papers} 近3年${d.recent3} 学生${d.n_students_est} | ${(d.research_keywords || []).join('、').slice(0, 46)}`);
}
