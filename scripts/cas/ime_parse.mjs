// ime_parse.mjs — 解析微电子所导师详情页
import fs from 'node:fs';
import path from 'node:path';
const RAW = 'E:\\ytm\\mentor-db\\data\\raw\\cas';
const DETAIL = path.join(RAW, 'ime_detail');
const list = JSON.parse(fs.readFileSync(path.join(RAW, 'ime_advisors_list.json'), 'utf8'));

function field(txt, label) {
  const i = txt.indexOf(label);
  if (i < 0) return null;
  let tail = txt.slice(i + label.length);
  const stop = tail.search(/\n(姓名|性别|职称|职务|学历|电话|传真|电子邮件|所属部门|通讯地址|简历|社会任职|研究方向|承担科研项目|代表论著|专著|专利申请|获奖及荣誉|个人主页|教育活动|指导学生)/);
  if (stop > 0) tail = tail.slice(0, stop);
  const v = tail.replace(/[\s\u3000]+/g, ' ').trim();
  return v || null;
}

const rows = [];
for (const e of list) {
  const id = e.url.split('/').pop().replace('.html', '');
  const fp = path.join(DETAIL, id + '.txt');
  if (!fs.existsSync(fp)) { console.log('MISS ' + id); continue; }
  const txt = fs.readFileSync(fp, 'utf8');
  const title = field(txt, '职称：');
  const dept = field(txt, '所属部门：');
  const dirRaw = field(txt, '研究方向：');
  const honor = field(txt, '获奖及荣誉：');
  const duty = field(txt, '职务：');
  rows.push({
    name_cn: e.name,
    title: title,
    duty: duty,
    department_ime: dept,
    research: dirRaw,
    honor: honor,
    kinds: e.kinds,
    url: e.url,
  });
}
fs.writeFileSync(path.join(RAW, 'ime_parsed.json'), JSON.stringify(rows, null, 1), 'utf8');
console.log('parsed ' + rows.length);
console.log('no title: ' + rows.filter((r) => !r.title).length);
console.log('no dept: ' + rows.filter((r) => !r.department_ime).length);
console.log('no research: ' + rows.filter((r) => !r.research).length);
const titles = {};
for (const r of rows) titles[r.title || 'NULL'] = (titles[r.title || 'NULL'] || 0) + 1;
console.log(JSON.stringify(titles, null, 1));
const depts = {};
for (const r of rows) depts[r.department_ime || 'NULL'] = (depts[r.department_ime || 'NULL'] || 0) + 1;
console.log(JSON.stringify(depts, null, 1));
