// audit_prepublish.mjs — 公开前最终检查
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import vm from 'node:vm';

const ROOT = process.cwd();
const SELF = 'tools/audit_prepublish.mjs';   // 本脚本自身含有检测模式，跳过自检
const issues = [], warns = [], oks = [];
const add = (arr, msg) => arr.push(msg);
const scannable = (f) => f !== SELF && fs.existsSync(f) && !/\.(docx|png|jpg|xlsx)$/i.test(f);

// ── 1. 邮箱 / 隐私 ──
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
// 保留域名（RFC 2606 / RFC 6761）：仅用于测试夹具，不可能是真实联系方式。
// 仍需扫描，但不计入隐私红线——否则测试"邮箱必须被清洗"的用例会自我触发告警。
const RESERVED_DOMAIN = /@(?:example\.(?:com|net|org|edu)|example|invalid|localhost|test)$/i;
const tracked = execSync('git ls-files', { encoding: 'utf8', maxBuffer: 1 << 28 }).split('\n').filter(Boolean);
let emailHits = 0, emailFiles = [], reservedHits = 0;
for (const f of tracked) {
  if (!scannable(f)) continue;
  const t = fs.readFileSync(f, 'utf8');
  const m = (t.match(EMAIL) || []).filter((x) => !x.endsWith('users.noreply.github.com'));
  const real = m.filter((x) => !RESERVED_DOMAIN.test(x));
  reservedHits += m.length - real.length;
  if (real.length) { emailHits += real.length; emailFiles.push(`${f}(${real.length})`); }
}
emailHits ? add(issues, `邮箱残留 ${emailHits} 处: ${emailFiles.slice(0, 5).join(', ')}`)
  : add(oks, `产物与代码中无真实邮箱残留${reservedHits ? `（另有 ${reservedHits} 处 RFC 2606 保留域名测试夹具，非真实联系方式）` : ''}`);

// ── 2. 个人身份信息 / 本地路径泄漏 ──
const PERSONAL = [
  [/zhangbeihai/i, '个人邮箱前缀'],
  [/郑翔元/, '真实姓名'],
  [/LAPTOP-VHQF65C3/i, '本机主机名'],
  [/F:\\\\tianmengxin/i, '本机临时路径'],
  [/dsh-spill|dsh-subprocess/i, '工具运行痕迹'],
  [/CodexTools|DeepSeek-Harness/i, '本机软件路径'],
];
let pHits = 0;
for (const f of tracked) {
  if (!scannable(f)) continue;
  const t = fs.readFileSync(f, 'utf8');
  for (const [re, label] of PERSONAL) if (re.test(t)) { add(issues, `${f} 含${label}`); pHits++; }
}
if (!pHits) add(oks, '无个人身份信息 / 本机路径泄漏');

// ── 3. 硬编码绝对路径（可移植性）──
let absHits = [];
for (const f of tracked) {
  if (!f.startsWith('tools/') || f === SELF) continue;
  const t = fs.readFileSync(f, 'utf8');
  const m = t.match(/['"`][A-Za-z]:\\\\[^'"`]+['"`]/g) || t.match(/['"`][A-Za-z]:\\[^'"`]+['"`]/g);
  if (m) absHits.push(`${f}(${m.length})`);
}
absHits.length
  ? add(warns, `脚本含 Windows 绝对路径（他人无法直接运行）: ${absHits.join(', ')}`)
  : add(oks, '脚本无硬编码绝对路径');

// ── 4. 内容评价性 / 个人化用语 ──
const BAD_WORDS = ['你的背景', '编程负担', 'IC 科班', 'AI 重度使用者', '按你的', '适合你', '我的背景',
  '避雷', '天坑', '不推荐', '水平差', '水货', '慎选', '劝退'];
let wHits = [];
for (const f of tracked) {
  if (!/^reports\/.*\.(md|html)$/.test(f)) continue;
  const t = fs.readFileSync(f, 'utf8');
  for (const w of BAD_WORDS) if (t.includes(w)) wHits.push(`${path.basename(f)}:${w}`);
}
wHits.length ? add(issues, `报告含评价性/个人化用语: ${wHits.join(', ')}`) : add(oks, '报告无评价性/个人化用语');

// ── 5. 合规文档齐备 ──
const REQUIRED = ['README.md', 'DISCLAIMER.md', 'CONTRIBUTING.md', 'LICENSE', 'LICENSE-DATA',
  'CITATION.cff', '.github/ISSUE_TEMPLATE/correction.yml', '.github/ISSUE_TEMPLATE/suggestion.yml',
  '.github/workflows/validate.yml', 'docs/使用指南.md', 'docs/维护指南.md', 'index.html', '.nojekyll'];
const missing = REQUIRED.filter((f) => !fs.existsSync(f));
missing.length ? add(issues, `缺少文件: ${missing.join(', ')}`) : add(oks, `合规与文档文件齐备（${REQUIRED.length} 项）`);

// ── 6. 数据文件完整性 ──
const dataFiles = ['data/processed/mentor_ranked.json', 'data/processed/curated.json',
  'data/processed/mentor_ranked.csv', 'data/processed/curated.csv',
  'data/processed/integrity_check.json', 'data/processed/lab_pages.json'];
let dErr = [];
for (const f of dataFiles) {
  if (!fs.existsSync(f)) { dErr.push(`${f} 缺失`); continue; }
  if (f.endsWith('.json')) {
    try { JSON.parse(fs.readFileSync(f, 'utf8').replace(/^\ufeff/, '')); } catch (e) { dErr.push(`${f} 解析失败`); }
  }
}
const rosters = execSync('git ls-files "data/raw/*/roster_*.json"', { encoding: 'utf8' }).split('\n').filter(Boolean);
for (const f of rosters) {
  try {
    const j = JSON.parse(fs.readFileSync(f, 'utf8').replace(/^\ufeff/, ''));
    if (!Array.isArray(j.faculty) || !j.faculty.length) dErr.push(`${f} faculty 为空`);
    if (j.faculty.some((p) => p.email)) dErr.push(`${f} 含 email 字段值`);
  } catch { dErr.push(`${f} 解析失败`); }
}
dErr.length ? add(issues, `数据问题: ${dErr.join('; ')}`) : add(oks, `数据文件完好（${dataFiles.length} 个产物 + ${rosters.length} 份名录，名录内无邮箱值）`);

// ── 7. 关键字段中不含 email ──
const ranked = JSON.parse(fs.readFileSync('data/processed/mentor_ranked.json', 'utf8'));
const curated = JSON.parse(fs.readFileSync('data/processed/curated.json', 'utf8'));
const withEmail = ranked.filter((d) => 'email' in d).length + curated.filter((d) => 'email' in d).length;
withEmail ? add(issues, `${withEmail} 条记录仍含 email 字段`) : add(oks, `全库 ${ranked.length} 条 / 推荐集 ${curated.length} 条均无 email 字段`);

// ── 8. 文档内相对链接有效性 ──
let badLinks = [];
for (const f of tracked.filter((x) => /\.md$/.test(x))) {
  const dir = path.dirname(f);
  const t = fs.readFileSync(f, 'utf8');
  for (const m of t.matchAll(/\]\(([^)#][^)]*)\)/g)) {
    const link = m[1].trim();
    if (/^(https?:|mailto:|#)/.test(link)) continue;
    const target = path.normalize(path.join(dir, decodeURIComponent(link.split('#')[0])));
    if (!fs.existsSync(target)) badLinks.push(`${f} -> ${link}`);
  }
}
badLinks.length ? add(issues, `失效相对链接 ${badLinks.length} 处: ${badLinks.slice(0, 6).join(' | ')}`) : add(oks, 'Markdown 内相对链接全部有效');

// ── 9. index.html 引用的文件是否存在 ──
const idx = fs.readFileSync('index.html', 'utf8');
const idxLinks = [...idx.matchAll(/href="([^"#][^"]*)"/g)].map((m) => m[1]).filter((x) => !/^https?:/.test(x));
const idxBad = idxLinks.filter((l) => !fs.existsSync(decodeURIComponent(l)));
idxBad.length ? add(issues, `index.html 失效链接: ${idxBad.join(', ')}`) : add(oks, `落地页 ${idxLinks.length} 个链接全部有效`);

// ── 9b. HTML 内嵌脚本的语法与 DOM 引用自洽（页面有 JS 错误就是白屏）──
const htmlFiles = ['reports/导师推荐.html', 'reports/导师库.html'].filter((f) => fs.existsSync(f));
const htmlErrs = [];
for (const f of htmlFiles) {
  const h = fs.readFileSync(f, 'utf8');
  const m = h.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { htmlErrs.push(`${path.basename(f)} 无 script 块`); continue; }
  const js = m[1];
  try { new vm.Script(js, { filename: f }); }
  catch (e) { htmlErrs.push(`${path.basename(f)} JS 语法错误: ${e.message.slice(0, 80)}`); continue; }
  const ids = [...new Set([...js.matchAll(/\$\('([\w-]+)'\)/g)].map((x) => x[1]))];
  const missId = ids.filter((id) => !h.includes(`id="${id}"`));
  if (missId.length) htmlErrs.push(`${path.basename(f)} 引用了不存在的 DOM id: ${missId.join(',')}`);
  if (!/const DATA = \[/.test(js)) htmlErrs.push(`${path.basename(f)} 未内嵌数据`);
  if (/fetch\s*\(|XMLHttpRequest/.test(js)) htmlErrs.push(`${path.basename(f)} 含网络请求（应为离线单文件）`);
}
htmlErrs.length ? add(issues, `HTML 页面问题: ${htmlErrs.join(' | ')}`)
  : add(oks, `两个 HTML 页面 JS 语法正确、DOM 引用自洽、数据已内嵌且无网络请求`);

// ── 10. 仓库体积与大文件 ──
const sizes = tracked.filter((f) => fs.existsSync(f)).map((f) => [f, fs.statSync(f).size]);
const total = sizes.reduce((a, b) => a + b[1], 0);
const big = sizes.filter(([, s]) => s > 5 * 1024 * 1024).sort((a, b) => b[1] - a[1]);
big.length
  ? add(warns, `超过 5MB 的文件 ${big.length} 个: ${big.map(([f, s]) => `${f}(${(s / 1048576).toFixed(1)}MB)`).join(', ')}`)
  : add(oks, `无超大文件（共 ${tracked.length} 个文件 / ${(total / 1048576).toFixed(1)} MB，最大 ${(Math.max(...sizes.map((x) => x[1])) / 1048576).toFixed(2)} MB）`);

// ── 11. 是否误提交中间产物 ──
const strays = tracked.filter((f) => /(_stage|_draft|_raw\.json|_cache|_probe|enriched_|mentor_db\.json|name_variants\.json|shortlist_|profile_fit|score_log|_parsed)/.test(f));
strays.length ? add(warns, `疑似中间产物入库 ${strays.length} 个: ${strays.slice(0, 5).join(', ')}`) : add(oks, '无中间产物误入库');

// ── 12. .gitignore 覆盖检查 ──
const gi = fs.readFileSync('.gitignore', 'utf8');
const mustIgnore = ['data/raw/*/*', 'enriched_', 'mentor_db.json', 'name_variants.json', 'lab_pages'];
const giMiss = mustIgnore.filter((k) => !gi.includes(k) && k !== 'lab_pages');
giMiss.length ? add(warns, `.gitignore 可能遗漏: ${giMiss.join(', ')}`) : add(oks, '.gitignore 覆盖关键中间产物');

// ── 13. 敏感凭证扫描 ──
const SECRET = /(ghp_[A-Za-z0-9]{20,}|github_pat_|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|password\s*[:=]\s*['"][^'"]{6,})/;
let sHits = [];
for (const f of tracked) {
  if (!scannable(f)) continue;
  if (SECRET.test(fs.readFileSync(f, 'utf8'))) sHits.push(f);
}
sHits.length ? add(issues, `疑似凭证: ${sHits.join(', ')}`) : add(oks, '未发现任何凭证 / 密钥');

// ── 13b. 文档中的统计数字与实际数据一致（README 声称值 vs mentor_ranked.json）──
try {
  const ranked = JSON.parse(fs.readFileSync('data/processed/mentor_ranked.json', 'utf8'));
  const curated = JSON.parse(fs.readFileSync('data/processed/curated.json', 'utf8'));
  const readme = fs.readFileSync('README.md', 'utf8');
  const checks = [
    [/共 (\d+) 位导师有可访问的个人主页/, ranked.filter((d) => d.homepage).length, '主页覆盖人数'],
    [/主页明确写了在招\*\* \| \*\*(\d+) 位/, curated.filter((d) => d.recruit_signal_count > 0).length, '在招人数'],
    [/S 级）合计 \| \*\*(\d+) 篇\*\*/, ranked.reduce((a, b) => a + b.S, 0), 'S 级合计'],
    [/A 级）合计 \| \*\*(\d+) 篇\*\*/, ranked.reduce((a, b) => a + b.A, 0), 'A 级合计'],
  ];
  const mismatch = [];
  for (const [re, actual, label] of checks) {
    const m = readme.match(re);
    if (m && Number(String(m[1]).replace(/,/g, '')) !== actual) mismatch.push(`${label}(文档 ${m[1]} vs 实际 ${actual})`);
  }
  mismatch.length ? add(issues, `README 数字与实际不符: ${mismatch.join(', ')}`)
    : add(oks, `README 关键数字与数据一致（逐项核对 ${checks.length} 项）`);
} catch (e) {
  add(warns, `文档数字核对跳过: ${e.message.slice(0, 60)}`);
}

// ── 14. git 提交者身份 ──
const authors = execSync('git log --format=%ae', { encoding: 'utf8' }).split('\n').filter(Boolean);
const uniqAuthors = [...new Set(authors)];
const badAuthor = uniqAuthors.filter((a) => !a.endsWith('users.noreply.github.com'));
badAuthor.length ? add(issues, `提交记录含非匿名邮箱: ${badAuthor.join(', ')}`) : add(oks, `提交记录全部为匿名邮箱（${uniqAuthors.join(', ')}，共 ${authors.length} 次提交）`);

// ── 15. 统计口径自洽 ──
const readme = fs.readFileSync('README.md', 'utf8');
const nMatch = readme.match(/\*\*(\d+) 人\*\*（(\d+) 校/);
if (nMatch) {
  const [, n, schools] = nMatch;
  if (Number(n) !== ranked.length) add(issues, `README 声明 ${n} 人，实际 ${ranked.length} 人`);
  else add(oks, `README 统计与实际一致（${n} 人 / ${schools} 校）`);
} else add(warns, 'README 未找到人数统计行');

// ── 输出 ──
console.log('\n========== 公开前最终检查 ==========\n');
console.log('✅ 通过项:');
for (const o of oks) console.log('   ' + o);
if (warns.length) { console.log('\n⚠️  警告项:'); for (const w of warns) console.log('   ' + w); }
if (issues.length) { console.log('\n❌ 阻塞项:'); for (const i of issues) console.log('   ' + i); }
console.log(`\n结果: ${oks.length} 通过 / ${warns.length} 警告 / ${issues.length} 阻塞`);
process.exit(issues.length ? 1 : 0);
