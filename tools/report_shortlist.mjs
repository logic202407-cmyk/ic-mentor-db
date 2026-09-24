// report_shortlist.mjs — 生成 2027 推免（AI 芯片方向）导师短名单报告
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\2027推免-AI芯片方向导师短名单.md';
const list = JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_final.json'), 'utf8'));
const all = JSON.parse(fs.readFileSync(path.join(PROC, 'shortlist_2027.json'), 'utf8'));

const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };
const sh = (s) => SHORT[s] || s;
const DIRNAME = { analog: '模拟/电源', rf: '射频', digital_ai: '数字/AI芯片', eda: 'EDA', device: '器件/存储', photonics: '光电', mems: 'MEMS/生医', quantum: '量子', other: '其他', power: '电力电子' };

// 明确不招（负面信号）
const NEG = /NO (PhD|Master|M\.?S\.?|graduate) position|not (currently )?(recruiting|accepting)|不(再)?招收|名额已满|已招满/i;
const negList = list.filter((d) => d.recruit_signals.some((s) => NEG.test(s.snippet)));

// 分级
const explicit = list.filter((d) => d.recruit_signal_count > 0 && !negList.includes(d));
const tierS = explicit.filter((d) => d.ai_score >= 55);
const tierA = list.filter((d) => !explicit.includes(d) && d.ai_score >= 65 && d.composite >= 55).slice(0, 60);
const tierB = list.filter((d) => !explicit.includes(d) && !tierA.includes(d) && d.ai_score >= 45 && d.composite >= 45).slice(0, 60);

function card(d, i) {
  const email = d.email || '（主页未公开邮箱，需从学院页面找）';
  const lab = (d.lab_names || [])[0] || '（未识别到课题组名）';
  const sig = d.recruit_signals.slice(0, 2).map((s) => `> 「${s.snippet}」`).join('\n');
  const papers = (d.recent_titles || []).slice(0, 2).map((t) => `- ${t}`).join('\n') || '- （近年论文见主页）';
  return `#### ${i}. ${d.name} ｜ ${sh(d.school)} ｜ ${d.title}\n\n` +
    `| 项目 | 内容 |\n|:--|:--|\n` +
    `| 院系 | ${d.department || '—'} |\n` +
    `| 课题组 | ${lab} |\n` +
    `| 主方向 | ${DIRNAME[d.primary_direction] || d.primary_direction} ｜ AI 相关度 **${d.ai_score}** |\n` +
    `| 学术证据 | 综合分 ${d.composite} ｜ 顶刊顶会 S${d.S} / 一流 A${d.A} ｜ 论文 ${d.n_ic_papers} 篇 ｜ 近 3 年 ${d.recent3} 篇 |\n` +
    `| 组内学生(估) | ${d.n_students_est} 人 ｜ 近两年学生一作 ${d.recent_student_first_authors} 人 |\n` +
    `| 邮箱 | \`${email}\` |\n` +
    `| 主页 | ${d.homepage} |\n` +
    `| 官方方向 | ${(d.research_keywords || []).join('、')} |\n\n` +
    `**主页招生原话**：\n${sig || '> （主页未见明确招生表述，建议邮件直接询问）'}\n\n` +
    `**邮件可引用的近期论文**：\n${papers}\n\n`;
}

function table(rows) {
  let t = `| # | 姓名 | 学校 | 职称 | 方向 | AI相关度 | 综合分 | S/A | 论文 | 近3年 | 学生(估) | 邮箱 | 主页 |\n|--:|:--|:--|:--|:--|--:|--:|:--|--:|--:|--:|:--|:--|\n`;
  rows.forEach((d, i) => {
    t += `| ${i + 1} | **${d.name}** | ${sh(d.school)} | ${d.title || '—'} | ${DIRNAME[d.primary_direction] || d.primary_direction} | ${d.ai_score} | ${d.composite} | ${d.S}/${d.A} | ${d.n_ic_papers} | ${d.recent3} | ${d.n_students_est} | ${d.email || '—'} | ${d.homepage ? '[主页](' + d.homepage + ')' : '—'} |\n`;
  });
  return t;
}

let md = `# 2027 推免 · AI 芯片方向 导师短名单（可直接用于邮件联系）

> **你的筛选条件**：① 排除 毫米波/射频、光电/硅光、MEMS/生医；② 优先 AI 相关；③ 需仍在招生
> **数据基础**：11 校 2114 位导师库 → 方向过滤后 643 人 → 抓取 **231 位候选人的课题组/个人主页**（原始页面存于 \`data/raw/lab_pages/\`）
> **筛选日期**：2026-09-24

---

## 一、这份名单怎么筛出来的

| 步骤 | 口径 | 结果 |
|:--|:--|:--|
| 1. 方向排除 | 剔除主方向为 射频/毫米波、光电/硅光、MEMS/生医 者；并做关键词二次排除（天线、太赫兹、激光、微流控…） | 2114 → **643 人** |
| 2. AI 相关度（0–100） | 主方向为数字/AI芯片 +30、EDA +18；官方方向命中 AI 强关键词 +26；论文标题 AI 命中；ISCA/MICRO/HPCA/DAC/ICCAD/ISSCC 等 AI 类顶会加成 | — |
| 3. 在招可能性（0–100） | 青年 PI +28、副教授 +18；院士/校长/院长 −18；近 3 年产出、组内学生数、有邮箱、博导身份加权 | — |
| 4. 实抓主页 | 抓取 231 位候选人的课题组/个人主页，用 11 条精确句式（招收硕士/推免/夏令营/join us…）提取**招生原话**，并过滤导航栏噪声 | **53 人主页有明确招生语句** |
| 5. 近期活跃度 | 统计 2024–2026 年论文中"学生一作"的去重人数（说明组内确实有学生在干活） | — |

---

## 二、S 级名单：主页明确在招 + AI 强相关（**优先联系**，${tierS.length} 人）

> 这些人主页上直接写明了招收研究生，且方向落在 AI 芯片/体系结构/存算一体/EDA+AI 上。**建议第一批发邮件。**

${tierS.map((d, i) => card(d, i + 1)).join('\n---\n\n')}

---

## 三、A 级名单：AI 强相关、产出强（招生信息未公开，**可试探性联系**，${tierA.length} 人）

> 学术证据充分、方向高度对口，但主页没有明确招生表述。建议邮件里直接问"2027 级是否还有推免名额"。

${table(tierA)}

---

## 四、B 级名单：其他可选（AI 相关度中等或产出中等，${tierB.length} 人）

> 作为备选池。若前面几批回复不理想，从这里补。

${table(tierB)}

---

## 五、⚠️ 需要回避或特别确认的

`;

if (negList.length) {
  md += `**主页明确写了不招的**：\n\n| 姓名 | 学校 | 职称 | 主页原话 |\n|:--|:--|:--|:--|\n`;
  for (const d of negList) md += `| ${d.name} | ${sh(d.school)} | ${d.title || '—'} | ${d.recruit_signals.filter((s) => NEG.test(s.snippet))[0].snippet.slice(0, 120)} |\n`;
  md += `\n> 注意区分"不招博士"与"不招硕士"——原文若写 NO PhD position，硕士名额可能仍开放，但建议邮件确认。\n\n`;
}

// 大牌但难招
const bigNames = all.filter((d) => /院士|校长|副校长|院长/.test(`${d.title || ''} ${d.notes || ''}`) && d.ai_score >= 50).slice(0, 12);
md += `**头衔很重、但个人指导时间可能有限（联系时建议同时联系组内小导师）**：\n\n${table(bigNames)}\n\n`;

md += `---

## 六、邮件模板（中英双版）

### 中文模板

\`\`\`
主题：2027 级推免申请咨询 - [你的学校] - [你的姓名] - [方向：AI 芯片/体系结构]

尊敬的 X 老师：

您好！我是 [学校] [专业] 2023 级本科生 [姓名]，专业排名 [X/总人数]（前 X%），
预计获得 2027 届推免资格。我在您课题组主页看到 [引用一句他主页上的招生原话，例如"课题组每年招收 3-5 名博士/硕士研究生"]，
非常希望能加入您的团队。

我关注到您近期的工作《[引用 1 篇他 2025-2026 年的论文标题]》，
其中 [用一句话说出你理解的技术点，例如"在 XX 工艺下把能效提升了 X 倍"]，
这与我 [做过的项目/读过的课程/复现过的实验] 高度相关：
- [项目 1：一句话 + 量化结果]
- [项目 2：一句话 + 量化结果]
- 技能：Verilog/PyTorch/C++/Cadence…（只写真的会的）

附件是我的简历与成绩单。若您 2027 级还有推免名额，我非常希望能有机会进一步沟通，
也随时可以按您要求做一些前置的文献阅读或小任务。

感谢您的时间！

[姓名]
[电话] | [邮箱] | [个人主页/GitHub]
\`\`\`

### 英文模板（部分导师主页为英文、或有海外背景）

\`\`\`
Subject: Prospective Master's Student (2027 Fall, Recommended Admission) - [Your Name]

Dear Professor [Last Name],

I am [Name], a third-year undergraduate in [Major] at [University] (GPA [X], rank [X/Y]).
I expect to receive the recommendation-based admission (推免) qualification for Fall 2027
and am very interested in joining your group.

I read your recent work "[Paper Title]" and was particularly impressed by [one specific
technical point]. My background aligns well: [project 1 with result], [project 2 with result],
and I am proficient in [skills].

I have attached my CV and transcript. Could you let me know whether you will have openings
for Fall 2027? I am happy to do any reading or a small task in advance.

Best regards,
[Name]
\`\`\`

### 发信注意事项
1. **一次只发给 3–5 位**，按 S → A → B 分批，避免同时骚扰太多导致口碑问题；
2. **主题行要具体**（学校+姓名+方向），不要写"咨询"两个字了事；
3. **附简历 PDF**（1 页）+ 成绩单；文件命名：\`姓名-学校-专业-2027推免.pdf\`；
4. **引用论文要真读过**——导师一眼能看出模板信；
5. 一周没回复可再发一封简短跟进，仍无回复就换人；
6. 若导师主页写了具体要求的（如"发送简历与研究兴趣简介"），**严格照做**。

---

## 七、2027 推免时间线（务必确认你属于哪一档）

| 目标入学 | 关键节点 | 现在该做什么 |
|:--|:--|:--|
| **2027 级**（当前正在进行） | 夏令营：2026 年 5–7 月（多数已结束）｜**预推免：2026 年 8–9 月**｜推免系统填报：9 月底–10 月 | 若目标是 2027 级，**现在就是最后窗口**，立即发邮件 + 关注各校研究生院"2027 级推免报名通知" |
| **2028 级**（提前布局） | 夏令营：2027 年 5–7 月｜预推免：2027 年 9 月 | 现在开始联系导师做**前置科研**（进组实习/远程做小课题），夏令营前拿到导师意向 |

> 已在本轮抓取中确认：复旦大学研究生院已发布《招收 2027 级推荐免试研究生报名通知》（见邹卓老师主页公告栏），说明 2027 级推免工作正在进行中。

---

## 八、局限与提醒

1. **"主页没写招生"≠不招**：很多导师不更新主页，A/B 级名单同样值得发邮件问；
2. **"主页写了招生"≠有名额**：可能已招满，务必邮件确认；
3. **方向词是自动分类**，个别导师可能横跨多个方向（如既做 AI 芯片又做器件），请点开主页核对；
4. **院士/院长/校长级导师**常由组内小导师实际指导，联系前先确认"实际带你的老师是谁"；
5. 本名单基于公开信息整理，**不构成任何录取承诺或报考建议**。

*名单生成：2026-09-24 ｜ 数据文件：\`data/processed/shortlist_final.json\`、\`shortlist_final.csv\`*
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, md, 'utf8');

// CSV
const csv = ['name,school,title,department,lab,primary_direction,ai_score,recruit_final,fit_final,composite,S,A,n_ic_papers,recent3,n_students_est,recent_student_first_authors,email,homepage,recruit_signal,research_keywords']
  .concat(list.map((d) => [d.name, d.school, d.title, d.department, (d.lab_names || [])[0], d.primary_direction, d.ai_score, d.recruit_final, d.fit_final, d.composite, d.S, d.A, d.n_ic_papers, d.recent3, d.n_students_est, d.recent_student_first_authors, d.email, d.homepage, (d.recruit_signals[0] || {}).snippet || '', (d.research_keywords || []).join('、')]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')))
  .join('\n');
fs.writeFileSync(path.join(PROC, 'shortlist_final.csv'), '\ufeff' + csv, 'utf8');

console.log('saved', OUT, (md.length / 1024).toFixed(0) + 'KB');
console.log('S级', tierS.length, '| A级', tierA.length, '| B级', tierB.length, '| 明确不招', negList.length);
