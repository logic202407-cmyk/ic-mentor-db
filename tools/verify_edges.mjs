// verify_edges.mjs — 抽查边的证据，验证可靠性
import fs from 'fs';
const net = JSON.parse(fs.readFileSync('data/processed/network.json', 'utf8'));

function show(studentName, mentorName) {
  const e = net.advisor.find((x) => net.people[x.s]?.name === studentName && net.people[x.t]?.name === mentorName);
  if (!e) { console.log(`  [未找到] ${studentName} -> ${mentorName}`); return; }
  console.log(`\n${studentName}（${net.people[e.s].school}）→ ${mentorName}（${net.people[e.t].school}）`);
  console.log(`  证据: ${e.n} 篇「${studentName}一作 + ${mentorName}末位」，集中期 ${e.span}，早期命中 ${e.early} 篇，置信度 ${e.confidence}`);
  for (const p of e.papers.slice(0, 5)) {
    console.log(`    ${p.year} | ${(p.venue || '').slice(0, 40)}`);
    console.log(`      ${(p.title || '').slice(0, 100)}`);
    console.log(`      学生机构: ${(p.aff || '').slice(0, 70)} | 导师机构: ${(p.mentorAff || '').slice(0, 60)}`);
  }
}

console.log('===== 抽查 1：可疑边（资深教授被列为学生）=====');
show('洪志良', '朱樟明');
console.log('\n===== 抽查 2：已知真实的师徒（赵巍胜的学生）=====');
show('康旺', '赵巍胜');
console.log('\n===== 抽查 3：已知真实的师徒（郝跃的学生）=====');
show('张金风', '郝跃');
console.log('\n===== 抽查 4：跨校（学生已去别校任职）=====');
show('蔡浩', '赵巍胜');
show('李学清', '杨华中');

// 统计：学生与导师当前是否同校
console.log('\n\n===== 统计：师徒边中学生的现单位分布 =====');
let same = 0, diff = 0;
const crossSchool = [];
for (const e of net.advisor) {
  if (net.people[e.s].school === net.people[e.t].school) same++;
  else { diff++; crossSchool.push(e); }
}
console.log(`  同校 ${same} 条 | 跨校 ${diff} 条（跨校多为学生毕业去别处任教，是强信号）`);
console.log('\n  跨校师徒样例（前 15）：');
for (const e of crossSchool.slice(0, 15)) {
  console.log(`    ${net.people[e.s].name}(${net.people[e.s].school.replace('中国科学院', '中科院').slice(0, 8)}) ← ${net.people[e.t].name}(${net.people[e.t].school.replace('中国科学院', '中科院').slice(0, 8)}) | ${e.n}篇 ${e.span}`);
}

// 置信度分布
const conf = {};
for (const e of net.advisor) conf[e.confidence] = (conf[e.confidence] || 0) + 1;
console.log('\n  置信度分布:', JSON.stringify(conf));
