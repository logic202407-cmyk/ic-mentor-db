// classify.mjs — 论文→研究方向分类 + venue 分层（评分基础）
// 供 score.mjs 引用
export const VENUE_TIER = [
  // S：IC 领域最高殿堂 / 顶级体系结构会议（全部使用「整体词」匹配，避免 Microwave 误命中 MICRO）
  [/(international )?solid-state circuits conference|(^|\W)ISSCC(\W|$)/i, 'S', 'ISSCC'],
  [/journal of solid-state circuits|(^|\W)JSSC(\W|$)/i, 'S', 'JSSC'],
  [/symposium on vlsi (circuits|technology)/i, 'S', 'VLSI Symposium'],
  [/international symposium on computer architecture|(^|\W)ISCA(\W|$)/i, 'S', 'ISCA'],
  [/international symposium on microarchitecture|(^|\W)MICRO-?\d*(\W|$)/i, 'S', 'MICRO'],
  [/high-performance computer architecture|(^|\W)HPCA(\W|$)/i, 'S', 'HPCA'],
  [/architectural support for programming languages|(^|\W)ASPLOS(\W|$)/i, 'S', 'ASPLOS'],
  [/nature electronics/i, 'S', 'Nature Electronics'],
  [/international electron devices meeting|(^|\W)IEDM(\W|$)/i, 'S', 'IEDM'],
  // A：一流期刊/会议
  [/custom integrated circuits conference|(^|\W)CICC(\W|$)/i, 'A', 'CICC'],
  [/asian solid-state circuits|A-SSCC|(^|\W)ASSCC(\W|$)/i, 'A', 'A-SSCC'],
  [/european solid-state circuits|(^|\W)ESSCIRC(\W|$)/i, 'A', 'ESSCIRC'],
  [/radio frequency integrated circuits (symposium|conference)|(^|\W)RFIC(\W|$)/i, 'A', 'RFIC'],
  [/circuits and systems i|(^|\W)TCAS-?I(\W|$)/i, 'A', 'TCAS-I'],
  [/circuits and systems ii|(^|\W)TCAS-?II(\W|$)/i, 'A', 'TCAS-II'],
  [/very large scale integration|(^|\W)TVLSI(\W|$)/i, 'A', 'TVLSI'],
  [/computer-aided design of integrated circuits|(^|\W)TCAD(\W|$)/i, 'A', 'TCAD'],
  [/transactions on electron devices|(^|\W)TED(\W|$)/i, 'A', 'TED'],
  [/microwave theory and techniques|(^|\W)MTT(\W|$)/i, 'A', 'MTT'],
  [/biomedical circuits and systems|(^|\W)TBioCAS(\W|$)/i, 'A', 'TBioCAS'],
  [/transactions on power electronics|(^|\W)TPEL(\W|$)/i, 'A', 'TPEL'],
  [/transactions on computers\b|(^|\W)IEEE Trans.*\bComputers\b/i, 'A', 'TC'],
  [/design automation conference|(^|\W)DAC(\W|$)/i, 'A', 'DAC'],
  [/computer-aided design.*(conference|ICCAD)|(^|\W)ICCAD(\W|$)/i, 'A', 'ICCAD'],
  [/field-programmable gate arrays|(^|\W)FPGA(\W|$)/i, 'A', 'FPGA'],
  [/solid-state circuits letters|(^|\W)SSC-?L(\W|$)/i, 'A', 'SSC-L'],
  [/journal of lightwave technology/i, 'A', 'JLT'],
  // B：良好期刊/会议
  [/electron device letters|(^|\W)EDL(\W|$)/i, 'B', 'EDL'],
  [/microwave and wireless (components|technology) letters|(^|\W)MWCL(\W|$)|(^|\W)MWTL(\W|$)/i, 'B', 'MWCL/MWTL'],
  [/emerging and selected topics in circuits|(^|\W)JETCAS(\W|$)/i, 'B', 'JETCAS'],
  [/open journal of the solid-state circuits|(^|\W)OJSSCS(\W|$)/i, 'B', 'OJSSCS'],
  [/^IEEE Micro$/i, 'B', 'IEEE Micro'],
  [/low power electronics and design|(^|\W)ISLPED(\W|$)/i, 'B', 'ISLPED'],
  [/asian and south pacific design automation|(^|\W)ASP-?DAC(\W|$)/i, 'B', 'ASP-DAC'],
  [/international symposium on circuits and systems|(^|\W)ISCAS(\W|$)/i, 'B', 'ISCAS'],
  [/international microwave symposium|(^|\W)IMS(\W|$)/i, 'B', 'IMS'],
  [/photonics technology letters|(^|\W)PTL(\W|$)/i, 'B', 'PTL'],
  [/transactions on antennas and propagation|(^|\W)TAP(\W|$)/i, 'B', 'TAP'],
  [/transactions on biomedical engineering|(^|\W)TBME(\W|$)/i, 'B', 'TBME'],
  [/IEEE Sensors (Journal|Letters)/i, 'B', 'IEEE Sensors'],
  [/transactions on industrial electronics|(^|\W)TIE(\W|$)/i, 'B', 'TIE'],
  [/transactions on instrumentation and measurement|(^|\W)TIM(\W|$)/i, 'B', 'TIM'],
  [/transactions on signal processing|(^|\W)TSP(\W|$)/i, 'B', 'TSP'],
  [/transactions on wireless communications|(^|\W)TWC(\W|$)/i, 'B', 'TWC'],
  [/transactions on communications|(^|\W)TCOM(\W|$)/i, 'B', 'TCOM'],
  [/reliability physics symposium|(^|\W)IRPS(\W|$)/i, 'B', 'IRPS'],
  [/nature communications|science advances|advanced materials|nature nanotechnology/i, 'B', 'Nature子刊/AdvMater'],
];

// 研究方向大类（顺序即优先级；同时支持英文论文文本与中文官方方向关键词）
export const DIRECTIONS = [
  {
    key: 'analog',
    name: '模拟/混合信号/电源管理IC',
    kw: /analog|amplifier|opamp|operational amplifier|ADC|DAC|data converter|sigma-delta|delta-sigma|PLL|phase-locked|bandgap|power management|DC-DC|LDO|buck|boost|charge pump|energy harvesting|PMIC|voltage regulator|IVR|Class-D|switched-capacitor|serdes|transceiver|equalizer|CDR|mixed-signal|模拟|混合信号|数模混合|电源管理|电源芯片|基准源|放大器|运算放大器|比较器|锁相环|时钟|数据转换器|转换器|驱动芯片|能量采集|能量收集|无线充电|无线供能|低功耗电路|模拟集成电路|模拟电路|电源|参考电压|振荡器|VCO|滤波器|SerDes|高速接口/i,
  },
  {
    key: 'rf',
    name: '射频/毫米波/太赫兹/天线',
    kw: /RF\b|radio frequency|mm-wave|mmWave|millimeter|terahertz|THz|LNA|power amplifier|mixer|frequency synthesizer|phased array|antenna|radar|front-end|beamforming|reflectarray|metasurface|microwave|射频|毫米波|太赫兹|微波|天线|相控阵|雷达|收发机|功率放大器|频率综合器|低噪声放大器|混频器|波束成形|超表面|电磁场与微波|无源器件|封装天线/i,
  },
  {
    key: 'digital_ai',
    name: '数字/AI芯片/处理器体系结构',
    kw: /accelerator|processor|SoC|system-on-chip|RISC-V|CPU|GPU|GPGPU|NPU|neural network hardware|deep learning accelerator|DNN|transformer accelerator|architecture|many-core|NoC|network-on-chip|FPGA|high-level synthesis|in-memory computing|near-memory|compute-in-memory|CIM|PIM|digital circuit|low-power design|systolic|sparse|quantization hardware|edge AI|hardware security|physical unclonable|PUF|数字集成电路|数字电路|处理器|体系结构|架构|加速器|人工智能芯片|AI芯片|智能芯片|存算一体|存内计算|近存计算|忆阻|片上网络|类脑|神经网络|硬件加速|深度学习|可重构|算力|微处理器|智能计算|芯片架构|计算机体系结构|智能芯片设计|处理器设计|SoC设计|系统芯片|嵌入式|硬件安全|密码芯片|同态加密/i,
  },
  {
    key: 'eda',
    name: 'EDA/设计自动化/封装集成',
    kw: /EDA|electronic design automation|physical design|placement|routing|logic synthesis|formal verification|timing analysis|design for test|DFT|test generation|yield|3D IC|chiplet|thermal analysis|layout|LVS|DRC|设计自动化|物理设计|布局布线|逻辑综合|形式验证|时序分析|可测性|测试生成|良率|三维集成|芯粒|封装|多物理场|建模仿真|设计方法学|电路仿真|器件建模|可靠性设计/i,
  },
  {
    key: 'device',
    name: '器件/工艺/宽禁带/存储',
    kw: /device|transistor|FinFET|GAA|nanosheet|MOSFET|HEMT|GaN|SiC|wide bandgap|power device|RRAM|ReRAM|MRAM|memristor|ferroelectric|memory device|3D NAND|flash memory|DRAM|process integration|fabrication|thin film|dielectric|Ga2O3|IGZO|tunnel FET|quantum dot|器件|工艺|晶体管|存储器|存储器件|阻变|铁电|相变存储|宽禁带|氮化镓|碳化硅|氧化镓|二维材料|半导体材料|微纳加工|薄膜|功率器件|互连|先进封装|纳米线|异质集成|外延|光刻|刻蚀|薄膜沉积|器件物理|可靠性|辐照/i,
  },
  {
    key: 'photonics',
    name: '光电/硅光/光计算/成像',
    kw: /photonic|silicon photonic|optical|laser|waveguide|modulator|photodetector|LiDAR|optoelectronic|light-emitting|LED|display|micro-LED|imaging sensor|CMOS image sensor|CIS|SPAD|single-photon|holograph|optical computing|fiber|光电|光子|硅光|激光|波导|调制器|探测器|光计算|光互连|光通信|成像|图像传感器|显示|发光二极管|光学|红外|光传感|计算成像|光谱|光芯片|集成光电子/i,
  },
  {
    key: 'mems',
    name: 'MEMS/传感器/生物医疗电子',
    kw: /MEMS|microelectromechanical|accelerometer|gyroscope|resonator|microfluidic|lab-on-chip|implantable|biomedical|neural interface|biosensor|wearable|flexible electronics|ultrasound|piezoelectric|transducer|microfabrication|MEMS|微机电|陀螺|谐振器|微流控|植入|生物医学电子|神经接口|生物传感器|可穿戴|柔性电子|超声|压电|换能器|微纳传感|传感器|智能传感|执行器|声学器件|脑机接口/i,
  },
  {
    key: 'power',
    name: '电力电子/功率集成/能源',
    kw: /power electronics|inverter|motor drive|photovoltaic|battery management|wireless power transfer|gate driver|grid|电力电子|变流器|逆变器|电机驱动|光伏|电池管理|无线输能|门极驱动|电网|变换器|拓扑|磁性元件|能源系统/i,
  },
  {
    key: 'quantum',
    name: '量子芯片/低温电子学',
    kw: /quantum|qubit|superconducting qubit|cryogenic|Josephson|spin qubit|quantum control|量子|量子比特|超导|低温电子学|低温集成电路|约瑟夫森|自旋量子|量子测控/i,
  },
];

export function classifyPaper(p) {
  const text = `${p.title || ''} ${p.venue || ''}`;
  let tier = null, venueKey = null;
  for (const [re, t, k] of VENUE_TIER) {
    if (re.test(p.venue || '')) { tier = t; venueKey = k; break; }
  }
  const dirs = [];
  for (const d of DIRECTIONS) if (d.kw.test(text)) dirs.push(d.key);
  // venue 强信号：DAC/ICCAD/TCAD 论文一律计入 EDA 方向（避免被数字/器件方向淹没）
  if (venueKey === 'DAC' || venueKey === 'ICCAD' || venueKey === 'TCAD') dirs.push('eda', 'eda');
  return { tier, venueKey, dirs: dirs.length ? dirs : ['other'] };
}

// 高辨识度关键词：命中即给该方向额外加权（避免「模拟电路设计自动化」被误判为纯模拟）
export const STRONG_KW = {
  eda: /EDA|电子设计自动化|设计自动化|物理设计|布局布线|逻辑综合|可测性|设计方法学|形式验证/i,
  digital_ai: /AI芯片|人工智能芯片|智能芯片|存算一体|存内计算|近存计算|处理器|体系结构|加速器|类脑|RISC-V|算力芯片|GPGPU|片上网络/i,
  analog: /模拟集成电路|模拟电路|混合信号|数模混合|电源管理|ADC|DAC|锁相环|放大器/i,
  rf: /射频|毫米波|太赫兹|微波|天线|相控阵|雷达/i,
  device: /器件|工艺|宽禁带|氮化镓|碳化硅|存储器|阻变|铁电|微纳加工/i,
  photonics: /硅光|光子|光电|光计算|激光|光互连|光芯片/i,
  mems: /MEMS|微机电|传感器|微流控|可穿戴|柔性电子/i,
  power: /电力电子|功率集成|变流器|电机|无线输能/i,
  quantum: /量子|超导|低温电子/i,
};
