// disambig.mjs — 同校同名消歧：给重名者加上研究所/方向后缀，保证管线键唯一
import fs from 'node:fs';

const TARGETS = ['cas', 'buaa'];
const ABBR = {
  '微电子研究所': '微电子所', '半导体研究所': '半导体所', '上海微系统与信息技术研究所': '上海微系统所',
  '计算技术研究所': '计算所', '自动化研究所': '自动化所', '上海高等研究院': '上海高研院',
  '集成电路科学与工程学院': null, '电子信息工程学院': null,
};
let total = 0;
for (const k of TARGETS) {
  const p = `E:\\ytm\\mentor-db\\data\\raw\\${k}\\roster_${k}.json`;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  // 统一括号为中文全角
  for (const f of j.faculty) f.name_cn = String(f.name_cn).replace(/\(/g, '（').replace(/\)/g, '）');
  // 找出仍重名的
  const m = new Map();
  for (const f of j.faculty) (m.get(f.name_cn) || m.set(f.name_cn, []).get(f.name_cn)).push(f);
  for (const [name, arr] of m) {
    if (arr.length < 2) continue;
    for (const f of arr) {
      if (/（/.test(f.name_cn)) continue;
      const dep = ABBR[f.department] !== undefined ? ABBR[f.department] : f.department;
      // 同院系内重名 → 用研究方向首词消歧
      let tag = dep;
      if (!tag) {
        const kw = (f.research_keywords || [])[0] || '';
        tag = kw.split(/[/、,，]/)[0].slice(0, 8) || '方向' + (arr.indexOf(f) + 1);
      }
      const before = f.name_cn;
      f.name_cn = `${name}（${tag}）`;
      f.notes = (f.notes ? f.notes + '；' : '') + `本项目为消歧标注：同名者，见「${tag}」`;
      console.log(`  ${j.school} | ${before} → ${f.name_cn} | ${f.title}`);
      total++;
    }
  }
  fs.writeFileSync(p, JSON.stringify(j, null, 1), 'utf8');
}
console.log(`\n共消歧 ${total} 条`);
