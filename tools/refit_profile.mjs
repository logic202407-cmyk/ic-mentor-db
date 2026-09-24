// refit_profile.mjs — 按「IC 科班 + 编程一般 + AI 重度使用者」重排推荐
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const pool = JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_2027.json'), 'utf8'));   // 643 人候选池
const labPages = fs.existsSync(path.join(PROC, 'shortlist_final.json'))
  ? JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_final.json'), 'utf8')) : [];
const labMap = new Map(labPages.map((d) => [`${d.school}|${d.name}`, d]));

// ── 编程负担关键词 ──
const CODE_HEAVY = /编译器|操作系统|分布式系统|分布式计算|存储系统|大数据|并行计算|数据库|计算机网络|云计算|虚拟化|运行时|软件工程|程序分析|形式化方法|图计算|高性能计算|体系结构模拟|模拟器|gem5|大模型训练|推理框架|推理系统|算法优化|机器学习算法|深度学习算法|计算机视觉|自然语言处理|语音识别|推荐系统|多模态|强化学习|联邦学习|隐私计算|软件定义网络|边缘计算平台|服务器|数据中心|集群/i;
const CODE_MED = /AI芯片|人工智能芯片|智能芯片|加速器|存算一体|存内计算|近存计算|RTL|EDA|设计自动化|体系结构|处理器|微处理器|SoC|片上系统|FPGA|RISC-V|可重构|硬件安全|密码芯片|类脑|神经形态|数字集成电路|数字电路|嵌入式|智能计算|Chiplet/i;
const CODE_LIGHT = /模拟集成电路|模拟电路|混合信号|数模混合|电源管理|DC-?DC|LDO|稳压器|电压调节|ADC|DAC|数据转换器|锁相环|PLL|时钟|放大器|基准源|版图|物理设计|后端设计|可测性|DFT|测试|可靠性|ESD|功率器件|功率集成|功率半导体|器件|工艺|传感器接口|接口电路|驱动芯片|电源芯片|能量采集|射频前端/i;

// ── IC 本体 vs 纯 CS/AI ──
const PURE_CS_DEPT = /计算机学院|计算机科学与技术|软件学院|人工智能学院|智能学院|网络空间安全|数据科学/i;
const IC_DEPT = /集成电路|微电子|电子科学与工程|电子信息|信息与电子|电子工程|微纳电子|仪器科学|光电科学与工程|自动化工程/i;

// IC × AI 交叉的细分方向
const CROSS_TAGS = [
  { tag: 'AI辅助EDA/智能设计工具', re: /AI.{0,3}EDA|EDA.{0,3}AI|智能EDA|人工智能.*设计自动化|机器学习.*(设计|布局|布线|综合|验证)|大模型.*(芯片|电路|RTL|设计)|LLM.{0,4}(IC|芯片|电路|设计)|AI辅助(设计|电路|布局)|无人化设计/i },
  { tag: 'AI芯片/加速器架构', re: /AI芯片|人工智能芯片|智能芯片|神经网络加速|深度学习加速|加速器|大算力|算力芯片|GPGPU|NPU|推理芯片|训练芯片/i },
  { tag: '存算一体/近存计算', re: /存算一体|存内计算|近存计算|忆阻|非易失处理器|感存算/i },
  { tag: '类脑/神经形态', re: /类脑|神经形态|脉冲神经网络|SNN/i },
  { tag: '智能电源/算力供电', re: /电源管理|IVR|供电架构|电压调节|DC-?DC|LDO|电源芯片/i },
  { tag: '智能传感/边缘AI硬件', re: /智能传感|边缘AI|端侧AI|智能感知芯片|传感器接口|AIoT/i },
  { tag: 'AI辅助模拟/器件设计', re: /模拟.*(AI|机器学习|神经网络)|器件.*(AI|机器学习)|工艺.*(AI|机器学习)|建模.*神经网络/i },
  { tag: '芯片安全/密码硬件', re: /硬件安全|密码芯片|安全芯片|可信计算|侧信道|PUF/i },
];

function scorePerson(d) {
  const kw = `${(d.research_keywords || []).join(' ')} ${d.notes || ''} ${d.primary_direction}`;
  const titles = (d.papers || []).map((p) => p.title || '').join(' ');
  const text = `${kw} ${titles}`;
  const dept = d.department || '';

  // 编程负担 0–100（越低越适合）
  let code = 45;
  if (CODE_HEAVY.test(text)) code += 30;
  if (CODE_HEAVY.test(dept)) code += 10;
  if (CODE_MED.test(text)) code -= 5;
  if (CODE_LIGHT.test(text)) code -= 18;
  if (PURE_CS_DEPT.test(dept) && !CODE_LIGHT.test(text)) code += 18;
  if (/集成电路|微电子/.test(dept)) code -= 12;
  if (d.primary_direction === 'analog') code -= 12;
  if (d.primary_direction === 'eda') code += 8;
  code = Math.max(5, Math.min(100, Math.round(code)));

  // IC 核心度 0–100（越高越"是集成电路本体"）
  let ic = 40;
  if (/集成电路|微电子/.test(dept)) ic += 25;
  else if (IC_DEPT.test(dept)) ic += 12;
  if (PURE_CS_DEPT.test(dept)) ic -= 22;
  if (/集成电路设计|芯片设计|模拟集成电路|数字集成电路|混合信号|电源管理|SoC|EDA|设计自动化|版图|后端|验证|器件|工艺|存算一体/i.test(kw)) ic += 20;
  if (['analog', 'device', 'eda', 'digital_ai'].includes(d.primary_direction)) ic += 10;
  ic = Math.max(0, Math.min(100, Math.round(ic)));

  // AI 交叉标签
  const tags = CROSS_TAGS.filter((t) => t.re.test(text)).map((t) => t.tag);

  const ai = d.ai_score;
  const lab = labMap.get(`${d.school}|${d.name_cn}`);
  const rec = lab?.recruit_final ?? d.recruit_score;

  // 适配分
  const fit = +(ic * 0.30 + ai * 0.25 + (100 - code) * 0.25 + Math.min(100, d.composite) * 0.12 + rec * 0.08).toFixed(1);

  return {
    ...d,
    code_load: code,
    ic_core: ic,
    cross_tags: tags.length ? tags : ['（未识别到明确 AI 交叉点）'],
    recruit_final: rec,
    lab_names: lab?.lab_names || [],
    recruit_signals: lab?.recruit_signals || [],
    recruit_signal_count: lab?.recruit_signal_count || 0,
    page_email: lab?.page_email || null,
    email: d.email || lab?.email || null,
    recent_student_first_authors: lab?.recent_student_first_authors ?? 0,
    recent_titles: lab?.recent_titles || [],
    fit_profile: fit,
  };
}

const scored = pool.map(scorePerson).sort((a, b) => b.fit_profile - a.fit_profile);
fs.writeFileSync(path.join(PROC, 'profile_fit.json'), JSON.stringify(scored, null, 1));

const csv = ['name,school,title,department,primary_direction,fit_profile,ic_core,ai_score,code_load,recruit_score,composite,S,A,n_ic_papers,recent3,n_students_est,cross_tags,email,homepage,lab,research_keywords,notes']
  .concat(scored.map((d) => [d.name_cn, d.school, d.title, d.department, d.primary_direction, d.fit_profile, d.ic_core, d.ai_score, d.code_load, d.recruit_final, d.composite, d.S, d.A, d.n_ic_papers, d.recent3, d.n_students_est, d.cross_tags.join(' / '), d.email, d.homepage, (d.lab_names || [])[0], (d.research_keywords || []).join('、'), (d.notes || '').replace(/\n/g, ' ')]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')))
  .join('\n');
fs.writeFileSync(path.join(PROC, 'profile_fit.csv'), '\ufeff' + csv, 'utf8');

console.log('重排人数:', scored.length);
console.log('\n=== 最契合「IC 科班 + 编程一般 + AI 使用者」Top 35 ===');
for (const d of scored.slice(0, 35)) {
  console.log(`fit${String(d.fit_profile).padStart(5)} | IC${String(d.ic_core).padStart(3)} AI${String(d.ai_score).padStart(3)} 编程${String(d.code_load).padStart(3)} 招${String(d.recruit_final).padStart(3)} | ${d.name_cn}(${d.school.replace('清华大学深圳国际研究生院', '清华深研院').replace('大学', '')}) ${d.title} | ${d.cross_tags[0]} | 在招:${d.recruit_signal_count > 0 ? '是' : '未明'}`);
}
console.log('\n=== 编程负担最低的 15 人（适合不想写代码）===');
for (const d of [...scored].sort((a, b) => a.code_load - b.code_load).slice(0, 15)) {
  console.log(`  编程${d.code_load} | ${d.name_cn}(${d.school.slice(0, 4)}) ${d.title} | IC${d.ic_core} AI${d.ai_score} | ${(d.research_keywords || []).join('、').slice(0, 44)}`);
}
console.log('\n=== 编程负担最重的 10 人（建议避开）===');
for (const d of [...scored].sort((a, b) => b.code_load - a.code_load).slice(0, 10)) {
  console.log(`  编程${d.code_load} | ${d.name_cn}(${d.school.slice(0, 4)}) ${d.title} | ${(d.research_keywords || []).join('、').slice(0, 44)}`);
}
