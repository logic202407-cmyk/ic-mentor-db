// make_screen_report.mjs — 生成「时间-机构重叠」重点筛查清单报告
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ov = JSON.parse(fs.readFileSync(path.join(PROC, 'overlap_screen.json'), 'utf8'));
const tl = JSON.parse(fs.readFileSync(path.join(PROC, 'timeline_clean.json'), 'utf8'));
const variants = JSON.parse(fs.readFileSync(path.join(PROC, 'name_variants.json'), 'utf8'));

const fk2pk = {};
for (const [sk, m] of Object.entries(variants)) for (const p of m.people) fk2pk[`${sk}_${p.name_cn}`] = `${m.school}|${p.name_cn}`;
const info = {};
for (const [fk, arr] of Object.entries(tl)) {
  const pk = fk2pk[fk]; if (!pk) continue;
  const [school, name] = pk.split('|');
  const p = variants[school2sk(school)]?.people.find((x) => x.name_cn === name);
  info[pk] = { name, school, title: p?.title || '', dept: p?.department || '', tl: arr };
}
function school2sk(s) { for (const [sk, m] of Object.entries(variants)) if (m.school === s) return sk; return null; }

const R = ov.results;
const byType = {};
for (const r of R) (byType[r.type] = byType[r.type] || []).push(r);

const L = [];
const nm = (k) => `${info[k]?.name || k.split('|')[1]}（${(info[k]?.school || k.split('|')[0]).replace('中国科学院', '中科院')}${info[k]?.title ? '·' + info[k].title : ''}）`;
const tlOf = (k) => (info[k]?.tl || []).map((e) => `${e.y1}–${e.y2} ${e.inst}`).join('；');

L.push('# 导师关系重点筛查清单（时间-机构重叠法）\n');
L.push(`> 生成日期：${new Date().toISOString().slice(0, 10)}`);
L.push('> 方法：从本人页面的学历/工作经历抽取**驻留时间段** → 找两人在同一机构的时间**重叠** → 要求重叠期内**有共同署名** → 列为重点对象\n');
L.push('---\n');
L.push('## 一、方法说明\n');
L.push('传统「共同署名反推」看不出两个人**是否真的在同一时期同一地方**。本方法补上了时间维度：\n');
L.push('```');
L.push('① 抽取经历时间段    "2012-2016 东北大学；2016-2025 北京大学"');
L.push('② 筛该时段的论文    只保留落在这些年份内的共同署名');
L.push('③ 判定时间重叠      两人同机构的时间段有交集');
L.push('④ 交叉验证          重叠期内确实有共同署名 => 才列为重点');
L.push('```\n');
L.push(`**本轮数据**：`);
L.push(`- 抽取到时间段的导师：**${Object.keys(tl).length} 人**（清洗后 ${Object.values(tl).reduce((a, b) => a + b.length, 0)} 条区间）`);
L.push(`- 同期同机构的重叠配对：**${(ov.perPerson ? Object.keys(ov.perPerson).length : 0)} 人参与**`);
L.push(`- 重叠期内**仍有共同署名**（即重点对象）：**${R.length} 对**\n`);
L.push('| 关系类型 | 对数 | 说明 |');
L.push('|:--|--:|:--|');
L.push(`| **师徒候选** | ${(byType['师徒（X为学生）']?.length || 0) + (byType['师徒（Y为学生）']?.length || 0)} | 一方稳定为一作、另一方稳定为末位 |`);
L.push(`| 共同指导 / 合作 | ${byType['共同指导/合作']?.length || 0} | 双方都有作为一作的论文 |`);
L.push(`| 同组 / 同事 | ${byType['同组/同事']?.length || 0} | 角色不固定，多为同课题组协作 |\n`);
L.push('---\n');

// 师徒候选详表
L.push('## 二、师徒候选（重点详查对象）\n');
const mentorLike = R.filter((r) => r.type.startsWith('师徒')).sort((a, b) => b.nInWindow - a.nInWindow);
if (!mentorLike.length) L.push('_无_\n');
for (const r of mentorLike) {
  const stu = r.type.includes('X为学生') ? r.a : r.b;
  const men = r.type.includes('X为学生') ? r.b : r.a;
  L.push(`### ${info[stu]?.name || stu.split('|')[1]} ← ${info[men]?.name || men.split('|')[1]}\n`);
  L.push(`| 项目 | 内容 |`);
  L.push(`|:--|:--|`);
  L.push(`| 学生 | ${nm(stu)} |`);
  L.push(`| 导师 | ${nm(men)} |`);
  L.push(`| 共同机构 | ${r.inst} |`);
  L.push(`| 时间重叠 | **${r.y1}–${r.y2}**（${r.years} 年） |`);
  L.push(`| 重叠期内共同署名 | **${r.nInWindow} 篇**（S 级 ${r.tierS} / A 级 ${r.tierA}） |`);
  L.push(`| 判定依据 | ${r.reason} |`);
  L.push(`| 学生经历 | ${tlOf(stu) || '（页面未提供）'} |`);
  L.push(`| 导师经历 | ${tlOf(men) || '（页面未提供）'} |`);
  L.push('');
  L.push('代表论文：');
  for (const s of r.samples) L.push(`- ${s}`);
  L.push('');
}
L.push('---\n');

// 共同指导/合作
L.push('## 三、共同指导 / 合作（双方均有主导论文）\n');
L.push('| 甲 | 乙 | 机构 | 时间重叠 | 同期共著 | S/A |');
L.push('|:--|:--|:--|:--|--:|:--|');
for (const r of R.filter((x) => x.type === '共同指导/合作').sort((a, b) => b.nInWindow - a.nInWindow)) {
  L.push(`| ${nm(r.a)} | ${nm(r.b)} | ${r.inst} | ${r.y1}–${r.y2} | ${r.nInWindow} | ${r.tierS}/${r.tierA} |`);
}
L.push('');

// 同组同事 top
L.push('## 四、同组 / 同事（长期共事，角色不固定）\n');
L.push('| 甲 | 乙 | 机构 | 时间重叠 | 同期共著 |');
L.push('|:--|:--|:--|:--|--:|');
for (const r of R.filter((x) => x.type === '同组/同事').sort((a, b) => b.nInWindow - a.nInWindow).slice(0, 40)) {
  L.push(`| ${nm(r.a)} | ${nm(r.b)} | ${r.inst} | ${r.y1}–${r.y2} | ${r.nInWindow} |`);
}
L.push('');

fs.writeFileSync(path.join(REPO, 'reports', '导师关系-重点筛查清单.md'), L.join('\n'), 'utf8');
console.log('saved reports/导师关系-重点筛查清单.md');
console.log(`重点对象 ${R.length} 对 | 师徒候选 ${mentorLike.length} | 共同指导 ${byType['共同指导/合作']?.length || 0} | 同组 ${byType['同组/同事']?.length || 0}`);
