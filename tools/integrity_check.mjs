// integrity_check.mjs — 用 Crossref 逐 DOI 核查撤稿 / 更正 / 关注声明（update-to 关系）
// 用法: node integrity_check.mjs <topN|all> [schoolKey]
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CONC = Number(process.env.CONC || 10);

const db = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_db.json'), 'utf8'));
const arg = process.argv[2] || 'top120';
const schoolFilter = process.argv[3] || null;
let people = db.filter((r) => (r.papers || []).length);
if (schoolFilter) people = people.filter((r) => r.school_key === schoolFilter);
if (arg !== 'all') {
  const n = arg.startsWith('top') ? Number(arg.slice(3)) : Number(arg);
  people = people.slice(0, n);
}
// 每人最多核查其被引最高的 MAXP 篇
const MAXP = Number(process.env.MAXP || 12);

const tasks = [];
for (const p of people) {
  const list = [...(p.papers || [])].sort((a, b) => (b.cited || 0) - (a.cited || 0)).slice(0, MAXP);
  for (const x of list) if (x.doi) tasks.push({ person: p, doi: x.doi, title: x.title, year: x.year });
}
console.log(`待核查 DOI: ${tasks.length}（${people.length} 位导师，每人最多 ${MAXP} 篇）`);

const RETRACT = /retract|withdraw|remov/i;
const CONCERN = /concern|expression of concern|corrigend|correction|erratum|update/i;

const results = [];
let idx = 0, done = 0;
const t0 = Date.now();
async function worker() {
  while (true) {
    const i = idx++;
    if (i >= tasks.length) return;
    const t = tasks[i];
    let rec = { name: t.person.name_cn, school: t.person.school, doi: t.doi, year: t.year, title: t.title, status: 'ok', updates: [] };
    try {
      const r = await fetch(`https://api.crossref.org/works/${encodeURIComponent(t.doi)}?mailto=ic-mentor-db@users.noreply.github.com`,
        { headers: { 'User-Agent': UA } });
      if (r.ok) {
        const m = (await r.json()).message || {};
        const ups = [...(m['updated-by'] || []), ...(m['update-to'] || [])];
        for (const u of ups) {
          const ty = String(u.type || '');
          rec.updates.push({ type: ty, doi: u.DOI, label: u.label });
          if (RETRACT.test(ty) || RETRACT.test(String(u.label || ''))) rec.status = 'retracted';
          else if (CONCERN.test(ty) || CONCERN.test(String(u.label || ''))) rec.status = rec.status === 'retracted' ? 'retracted' : 'corrected';
        }
      } else rec.status = 'fetch_' + r.status;
    } catch (e) { rec.status = 'err'; }
    results.push(rec);
    done++;
    if (done % 500 === 0) console.log(`  ${done}/${tasks.length} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    await sleep(60);
  }
}
await Promise.all(Array.from({ length: Math.min(CONC, tasks.length) }, worker));

fs.writeFileSync(path.join(PROC, 'integrity_check.json'), JSON.stringify(results, null, 1));
const bad = results.filter((r) => r.status === 'retracted' || r.status === 'corrected');
console.log(`\n完成 ${results.length} 条，耗时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
console.log('撤稿:', results.filter((r) => r.status === 'retracted').length,
  '| 更正/关注:', results.filter((r) => r.status === 'corrected').length,
  '| 其他异常:', results.filter((r) => r.status.startsWith('fetch') || r.status === 'err').length);
for (const b of bad) console.log(`  [${b.status}] ${b.name}(${b.school.slice(0, 4)}) ${b.year} ${String(b.title).slice(0, 55)} | ${b.updates.map((u) => u.type).join(',')}`);
