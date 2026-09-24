// discover.mjs — 定位 OpenAlex 机构 ID 与 IC 领域关键期刊/会议 source ID
import fs from 'node:fs';
const UA = 'mentor-db/1.0 (mailto:mentor.db.builder@gmail.com)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      if (r.status === 429) { await sleep(1500 * (i + 1)); continue; }
      if (!r.ok) return { err: r.status };
      return await r.json();
    } catch (e) {
      if (i === tries - 1) return { err: e.message };
      await sleep(800);
    }
  }
  return { err: 'exhausted' };
}

const institutions = [
  'Tsinghua University', 'Tsinghua Shenzhen International Graduate School',
  'Fudan University', 'Shanghai Jiao Tong University', 'Zhejiang University',
  'Nanjing University', 'University of Science and Technology of China',
];

const sources = [
  'IEEE Journal of Solid-State Circuits',
  'IEEE Transactions on Circuits and Systems I: Regular Papers',
  'IEEE Transactions on Circuits and Systems II: Express Briefs',
  'IEEE Transactions on Very Large Scale Integration (VLSI) Systems',
  'IEEE International Solid-State Circuits Conference',
  'IEEE Custom Integrated Circuits Conference',
  'Symposium on VLSI Circuits',
  'IEEE Asian Solid-State Circuits Conference',
  'IEEE Transactions on Electron Devices',
  'IEEE Electron Device Letters',
  'IEEE Transactions on Microwave Theory and Techniques',
  'IEEE Journal of Solid-State Circuits',
  'IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems',
  'IEEE Transactions on Biomedical Circuits and Systems',
  'IEEE Transactions on Power Electronics',
  'Nature Electronics',
  'IEEE Symposium on VLSI Technology and Circuits',
];

const out = { institutions: {}, sources: {} };
for (const name of institutions) {
  const j = await get(`https://api.openalex.org/institutions?search=${encodeURIComponent(name)}&per-page=5&select=id,display_name,country_code,type,works_count,display_name_acronyms`);
  if (j.err) { console.log('INST ERR', name, j.err); continue; }
  out.institutions[name] = j.results;
  console.log('=== ' + name);
  for (const r of j.results) console.log(`   ${r.id} | ${r.display_name} | ${r.country_code} | works=${r.works_count}`);
  await sleep(250);
}
for (const name of sources) {
  const j = await get(`https://api.openalex.org/sources?search=${encodeURIComponent(name)}&per-page=4&select=id,display_name,type,works_count,issn_l`);
  if (j.err) { console.log('SRC ERR', name, j.err); continue; }
  out.sources[name] = j.results;
  console.log('=== ' + name);
  for (const r of j.results) console.log(`   ${r.id} | ${r.display_name} | ${r.type} | works=${r.works_count}`);
  await sleep(250);
}
fs.writeFileSync('E:\\ytm\\mentor-db\\data\\raw\\openalex_ids.json', JSON.stringify(out, null, 1));
console.log('\nsaved openalex_ids.json');
