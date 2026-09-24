// report.mjs — 生成导师库排名总报告（Markdown）
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\导师库-排名总报告.md';
const rows = JSON.parse(fs.readFileSync(path.join(PROC, 'mentor_db.json'), 'utf8'));

const DIRNAME = {
  analog: '模拟 / 混合信号 / 电源管理 IC',
  rf: '射频 / 毫米波 / 太赫兹 / 天线',
  digital_ai: '数字 / AI 芯片 / 处理器体系结构',
  eda: 'EDA / 设计自动化 / 先进封装',
  device: '器件 / 工艺 / 宽禁带 / 存储器',
  photonics: '光电 / 硅光 / 光计算 / 成像',
  mems: 'MEMS / 传感器 / 生物医疗电子',
  power: '电力电子 / 功率集成',
  quantum: '量子芯片 / 低温电子学',
  other: '其他 / 交叉方向',
};

function tierOf(d) {
  if (d.n_ic_papers < 3 && d.S === 0) return 'T4';
  if (d.score >= 58) return 'T0';
  if (d.score >= 40) return 'T1';
  if (d.score >= 24) return 'T2';
  if (d.score >= 12) return 'T3';
  return 'T4';
}
const TIER_LABEL = {
  T0: '**夯**（公认强：顶刊顶会密集 + 近年持续高产）',
  T1: '**稳**（一流产出稳定，方向清晰）',
  T2: '**中**（有产出，或方向相关但证据中等）',
  T3: '**观察**（证据偏少 / 方向交叉 / 需人工核实）',
  T4: '**信息不足**（公开检索未获足够证据——**不代表水平差**）',
};
const TIER_ORDER = ['T0', 'T1', 'T2', 'T3'];

const conf = { high: '高', medium: '中', low: '低' };
const fa = (d) => (d.homepage ? `[主页](${d.homepage})` : '');
const kw = (d) => (d.research_keywords || []).slice(0, 4).join('、');

function rowLine(d, extra = '') {
  const t = tierOf(d);
  const flag = d.recall_risk === 'yes' ? ' ⚠️疑似漏检' : '';
  return `| ${d.name_cn}${flag} | ${d.school.replace('清华大学深圳国际研究生院', '清华深研院')} | ${(d.title || '—').replace(/\|/g, '/')} | ${d.S} | ${d.A} | ${d.n_ic_papers} | ${d.recent3} | ${d.citations} | ${d.n_students_est || 0} | ${d.score} | ${conf[d.confidence]} | ${kw(d)} | ${extra}${fa(d)} |`;
}
const HDR = '| 姓名 | 学校 | 职称 | 顶刊顶会S | 一流A | 论文 | 近3年 | 引用 | 学生(估) | 强度分 | 置信 | 官方方向 | 链接 |\n|:--|:--|:--|--:|--:|--:|--:|--:|--:|--:|:--:|:--|:--|';

// ── 统计 ──
const schools = [...new Set(rows.map((r) => r.school))];
const dirs = Object.keys(DIRNAME).filter((k) => rows.some((r) => r.primary_direction === k));
const tierCount = {};
for (const r of rows) tierCount[tierOf(r)] = (tierCount[tierOf(r)] || 0) + 1;

let md = `# 集成电路 / 微电子 / 电子信息 / AI 芯片 方向导师库与分级排名

> **覆盖院校**：清华大学深圳国际研究生院、复旦大学、上海交通大学、浙江大学、南京大学、中国科学技术大学
> **入库规模**：**${rows.length} 位在职教师/导师**（其中 ${rows.filter((r) => r.n_ic_papers > 0).length} 位检索到可核实的论文记录）
> **数据源**：六校官方师资页面（逐人抓取，${rows.length} 条记录全部来自实际页面）＋ Crossref 文献数据库（2015–2026，含作者机构校验）
> **生成日期**：2026-09-22

---

## 〇、先读这一页（重要）

### 这份排名是什么

基于**公开文献计量证据**（顶刊顶会数量、一流期刊会议数量、近三年活跃度、引用、署名结构）对导师做的**证据强度分级**。它回答的是"**这位老师在公开文献里有多能打、在做什么方向**"。

### 这份排名不是什么

1. **不是导师人品的评价**。"拉"（信息不足档）表示**公开可检索的证据少**（方向冷门、英文名不统一、页面未更新等），**绝不等于老师水平差或对学生不好**——本榜单里就有多位院士、杰青落在"信息不足"档，原因是他们的名字拼音重名太多，自动匹配无法确证。
2. **不含指导质量**。导师是否 push、是否放养、组会频率、毕业去向、补助多少——**这些文献数据里没有**，必须找在读/毕业的师兄师姐问。
3. **存在同名污染**。中文拼音重名严重（如"张伟""刘洋""李鹏"），我们已用"姓名精确匹配 + 作者本人机构校验 + 方向一致性"三重过滤，但仍无法 100% 排除。每条记录标注了**匹配置信度**（高/中/低），低置信的记录请以官方主页为准。
4. **覆盖率不完整**：Crossref 对 IEEE 会议论文的机构字段收录不总是完整；中文期刊（CNKI/万方）无法访问；部分老师英文名写法与拼音不符导致漏检。

### 结论怎么用

- **先按方向筛**（第 2 节），再按梯队看；
- **T0/T1 = 硬通货**：有 ISSCC/JSSC/VLSI/ISCA/MICRO 等顶刊顶会产出的组，通常意味着平台、经费、流片机会和师兄师姐的网络；
- **T4 不要直接排除**：请点开官方主页核对，或直接发邮件问；
- **青年教师（助理教授/特任/百人计划）常出现在 T1–T2**，他们往往带学生更细、更愿意投入，但资源和名气不如资深组——这是权衡，不是优劣。

---

## 一、总览

### 1.1 六校入库规模与顶刊顶会产出

| 学校 | 入库人数 | 有论文记录 | 顶刊顶会(S)合计 | 一流(A)合计 | S 人均 |
|:--|--:|--:|--:|--:|--:|
`;

for (const s of schools) {
  const sub = rows.filter((r) => r.school === s);
  const S = sub.reduce((a, b) => a + b.S, 0), A = sub.reduce((a, b) => a + b.A, 0);
  const withP = sub.filter((r) => r.n_ic_papers > 0).length;
  md += `| ${s} | ${sub.length} | ${withP} | ${S} | ${A} | ${(S / sub.length).toFixed(2)} |\n`;
}
md += `| **合计** | **${rows.length}** | **${rows.filter((r) => r.n_ic_papers > 0).length}** | **${rows.reduce((a, b) => a + b.S, 0)}** | **${rows.reduce((a, b) => a + b.A, 0)}** | — |\n`;

md += `
> S = ISSCC / JSSC / VLSI Symposium / ISCA / MICRO / HPCA / ASPLOS / IEDM / Nature Electronics；
> A = CICC / A-SSCC / ESSCIRC / RFIC / TCAS-I / TCAS-II / TVLSI / TCAD / TED / MTT / TPEL / TC / DAC / ICCAD / FPGA / SSC-L / JLT。
>
> ⚠️ **不要用"S 人均"直接给学校排名**：本库 venue 表以**电路与系统**类为主，对**器件/材料/物理**方向（如南大物理学院、复旦微电子器件方向）天然不利——他们在 Nature 子刊、Adv. Mater.、IEDM、VLSI Technology 上的产出会被低估。南大 S 人均偏低主要源于此，以及其信电/物理师资以器件与物理电子学为主。

### 1.2 方向分布

| 研究方向 | 人数 | 其中 S≥1 | 平均强度分 |
|:--|--:|--:|--:|
`;
for (const d of dirs) {
  const sub = rows.filter((r) => r.primary_direction === d);
  md += `| ${DIRNAME[d]} | ${sub.length} | ${sub.filter((r) => r.S > 0).length} | ${(sub.reduce((a, b) => a + b.score, 0) / sub.length).toFixed(1)} |\n`;
}

md += `
### 1.3 梯队分布

| 梯队 | 含义 | 人数 |
|:--|:--|--:|
| 夯 T0 | 顶刊顶会密集、近年持续高产 | ${tierCount.T0 || 0} |
| 稳 T1 | 一流产出稳定 | ${tierCount.T1 || 0} |
| 中 T2 | 有产出或方向相关 | ${tierCount.T2 || 0} |
| 观察 T3 | 证据偏少/交叉 | ${tierCount.T3 || 0} |
| 信息不足 T4 | 公开证据不足（**非负面评价**） | ${tierCount.T4 || 0} |

### 1.4 全库 Top 100（跨方向总榜，按证据强度分）

> 想快速锁定候选，直接从这张表开始；再按方向到第 2 节看细节。

${HDR}
`;

for (const r of rows.slice(0, 100)) md += rowLine(r) + '\n';

md += `
---

## 二、分方向分级榜单

> 每位老师只出现在其**主方向**榜单中（一人可能横跨多方向，主方向 = 论文与官方关键词加权最大者）。
> 交叉方向能力请见第 5 节"跨界型导师"。

`;

for (const d of dirs) {
  const sub = rows.filter((r) => r.primary_direction === d).sort((a, b) => b.score - a.score);
  if (!sub.length) continue;
  md += `### 2.${dirs.indexOf(d) + 1} ${DIRNAME[d]}（${sub.length} 人）\n\n`;
  for (const t of TIER_ORDER) {
    const list = sub.filter((r) => tierOf(r) === t);
    if (!list.length) continue;
    md += `#### ${TIER_LABEL[t]} — ${list.length} 人\n\n${HDR}\n`;
    for (const r of list.slice(0, t === 'T2' || t === 'T3' ? 15 : 20)) md += rowLine(r) + '\n';
    if (list.length > (t === 'T2' || t === 'T3' ? 15 : 20)) md += `\n*（该梯队另有 ${list.length - 15} 人，完整名单见 CSV / HTML 数据库）*\n`;
    md += '\n';
  }
  const t4 = sub.filter((r) => tierOf(r) === 'T4');
  if (t4.length) md += `<details><summary>信息不足档 ${t4.length} 人（点击展开，需人工核实，不代表水平差）</summary>\n\n${HDR}\n${t4.map((r) => rowLine(r)).join('\n')}\n\n</details>\n\n`;
}

// ── 分学校 Top ──
md += `---\n\n## 三、分学校 Top 榜（各校前 15）\n\n`;
for (const s of schools) {
  const sub = rows.filter((r) => r.school === s).sort((a, b) => b.score - a.score).slice(0, 15);
  md += `### ${s}\n\n${HDR}\n`;
  for (const r of sub) md += rowLine(r) + '\n';
  md += '\n';
}

// ── 专题榜 ──
const young = rows.filter((r) => /助理教授|助理研究员|青年|特任|百人计划|博士后|副研究员/.test(r.title || '') && r.score >= 20).sort((a, b) => b.score - a.score);
md += `---\n\n## 四、专题榜：值得重点关注的青年 PI（助理教授/特任/青年研究员，强度分≥20）\n\n`;
md += `> 青年 PI 通常刚建组 1–5 年，带学生更细、更愿意给一作，但经费与名气不如资深组。适合"想被手把手带、且方向明确"的同学。\n\n${HDR}\n`;
for (const r of young.slice(0, 40)) md += rowLine(r) + '\n';

const senior = rows.filter((r) => /院士|讲席|特聘教授|长江|杰青|教授/.test(`${r.title || ''} ${r.notes || ''}`) && r.S >= 3).sort((a, b) => b.S - a.S).slice(0, 30);
md += `\n---\n\n## 五、专题榜：资深强组（顶刊顶会 S≥3 的教授/院士团队负责人，按 S 排序）\n\n${HDR}\n`;
for (const r of senior) md += rowLine(r, `${(r.notes || '').slice(0, 40)} | `) + '\n';

const studentFriendly = rows.filter((r) => r.n_ic_papers >= 15 && r.advisor_first_ratio !== null && r.advisor_first_ratio < 0.15).sort((a, b) => a.advisor_first_ratio - b.advisor_first_ratio).slice(0, 25);
md += `\n---\n\n## 六、专题榜：署名结构健康（本人一作占比 <15%＝更倾向让学生挂一作）\n\n`;
md += `> 说明：一作占比低，通常意味着"导师做通讯、学生做一作"的组内惯例，对想攒一作的同学友好。但要注意：青年 PI 在自己晋升期可能必须拿一作，需单独沟通。\n\n| 姓名 | 学校 | 职称 | 论文 | 本人一作占比 | 学生一作占比 | 组内学生数(估) | 强度分 | 链接 |\n|:--|:--|:--|--:|--:|--:|--:|--:|:--|\n`;
for (const r of studentFriendly) {
  md += `| ${r.name_cn} | ${r.school.replace('清华大学深圳国际研究生院', '清华深研院')} | ${(r.title || '—')} | ${r.n_ic_papers} | ${(r.advisor_first_ratio * 100).toFixed(0)}% | ${r.student_led_ratio !== null ? (r.student_led_ratio * 100).toFixed(0) + '%' : '—'} | ${r.n_students_est} | ${r.score} | ${fa(r)} |\n`;
}

// ── 选导师建议 ──
md += `
---

## 七、怎么用这份库选导师（决策清单）

### 第一步：定方向（比选人重要）
- **模拟/混合信号/电源**：看 JSSC + ISSCC + CICC，国内复旦、上交、中科大、浙大是主力；这方向"流片机会"是生命线，一定问清楚**一年能流几次片、什么工艺（28nm/40nm/180nm）**。
- **数字/AI 芯片/体系结构**：看 ISSCC + ISCA/MICRO/HPCA + DAC，注意区分"**做芯片**"（有流片、有测试报告）和"**做架构仿真**"（只有仿真）。想做 AI 芯片的，务必问"有没有实际流片回来测过"。
- **射频/毫米波**：看 ISSCC/RFIC/MTT，设备（矢网、探针台）依赖极重，进组先看实验室设备清单。
- **EDA**：看 DAC/ICCAD/TCAD，纯 EDA 组通常不需要流片，但需要强编程能力，就业面向 EDA 三巨头与国产 EDA。
- **器件/工艺/宽禁带/存储**：看 TED/EDL/JSSC + Nature 子刊，实验依赖洁净室，成果周期长（一篇器件论文 1–2 年正常），要能接受"慢"。
- **光电/硅光**：看 JLT/PTL/OFC + Nature Photonics，流片多走 MPW  shuttle。
- **MEMS/生物医疗电子**：看 TBioCAS/TBME/IEEE Sensors，交叉性强，适合想走医疗仪器/可穿戴方向的同学。

### 第二步：按证据强度排候选（本库梯队）
- T0/T1：优先考虑（平台、经费、流片能力大概率到位）；
- T2：重点看**方向匹配度**与**近年活跃度**（近 3 年列），有些人只是英文名难匹配导致分数偏低；
- T3/T4：**必须人工核实**（点官方主页、发邮件、问师兄师姐）。

### 第三步：查三类"文献里看不到"的信息（决定性）
1. **毕业去向**：近 3 年毕业的硕士/博士去了哪（华为海思/中兴/比亚迪半导体/英伟达/AMD/高校/出国）。直接问在读师兄师姐，或看导师主页的"毕业生"栏目。
2. **指导风格**：组会频率、是否 push、是否允许实习、毕业卡不卡、补助多少（尤其上海/深圳的房租）。
3. **一作与通讯惯例**：本库"署名结构"专题已给出统计线索，但最终以口头承诺 + 组内惯例为准。

### 第四步：避坑提示（来自公开数据的信号）
- **近年产出断崖**：本库"近3年"列若明显低于总量，需问清是否已转行政/即将退休；
- **只挂名不指导**：S 很多但组内学生数（估）极少、或论文里从不出现学生一作，需警惕；
- **方向漂移**：官方关键词与近年论文方向不一致（本库"官方方向"与"主方向"可对比）；
- **纯挂名大组**：院士/校长/院长级导师常见"挂名 + 小导师实际带"，务必问清**实际指导人是谁**。

---

## 八、数据字典与文件索引

| 文件 | 内容 |
|:--|:--|
| \`reports/导师库.html\` | **可交互检索库**（按学校/方向/梯队筛选 + 排序，双击打开即用） |
| \`data/processed/mentor_db.csv\` | Excel 可直接打开的完整表（${rows.length} 行 × 24 列） |
| \`data/processed/mentor_db.json\` | 完整结构化数据（含每人论文清单、venue 分层、署名结构） |
| \`data/raw/*/roster_*.json\` | 六校官方师资页原始名录（含抓取来源 URL） |
| \`data/raw/crossref/*_papers.json\` | 各校期刊论文池原始快照（按 ISSN 抓取） |
| \`data/processed/enriched_*.json\` | 逐人 Crossref 检索结果（含每篇论文的作者序列与机构串） |

**字段说明**：
- **强度分（0–100）**：0.34×饱和(S数) + 0.24×饱和(A数) + 0.08×饱和(B数) + 0.12×饱和(论文数) + 0.12×饱和(log 引用) + 0.10×饱和(近3年数)，各项用饱和函数抑制"高产碾压"；
- **学生(估)**：论文一作中非本校在职教师的去重人数——是**团队规模的下限估计**，不是实际在读人数；
- **置信**：high＝论文多且顶刊集中；medium＝一般；low＝匹配样本少或重名风险高；
- **本报告所有"顶刊顶会"计数均基于 Crossref 收录**，实际产出可能更高（会议论文机构字段缺失时会漏计）。

---

## 九、局限与免责声明

1. **同名污染**：中文拼音重名严重，虽已三重过滤，仍可能有个别论文被错误归属。标 **置信=低** 的记录请务必核对官方主页。
2. **覆盖不全**：Crossref 对 IEEE 会议论文的作者机构字段收录不完整（尤其 ISSCC/CICC 早期年份），会**系统性低估**实际顶会产出；中文期刊（CNKI/万方）完全未覆盖。
3. **不含非公开信息**：指导风格、课题组氛围、补助、毕业去向、是否允许实习等**均未包含**，需自行核实。
4. **职称与时点**：全部信息截至 2026-09-22，来自各校官网；官网未更新职称者以官网为准。
5. **本报告不构成任何学术评价、人事评价或报考建议**，仅作为公开信息的整理与线索提供。使用者的报考决策应结合官方招生简章、导师本人沟通与在读学生反馈。

*报告生成：2026-09-22 ｜ 工具链：mentor-db（Crossref 采集 + 消歧 + 分层评分）*
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, md, 'utf8');
console.log('saved', OUT, (md.length / 1024).toFixed(0) + 'KB');
console.log('梯队分布', JSON.stringify(tierCount));
