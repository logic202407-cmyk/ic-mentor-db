// fill_titles3.mjs — 严格版职称补全：先回滚自动补入的值，再用严格规则重抽
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');

// 1) 回滚此前自动补入的职称
let rolled = 0;
for (const key of fs.readdirSync(RAW)) {
  const rp = path.join(RAW, key, `roster_${key}.json`);
  if (!fs.existsSync(rp)) continue;
  const j = JSON.parse(fs.readFileSync(rp, 'utf8'));
  let changed = false;
  for (const f of j.faculty) {
    if (/职称由(个人)?主页?文本提取|职称由缓存页面文本提取/.test(f.notes || '')) {
      f.title = null;
      f.notes = (f.notes || '').split('；').filter((x) => !/职称由/.test(x)).join('；') || null;
      rolled++; changed = true;
    }
  }
  if (changed) fs.writeFileSync(rp, JSON.stringify(j, null, 1), 'utf8');
}
console.log(`回滚自动补入的职称 ${rolled} 条`);

// 2) 严格重抽
//    · 姓名必须真的出现在该文件里
//    · 职称必须紧邻姓名（前后 40 字内），避免抓到页面里其他人的头衔
//    · 不自动判定"院士"（风险最高，必须人工确认）
const TITLES = ['长聘教授', '准聘教授', '特聘教授', '讲席教授', '青年首席教授', '助理教授', '副教授', '教授',
  '正高级工程师', '高级工程师', '青年研究员', '助理研究员', '副研究员', '研究员', '讲师'];
const clean = (s) => s.replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/gi, ' ').replace(/\s+/g, ' ');

function pick(text, name) {
  const t = clean(text);
  let from = 0;
  for (let k = 0; k < 6; k++) {
    const pos = t.indexOf(name, from);
    if (pos < 0) return null;
    from = pos + name.length;
    // 姓名前后 40 字窗口
    const win = t.slice(Math.max(0, pos - 40), pos + name.length + 40);
    for (const kw of TITLES) {
      const i = win.indexOf(kw);
      if (i < 0) continue;
      const near = win.slice(Math.max(0, i - 12), i + kw.length + 6);
      if (/博士生?导师|硕士生?导师|研究生导师|指导教师|导师简介|招生/.test(near)) continue;
      return kw;
    }
  }
  return null;
}

function collect(dir, depth = 0) {
  const out = [];
  if (depth > 3 || !fs.existsSync(dir)) return out;
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    let st; try { st = fs.statSync(p); } catch { continue; }
    if (st.isDirectory()) { out.push(...collect(p, depth + 1)); continue; }
    if (/\.(html?|txt)$/i.test(f) && st.size < 3_000_000) out.push(p);
  }
  return out;
}

let filled = 0;
for (const key of fs.readdirSync(RAW)) {
  const rp = path.join(RAW, key, `roster_${key}.json`);
  if (!fs.existsSync(rp)) continue;
  const j = JSON.parse(fs.readFileSync(rp, 'utf8'));
  const todo = j.faculty.filter((f) => !f.title);
  if (!todo.length) continue;
  const blobs = collect(path.join(RAW, key))
    .filter((p) => !/lab_pages/.test(p))
    .map((p) => { try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } });
  let changed = false;
  const got = [];
  for (const f of todo) {
    for (const b of blobs) {
      if (!b.includes(f.name_cn)) continue;
      const t = pick(b, f.name_cn);
      if (t) { f.title = t; f.notes = (f.notes ? f.notes + '；' : '') + '职称由公开页面文本提取（严格窗口匹配）'; got.push(`${f.name_cn}=${t}`); filled++; changed = true; break; }
    }
  }
  if (changed) fs.writeFileSync(rp, JSON.stringify(j, null, 1), 'utf8');
  if (got.length) console.log(`  ${j.school} 补 ${got.length} 人: ${got.join('、')}`);
}
console.log(`\n严格规则共补 ${filled} 人`);
