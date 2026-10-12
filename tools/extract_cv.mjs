// extract_cv.mjs — 从 3085 份导师页面文本中抽取「学历 / 工作经历 / 师承」结构化信息
//
// 与之前「共同署名反推」的本质区别：本脚本抽取的是**本人页面的自述**——
// 「师从 X 教授」「博士导师为 Y」属于直接证据，可靠性远高于统计推断。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const LB = path.join(REPO, 'data', 'raw', 'lab_pages');
const PROC = path.join(REPO, 'data', 'processed');

const clean = (s) => String(s || '')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;|&amp;/g, ' ')
  .replace(/[\u200b\ufeff]/g, '')
  .replace(/\s+/g, ' ')
  .trim();

// 学位关键词
const DEG = '(?:博士|硕士|学士|本科|研究生|博士后)';
// 机构后缀
const INST = '(?:大学|学院|研究院|研究所|实验室|理工|中心|Universit[a-z]*|Institute|College|School)';

// ── 名单头（「杭州全职导师：A、B、C」这类是**课题组名单**，不是「我的导师是谁」）──
const LIST_HEADER = /(?:全职|兼职|校内|校外|外聘|联合|合作|招生|指导)?\s*(?:导师|教师|人员|成员|团队|梯队|队伍)\s*[：:]\s*$/;
// ── 地点前缀（「杭州全职导师」这类）──
const PLACE = /(?:北京|上海|广州|深圳|杭州|苏州|无锡|南京|合肥|成都|西安|武汉|天津|重庆|宁波|绍兴|嘉兴|东莞|佛山|厦门|济南|青岛|大连|哈尔滨|长春|沈阳|郑州|长沙|福州|南昌|昆明|贵阳|南宁|兰州|太原|石家庄|呼和浩特|银川|西宁|乌鲁木齐|拉萨|海口|香港|澳门)$/;
// ── 成组出现的名单特征：≥4 个名字用顿号/分号连在一起 ──
function looksLikeList(s) {
  const parts = s.split(/[、，,；;\/]+/).filter((x) => x.trim().length >= 2);
  return parts.length >= 4;
}

const RE = {
  // 毕业：2015年博士毕业于清华大学 —— 用「非空白非标点的最长串」抓机构，避免懒惰匹配截断
  grad: /(\d{4})\s*年[^。；;]{0,26}?毕业于\s*([^\s，,。；;、)）(（]{2,32})/g,
  // 学位+机构：于清华大学获博士学位 / 在XX大学获得博士学位
  deg: /(?:于|在)\s*([^\s，,。；;、)）(（]{2,32}?)\s*(?:获得|获|取得)\s*(博士|硕士|学士|本科)/g,
  // 导师：先粗抓「导师为 XXX」整段，再做后处理清洗头衔
  mentor: /(?:博士|硕士|研究生|合作|指导)?\s*(?:导师|老师|指导教师)\s*(?:为|是|：|:)\s*([^。；;\n]{2,60})/g,
  // 师从：师从X教授
  shicong: /师从\s*([^。；;，,\n]{2,50})/g,
  // 课题组名单：「X 组：A、B、C」「团队成员：…」
  roster: /(?:课题组|团队|梯队|研究组|实验室)\s*(?:成员|人员|名单|教师|导师)?\s*[：:]\s*([^。\n]{4,200})/g,
  // 博后：2018-2020年在清华大学从事博士后研究
  postdoc: /(\d{4})\s*[年\-–—~至]+\s*(\d{4})?\s*年?[^。；;]{0,30}?在\s*([^\s，,。；;、]{2,30}?)\s*(?:从事|做|进行|开展)?\s*博士后/g,
  // 工作：2018年至今 清华大学 教授
  job: /(\d{4})\s*年?\s*[-–—~至]+\s*(?:至今|今|\d{4}\s*年?)[^。；;]{0,10}?([\u4e00-\u9fa5]{2,14}(?:大学|学院|研究所|研究院))/g,
};

// ── 头衔/机构前缀（需要剥离，剩下的才是人名）──
const TITLE_PREFIX = /^(?:美国|英国|中国|欧洲|加拿大|澳大利亚|日本|韩国|德国|法国|瑞士|荷兰|瑞典|新加坡)?(?:国家)?(?:工程院|科学院|皇家学会|艺术与科学院)?(?:院士|会士|外籍院士|Fellow|fellow)?[、，,和与及\s]*/;
const TITLE_WORD = /(?:IEEE|ACM|OSA|SPIE)?\s*(?:Fellow|会士|院士|教授|研究员|老师|先生|博士|诺奖得主|图灵奖得主)/gi;
// ── 导航/栏目噪声 ──
const NAV = /(?:介绍|招生|风采|就业|奖助学金|研究生|博士生|硕士生|本科生|培养|学位|学科|师资|队伍|平台|基地|实验|中心|通知|公告|新闻|动态|概况|简介|登录|首页|导航|链接|下载|联系|党建|工会|校友|学院|学校|大学|研究所|研究院|课题组|团队|教师|导师队伍)/;
// ── 明显不是人名的词 ──
const NOT_NAME = /^(?:我校|本院|学院|学校|研究生|博士生|硕士生|本科生|导师|教师|团队|课题组|公司|企业|博士后|教授|研究员|本人|其|该|上述|以上|相关|专业|方向|the|and|of|in|at|a|an)$/i;
const CN_NAME = /^[\u4e00-\u9fa5]{2,4}$/;                       // 中文姓名
const EN_NAME = /^[A-Z][a-zA-Z\.\-']*(?:\s+[A-Z][a-zA-Z\.\-']*){1,4}$/;  // 英文姓名（至少两段）

function cleanMentor(raw) {
  let s = raw.trim().replace(/[（(].*?[)）]/g, ' ').replace(TITLE_WORD, ' ').replace(TITLE_PREFIX, '').trim();
  // 用顿号/逗号切分，逐个校验
  const parts = s.split(/[、，,；;和与及\/]+/).map((x) => x.replace(TITLE_WORD, '').replace(TITLE_PREFIX, '').trim()).filter(Boolean);
  const good = [];
  for (let p of parts) {
    p = p.replace(/[（(].*$/, '').trim();
    if (p.length < 2 || p.length > 30) continue;
    if (NOT_NAME.test(p)) continue;
    if (NAV.test(p)) continue;                       // 导航噪声
    // 必须是像人名的形式：纯中文 2-4 字，或英文多段姓名
    if (CN_NAME.test(p) || EN_NAME.test(p)) good.push(p);
    else if (/^[\u4e00-\u9fa5]{2,4}[A-Za-z]/.test(p)) good.push(p.match(/^[\u4e00-\u9fa5]{2,4}/)[0]);
  }
  return [...new Set(good)];
}

const out = {};
let scanned = 0, hasEdu = 0, hasMentor = 0;
for (const f of fs.readdirSync(LB).filter((x) => x.endsWith('.txt'))) {
  const p = path.join(LB, f);
  let txt; try { txt = clean(fs.readFileSync(p, 'utf8')); } catch { continue; }
  if (txt.length < 60) continue;
  scanned++;
  const key = f.replace(/\.txt$/, '');
  const rec = { key, edu: [], mentors: [], postdoc: [], jobs: [] };

  for (const [k, re] of Object.entries(RE)) {
    re.lastIndex = 0;
    let m, n = 0;
    while ((m = re.exec(txt)) && n < 12) {
      n++;
      if (k === 'grad') {
        const year = +m[1], inst = m[2].trim();
        // 排除出生年：若该年份附近有「XXXX年-」或「XXXX年生」形态，跳过
        const around = txt.slice(Math.max(0, m.index - 12), m.index + 6);
        if (/年\s*[-–—]\s*$|年生|出生/.test(around)) continue;
        if (year >= 1975 && year <= 2030 && inst.length >= 2) rec.edu.push({ year, inst, deg: '毕业' });
      } else if (k === 'deg') {
        const inst = m[1].trim(), deg = m[2];
        if (inst.length >= 2 && !NAV.test(inst)) rec.edu.push({ year: null, inst, deg });
      } else if (k === 'mentor' || k === 'shicong') {
        // 排除「杭州全职导师：A、B、C」这类课题组名单：
        // ① 冒号前是地点/全职等限定词  ② 捕获内容本身是一长串名字
        const before = txt.slice(Math.max(0, m.index - 14), m.index);
        if (LIST_HEADER.test(before) || PLACE.test(before.trim())) continue;
        if (looksLikeList(m[1])) continue;
        for (const nm of cleanMentor(m[1])) rec.mentors.push({ name: nm, kind: k });
      } else if (k === 'roster') {
        // 课题组名单：单独存放，作为「同组」关系而非师承
        const names = m[1].split(/[、，,；;\/]+/).map((x) => x.replace(/[（(].*?[)）]/g, '').trim()).filter((x) => CN_NAME.test(x));
        if (names.length >= 2) rec.roster = [...new Set([...(rec.roster || []), ...names])];
      } else if (k === 'postdoc') {
        rec.postdoc.push({ y1: +m[1], y2: m[2] ? +m[2] : null, inst: m[3].trim() });
      } else {
        rec.jobs.push({ year: +m[1], org: m[2] });
      }
    }
  }
  if (rec.edu.length || rec.mentors.length) {
    out[key] = rec;
    if (rec.edu.length) hasEdu++;
    if (rec.mentors.length) hasMentor++;
  }
}

console.log(`扫描页面 ${scanned} 份`);
console.log(`抽到学历信息: ${hasEdu} 份 | 抽到师承提及: ${hasMentor} 份 | 有效记录 ${Object.keys(out).length} 份`);
const totM = Object.values(out).reduce((a, b) => a + b.mentors.length, 0);
const totE = Object.values(out).reduce((a, b) => a + b.edu.length, 0);
console.log(`师承提及共 ${totM} 条 | 学历条目共 ${totE} 条`);

fs.writeFileSync(path.join(PROC, 'cv_extracted.json'), JSON.stringify(out, null, 1), 'utf8');

console.log('\n=== 抽到的师承样例（前 20）===');
let n = 0;
for (const [k, r] of Object.entries(out)) {
  if (!r.mentors.length) continue;
  if (n++ >= 20) break;
  console.log(`  ${k}`);
  console.log(`    导师: ${r.mentors.map((m) => m.name + '(' + m.kind + ')').join('、')}`);
  if (r.edu.length) console.log(`    学历: ${r.edu.slice(0, 3).map((e) => (e.year || '?') + ' ' + e.deg + ' ' + e.inst).join(' | ')}`);
}

console.log('\n=== 抽到的学历样例（前 12，无师承的）===');
n = 0;
for (const [k, r] of Object.entries(out)) {
  if (r.mentors.length || !r.edu.length) continue;
  if (n++ >= 12) break;
  console.log(`  ${k}: ${r.edu.slice(0, 3).map((e) => (e.year || '?') + ' ' + e.deg + ' ' + e.inst).join(' | ')}`);
}
