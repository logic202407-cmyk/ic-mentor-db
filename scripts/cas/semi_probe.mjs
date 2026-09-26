// semi_probe.mjs — 探查半导体所导师列表页规模与分页
import fs from 'node:fs';
const html = fs.readFileSync('E:\\ytm\\mentor-db\\data\\raw\\cas\\bdt.semi.ac.cn_yanjiusheng_.html', 'utf8');
const links = [...html.matchAll(/<a[^>]+href=["']([^"']*\/contents\/695\/(\d+)\.html)["'][^>]*>([\s\S]*?)<\/a>/gi)];
console.log('advisor links: ' + links.length);
for (const l of links.slice(0, 5)) console.log(l[2] + ' :: ' + l[3].replace(/<[^>]+>/g, '').trim().slice(0, 90));
// pagination
const pag = [...html.matchAll(/href=["']([^"']*(?:page|list|index)[^"']*)["']/gi)].map((m) => m[1]);
console.log('pag candidates: ' + JSON.stringify([...new Set(pag)].slice(0, 30)));
const more = html.match(/createPageHTML[\s\S]{0,300}/);
console.log('createPageHTML: ' + (more ? more[0].slice(0, 300) : 'none'));
// total count hints
const cnt = html.match(/(共|total)[^<]{0,40}(条|页|record)/g);
console.log('counts: ' + JSON.stringify(cnt));
// ids
const ids = links.map((l) => +l[2]).sort((a, b) => a - b);
console.log('id min/max: ' + ids[0] + '/' + ids[ids.length - 1]);
