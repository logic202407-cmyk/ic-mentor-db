// sync_roster_fields.mjs — 把名录（roster）中的身份字段同步回 enriched_*.json
// 名录是身份信息的唯一真源；消歧改名、主页规范化、关键词清洗后都需要同步。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const RAW = path.join(REPO, 'data', 'raw');

const FIELDS = ['name_cn', 'title', 'department', 'is_phd_advisor', 'research_keywords', 'homepage', 'notes'];
let synced = 0, renamed = 0, missing = 0;
const ambiguous = [];

for (const key of fs.readdirSync(RAW)) {
  const rp = path.join(RAW, key, `roster_${key}.json`);
  const ep = path.join(PROC, `enriched_${key}.json`);
  if (!fs.existsSync(rp) || !fs.existsSync(ep)) continue;
  const roster = JSON.parse(fs.readFileSync(rp, 'utf8'));
  const e = JSON.parse(fs.readFileSync(ep, 'utf8'));
  const byName = new Map(e.people.map((p) => [p.name_cn, p]));
  for (const f of roster.faculty) {
    const p = byName.get(f.name_cn);
    if (!p) { missing++; continue; }
    for (const k of FIELDS) {
      const v = f[k] === undefined ? null : f[k];
      if (JSON.stringify(p[k]) !== JSON.stringify(v)) { p[k] = v; synced++; }
    }
  }
  // 消歧改名后：把 enriched 里的旧名（基名）改名为名录中的新名，而不是删除。
  // 若基名对应多个消歧名（如两个「刘明」），无法自动判定归属，则保留原样并告警。
  const rosterNames = new Set(roster.faculty.map((f) => f.name_cn));
  const base2full = new Map();
  for (const f of roster.faculty) {
    const base = f.name_cn.replace(/[（(][^）)]*[）)]/g, '');
    if (!base2full.has(base)) base2full.set(base, []);
    base2full.get(base).push(f.name_cn);
  }
  for (const p of e.people) {
    if (rosterNames.has(p.name_cn)) continue;
    const cands = (base2full.get(p.name_cn) || []).filter((n) => !e.people.some((q) => q.name_cn === n));
    if (cands.length === 1) { p.name_cn = cands[0]; renamed++; }
    else if (cands.length > 1) { ambiguous.push(`${key}|${p.name_cn} -> ${cands.join(' / ')}`); }
  }
  fs.writeFileSync(ep, JSON.stringify(e, null, 1), 'utf8');
}
console.log(`同步字段更新 ${synced} 处 | 重命名 ${renamed} 条 | 名录有但 enriched 无 ${missing} 条`);
if (ambiguous.length) {
  console.log(`\n⚠ 基名对应多个消歧名，需人工确认归属（${ambiguous.length} 条）：`);
  for (const a of ambiguous) console.log('   ' + a);
}
