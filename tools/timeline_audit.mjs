// timeline_audit.mjs — 时间线数据质量体检（可复用的回归检查）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const tl = JSON.parse(fs.readFileSync(path.join(PROC, 'timeline_clean.json'), 'utf8'));
const raw = JSON.parse(fs.readFileSync(path.join(PROC, 'timeline.json'), 'utf8'));

let bad = 0;
const checks = [];
const add = (ok, msg) => { checks.push({ ok, msg }); if (!ok) bad++; };

// 1) 机构名不得含句子片段
const DIRTY = /毕业于|获得|取得|攻读|学位|期间|从事|方向|先后|分别|年|月/;
const dirty = [];
for (const [k, arr] of Object.entries(tl)) for (const e of arr) if (DIRTY.test(e.inst)) dirty.push(`${k}: ${e.inst}`);
add(dirty.length === 0, `机构名含句子片段: ${dirty.length} 处${dirty.length ? ' → ' + dirty.slice(0, 3).join(' / ') : ''}`);

// 2) 机构名不得是裸二级学院（但历史上的独立学院名、国家重点实验室属正常）
const BARE = /^(?:[\u4e00-\u9fa5]{2,10})?(?:学院|系|实验室|中心)$/;
const FOREIGN = /大学|Universit|Institute|College|School|瑞士|美国|英国|德国|法国|日本|新加坡|国立|联邦|理工|科技|工业|师范|医科|电子|交通|农业|财经|政法|国家|重点/;
const bare = [];
for (const [k, arr] of Object.entries(tl)) for (const e of arr) if (BARE.test(e.inst) && !FOREIGN.test(e.inst)) bare.push(`${k}: ${e.inst}`);
add(bare.length === 0, `裸二级学院未回填: ${bare.length} 处${bare.length ? ' → ' + bare.slice(0, 3).join(' / ') : ''}`);

// 3) 同机构区间不得重叠（合并后应互不相交）
let overlap = 0;
for (const [k, arr] of Object.entries(tl)) {
  const byInst = {};
  for (const e of arr) (byInst[e.inst] = byInst[e.inst] || []).push(e);
  for (const [inst, a] of Object.entries(byInst)) {
    a.sort((x, y) => x.y1 - y.y1);
    for (let i = 1; i < a.length; i++) if (a[i].y1 <= a[i - 1].y2) { overlap++; if (overlap <= 3) console.log(`    重叠样例: ${k} ${inst} ${a[i - 1].y1}-${a[i - 1].y2} / ${a[i].y1}-${a[i].y2}`); }
  }
}
add(overlap === 0, `同机构区间仍重叠: ${overlap} 处`);

// 4) 年份范围合理
const badYear = [];
for (const [k, arr] of Object.entries(tl)) for (const e of arr) if (e.y1 < 1955 || e.y2 > 2027 || e.y2 < e.y1) badYear.push(`${k}: ${e.y1}-${e.y2}`);
add(badYear.length === 0, `年份越界: ${badYear.length} 处`);

// 5) 单人区间数不应过多（>8 条多半是抽取噪声）
const many = Object.entries(tl).filter(([, a]) => a.length > 8);
add(many.length <= 5, `单人区间数 >8 的: ${many.length} 人${many.length ? ' → ' + many.slice(0, 3).map(([k, a]) => `${k}(${a.length})`).join(' ') : ''}`);

// 6) 保留率
const keepRate = Object.keys(tl).length / Math.max(Object.keys(raw).length, 1);
add(keepRate > 0.75, `清洗保留率 ${(keepRate * 100).toFixed(1)}%（原始 ${Object.keys(raw).length} → 清洗后 ${Object.keys(tl).length}）`);

// 7) 机构种类不应爆炸（>2000 说明没归一）
const insts = new Set();
for (const arr of Object.values(tl)) for (const e of arr) insts.add(e.inst);
add(insts.size < 1200, `机构种类 ${insts.size} 个`);

// 8) 中英文校名是否还有未归一（同一实体两种写法）
const enLeft = [...insts].filter((x) => /[A-Za-z]/.test(x));
add(enLeft.length < 60, `仍含英文的机构名 ${enLeft.length} 个${enLeft.length ? ' → ' + enLeft.slice(0, 4).join(' / ') : ''}`);

console.log('═══ 时间线数据质量体检 ═══');
for (const c of checks) console.log(`  ${c.ok ? '✓' : '✗'} ${c.msg}`);
console.log(`\n${bad ? '❌ ' + bad + ' 项未通过' : '✅ 全部通过'}`);
console.log(`\n规模：${Object.keys(tl).length} 人 / ${Object.values(tl).reduce((a, b) => a + b.length, 0)} 条区间 / ${insts.size} 个机构`);
process.exit(bad ? 1 : 0);
