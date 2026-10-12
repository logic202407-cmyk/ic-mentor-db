// finalize_network.mjs — 从原始配对中提炼最终关系网络
//
// 关键改进：**「某人一作 + 另一人末位」不能直接判为师徒**——
// 两位教师合作时，资历浅的那位也常是一作。判据必须加上时间维度：
//   师徒 => 该配对论文集中出现在 P 学术生涯的**早期**（不晚于其首篇论文 + EARLY_WINDOW 年）
//           且 P 在这些论文里是学生角色（非末位），Q 始终是末位（导师角色）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROC = path.join(REPO, 'data', 'processed');

const MIN_ADV = 3;          // 至少 3 篇「学生一作+导师末位」
const EARLY_WINDOW = 6;     // 这些论文须落在其学术生涯前 6 年内
const MIN_COLLAB = 3;       // 合作关系至少共同署名 3 篇（提高可靠性）

const people = JSON.parse(fs.readFileSync(path.join(PROC, '_net_people.json'), 'utf8'));
const collab = JSON.parse(fs.readFileSync(path.join(PROC, '_net_collab.json'), 'utf8'));
const pairs = JSON.parse(fs.readFileSync(path.join(PROC, '_net_pair.json'), 'utf8'));
const papersByKey = JSON.parse(fs.readFileSync(path.join(PROC, '_net_papers_by_key.json'), 'utf8'));

// 每人的首篇论文年份（学术生涯起点）
const firstYear = {};
for (const [k, ps] of Object.entries(papersByKey)) {
  const ys = ps.map((p) => p.year).filter(Boolean);
  if (ys.length) firstYear[k] = Math.min(...ys);
}

// ── 1. 师徒边（加时间约束，分两档置信度）──
// 高置信：≥3 篇「学生一作+导师末位」且落在学生生涯早期
// 中置信：=2 篇且落在早期，且两人当前同校（同校 + 学生早期一作 + 导师末位，仍是强信号）
const advisorEdges = [];
const nearMiss = [];
for (const pr of pairs) {
  const [student, mentor] = pr.k.split('||');
  if (!people[student] || !people[mentor]) continue;
  const fy = firstYear[student];
  if (!fy) continue;
  const ys = pr.papers.map((p) => p.year).filter(Boolean).sort();
  const early = ys.filter((y) => y <= fy + EARLY_WINDOW);
  if (!early.length) continue;
  if (early[early.length - 1] - early[0] > EARLY_WINDOW) continue;
  const sameSchool = people[student].school === people[mentor].school;
  const sameDept = sameSchool && people[student].dept && people[student].dept === people[mentor].dept;

  let conf = null;
  if (pr.n >= MIN_ADV && early.length >= MIN_ADV) conf = early.length >= 4 ? 'high' : 'medium';
  else if (pr.n === 2 && early.length === 2 && sameSchool) conf = 'medium';
  if (!conf) { nearMiss.push({ s: student, t: mentor, n: pr.n, early: early.length }); continue; }

  advisorEdges.push({
    s: student, t: mentor, n: pr.n, early: early.length,
    span: `${early[0]}–${early[early.length - 1]}`,
    sameDept,
    studentSchool: people[student].school,
    mentorSchool: people[mentor].school,
    papers: pr.papers.slice(0, 6),
    confidence: conf,
  });
}
console.log(`师徒边: ${advisorEdges.length}（高置信 ${advisorEdges.filter((e) => e.confidence === 'high').length} / 中置信 ${advisorEdges.filter((e) => e.confidence === 'medium').length}）`);
console.log(`未采纳的弱配对: ${nearMiss.length}（多为平级合作，非师徒）`);

// ── 2. 合作边 ──
const advisorSet = new Set(advisorEdges.map((e) => `${e.s}||${e.t}`));
const collabEdges = [];
for (const c of collab) {
  if (c.n < MIN_COLLAB) continue;
  const [a, b] = c.k.split('||');
  if (advisorSet.has(`${a}||${b}`) || advisorSet.has(`${b}||${a}`)) continue;  // 已被师徒边覆盖
  collabEdges.push({ s: a, t: b, n: c.n, papers: c.papers.slice(0, 4) });
}
console.log(`合作边: ${collabEdges.length}（阈值 ≥${MIN_COLLAB} 篇）`);

// ── 3. 同门边（共享导师）──
const byMentor = new Map();
for (const e of advisorEdges) {
  if (!byMentor.has(e.t)) byMentor.set(e.t, []);
  byMentor.get(e.t).push(e.s);
}
const siblingEdges = [];
for (const [mentor, students] of byMentor) {
  for (let i = 0; i < students.length; i++) {
    for (let j = i + 1; j < students.length; j++) {
      siblingEdges.push({ s: students[i], t: students[j], via: mentor });
    }
  }
}
console.log(`同门边: ${siblingEdges.length}（来自 ${byMentor.size} 位导师）`);

// ── 4. 汇总参与节点 ──
const used = new Set();
for (const e of [...advisorEdges, ...collabEdges, ...siblingEdges]) { used.add(e.s); used.add(e.t); }
console.log(`涉及节点: ${used.size} 人`);

// ── 5. 导师产出榜（谁的学生最多）──
console.log('\n指导学生最多的导师 Top 20:');
const ranked = [...byMentor].map(([m, ss]) => ({ m, n: ss.length, ss })).sort((a, b) => b.n - a.n);
for (const r of ranked.slice(0, 20)) {
  const p = people[r.m];
  console.log(`  ${String(r.n).padStart(3)} 人  ${p.name.padEnd(9)} ${p.school.replace('中国科学院', '中科院').slice(0, 12).padEnd(13)} ${p.title}`);
  console.log(`         学生: ${r.ss.map((k) => people[k].name + '(' + people[k].school.replace('中国科学院', '中科院').slice(0, 6) + ')').join('、').slice(0, 150)}`);
}

fs.writeFileSync(path.join(PROC, 'network.json'), JSON.stringify({
  meta: {
    builtAt: new Date().toISOString().slice(0, 10),
    minAdv: MIN_ADV, earlyWindow: EARLY_WINDOW, minCollab: MIN_COLLAB,
    nodes: used.size, advisorEdges: advisorEdges.length, collabEdges: collabEdges.length, siblingEdges: siblingEdges.length,
  },
  people: Object.fromEntries([...used].map((k) => [k, people[k]])),
  advisor: advisorEdges, collab: collabEdges, sibling: siblingEdges,
}, null, 1), 'utf8');
console.log('\n已导出 data/processed/network.json');
