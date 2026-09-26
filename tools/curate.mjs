// curate.mjs — 构建推荐数据集（中性版）
//   scope = "focus"      : 集成电路设计与 AI 交叉方向
//   scope = "recruiting" : 其他 IC 方向，但个人/课题组主页明确写了在招
// 输入: mentor_ranked.json（全库排名）+ shortlist_final.json（主页分析）+ lab_pages.json
// 输出: data/processed/curated.json / curated.csv
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const labPages = fs.existsSync(path.join(PROC, 'lab_pages.json'))
  ? JSON.parse(fs.readFileSync(path.join(PROC, 'lab_pages.json'), 'utf8')) : [];
const labMap = new Map(labPages.map((d) => [`${d.school}|${d.name}`, d]));
const analyzed = fs.existsSync(path.join(PROC, 'shortlist_final.json'))
  ? JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_final.json'), 'utf8')) : [];
const anaMap = new Map(analyzed.map((d) => [`${d.school}|${d.name}`, d]));

// ── 细分研究方向（从具体到宽泛的顺序匹配；多标签）──
const GROUPS = [
  { key: 'cim', name: '存算一体 / 新型存储', re: /存算一体|存内计算|近存计算|忆阻|非易失|新型存储|RRAM|ReRAM|MRAM|铁电|相变存储/i },
  { key: 'eda', name: 'EDA / 设计自动化', re: /EDA|设计自动化|布局布线|逻辑综合|形式验证|设计方法学|工艺协同|计算光刻|签核|物理设计/i },
  { key: 'neuromorphic', name: '类脑 / 神经形态计算', re: /类脑|神经形态|脉冲神经网络|SNN|突触/i },
  { key: 'security', name: '芯片安全 / 密码硬件', re: /硬件安全|密码芯片|安全芯片|侧信道|PUF|可信计算|同态加密/i },
  { key: 'analog', name: '模拟 / 混合信号 / 电源管理', re: /模拟集成电路|模拟电路|混合信号|数模混合|电源管理|ADC|DAC|数据转换器|锁相环|PLL|基准源|放大器|DC-?DC|LDO|IVR|供电|电源芯片|能量采集/i },
  { key: 'ai_chip', name: 'AI 芯片 / 加速器 / 体系结构', re: /AI芯片|人工智能芯片|智能芯片|加速器|GPGPU|NPU|大算力|算力芯片|深度学习加速|神经网络加速|AI加速|智能计算|推理芯片|训练芯片|具身智能|自动驾驶芯片/i },
  { key: 'digital', name: '数字 IC / SoC / 验证后端', re: /数字集成电路|数字电路|SoC|片上系统|处理器|微处理器|体系结构|RISC-V|可重构|验证|后端|可测性|DFT|Chiplet|硬件加速|低功耗设计|嵌入式|MCU/i },
  { key: 'rf', name: '射频 / 毫米波 / 太赫兹', re: /射频|毫米波|太赫兹|微波|天线|相控阵|雷达|收发机|频率综合/i },
  { key: 'photonics', name: '光电 / 硅光 / 光计算', re: /硅光|光子|光电|光计算|激光|光互连|光芯片|成像|图像传感器|显示/i },
  { key: 'mems', name: 'MEMS / 传感器 / 生医电子', re: /MEMS|微机电|微纳传感|传感器|微流控|可穿戴|柔性电子|生物医疗|植入|脑机接口/i },
  { key: 'edge', name: '智能传感 / 边缘计算硬件', re: /智能传感|边缘AI|端侧AI|智能感知|AIoT|传感器接口|感存算|物联网芯片/i },
  { key: 'quantum', name: '量子芯片 / 低温电子学', re: /量子|超导|低温电子|约瑟夫森|自旋量子/i },
  { key: 'device', name: '器件 / 工艺 / 宽禁带', re: /器件|工艺|宽禁带|氮化镓|碳化硅|氧化镓|微纳加工|薄膜|异质集成|光刻|封装/i },
];
const GNAME = Object.fromEntries(GROUPS.map((g) => [g.key, g.name]));
function groupsOf(d) {
  const text = `${(d.research_keywords || []).join(' ')} ${d.notes || ''} ${(d.papers || []).map((p) => p.title).join(' ')}`;
  const hits = GROUPS.filter((g) => g.re.test(text)).map((g) => g.key);
  return hits.length ? hits : [d.primary_direction === 'device' ? 'device' : 'digital'];
}

// ── 聚焦范围：集成电路设计与 AI 交叉 ──
const IN_SCOPE_DIRS = new Set(['digital_ai', 'eda', 'analog']);
const DEVICE_RELEVANT = /存算一体|存内计算|近存计算|忆阻|类脑|神经形态|智能芯片|AI芯片|存储器|感存算|智能传感|边缘AI|硬件安全|密码芯片/i;

const BAD_TITLE = /carcinoma|cancer|tumor|clinical|patient|medical|disease|surgery|endoscop|diagnosis|gene|protein|mice|rat |in vivo|cohort|hospital/i;

function buildRecord(d, scope) {
  const key = `${d.school}|${d.name_cn}`;
  const lab = labMap.get(key);
  const ana = anaMap.get(key);
  const groups = groupsOf(d);
  const sigs = (ana && ana.recruit_signals) || [];
  return {
    name: d.name_cn, school: d.school, title: d.title, department: d.department,
    scope,
    group: groups[0], group_name: GNAME[groups[0]] || groups[0],
    groups, group_names: groups.map((g) => GNAME[g] || g),
    primary_direction: d.primary_direction,
    composite: d.composite, rank: d.rank,
    tier: d.composite >= 72 ? 'T0' : d.composite >= 58 ? 'T1' : d.composite >= 42 ? 'T2' : d.composite >= 26 ? 'T3' : 'T4',
    S: d.S, A: d.A, B: d.B, n_ic_papers: d.n_ic_papers, n_related_papers: d.n_related_papers,
    recent3: d.recent3, citations: d.citations,
    cite_per_paper: d.n_ic_papers ? +(d.citations / d.n_ic_papers).toFixed(1) : 0,
    n_students_est: d.n_students_est, is_phd_advisor: d.is_phd_advisor,
    advisor_first_ratio: d.advisor_first_ratio, student_led_ratio: d.student_led_ratio,
    confidence: d.confidence, recall_risk: d.recall_risk, n_off_field: d.n_off_field,
    integrity_retracted: d.integrity ? d.integrity.retracted : 0,
    integrity_corrected: d.integrity ? d.integrity.corrected : 0,
    research_keywords: d.research_keywords || [], notes: d.notes || '',
    top_venues: d.top_venues || [],
    homepage: d.homepage || null,
    lab_names: (ana && ana.lab_names) || (lab && lab.lab_names) || [],
    recruit_signals: sigs,
    recruit_signal_count: sigs.length,
    recent_student_first_authors: (ana && ana.recent_student_first_authors) || 0,
    page_status: lab ? lab.status : 'not_fetched',
    recent_titles: (ana && ana.recent_titles && ana.recent_titles.length
      ? ana.recent_titles
      : (d.papers || []).filter((p) => (p.year || 0) >= 2025 && !BAD_TITLE.test(p.title || ''))
        .sort((a, b) => (b.cited || 0) - (a.cited || 0)).slice(0, 3).map((p) => `${p.year} ${p.title}`)),
  };
}

const curated = [];
const seen = new Set();
for (const d of ranked) {
  if ((d.n_ic_papers || 0) < 3) continue;
  const kwText = `${(d.research_keywords || []).join(' ')} ${d.notes || ''}`;
  const inFocus = IN_SCOPE_DIRS.has(d.primary_direction)
    || (d.primary_direction === 'device' && DEVICE_RELEVANT.test(kwText));
  if (!inFocus) continue;
  curated.push(buildRecord(d, 'focus'));
  seen.add(`${d.school}|${d.name_cn}`);
}
// 补充：其他方向但主页明确在招
let extra = 0;
for (const d of ranked) {
  const key = `${d.school}|${d.name_cn}`;
  if (seen.has(key) || (d.n_ic_papers || 0) < 3) continue;
  const ana = anaMap.get(key);
  if (!ana || !ana.recruit_signal_count) continue;
  curated.push(buildRecord(d, 'recruiting'));
  seen.add(key);
  extra++;
}
curated.sort((a, b) => b.composite - a.composite);

fs.writeFileSync(path.join(PROC, 'curated.json'), JSON.stringify(curated, null, 1));

const csv = ['name,school,title,department,scope,group,primary_direction,tier,composite,rank,S,A,n_ic_papers,recent3,citations,cite_per_paper,n_students_est,is_phd_advisor,student_led_ratio,confidence,homepage,lab,research_keywords,recruit_signal,notes']
  .concat(curated.map((d) => [d.name, d.school, d.title, d.department, d.scope, d.group_name, d.primary_direction, d.tier, d.composite, d.rank, d.S, d.A, d.n_ic_papers, d.recent3, d.citations, d.cite_per_paper, d.n_students_est, d.is_phd_advisor, d.student_led_ratio, d.confidence, d.homepage, d.lab_names[0], (d.research_keywords || []).join('、'), (d.recruit_signals[0] || {}).snippet || '', (d.notes || '').replace(/\n/g, ' ')]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')))
  .join('\n');
fs.writeFileSync(path.join(PROC, 'curated.csv'), '\ufeff' + csv, 'utf8');

const byGroup = {};
for (const d of curated) byGroup[d.group_name] = (byGroup[d.group_name] || 0) + 1;
console.log('推荐集人数:', curated.length, `（聚焦 ${curated.length - extra} + 在招补充 ${extra}）`);
console.log('细分方向分布:');
for (const [k, v] of Object.entries(byGroup).sort((a, b) => b[1] - a[1])) console.log(`  ${String(v).padStart(4)}  ${k}`);
console.log('有主页抓取记录:', curated.filter((d) => d.page_status.startsWith('ok')).length);
console.log('主页明确在招:', curated.filter((d) => d.recruit_signal_count > 0).length);
