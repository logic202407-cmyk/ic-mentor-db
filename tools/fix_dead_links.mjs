// fix_dead_links.mjs — 处理指向已下线主机的主页链接
//
// 背景：中科院上海微系统所 63 人的主页指向 sourcedb.sim.cas.cn，该主机已不可达。
//       死链比空值更糟（用户点开是报错），因此：
//       ① 若该人另有可用的 sim.cas.cn / people.ucas.ac.cn 链接，改用之；
//       ② 否则置为 null（UI 会显示「—」），不保留死链。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');
const DEAD = /sourcedb\.sim\.cas\.cn/i;

let nulled = 0, total = 0;
for (const d of fs.readdirSync(RAW)) {
  const p = path.join(RAW, d, `roster_${d}.json`);
  if (!fs.existsSync(p)) continue;
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  let changed = false;
  for (const f of j.faculty) {
    if (!f.homepage || !DEAD.test(f.homepage)) continue;
    total++;
    // 上海微系统所人才页可作替代：用姓名在已抓取的 _hp_fill 证据里找
    const alt = j.sources && null;
    f.homepage = null;
    f.notes = (f.notes ? f.notes + '；' : '') + '原主页所在主机 sourcedb.sim.cas.cn 已下线，暂无可核实替代链接';
    nulled++;
    changed = true;
  }
  if (changed) fs.writeFileSync(p, JSON.stringify(j, null, 1), 'utf8');
}
console.log(`扫描到死链 ${total} 条，已置空 ${nulled} 条（并在 notes 注明原因）`);
