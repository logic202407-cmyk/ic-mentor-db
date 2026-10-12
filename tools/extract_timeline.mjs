// extract_timeline.mjs — 抽取每人的「驻留时间段」：哪几年在哪个机构
//
// 这是关系推断的基础：只有先知道「A 在 2012-2017 于 X 大学」，
// 才能判断 B 是否在同期的同一机构，进而筛出候选关系。
//
// 两类来源：
//   ① 结构化模板（清华等校）："[1] 2006.9-2010.6 \n Harvard University \n 博士学位"
//   ② 自由文本："2006年本科毕业于北京大学；2011-2014年于慕尼黑工业大学从事博士后研究"
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const LB = path.join(REPO, 'data', 'raw', 'lab_pages');
const PROC = path.join(REPO, 'data', 'processed');

const clean = (s) => String(s || '')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;|&amp;/g, ' ')
  .replace(/\u00a0/g, ' ')
  .replace(/[\u200b\ufeff]/g, '')
  .replace(/[ \t]+/g, ' ')
  .replace(/\n{2,}/g, '\n')
  .trim();

// ── 页脚/版权噪声 ──
const FOOTER = /版权所有|ICP备|文保网安|京公网安|地址：|邮编：|电话：|传真：|Copyright|All Rights|技术支持|扫一扫|微信公众号/;
// ── 机构名白名单特征（避免把句子当成机构名）──
const INST_OK = /(?:大学|学院|研究院|研究所|实验室|理工学院|Universit|Institute|College|School|Laborator|ETH|EPFL|CNRS|MIT|NUS|NTU)/i;

function yr(s) { return parseInt(s, 10); }

// ── ① 结构化模板 ──
// 形如：教育经历 [1] 2006.9-2010.6 Harvard University 博士学位 [2] ...
const RE_STRUCT = /(?:^|\n)\s*\[?\d{1,2}\]?[\.、]?\s*((?:19|20)\d{2})\s*[\.\-\/年]\s*(\d{1,2})?\s*[-–—~至]+\s*((?:19|20)\d{2}|至今|今)\s*[\.\-\/年]?\s*(\d{1,2})?\s*\n?\s*([^\n]{2,90})/g;

// ── ② 自由文本：区间 + 机构 ──
const RE_RANGE = /((?:19|20)\d{2})\s*年?\s*[-–—~至]+\s*((?:19|20)\d{2})\s*年?\s*[^。；;\n]{0,20}?(?:在|于|就职于|加入|任职于|来到|进入)?\s*([^\s，,。；;、]{2,32}?(?:大学|学院|研究院|研究所|实验室|理工学院))/g;
// 单点：2015年博士毕业于XX大学
const RE_GRAD = /((?:19|20)\d{2})\s*年[^。；;\n]{0,22}?(?:毕业于|获|取得)[^。；;\n]{0,10}?([^\s，,。；;、]{2,32}?(?:大学|学院|研究院|研究所|实验室))/g;
// 至今：2018年至今 在 XX
const RE_SINCE = /((?:19|20)\d{2})\s*年?\s*至今[^。；;\n]{0,16}?([^\s，,。；;、]{2,32}?(?:大学|学院|研究院|研究所|实验室))/g;
// 进入/就读
const RE_ENTER = /((?:19|20)\d{2})\s*年[^。；;\n]{0,14}?(?:进入|就读于|考入|入学|加入)\s*([^\s，,。；;、]{2,32}?(?:大学|学院|研究院|研究所|实验室))/g;

const CUR = 2026;
const out = {};
let files = 0, withTl = 0;
const KIND = { 学历: 'edu', 工作: 'work' };

for (const f of fs.readdirSync(LB).filter((x) => x.endsWith('.txt'))) {
  let raw; try { raw = clean(fs.readFileSync(path.join(LB, f), 'utf8')); } catch { continue; }
  if (raw.length < 60) continue;
  files++;
  const key = f.replace(/\.txt$/, '');
  // 按句切分前先剔除页脚行
  const txt = raw.split('\n').filter((l) => !FOOTER.test(l)).join('\n');
  const tl = [];

  RE_STRUCT.lastIndex = 0;
  let m;
  while ((m = RE_STRUCT.exec(txt))) {
    const y1 = yr(m[1]);
    const y2 = /至今|今/.test(m[3]) ? CUR : yr(m[3]);
    const body = m[5].trim();
    if (y2 < y1 || y1 < 1950 || y2 > CUR + 1) continue;
    if (FOOTER.test(body)) continue;
    if (!INST_OK.test(body)) continue;
    const inst = (body.match(new RegExp(`[^\\s|]{2,40}?(?:${INST_OK.source.slice(2, -2)})`, 'i')) || [body])[0];
    tl.push({ y1, y2, inst: inst.slice(0, 40), kind: /博士|硕士|学士|学历|学位/.test(body) ? 'edu' : 'work', src: 'struct', raw: body.slice(0, 100) });
  }

  for (const [re, kind] of [[RE_RANGE, 'work'], [RE_GRAD, 'edu'], [RE_SINCE, 'work'], [RE_ENTER, 'edu']]) {
    re.lastIndex = 0;
    while ((m = re.exec(txt))) {
      const y1 = yr(m[1]);
      const y2 = kind === 'edu' && re === RE_GRAD ? y1 : (re === RE_SINCE ? CUR : yr(m[2] || m[1]));
      const inst = (m[3] || m[2] || '').trim();
      if (!inst || inst.length < 2 || FOOTER.test(inst)) continue;
      if (y1 < 1955 || y1 > CUR) continue;
      if (y2 < y1 || y2 > CUR + 1) continue;
      if (y2 - y1 > 12) continue;                       // 过长的区间多半是版权年份
      tl.push({ y1, y2: Math.max(y1, y2), inst: inst.slice(0, 40), kind, src: 'text', raw: txt.slice(Math.max(0, m.index - 10), m.index + 120).replace(/\s+/g, ' ') });
    }
  }

  // 去重
  const seen = new Set();
  const uniq = [];
  for (const e of tl) {
    const k = `${e.y1}-${e.y2}|${e.inst}`;
    if (seen.has(k)) continue;
    seen.add(k); uniq.push(e);
  }
  uniq.sort((a, b) => a.y1 - b.y1);
  if (uniq.length) { out[key] = uniq; withTl++; }
}

console.log(`扫描 ${files} 份页面 → 抽到时间段 ${withTl} 份 (${(withTl / files * 100).toFixed(1)}%)`);
const total = Object.values(out).reduce((a, b) => a + b.length, 0);
console.log(`时间段条目共 ${total} 条，人均 ${(total / Math.max(withTl, 1)).toFixed(1)} 条`);
fs.writeFileSync(path.join(PROC, 'timeline.json'), JSON.stringify(out, null, 1), 'utf8');

console.log('\n=== 样例（8 人）===');
let n = 0;
for (const [k, v] of Object.entries(out)) {
  if (n++ >= 8) break;
  console.log(`  ${k}`);
  for (const e of v.slice(0, 5)) console.log(`     ${e.y1}–${e.y2}  [${e.kind}]  ${e.inst}  (${e.src})`);
}
