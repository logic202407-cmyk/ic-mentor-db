// strip_emails.mjs — 兜底清洗：从所有对外产物中移除邮箱字段与邮箱地址
import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'E:\\ytm\\mentor-db';
const TARGETS = ['data/processed', 'data/raw', 'reports'];
const CHECK_ONLY = process.argv.includes('--check');   // --check：只报告不修改（供 CI 使用）
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const EMAIL_KEY = /^(email|e_mail|mail|page_email|db_email|contact_email|邮箱)$/i;

let jsonKeys = 0, jsonVals = 0, csvCols = 0, csvCells = 0, mdHits = 0, htmlHits = 0, files = 0, leaked = 0;
const write = (p, txt) => { if (!CHECK_ONLY) fs.writeFileSync(p, txt, 'utf8'); };

function walk(o, file) {
  if (Array.isArray(o)) return o.map((x) => walk(x, file));
  if (o && typeof o === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(o)) {
      if (EMAIL_KEY.test(k)) { jsonKeys++; continue; }
      out[k] = walk(v, file);
    }
    return out;
  }
  // 字符串值里嵌的邮箱（例如主页招生原话中的"请发送简历至〈邮箱〉"）同样要清洗
  if (typeof o === 'string' && EMAIL_RE.test(o)) {
    EMAIL_RE.lastIndex = 0;
    jsonVals++;
    return o.replace(EMAIL_RE, '（联系方式见官网主页）');
  }
  return o;
}

for (const t of TARGETS) {
  const dir = path.join(ROOT, t);
  if (!fs.existsSync(dir)) continue;
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    if (!fs.statSync(p).isFile()) continue;
    files++;
    const ext = path.extname(f).toLowerCase();
    if (ext === '.json') {
      let data;
      try { data = JSON.parse(fs.readFileSync(p, 'utf8')); } catch { continue; }
      const before = JSON.stringify(data).match(EMAIL_RE)?.length || 0;
      const cleaned = walk(data, f);
      const after = JSON.stringify(cleaned).match(EMAIL_RE)?.length || 0;
      if (before !== after || jsonKeys) write(p, JSON.stringify(cleaned, null, 1));
      if (CHECK_ONLY && before) { leaked += before; console.log(`  [残留] ${f}: ${before} 个邮箱地址`); }
      else if (after) console.log(`  [警告] ${f} 仍有 ${after} 个邮箱地址`);
    } else if (ext === '.csv') {
      let txt = fs.readFileSync(p, 'utf8');
      // ① 单元格文本里嵌的邮箱一并替换
      const inText = (txt.match(EMAIL_RE) || []).length;
      if (inText) { txt = txt.replace(EMAIL_RE, '（联系方式见官网主页）'); csvCells += inText; }
      const lines = txt.split('\n');
      if (CHECK_ONLY && inText) { leaked += inText; console.log('  [残留] ' + f + ': 单元格含 ' + inText + ' 个邮箱'); continue; }
      if (!lines.length) { if (inText) write(p, txt); continue; }
      const hdr = lines[0].replace(/^\ufeff/, '').split(',').map((h) => h.replace(/^"|"$/g, ''));
      const drop = hdr.map((h, i) => (EMAIL_KEY.test(h) ? i : -1)).filter((i) => i >= 0);
      if (drop.length) {
        const out = lines.map((ln) => {
          if (!ln.trim()) return ln;
          const cells = ln.split('","');
          return cells.filter((_, i) => !drop.includes(i)).join('","');
        });
        txt = out.join('\n');
        csvCols += drop.length;
        console.log(`  ${f}: 移除列 ${drop.map((i) => hdr[i]).join(',')}`);
      }
      if (inText || drop.length) write(p, txt);
    } else if (ext === '.md' || ext === '.html') {
      let txt = fs.readFileSync(p, 'utf8');
      const hits = txt.match(EMAIL_RE) || [];
      // 仅豁免 GitHub 匿名邮箱（项目自身标识）
      const real = hits.filter((x) => !/users\.noreply\.github\.com$/i.test(x));
      if (real.length) {
        txt = txt.replace(EMAIL_RE, (m) => (/users\.noreply\.github\.com$/i.test(m) ? m : '（联系方式见官网主页）'));
        write(p, txt);
        if (ext === '.md') mdHits += real.length; else htmlHits += real.length;
        if (CHECK_ONLY) leaked += real.length;
        console.log(`  ${f}: 替换 ${real.length} 个邮箱地址`);
      }
    }
  }
}
console.log(`\n扫描 ${files} 个文件`);
console.log(`JSON 移除邮箱字段: ${jsonKeys} ｜ JSON 文本内替换: ${jsonVals} ｜ CSV 列: ${csvCols} 单元格: ${csvCells} ｜ MD: ${mdHits} ｜ HTML: ${htmlHits}`);
if (CHECK_ONLY) {
  console.log(leaked ? `\n❌ 检查未通过：仍有 ${leaked} 处邮箱残留` : '\n✅ 检查通过：未发现任何邮箱残留');
  process.exit(leaked ? 1 : 0);
}
