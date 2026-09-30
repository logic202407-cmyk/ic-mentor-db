// clone_selftest.mjs — 全新克隆自检：确认只依赖已入库文件的脚本都能跑通
//
// 用途：公开仓库的核心承诺之一是"别人克隆下来能复现"。
// 本脚本区分两类工具：
//   A 类：只读已入库产物（mentor_ranked / curated / lab_pages / 名录）→ 克隆后必须能跑
//   B 类：需要中间产物（enriched_* / name_variants）→ 克隆后应给出友好提示而非抛栈
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const TRACKED_INPUTS = ['data/processed/mentor_ranked.json', 'data/processed/curated.json', 'data/processed/lab_pages.json'];
console.log('=== 已入库的输入文件 ===');
for (const f of TRACKED_INPUTS) {
  const p = path.join(REPO, f);
  console.log(`  ${fs.existsSync(p) ? '✓' : '✗'} ${f}${fs.existsSync(p) ? ` (${(fs.statSync(p).size / 1048576).toFixed(2)} MB)` : ''}`);
}

// A 类：克隆后必须可运行
const A = ['summary.mjs', 'check_doc_numbers.mjs', 'check_html_ui.mjs', 'lint_html_js.mjs',
  'list_tiers.mjs', 'anomaly_check.mjs', 'assess_filter.mjs', 'strip_emails.mjs', 'dbstats.mjs'];
console.log('\n=== A 类工具（只依赖已入库文件，克隆后应可运行）===');
let failA = 0;
for (const s of A) {
  const p = path.join(REPO, 'tools', s);
  if (!fs.existsSync(p)) { console.log(`  ⚠ ${s} 不存在`); continue; }
  const extra = s === 'lint_html_js.mjs' ? ['reports/导师推荐.html', 'reports/导师库.html'] : [];
  try {
    execFileSync(process.execPath, [p, ...extra], { cwd: REPO, stdio: 'pipe', timeout: 300000 });
    console.log(`  ✓ ${s}`);
  } catch (e) {
    const msg = (e.stderr || e.stdout || '').toString().split('\n').filter((x) => /Error|错误/.test(x))[0] || e.message;
    console.log(`  ✗ ${s}: ${msg.slice(0, 110)}`);
    failA++;
  }
}

// B 类：缺中间产物时应友好退出（退出码 0 且有提示）
console.log('\n=== B 类工具（需中间产物，缺失时应友好提示）===');
const NEED = path.join(REPO, 'data', 'processed', 'name_variants.json');
const B = ['contamination_scan.mjs'];
for (const s of B) {
  const p = path.join(REPO, 'tools', s);
  if (!fs.existsSync(p)) { console.log(`  ⚠ ${s} 不存在`); continue; }
  if (fs.existsSync(NEED)) { console.log(`  – ${s}: 本机有中间产物，跳过缺失场景测试`); continue; }
  try {
    const out = execFileSync(process.execPath, [p], { cwd: REPO, stdio: 'pipe', timeout: 300000 }).toString();
    console.log(`  ✓ ${s}: 友好提示（${out.split('\n')[0].slice(0, 60)}）`);
  } catch (e) {
    console.log(`  ✗ ${s}: 抛异常而非友好提示`);
    failA++;
  }
}
console.log(failA ? `\n❌ ${failA} 项未通过` : '\n✅ 克隆自检通过');
process.exit(failA ? 1 : 0);
