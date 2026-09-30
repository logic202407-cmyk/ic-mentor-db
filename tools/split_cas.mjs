// split_cas.mjs — 把中国科学院名录按研究所拆分为 6 份独立名录
//
// 目的：中科院 449 人原本归在一个「中国科学院」条目下，选所时不直观；
//       拆开后每个研究所独立成校，并各自配置精确的 Crossref 机构匹配规则，
//       同时提升论文归属的精度（避免所间串号）。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RAW = path.join(REPO, 'data', 'raw');

const SRC = path.join(RAW, 'cas', 'roster_cas.json');
const j = JSON.parse(fs.readFileSync(SRC, 'utf8'));

// 研究所 -> { key, 全称, Crossref 机构串匹配正则 }
const INSTITUTES = {
  '微电子研究所': {
    key: 'ime', name: '中国科学院微电子研究所',
    include: 'institute of microelectronics',
    exclude: null,
  },
  '半导体研究所': {
    key: 'semi', name: '中国科学院半导体研究所',
    include: 'institute of semiconductors?\\b',
    exclude: null,
  },
  '上海微系统与信息技术研究所': {
    key: 'simit', name: '中国科学院上海微系统与信息技术研究所',
    include: 'shanghai institute of microsystem|simit',
    exclude: null,
  },
  '计算技术研究所': {
    key: 'ict', name: '中国科学院计算技术研究所',
    include: 'institute of computing technology',
    exclude: null,
  },
  '自动化研究所': {
    key: 'ia', name: '中国科学院自动化研究所',
    include: 'institute of automation,?\\s*(the\\s*)?chinese academy|institute of automation',
    exclude: 'institute of automation.*(german|fraunhofer)',
  },
  '上海高等研究院': {
    key: 'sari', name: '中国科学院上海高等研究院',
    include: 'shanghai advanced research institute',
    exclude: null,
  },
};

const byInst = new Map();
for (const f of j.faculty) {
  const inst = f.department || '(未标注研究所)';
  if (!byInst.has(inst)) byInst.set(inst, []);
  byInst.get(inst).push(f);
}

const written = [];
for (const [inst, faculty] of byInst) {
  const meta = INSTITUTES[inst];
  if (!meta) { console.log(`⚠ 未登记的研究所，跳过：${inst}（${faculty.length} 人）`); continue; }
  const out = {
    school: meta.name,
    school_key: `cas_${meta.key}`,
    harvested_at: j.harvested_at,
    sources: j.sources,
    coverage_note: `【由「中国科学院」总名录拆分】原口径：${j.coverage_note}\n拆分后本所共 ${faculty.length} 人，department 字段统一为「${inst}」。`,
    faculty: faculty.map((f) => ({ ...f, department: inst })),
  };
  // 目录名用 cas_ime 形式，文件名 roster_cas_ime.json —— 与现有 tooling 的 <dir>/roster_<dir>.json 约定一致
  const dir = path.join(RAW, out.school_key);
  fs.mkdirSync(dir, { recursive: true });
  const fp = path.join(dir, `roster_${out.school_key}.json`);
  fs.writeFileSync(fp, JSON.stringify(out, null, 1), 'utf8');
  written.push({ key: out.school_key, school: meta.name, n: faculty.length, include: meta.include });
  console.log(`  ${out.school_key.padEnd(9)} ${String(faculty.length).padStart(4)} 人  ${meta.name}`);
}

console.log(`\n共拆分出 ${written.length} 个研究所名录`);
console.log('\n需要在 prepare_names.py 的 SCHOOL_META 中登记：');
for (const w of written) {
  console.log(`    "${w.key}": {"name": "${w.school}", "query": "${w.school.replace('中国科学院', 'Chinese Academy of Sciences, ')}", "include": r"${w.include}", "exclude": None},`);
}
console.log('\n原 cas 目录保留（未删除），拆分完成后可自行清理。');
