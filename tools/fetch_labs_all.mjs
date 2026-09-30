// fetch_labs_all.mjs — 抓取推荐集导师的个人/课题组主页（已抓过的复用本地文本）
import fs from 'node:fs';
import path from 'node:path';

// ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');


const PROC = path.join(REPO, 'data', 'processed');
const RAWDIR = path.join(REPO, 'data', 'raw', 'lab_pages');
fs.mkdirSync(RAWDIR, { recursive: true });

// 抓取范围：全部有个人主页的导师（不限论文数——论文少的人也可能是活跃招生的青年教师）
const ranked = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_ranked.json'), 'utf8'));
const targets = ranked
  .filter((d) => d.homepage && /^https?:\/\//i.test(d.homepage))
  .map((d) => ({
    name_cn: d.name_cn, school: d.school, school_key: d.school_key,
    title: d.title, department: d.department,
    homepage: d.homepage, primary_direction: d.primary_direction,
  }));
console.log(`全库 ${ranked.length} 人 → 抓取目标 ${targets.length} 人`);

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 文件名用 school_key（中文学校名前 4 字会撞车：清华 vs 清华深研院、6 个中科院所）
const txtPath = (key, name) => path.join(RAWDIR, `${key}_${name}.txt`);

function toText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<\/(p|div|tr|li|h1|h2|h3|h4|br)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .split('\n').map((s) => s.replace(/[ \t\u00a0]+/g, ' ').trim()).filter(Boolean).join('\n');
}

const LAB_PAT = /([\u4e00-\u9fa5A-Za-z0-9\-\s]{2,30}(课题组|研究室|实验室|研究组|团队|研究中心|Group|Lab|Laboratory))/g;

async function grab(url) {
  for (const u of [url, url.replace(/^https:/, 'http:')]) {
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 22000);
      const r = await fetch(u, { headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9' }, signal: ctl.signal, redirect: 'follow' });
      clearTimeout(timer);
      if (!r.ok) continue;
      const buf = Buffer.from(await r.arrayBuffer());
      if (/pdf/i.test(r.headers.get('content-type') || '')) return { ok: false, reason: 'pdf' };
      let html = buf.toString('utf8');
      if ((html.match(/\uFFFD/g) || []).length > 5) { try { html = new TextDecoder('gbk').decode(buf); } catch { /* keep */ } }
      return { ok: true, url: u, html };
    } catch (e) { /* next */ }
  }
  return { ok: false, reason: 'fetch_failed' };
}

const results = new Array(targets.length);
let idx = 0, done = 0, reused = 0, fetched = 0;
const CONC = 8;
const t0 = Date.now();
async function worker() {
  while (true) {
    const i = idx++;
    if (i >= targets.length) return;
    const d = targets[i];
    const f = txtPath(d.school_key, d.name_cn);
    let rec = {
      name: d.name_cn, school: d.school, school_key: d.school_key, title: d.title, department: d.department,
      homepage: d.homepage, primary_direction: d.primary_direction,
      ai_score: d.ai_score, recruit_score: d.recruit_score, fit: d.fit,
      status: 'ok', lab_names: [], recruit_hits: [], page_title: null, text_len: 0,
    };
    let txt = null;
    if (fs.existsSync(f) && fs.statSync(f).size > 1500) {
      txt = fs.readFileSync(f, 'utf8');
      rec.status = 'ok(reused)';
      reused++;
    } else {
      const r = await grab(d.homepage);
      if (r.ok) {
        txt = toText(r.html);
        fs.writeFileSync(f, txt, 'utf8');
        const tm = r.html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
        rec.page_title = tm ? tm[1].replace(/\s+/g, ' ').trim().slice(0, 120) : null;
        fetched++;
      } else { rec.status = r.reason || 'fail'; }
    }
    if (txt) {
      rec.text_len = txt.length;
      const labs = new Set();
      for (const m of txt.matchAll(LAB_PAT)) { const v = m[1].trim(); if (v.length >= 4 && v.length <= 34) labs.add(v); }
      rec.lab_names = [...labs].slice(0, 6);
      // 注意：本项目不收录邮箱，因此不提取页面中的任何邮箱字段
    }
    results[i] = rec;
    done++;
    if (done % 50 === 0) console.log(`  ${done}/${targets.length} (新抓 ${fetched} / 复用 ${reused}, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    if (rec.status === 'ok') await sleep(100);
  }
}
await Promise.all(Array.from({ length: CONC }, worker));

const out = results.filter(Boolean);
fs.writeFileSync(path.join(PROC, 'lab_pages.json'), JSON.stringify(out, null, 1));
console.log(`\n完成 ${out.length} 人（新抓 ${fetched}，复用 ${reused}）`);
console.log('有主页文本:', out.filter((r) => r.text_len > 0).length);
console.log('识别到课题组名:', out.filter((r) => (r.lab_names || []).length).length);
