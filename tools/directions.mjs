// directions.mjs — 方向分类：把页面关键词归入若干研究方向
// 只用页面自述里出现的词做匹配，不做任何推断
export const DIRS = [
  { key: 'cim', name: '存算一体 / 存内计算', color: '#f472b6',
    re: /存算一体|存内计算|近存计算|内存计算|以存储为中心|存算融合|In-?Memory Computing|Computing-?in-?Memory|CIM|PIM|忆阻器|阻变|RRAM|ReRAM|相变存储|PCRAM|MRAM|自旋存储|铁电存储|闪存|Flash|三维存储|3D NAND/i },
  { key: 'spin', name: '自旋电子 / 新型信息器件', color: '#a78bfa',
    re: /自旋电子|自旋器件|磁隧道结|MTJ|自旋轨道矩|SOT|自旋霍尔|磁存储|磁传感器|拓扑绝缘体|二维材料|石墨烯|碳纳米管|量子器件|量子计算|量子输运|伊辛/i },
  { key: 'ai', name: 'AI 芯片 / 计算架构', color: '#60a5fa',
    re: /AI ?芯片|人工智能芯片|智能芯片|加速器|领域专用|专用芯片|ASIC|处理器架构|微处理器|CPU|GPU|RISC-?V|SoC|片上系统|体系结构|架构设计|高能效计算|边缘计算|类脑|神经形态|脉冲神经/i },
  { key: 'analog', name: '模拟 / 射频 / 微波', color: '#34d399',
    re: /模拟集成电路|模拟电路|射频|微波|毫米波|太赫兹|天线|功率放大器|锁相环|PLL|ADC|DAC|数据转换器|收发机|滤波器|电磁|无线|雷达|5G|6G|相控阵/i },
  { key: 'power', name: '功率半导体 / 宽禁带器件', color: '#fbbf24',
    re: /功率半导体|功率器件|宽禁带|GaN|氮化镓|SiC|碳化硅|氧化镓|Ga2O3|IGBT|电力电子|功率集成电路|LDMOS|BCD|高压|器件可靠性/i },
  { key: 'photon', name: '光电 / 硅光子', color: '#22d3ee',
    re: /光电子|光子|硅光|光芯片|激光器|光电探测|光通信|光互连|光调制|波导|LED|显示|Micro-?LED|成像|图像传感|红外|光伏/i },
  { key: 'eda', name: 'EDA / 设计自动化', color: '#c084fc',
    re: /EDA|电子设计自动化|设计自动化|物理设计|布局布线|逻辑综合|形式验证|仿真器|寄生提取|可测性设计|DFT|良率/i },
  { key: 'sensor', name: '传感器 / MEMS', color: '#fb923c',
    re: /MEMS|微机电|传感器|执行器|陀螺|加速度计|谐振器|微流控|生物传感|气体传感|柔性电子|可穿戴/i },
  { key: 'reliable', name: '可靠性 / 测试 / 安全', color: '#94a3b8',
    re: /可靠性|失效分析|老化|辐照|抗辐照|测试|可测性|芯片安全|硬件安全|故障|容错|ESD|静电防护/i },
  { key: 'comm', name: '通信 / 信号处理', color: '#4ade80',
    re: /通信|信号处理|编码|调制|信息论|信道|基带|网络|协议|物联网|无线传感网/i },
  { key: 'matproc', name: '材料 / 工艺 / 器件物理', color: '#f87171',
    re: /半导体材料|外延|薄膜|工艺|光刻|刻蚀|氧化|退火|器件物理|半导体物理|异质结|能带|载流子|界面|介质|高k|金属化|封装|键合|先进封装|Chiplet|三维集成/i },
  { key: 'power_sys', name: '电源 / 电力电子系统', color: '#e879f9',
    re: /电源管理|开关电源|DC-?DC|LDO|能量采集|电池管理|充电|电机驱动|逆变/i },
];

// 归入第一个命中的方向（按上面的优先级顺序）
export function classifyDir(kw, fallback) {
  const s = String(kw || '');
  if (!s.trim()) return fallback || 'unknown';
  for (const d of DIRS) if (d.re.test(s)) return d.key;
  return 'other';
}
export const DIR_MAP = Object.fromEntries(DIRS.map((d) => [d.key, d]));
DIR_MAP.other = { key: 'other', name: '其他 / 未归类', color: '#64748b' };
DIR_MAP.unknown = { key: 'unknown', name: '无关键词记录', color: '#3f4855' };
