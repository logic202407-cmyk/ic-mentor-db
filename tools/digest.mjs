// digest.mjs — 生成各方向 T0/T1 速览（用于汇报）
import fs from 'node:fs';
const db = JSON.parse(fs.readFileSync('E:\\ytm\\mentor-db\\data\\processed\\mentor_db.json', 'utf8'));
const DIRNAME = {
  analog: '模拟/混合信号/电源', rf: '射频/毫米波', digital_ai: '数字/AI芯片/体系结构',
  eda: 'EDA/设计自动化', device: '器件/工艺/存储', photonics: '光电/硅光/光计算',
  mems: 'MEMS/传感器/生医电子', power: '电力电子', quantum: '量子芯片', other: '其他',
};
const tierOf = (d) => (d.n_ic_papers < 3 && d.S === 0) ? 'T4' : d.score >= 58 ? 'T0' : d.score >= 40 ? 'T1' : d.score >= 24 ? 'T2' : d.score >= 12 ? 'T3' : 'T4';
const dirs = [...new Set(db.map((r) => r.primary_direction))];
for (const d of dirs) {
  const list = db.filter((r) => r.primary_direction === d && ['T0', 'T1'].includes(tierOf(r))).sort((a, b) => b.score - a.score);
  if (!list.length) continue;
  console.log(`\n### ${DIRNAME[d] || d}  (T0/T1 共 ${list.length} 人)`);
  for (const r of list.slice(0, 12)) {
    console.log(`  ${r.score.toString().padStart(5)} ${tierOf(r)} ${r.name_cn}(${r.school.replace('清华大学深圳国际研究生院', '清华深研院').replace('大学', '')}) ${r.title} S${r.S} A${r.A} 论文${r.n_ic_papers} 近3年${r.recent3}`);
  }
}
