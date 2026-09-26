// ime_parse.mjs — 解析微电子所导师详情页
import fs from 'node:fs';
import path from 'node:path';
const RAW = 'E:\\ytm\\mentor-db\\data\\raw\\cas';
const DETAIL = path.join(RAW, 'ime_detail');
const list = JSON.parse(fs.readFileSync(path.join(RAW, 'ime_advisors_list.json'), 'utf8'));

const STOP_RE = '(承担科研项目情况|代表论著|获奖及荣誉|社会任职|研究方向|所属部门|通讯地址|简\\s*历|姓名|性别|职称|职务|学历|电话|传真|电子邮件|专利申请|专著|教育活动|指导学生|个人主页|当前位置|工作简历|教育背景)';

function field(txt, label) {
  const i = txt.indexOf(label);
  if (i < 0) return null;
  let tail = txt.slice(i + label.length);
  const m = new RegExp(STOP_RE + '\\s*[：:]').exec(tail);
  if (m) tail = tail.slice(0, m.index);
  else {
    const nl = tail.indexOf('\n');
    if (nl >= 0) tail = tail.slice(0, nl);
  }
  const v = tail.replace(/[\s\u3000]+/g, ' ').trim();
  return v || null;
}

const rows = [];
for (const e of list) {
  const id = e.url.split('/').pop().replace('.html', '');
  const fp = path.join(DETAIL, id + '.txt');
  if (!fs.existsSync(fp)) { console.log('MISS ' + id); continue; }
  const txt = fs.readFileSync(fp, 'utf8').replace(/\u3000/g, ' ');
  rows.push({
    name_cn: e.name,
    title: field(txt, '职称：'),
    duty: field(txt, '职务：'),
    dept: field(txt, '所属部门：'),
    research: field(txt, '研究方向：'),
    honor: field(txt, '获奖及荣誉：'),
    kinds: e.kinds,
    url: e.url,
  });
}
fs.writeFileSync(path.join(RAW, 'ime_parsed.json'), JSON.stringify(rows, null, 1), 'utf8');
console.log('parsed ' + rows.length);
console.log('no title: ' + rows.filter((r) => !r.title).length);
console.log('no dept: ' + rows.filter((r) => !r.dept).length);
console.log('no research: ' + rows.filter((r) => !r.research).length);
console.log('long dept: ' + rows.filter((r) => r.dept && r.dept.length > 30).length);
const titles = {};
for (const r of rows) titles[r.title || 'NULL'] = (titles[r.title || 'NULL'] || 0) + 1;
console.log('TITLES ' + JSON.stringify(titles));
const depts = {};
for (const r of rows) depts[r.dept || 'NULL'] = (depts[r.dept || 'NULL'] || 0) + 1;
console.log('DEPTS ' + JSON.stringify(depts, null, 0));
for (const r of rows.filter((x) => x.dept && x.dept.length > 30)) console.log('LONGDEPT ' + r.name_cn + ' :: ' + r.dept.slice(0, 120));
