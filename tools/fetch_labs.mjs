// fetch_labs.mjs — 抓取候选导师个人/课题组主页，提取招生信息与联系方式
// 用法: node fetch_labs.mjs [topN]
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const RAWDIR = 'E:\\ytm\\mentor-db\\data\\raw\\lab_pages';
fs.mkdirSync(RAWDIR, { recursive: true });

const list = JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_2027.json'), 'utf8'));
const TOPN = Number(process.argv[2] || 120);
const targets = list.slice(0, TOPN).filter((d) => d.homepage);
console.log(`抓取 ${targets.length} 个主页（候选前 ${TOPN}）`);

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 招生相关信号
const RECRUIT_PAT = /(招收|招生|招聘|招募|欢迎报考|报考|推免|免试推荐|夏令营|研招|名额|课题组招|本组招|加入我们|加入课题组|有意者|联系我|申请|博士生|硕士生|研究生招生|openings?|join us|positions? available|recruit)/gi;
const LAB_PAT = /([\u4e00-\u9fa5A-Za-z0-9\-\s]{2,30}(课题组|研究室|实验室|研究组|团队|研究中心|Group|Lab|Laboratory))/g;

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

async function grab(url) {
  for (const u of [url, url.replace(/^https:/, 'http:')]) {
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 25000);
      const r = await fetch(u, { headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9' }, signal: ctl.signal, redirect: 'follow' });
      clearTimeout(timer);
      if (!r.ok) continue;
      const buf = Buffer.from(await r.arrayBuffer());
      const ct = r.headers.get('content-type') || '';
      if (/pdf/i.test(ct)) return { ok: false, reason: 'pdf' };
      let html = buf.toString('utf8');
      if ((html.match(/\uFFFD/g) || []).length > 5) { try { html = new TextDecoder('gbk').decode(buf); } catch { /* keep */ } }
      return { ok: true, url: u, html };
    } catch (e) { /* try next */ }
  }
  return { ok: false, reason: 'fetch_failed' };
}

const results = new Array(targets.length);
let idx = 0, done = 0;
const CONC = 8;
const t0 = Date.now();
async function worker() {
  while (true) {
    const i = idx++;
    if (i >= targets.length) return;
    const d = targets[i];
    const r = await grab(d.homepage);
    const rec = {
      name: d.name_cn, school: d.school, title: d.title, department: d.department,
      homepage: d.homepage, db_email: d.email, primary_direction: d.primary_direction,
      ai_score: d.ai_score, recruit_score: d.recruit_score, fit: d.fit,
      status: r.ok ? 'ok' : (r.reason || 'fail'),
      lab_names: [], recruit_hits: [], page_email: null, page_title: null, text_len: 0,
    };
    if (r.ok) {
      const txt = toText(r.html);
      rec.text_len = txt.length;
      const tm = r.html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      rec.page_title = tm ? tm[1].replace(/\s+/g, ' ').trim().slice(0, 120) : null;
      const labs = new Set();
      for (const m of txt.matchAll(LAB_PAT)) { const v = m[1].trim(); if (v.length >= 4 && v.length <= 34) labs.add(v); }
      rec.lab_names = [...labs].slice(0, 6);
      const em = txt.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g) || [];
      rec.page_email = em.length ? [...new Set(em)].slice(0, 3).join(' ; ') : null;
      const seen = new Set();
      for (const m of txt.matchAll(RECRUIT_PAT)) {
        const s = Math.max(0, m.index - 45), e = Math.min(txt.length, m.index + 90);
        const snip = txt.slice(s, e).replace(/\n/g, ' ');
        const key = snip.slice(0, 40);
        if (seen.has(key)) continue;
        seen.add(key);
        rec.recruit_hits.push({ kw: m[0], snippet: snip });
        if (rec.recruit_hits.length >= 6) break;
      }
      // 判断页面是否"像招生页"
      const yearHit = /20(2[4-9])/.test(txt);
      rec.has_recent_year = yearHit;
      fs.writeFileSync(path.join(RAWDIR, `${d.school.slice(0, 4)}_${d.name_cn}.txt`), txt, 'utf8');
    }
    results[i] = rec;
    done++;
    if (done % 20 === 0) console.log(`  ${done}/${targets.length} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    await sleep(120);
  }
}
await Promise.all(Array.from({ length: CONC }, worker));

fs.writeFileSync(path.join(PROC, 'lab_pages.json'), JSON.stringify(results.filter(Boolean), null, 1));
const ok = results.filter((r) => r && r.status === 'ok');
const withRecruit = ok.filter((r) => r.recruit_hits.length);
const withLab = ok.filter((r) => r.lab_names.length);
console.log(`\n成功抓取 ${ok.length}/${targets.length}`);
console.log(`页面含招生相关词: ${withRecruit.length}`);
console.log(`识别到课题组/实验室名称: ${withLab.length}`);
console.log(`页面自带邮箱: ${ok.filter((r) => r.page_email).length}`);
console.log('\n示例（含招生信号的）:');
for (const r of withRecruit.slice(0, 12)) {
  console.log(`  ${r.name_cn}(${r.school.slice(0, 4)}) 实验室=${r.lab_names.slice(0, 2).join('/')} | ${r.recruit_hits[0].snippet.slice(0, 70)}`);
}
