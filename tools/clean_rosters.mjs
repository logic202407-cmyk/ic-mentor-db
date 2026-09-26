// clean_rosters.mjs — 清洗名录数据：① 移除邮箱字段  ② 过滤垃圾研究方向关键词
import fs from 'node:fs';
import path from 'node:path';

const RAW = 'E:\\ytm\\mentor-db\\data\\raw';
const JUNK = /^(教育背景|工作经历|个人简介|简历|研究方向|简介|职称|学位|学历|邮箱|电话|地址|邮编|性别|出生|民族|政治面貌|导师|招生|备注|获奖|荣誉|论文|项目|专利|著作|主讲|课程)/;
const JUNK2 = /^[\d０-９\-—－~～年月日.、\s]+$/;
const JUNK3 = /(博士学位|硕士学位|学士学位|毕业|就读|工作于|任教|博士后|访问学者|课题组主页|点击|详见|以上|如下)/;
const JUNK4 = /^[A-Za-z\s.,&()-]{1,3}$/;
// 以年份/学制数字开头（如 "06 电子科技大学"、"2009-2013 清华大学"）、或含"大学/学院"等机构词但无技术术语的
const JUNK5 = /^(\d{2}|\d{4})\s*[-—－~～]?\s*(\d{2}|\d{4})?\s*/;
const JUNK6 = /^[^，,、;；]{0,12}(大学|学院|研究院|实验室|研究所|中心)\s*$/;

function cleanKeywords(list) {
  if (!Array.isArray(list)) return [];
  const out = [];
  for (let k of list) {
    k = String(k || '').replace(/\s+/g, ' ').trim();
    if (!k || k.length < 2 || k.length > 40) continue;
    if (JUNK.test(k) || JUNK2.test(k) || JUNK3.test(k) || JUNK4.test(k)) continue;
    // 以年份开头、或纯机构名（无技术术语）→ 属于简历片段
    if (JUNK5.test(k) && !/[，,、]/.test(k)) continue;
    if (JUNK6.test(k)) continue;
    if (/^(等|及|和|与)/.test(k)) continue;
    // 含机构名但完全不含技术术语的短句
    if (/(大学|学院|研究院|研究所)/.test(k) && k.length <= 12 && !/[，,、]/.test(k)) continue;
    if (out.some((x) => x === k || x.includes(k) || k.includes(x))) continue;
    out.push(k);
    if (out.length >= 6) break;
  }
  return out;
}

const files = [];
for (const d of fs.readdirSync(RAW)) {
  const dir = path.join(RAW, d);
  if (!fs.statSync(dir).isDirectory()) continue;
  for (const f of fs.readdirSync(dir)) {
    if (/^roster_.*\.json$/.test(f) && !f.includes('draft')) files.push(path.join(dir, f));
  }
}

let totalPeople = 0, emailRemoved = 0, kwBefore = 0, kwAfter = 0, kwEmptied = 0;
for (const f of files) {
  const data = JSON.parse(fs.readFileSync(f, 'utf8'));
  for (const fac of data.faculty || []) {
    totalPeople++;
    if (fac.email) { fac.email = null; emailRemoved++; }
    // 移除邮件的另一种写法
    if (fac.contact) delete fac.contact;
    const before = (fac.research_keywords || []).length;
    kwBefore += before;
    const cleaned = cleanKeywords(fac.research_keywords);
    kwAfter += cleaned.length;
    if (before > 0 && cleaned.length === 0) kwEmptied++;
    fac.research_keywords = cleaned;
    // 去掉明显是垃圾的 notes
    if (fac.notes && JUNK3.test(fac.notes) && fac.notes.length < 8) fac.notes = null;
  }
  fs.writeFileSync(f, JSON.stringify(data, null, 1), 'utf8');
  console.log(`  ${path.basename(f)}: ${(data.faculty || []).length} 人`);
}

console.log(`\n总人数 ${totalPeople}`);
console.log(`移除邮箱字段: ${emailRemoved}`);
console.log(`关键词 ${kwBefore} → ${kwAfter}（清理 ${kwBefore - kwAfter} 条垃圾）；清空者 ${kwEmptied} 人`);
