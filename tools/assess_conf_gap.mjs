// assess_conf_gap.mjs — 量化会议论文的覆盖情况与缺口
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));

// 每个 venue 的论文数（只统计计入 IC 的）
const v = new Map();
let confN = 0, jourN = 0;
for (const d of ranked) {
  for (const p of d.papers || []) {
    const key = (p.venue || '(无 venue)').slice(0, 58);
    v.set(key, (v.get(key) || 0) + 1);
    if (/conference|symposium|proceedings|workshop|ISSCC|CICC|VLSI|DAC|ICCAD|ISCA|MICRO|HPCA|ASPLOS|IEDM|RFIC|ESSCIRC|A-SSCC|ISCAS|FPGA|DATE/i.test(p.venue || '')) confN++;
    else jourN++;
  }
}
console.log(`计入 IC 的论文共 ${confN + jourN} 篇：会议 ${confN}（${(confN / (confN + jourN) * 100).toFixed(0)}%）| 期刊 ${jourN}`);
console.log('\nTop 30 venue:');
for (const [k, n] of [...v].sort((a, b) => b[1] - a[1]).slice(0, 30)) console.log(`  ${String(n).padStart(5)}  ${k}`);

// S 级会议的覆盖
const S_CONF = /ISSCC|International Solid-State Circuits Conference|VLSI Symposium|Symposium on VLSI|ISCA|MICRO|HPCA|ASPLOS|IEDM|International Electron Devices Meeting/i;
let sConf = 0;
const sConfPeople = new Set();
for (const d of ranked) for (const p of d.papers || []) if (S_CONF.test(p.venue || '')) { sConf++; sConfPeople.add(d.name_cn); }
console.log(`\nS 级会议论文: ${sConf} 篇，涉及 ${sConfPeople.size} 人`);
console.log('样例:');
let shown = 0;
for (const d of ranked) {
  const ps = (d.papers || []).filter((p) => S_CONF.test(p.venue || ''));
  if (!ps.length || shown >= 5) continue;
  shown++;
  console.log(`  ${d.name_cn}(${d.school.slice(0, 4)}) ${ps.length} 篇:`);
  for (const p of ps.slice(0, 2)) console.log(`     ${p.year} | ${(p.venue || '').slice(0, 50)} | ${(p.title || '').slice(0, 40)}`);
}
