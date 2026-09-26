// diag_low.mjs — 诊断低召回导师的真实原因
import fs from 'node:fs';
const UA = 'mentor-db/1.0 (mailto:ic-mentor-db@users.noreply.github.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const db = JSON.parse(fs.readFileSync('E:\\ytm\\mentor-db\\data\\processed\\mentor_ranked.json', 'utf8'));

const names = process.argv.slice(2);
const targets = names.length ? db.filter((d) => names.includes(d.name_cn)) : db.filter((d) => d.recall_risk === 'yes').slice(0, 8);

for (const d of targets) {
  console.log(`\n===== ${d.name_cn} | ${d.school} | ${d.title} | 计入论文 ${d.n_ic_papers} =====`);
  console.log('  关键词:', (d.research_keywords || []).join('、').slice(0, 70));
  // 直接查 Crossref：姓名 + 机构
  const q = encodeURIComponent(d.name_cn.split('').length ? '' : '');
  const nameGuess = pinyinish(d.name_cn);
  console.log('  尝试拼音:', nameGuess);
  const url = `https://api.crossref.org/works?query.author=${encodeURIComponent(nameGuess)}&rows=20&select=DOI,title,author,container-title,published&mailto=ic-mentor-db@users.noreply.github.com`;
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    const j = await r.json();
    let hit = 0;
    for (const it of j.message?.items || []) {
      const au = (it.author || []).map((a) => [a.given, a.family].filter(Boolean).join(' ')).join(', ');
      if (!new RegExp(nameGuess.split(' ').reverse().join('|'), 'i').test(au)) continue;
      const aff = (it.author || []).flatMap((a) => (a.affiliation || []).map((x) => x.name)).join(' ; ');
      if (!/xidian|tsinghua|peking|fudan|jiao\s*tong|zhejiang|nanjing|science and technology of china|southeast|electronic science/i.test(aff)) continue;
      hit++;
      if (hit <= 3) console.log(`    ✓ ${it.published?.['date-parts']?.[0]?.[0]} | ${(it['container-title'] || [''])[0].slice(0, 45)} | ${(it.title || [''])[0].slice(0, 55)}`);
    }
    console.log(`  Crossref 作者检索命中（机构校验后）: ${hit} / 前 20 条`);
  } catch (e) { console.log('  查询失败', e.message); }
  await sleep(400);
}

function pinyinish(cn) {
  // 极简：用已知映射无法覆盖，这里只做一个提示占位
  return cn;
}
