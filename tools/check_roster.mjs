// check_roster.mjs — 校验新采集的名录结构是否合规
import fs from 'node:fs';
const files = process.argv.slice(2);
let bad = 0;
for (const f of files) {
  if (!fs.existsSync(f)) { console.log(`✗ ${f} 不存在`); bad++; continue; }
  let d;
  try { d = JSON.parse(fs.readFileSync(f, 'utf8').replace(/^\ufeff/, '')); }
  catch (e) { console.log(`✗ ${f} JSON 解析失败: ${e.message}`); bad++; continue; }
  const errs = [];
  if (!d.school) errs.push('缺 school');
  if (!d.school_key) errs.push('缺 school_key');
  if (!Array.isArray(d.sources) || !d.sources.length) errs.push('缺 sources');
  if (!Array.isArray(d.faculty)) errs.push('缺 faculty 数组');
  const fac = d.faculty || [];
  if (fac.length < 20) errs.push(`人数偏少: ${fac.length}`);
  const names = new Set();
  for (const p of fac) {
    for (const k of ['name_cn', 'title', 'department', 'research_keywords', 'is_phd_advisor']) {
      if (p[k] === undefined) errs.push(`${p.name_cn || '?'} 缺字段 ${k}`);
    }
    if (p.email) errs.push(`${p.name_cn} 含邮箱（应为 null）`);
    if (typeof p.is_phd_advisor !== 'boolean' && p.is_phd_advisor !== null) errs.push(`${p.name_cn} is_phd_advisor 非法（应为 true/false/null）`);
    if (names.has(p.name_cn)) errs.push(`重名/重复: ${p.name_cn}`);
    names.add(p.name_cn);
    const cn = (p.name_cn || '').replace(/[（(][^）)]*[）)]/g, '').trim();
    const hasHan = /[\u4e00-\u9fa5]/.test(cn);
    if (hasHan && (cn.length < 2 || cn.length > 4)) errs.push(`中文姓名异常: ${cn}`);
    if (!hasHan && (cn.length < 3 || cn.length > 60)) errs.push(`外文姓名异常: ${cn}`);
    if (!p.name_en && !hasHan) errs.push(`外文姓名缺 name_en: ${cn}`);
  }
  const uniq = [...new Set(errs)];
  console.log(`${uniq.length ? '✗' : '✓'} ${f.split(/[\\/]/).pop()} : ${fac.length} 人, ${uniq.length} 个问题`);
  for (const e of uniq.slice(0, 8)) console.log('    - ' + e);
  if (uniq.length) bad++;
}
process.exit(bad ? 1 : 0);
