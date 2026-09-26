// semi_crawl.mjs — 抓取并解析半导体所导师简介
import fs from 'node:fs';
import path from 'node:path';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const RAW = 'E:\\ytm\\mentor-db\\data\\raw\\cas';
const DETAIL = path.join(RAW, 'semi_detail');
fs.mkdirSync(DETAIL, { recursive: true });

function toText(html) {
  return html.replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ').replace(/<\/(p|div|tr|li|h1|h2|h3|h4|br|dt|dd)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
    .split('\n').map((s) => s.replace(/[ \t\u00a0]+/g, ' ').trim()).filter(Boolean).join('\n');
}

const html = fs.readFileSync(path.join(RAW, 'bdt.semi.ac.cn_yanjiusheng_.html'), 'utf8');
const links = [...html.matchAll(/<a[^>]+href=["']([^"']*\/contents\/695\/(\d+)\.html)["'][^>]*>([\s\S]*?)<\/a>/gi)];
const seen = new Set();
const recs = [];
for (const l of links) {
  const id = l[2];
  if (seen.has(id)) continue;
  seen.add(id);
  const raw = l[3].replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, '').trim();
  recs.push({ id, raw, url: 'https://bdt.semi.ac.cn/yanjiusheng/contents/695/' + id + '.html' });
}
console.log('records: ' + recs.length);

const LABOR = '(半导体物理实验室|半导体集成技术中心|半导体照明研发中心|光电子材料与器件重点实验室|固态光电信息技术实验室|高速电路与神经网络实验室|光电系统实验室|全固态光源实验室|集成技术中心|纳米光电子实验室|半导体材料科学重点实验室|半导体集成技术工程研究中心|超晶格与量子器件实验室|微电子学与固体电子学|其他)';
const TITLE = '(正高级工程师|教授级高级工程师|青年研究员|项目研究员|研究员|副研究员|高级工程师|特别研究助理|博士后)';

const out = [];
for (const r of recs) {
  const raw = r.raw;
  const nameM = raw.match(/^([\u4e00-\u9fa5]{2,4})/);
  const name = nameM ? nameM[1] : null;
  const labM = raw.match(new RegExp(LABOR));
  const titleM = raw.match(new RegExp(TITLE));
  const phd = /博士生导师|博导/.test(raw);
  const master = /硕士生导师|硕导/.test(raw);
  const majorM = raw.match(/招生专业[：:]([\s\S]*?)(?=研究方向|$)/);
  const dirM = raw.match(/研究方向[：:]([\s\S]*)$/);
  out.push({
    id: r.id, url: r.url, name_cn: name, raw,
    lab: labM ? labM[1] : null,
    title: titleM ? titleM[1] : null,
    is_phd: phd, is_master: master,
    major: majorM ? majorM[1].trim() : null,
    research: dirM ? dirM[1].trim() : null,
  });
}
fs.writeFileSync(path.join(RAW, 'semi_parsed.json'), JSON.stringify(out, null, 1), 'utf8');
console.log('no name: ' + out.filter((o) => !o.name_cn).length);
console.log('no lab: ' + out.filter((o) => !o.lab).length);
console.log('no title: ' + out.filter((o) => !o.title).length);
console.log('no research: ' + out.filter((o) => !o.research).length);
console.log('no major: ' + out.filter((o) => !o.major).length);
for (const o of out.filter((x) => !x.research || !x.title || !x.lab)) console.log('PROB ' + o.id + ' :: ' + o.raw.slice(0, 120));
const labs = {};
for (const o of out) labs[o.lab || 'NULL'] = (labs[o.lab || 'NULL'] || 0) + 1;
console.log('LABS ' + JSON.stringify(labs));
const titles = {};
for (const o of out) titles[o.title || 'NULL'] = (titles[o.title || 'NULL'] || 0) + 1;
console.log('TITLES ' + JSON.stringify(titles));

// ---- fetch details
let ok = 0, fail = 0;
for (let i = 0; i < out.length; i++) {
  const e = out[i];
  const local = path.join(DETAIL, e.id + '.html');
  if (fs.existsSync(local)) { ok++; continue; }
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 20000);
    const res = await fetch(e.url, { headers: { 'User-Agent': UA }, signal: ctl.signal });
    clearTimeout(t);
    if (!res.ok) { console.log(`[${res.status}] ${e.url}`); fail++; continue; }
    const buf = Buffer.from(await res.arrayBuffer());
    let h = new TextDecoder('utf-8').decode(buf);
    if ((h.match(/\uFFFD/g) || []).length > 5) h = new TextDecoder('gbk').decode(buf);
    fs.writeFileSync(local, h);
    fs.writeFileSync(local.replace(/\.html$/, '.txt'), toText(h));
    ok++;
  } catch (err) { console.log(`[ERR ${err.message}] ${e.url}`); fail++; }
}
console.log(`detail ok=${ok} fail=${fail}`);
