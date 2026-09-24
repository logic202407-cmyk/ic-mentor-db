// report_profile.mjs — 按「IC 科班 + 编程一般 + AI 重度使用者」输出定制推荐报告
import fs from 'node:fs';
import path from 'node:path';

const PROC = 'E:\\ytm\\mentor-db\\data\\processed';
const OUT = 'E:\\ytm\\mentor-db\\reports\\2027推免-按你的背景重排（IC设计×AI）.md';
const scored = JSON.parse(fs.readFileSync(path.join(PROC, 'profile_fit.json'), 'utf8'));

const SHORT = { 清华大学深圳国际研究生院: '清华深研院', 清华大学: '清华', 复旦大学: '复旦', 上海交通大学: '上交', 浙江大学: '浙大', 南京大学: '南大', 中国科学技术大学: '中科大', 北京大学: '北大', 东南大学: '东南', 西安电子科技大学: '西电', 电子科技大学: '成电' };
const sh = (s) => SHORT[s] || s;
const DIR = { analog: '模拟/电源', rf: '射频', digital_ai: '数字/AI芯片', eda: 'EDA', device: '器件/存储', photonics: '光电', mems: 'MEMS', quantum: '量子', other: '其他', power: '电力电子' };

// ── 分赛道 ──
const isAnalog = (d) => d.primary_direction === 'analog' || /模拟集成电路|模拟电路|混合信号|数模混合|电源管理|ADC|DAC|数据转换器|锁相环|PLL|基准源|放大器|电源芯片|DC-?DC|LDO|IVR|供电/i.test((d.research_keywords || []).join(' ')) && d.code_load <= 25;
const isDigital = (d) => /数字集成电路|数字电路|SoC|片上系统|处理器|微处理器|RISC-V|验证|后端|物理设计|可测性|DFT|存算一体|存内计算|近存计算|芯片设计|集成电路设计/i.test((d.research_keywords || []).join(' ')) && d.code_load <= 45;
const isAiChip = (d) => d.ai_score >= 60 && d.code_load <= 58;
const isCodeHeavy = (d) => d.code_load >= 60;

const trackA = scored.filter((d) => isAnalog(d)).sort((a, b) => b.fit_profile - a.fit_profile);
const trackB = scored.filter((d) => !isAnalog(d) && isDigital(d)).sort((a, b) => b.fit_profile - a.fit_profile);
const trackC = scored.filter((d) => !isAnalog(d) && !isDigital(d) && isAiChip(d)).sort((a, b) => b.fit_profile - a.fit_profile);
const trackD = scored.filter((d) => isCodeHeavy(d)).sort((a, b) => b.ai_score - a.ai_score);

function tbl(rows, n = 30) {
  let t = `| # | 姓名 | 学校 | 职称 | 主方向 | 编程负担 | IC核心 | AI交叉 | 综合分 | S/A | 在招信号 | 邮箱 | 主页 |\n|--:|:--|:--|:--|:--|--:|--:|--:|--:|:--|:--|:--|:--|\n`;
  rows.slice(0, n).forEach((d, i) => {
    const rec = d.recruit_signal_count > 0 ? '✅ 主页明确' : (d.recruit_final >= 85 ? '可能在招' : '未明');
    t += `| ${i + 1} | **${d.name_cn}** | ${sh(d.school)} | ${d.title || '—'} | ${DIR[d.primary_direction] || d.primary_direction} | ${d.code_load} | ${d.ic_core} | ${d.ai_score} | ${d.composite} | ${d.S}/${d.A} | ${rec} | ${d.email || '—'} | ${d.homepage ? '[主页](' + d.homepage + ')' : '—'} |\n`;
  });
  return t;
}

function recruiting(rows) {
  return rows.filter((d) => d.recruit_signal_count > 0);
}

let md = `# 2027 推免：按「集成电路设计本科 + 编程一般 + AI 重度使用者」重排的导师推荐

> **本报告与上一版名单的区别**：上一版只按"方向 + 学术实力 + 是否在招"排；这一版加入了两个**针对你个人背景**的新维度：
> **编程负担**（越低越适合你）与 **IC 核心度**（越高越贴近你的本科专业），并把候选人分成四条赛道。
> **生成日期**：2026-09-24 ｜ 数据：643 人候选池 + 231 人课题组主页实抓

---

## 〇、先说结论：你应该怎么定位自己

| 你的条件 | 对应策略 |
|:--|:--|
| ✅ 集成电路设计本科 | **不要丢掉这个身份**——这是你相对纯 CS/AI 同学最大的差异化优势 |
| ⚠️ 编程能力一般 | **避开"以写代码为主业"的组**：高性能计算、存储系统、编译/形式化验证、纯 AI 算法组 |
| ✅ AI 重度使用者 | 这不是"算法能力"，而是**效率工具能力**——用在"用 AI 辅助设计/验证/脚本/文献"的组里最吃香 |
| 🎯 最佳定位 | **IC 本体设计 + AI 工具化交叉**：模拟/电源 IC、数字 IC/SoC、存算一体、AI 芯片架构（硬件侧）、AI 辅助设计 |

**一句话**：去做"**懂 AI 的芯片设计师**"，而不是"做 AI 的算法工程师"。前者稀缺且你的本科背景直接对口；后者你要和计算机科班拼代码。

### 四条赛道对比

| 赛道 | 内容 | 编程负担 | 与 AI 的关系 | 就业出口 | 适合度 |
|:--|:--|:--|:--|:--|:--|
| **A** | 模拟 / 混合信号 / 电源管理 IC | ⭐ 最低（Cadence/Spectre 为主） | AI 是辅助（AI 辅助模拟设计、算力芯片供电） | 华为海思、TI/ADI、国产模拟厂、电源芯片公司 | 🟢 **最稳** |
| **B** | 数字 IC / SoC / 验证 / 后端 / 存算一体 | ⭐⭐ 中等（Verilog + 脚本） | AI 芯片的下游与基础 | 海思、中兴、寒武纪、地平线、EDA 三巨头 | 🟢 **最推荐** |
| **C** | AI 芯片架构 / 类脑 / 加速器 | ⭐⭐⭐ 中高（C++/SystemC/仿真器） | 最贴 AI | 英伟达、寒武纪、地平线、大厂芯片部门 | 🟡 **可冲** |
| **D** | AI for EDA / 高性能计算 / 存储系统 | ⭐⭐⭐⭐ 最高（Python/ML/C++ 算法） | 用 AI 做工具 | EDA 公司、互联网、研究所 | 🔴 **慎选** |

> ⚠️ 注意：赛道 C/D 里也有"硬件侧"的岗位（如架构定义、RTL 实现），进去后未必天天写算法。但**入组前的面试与第一年训练**会以代码为主，需要你有心理准备。

---

## 一、赛道 A：模拟 / 混合信号 / 电源管理 IC（编程负担最低，${trackA.length} 人）

> **为什么适合你**：这类工作 80% 时间在 Cadence Virtuoso / Spectre 上做电路设计、仿真、版图，代码量极小；且"AI 辅助模拟设计"正在成为热点——你会用 AI 工具反而是加分项。
> **代价**：学习曲线陡（要靠经验积累），出成果慢（一次流片 3–6 个月），但**越老越值钱**。

${tbl(trackA, 30)}

**这个赛道里主页明确在招的**：

${recruiting(trackA).slice(0, 12).map((d) => `- **${d.name_cn}**（${sh(d.school)}，${d.title}）｜${(d.lab_names || [])[0] || '课题组'}｜邮箱 \`${d.email || '见主页'}\`${d.recruit_signals[0] ? `\n  > ${d.recruit_signals[0].snippet.slice(0, 130)}` : ''}`).join('\n') || '（本赛道主页明确写招生的较少，建议按名单直接发信询问）'}

---

## 二、赛道 B：数字 IC / SoC / 验证 / 后端 / 存算一体（最推荐，${trackB.length} 人）

> **为什么适合你**：Verilog/RTL 是"结构化编程"，比算法代码友好得多；存算一体是**器件-电路-架构交叉**，正好吃你"IC 本科 + 懂 AI"的组合。
> **AI 使用场景**：用 LLM 辅助写 testbench、生成脚本、debug 时序——你这方面会比同学快。

${tbl(trackB, 35)}

**这个赛道里主页明确在招的**：

${recruiting(trackB).slice(0, 15).map((d) => `- **${d.name_cn}**（${sh(d.school)}，${d.title}）｜${(d.lab_names || [])[0] || '课题组'}｜邮箱 \`${d.email || '见主页'}\`${d.recruit_signals[0] ? `\n  > ${d.recruit_signals[0].snippet.slice(0, 130)}` : ''}`).join('\n') || '（同上，建议直接发信）'}

---

## 三、赛道 C：AI 芯片架构 / 类脑 / 加速器（与 AI 最贴，编程中等偏上，${trackC.length} 人）

> **为什么可冲**：这是"IC × AI"最正的交叉点，就业最热。但组里通常要跑架构仿真（gem5/SystemC/C++），**第一年会有代码阵痛期**。
> **建议**：如果你能在本科毕设里做出一个"用 Python 写的加速器性能模型"，进这类组会稳很多。

${tbl(trackC, 25)}

---

## 四、赛道 D：建议避开或谨慎评估（编程负担 ≥60，${trackD.length} 人）

> 这些组实力很强（很多是院士/领域大牛），但日常工作是**写系统/算法代码**：编译器、操作系统、存储系统、形式化验证、并行计算、纯 AI 算法。
> **除非**你愿意在一年内把编程补到科班水平，否则进去会很痛苦。

${tbl(trackD.slice(0, 20), 20)}

---

## 五、你需要补的能力（按投入产出排序）

| 优先级 | 技能 | 理由 | 建议投入 |
|:--|:--|:--|:--|
| ⭐⭐⭐⭐⭐ | **Verilog / SystemVerilog + 一个完整 RTL 项目** | 数字 IC 组的通用门槛；有项目就能聊 | 1–2 个月，做出一个能综合、能仿真的小模块（如 AXI 接口、简易 NPU MAC 阵列） |
| ⭐⭐⭐⭐⭐ | **Cadence Virtuoso / Spectre 基础操作** | 模拟组第一年全靠它；会了就是即战力 | 2–4 周（跟本科课程/实验室） |
| ⭐⭐⭐⭐ | **Python（够用即可）** | 跑数据处理、画图、写自动化脚本；**有 AI 辅助，你的门槛比前人低** | 持续，能用 AI 补语法 |
| ⭐⭐⭐⭐ | **用 AI 做芯片设计的实操经验** | 这是你相对同学的最大差异化：用 LLM 生成 testbench、写 Tcl 脚本、辅助读时序报告 | 做成 1 个小项目写进简历 |
| ⭐⭐⭐ | 数字 IC 流程认知（综合/DFT/布局布线） | 面试常问"你了解后端流程吗" | 看 1 本书/1 套课程 |
| ⭐⭐ | C++ / 体系结构仿真（gem5） | 只有冲赛道 C 才需要 | 冲 C 再补 |

---

## 六、邮件策略调整（针对你的背景）

在你上一版模板基础上，**把叙事改成"我是 IC 科班 + 我会用 AI 提效"**：

\`\`\`
主题：2027 级推免咨询 - [学校] - [姓名] - 集成电路设计（数字/模拟方向）

尊敬的 X 老师：

您好！我是 [学校] 集成电路设计与集成系统专业 2023 级本科生 [姓名]，
专业排名 [X/Y]（前 X%），预计获 2027 届推免资格。

我在您课题组主页看到「[引用他主页的招生原话]」，非常希望加入。

**我的 IC 基础**：
- 修过：数字集成电路设计 / 模拟集成电路设计 / 半导体器件 / Verilog HDL（成绩 [X]）
- 做过：[项目名，例如"基于 Verilog 的 XXX 模块设计，完成综合与仿真，面积/功耗 XXX"]
- 熟悉工具：[Cadence Virtuoso / Synopsys DC / ModelSim / Vivado]

**我的差异化**：我是 AI 工具的深度使用者，能用 LLM 辅助完成
testbench 生成、脚本编写、时序报告分析、文献综述等重复性工作，
在您组里可以把更多时间留给电路本身。

关注到您近期工作《[某篇 2025–2026 论文]》，其中 [一句话技术点] 我很感兴趣。
若您 2027 级还有推免名额，希望能有机会进一步沟通，也愿意提前做文献阅读或小任务。

[姓名] | [电话] | [邮箱] | [GitHub/主页]
\`\`\`

**三条实操建议**：
1. **不要主动强调"我编程不好"**，改成"我的优势在电路设计与 AI 工具提效"——这是事实，也是定位；
2. **模拟组看重基础课成绩**（模拟 IC、半导体物理），数字组看重**项目 + 工具**，邮件里分别突出；
3. 联系赛道 A/C 的老师时，**附一份 1 页的"电路设计作品集"**（原理图/版图截图 + 仿真结果），比简历更打动人。

---

## 七、时间线提醒

| 目标入学 | 关键节点 | 现在（2026-09）该做什么 |
|:--|:--|:--|
| **2027 级** | 预推免 2026 年 8–9 月｜推免系统 9 月底–10 月 | **最后窗口**：立即按赛道 A/B 名单发信，优先"主页明确在招"的 15+ 人 |
| **2028 级** | 夏令营 2027 年 5–7 月 | 现在联系导师做**前置科研/进组实习**，同时补 Verilog 与 Virtuoso |

---

## 八、局限

1. 「编程负担」是根据**研究方向关键词 + 院系**自动估计的（0–100），不是导师亲口所述，个别组可能有偏差；
2. 「在招信号」只反映**主页是否写了招生表述**，未写 ≠ 不招，写了 ≠ 有名额；
3. 赛道划分按主方向自动归类，跨方向导师请点开主页核对；
4. 本报告基于公开信息整理，**不构成录取承诺或报考建议**。

*数据文件：\`data/processed/profile_fit.json\`、\`profile_fit.csv\`*
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, md, 'utf8');
console.log('saved', OUT, (md.length / 1024).toFixed(0) + 'KB');
console.log('赛道A(模拟/电源)', trackA.length, '| 赛道B(数字/SoC/存算)', trackB.length, '| 赛道C(AI芯片)', trackC.length, '| 赛道D(慎选)', trackD.length);
console.log('赛道A在招:', recruiting(trackA).length, '| 赛道B在招:', recruiting(trackB).length, '| 赛道C在招:', recruiting(trackC).length);
