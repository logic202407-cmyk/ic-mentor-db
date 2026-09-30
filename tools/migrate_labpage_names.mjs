// migrate_labpage_names.mjs — 把 lab_pages 文件名从「学校前4字_姓名」改为「school_key_姓名」
//
// 原因：中文学校名前 4 字会撞车——「清华大学」与「清华大学深圳国际研究生院」前 4 字相同；
//       中科院拆分为 6 个研究所后，6 个所的前 4 字均为「中国科学」。
// 做法：借助 lab_pages.json 中记录的 school + name 建立映射，重命名既有文件（不重新抓取）。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');
const LB = path.join(RAW, 'lab_pages');
const PROC = path.join(REPO, 'data', 'processed');

// school 名 -> school_key
const schoolKey = new Map();
for (const d of fs.readdirSync(RAW)) {
  const p = path.join(RAW, d, `roster_${d}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  schoolKey.set(j.school, j.school_key || d);
}

const pages = JSON.parse(fs.readFileSync(path.join(PROC, 'lab_pages.json'), 'utf8'));
let renamed = 0, missing = 0, conflict = 0;
const seen = new Set();
for (const p of pages) {
  const key = schoolKey.get(p.school);
  if (!key) { missing++; continue; }
  const oldName = `${p.school.slice(0, 4)}_${p.name}.txt`;
  const newName = `${key}_${p.name}.txt`;
  if (oldName === newName) continue;
  const op = path.join(LB, oldName), np = path.join(LB, newName);
  if (seen.has(newName)) { conflict++; continue; }
  seen.add(newName);
  if (!fs.existsSync(op)) { missing++; continue; }
  if (fs.existsSync(np)) { conflict++; continue; }
  fs.renameSync(op, np);
  renamed++;
}
console.log(`重命名 ${renamed} 个文件 | 源文件缺失 ${missing} | 目标冲突 ${conflict}`);
const rest = fs.readdirSync(LB).filter((f) => f.endsWith('.txt'));
console.log(`lab_pages 目录现有 ${rest.length} 个 txt`);
console.log('样例:', rest.slice(0, 5).join(', '));
