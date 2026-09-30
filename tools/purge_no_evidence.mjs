// purge_no_evidence.mjs — 删除「零可核实线索」的教师条目
//
// 收录标准：必须在公开渠道可核实到**至少一项**证据——
//   ① 有可核实论文（n_ic_papers > 0），或
//   ② 有可访问的个人/课题组主页（homepage 非空）。
// 两者皆无者，学生拿到也做不了任何事（既不了解方向，也无法联系），故移除。
//
// 注意：有论文但缺主页、或有主页但论文少的人**不删**——
//       前者论文证据充分（如郑纬民 22 篇、宋志棠 54 篇），
//       后者有招生与联系价值（如青年教师、Charles M. Lieber）。
//
// 用法：node tools/purge_no_evidence.mjs          # 预演
//       node tools/purge_no_evidence.mjs --apply  # 实际删除
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');
const APPLY = process.argv.includes('--apply');

const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const targets = ranked.filter((d) => (d.n_ic_papers || 0) === 0 && !d.homepage);
console.log(`零可核实线索者：${targets.length} 人\n`);
for (const d of targets) console.log(`  ${d.school} | ${d.name_cn} | ${d.title || '职称未知'} | ${d.department || '—'}`);

if (!targets.length) { console.log('\n无需处理'); process.exit(0); }
if (!APPLY) { console.log('\n（预演模式，未做改动。加 --apply 实际删除）'); process.exit(0); }

// 按 school 定位名录文件
const schoolKey = new Map();
for (const d of fs.readdirSync(RAW)) {
  const p = path.join(RAW, d, `roster_${d}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  schoolKey.set(j.school, p);
}

const removedLog = [];
let totalRemoved = 0;
for (const [school, p] of schoolKey) {
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  const before = j.faculty.length;
  const kill = new Set(targets.filter((t) => t.school === school).map((t) => t.name_cn));
  if (!kill.size) continue;
  const kept = j.faculty.filter((f) => !kill.has(f.name_cn));
  j.faculty = kept;
  // 记录移除原因，便于追溯
  j.removed_no_evidence = [...(j.removed_no_evidence || []), ...kill];
  j.coverage_note = (j.coverage_note || '') +
    `\n【移除】${kill.size} 人因在公开渠道既检索不到可核实论文、也无可访问的个人主页，已移除：${[...kill].join('、')}。`;
  fs.writeFileSync(p, JSON.stringify(j, null, 1), 'utf8');
  console.log(`  ${school}: ${before} → ${kept.length}（移除 ${kill.size}）`);
  for (const n of kill) removedLog.push(`${school}\t${n}`);
  totalRemoved += kill.size;
}

fs.writeFileSync(path.join(RAW, 'crossref', 'purged_no_evidence.tsv'), removedLog.join('\n') + '\n', 'utf8');
console.log(`\n共移除 ${totalRemoved} 人；清单已存 data/raw/crossref/purged_no_evidence.tsv`);
