// ime_crawl.mjs — 抓取中科院微电子所导师列表 + 详情页
import fs from 'node:fs';
import path from 'node:path';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const RAW = 'E:\\ytm\\mentor-db\\data\\raw\\cas';
const DETAIL = path.join(RAW, 'ime_detail');
fs.mkdirSync(DETAIL, { recursive: true });

function toText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<\/(p|div|tr|li|h1|h2|h3|h4|br|dt|dd)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
    .split('\n').map((s) => s.replace(/[ \t\u00a0]+/g, ' ').trim()).filter(Boolean).join('\n');
}

function parseList(html, base) {
  const out = [];
  const re = /<dt[^>]*>\s*<a href="([^"]+)"[^>]*>[\s\S]*?<\/a>\s*<\/dt>\s*<dd[^>]*>([\s\S]*?)<\/dd>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const href = m[1];
    const body = m[2];
    const nm = body.match(/<h5[^>]*>([\s\S]*?)<\/h5>/i);
    if (!nm) continue;
    const name = nm[1].replace(/<[^>]+>/g, '').replace(/\s+/g, '').trim();
    const dir = body.replace(/<[^>]+>/g, ' ').replace(/研究方向：/, '').replace(/[\s\u3000]+/g, ' ').trim();
    if (!name) continue;
    out.push({ name, dir, url: new URL(href, base).href });
  }
  return out;
}

// ---- 1) collect list entries
const lists = [];
const bsdsBase = 'https://www.ime.ac.cn/kjrh/dsjs/bsds/';
const ssdsBase = 'https://www.ime.ac.cn/kjrh/dsjs/ssds/';
for (const [dir, base, files] of [
  ['博士导师', bsdsBase, ['index.html', 'index_1.html', 'index_2.html', 'index_3.html']],
  ['硕士导师', ssdsBase, ['index.html', 'index_1.html', 'index_2.html', 'index_3.html']],
]) {
  for (const f of files) {
    const fp = path.join(RAW, 'www.ime.ac.cn_kjrh_dsjs_' + (base.includes('bsds') ? 'bsds' : 'ssds') + '_' + (f === 'index.html' ? '' : f) + '.html');
    if (!fs.existsSync(fp)) { console.log('MISS ' + fp); continue; }
    const items = parseList(fs.readFileSync(fp, 'utf8'), base);
    for (const it of items) lists.push({ ...it, kind: dir });
    console.log(`${dir} ${f}: ${items.length}`);
  }
}
const byUrl = new Map();
for (const it of lists) {
  if (!byUrl.has(it.url)) byUrl.set(it.url, { ...it, kinds: new Set([it.kind]) });
  else byUrl.get(it.url).kinds.add(it.kind);
}
console.log('unique advisors: ' + byUrl.size);
fs.writeFileSync(path.join(RAW, 'ime_advisors_list.json'), JSON.stringify([...byUrl.values()].map((v) => ({ ...v, kinds: [...v.kinds] })), null, 1), 'utf8');

// ---- 2) fetch details
const entries = [...byUrl.values()];
let ok = 0, fail = 0;
for (let i = 0; i < entries.length; i++) {
  const e = entries[i];
  const local = path.join(DETAIL, e.url.split('/').pop().replace('.html', '') + '.html');
  if (fs.existsSync(local)) { ok++; continue; }
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 25000);
    const res = await fetch(e.url, { headers: { 'User-Agent': UA }, signal: ctl.signal });
    clearTimeout(t);
    if (!res.ok) { console.log(`[${res.status}] ${e.url}`); fail++; continue; }
    const buf = Buffer.from(await res.arrayBuffer());
    let html = new TextDecoder('utf-8').decode(buf);
    if ((html.match(/\uFFFD/g) || []).length > 5) html = new TextDecoder('gbk').decode(buf);
    fs.writeFileSync(local, html);
    fs.writeFileSync(local.replace(/\.html$/, '.txt'), toText(html));
    ok++;
    if (i % 20 === 0) console.log(`...${i}/${entries.length}`);
  } catch (err) { console.log(`[ERR ${err.message}] ${e.url}`); fail++; }
}
console.log(`detail ok=${ok} fail=${fail}`);
