# -*- coding: utf-8 -*-
"""视觉素材自动生成脚本 (Visual Assets Generator)

为《循证知途》平台生成全套学术蓝白风格的高品质矢量 SVG 与透明 WebP 素材。
符合学术规范、专业性、中立性与美学标准：
- 零商业 Banner、零导师照片、零假头像、零主观评分
- 统一现代学术蓝 (#1e60d5)、低饱和青蓝 (#0284c7)、鼠尾草绿 (#10b981)、极浅蓝灰 (#f8fafc)
- 纯透明背景 (Alpha Channel) + 边缘羽化与细腻光晕
"""

import os
import sys
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = Path("workbench/web/assets/visuals")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. 首页 Hero 主视觉 (hero-academic.svg)
HERO_ACADEMIC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 560" width="900" height="560" fill="none">
  <defs>
    <linearGradient id="heroBlueGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0284c7" stop-opacity="0.9"/>
      <stop offset="60%" stop-color="#1e60d5" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#1e3a8a" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="heroCyanGrad" x1="0" y1="0" x2="1" y2="0.8">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
    <linearGradient id="heroEmeraldGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>
    <linearGradient id="paperGrad" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#f1f5f9" stop-opacity="0.85"/>
    </linearGradient>
    <radialGradient id="heroGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.25"/>
      <stop offset="60%" stop-color="#1e60d5" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#1e60d5" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadowLight" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#1e3a8a" flood-opacity="0.12"/>
    </filter>
    <filter id="glowFilt" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- 柔和背景光晕层 -->
  <circle cx="480" cy="270" r="260" fill="url(#heroGlow)" />
  <circle cx="680" cy="200" r="180" fill="url(#heroGlow)" opacity="0.6"/>

  <!-- 几何坐标网格与连接轨道 -->
  <g opacity="0.4" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 6">
    <circle cx="450" cy="280" r="210"/>
    <circle cx="450" cy="280" r="140"/>
    <circle cx="620" cy="200" r="90"/>
    <line x1="220" y1="280" x2="720" y2="280"/>
    <line x1="450" y1="70" x2="450" y2="490"/>
  </g>

  <!-- 学术文献层叠图层 (左中) -->
  <g transform="translate(180, 140)" filter="url(#shadowLight)">
    <!-- 底层文献 -->
    <rect x="0" y="40" width="220" height="280" rx="14" fill="#e2e8f0" transform="rotate(-7 110 180)"/>
    <!-- 中层文献 -->
    <rect x="15" y="20" width="220" height="280" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" transform="rotate(-2 125 160)"/>
    <!-- 顶层学术专著/档案卡片 -->
    <rect x="30" y="0" width="230" height="290" rx="14" fill="url(#paperGrad)" stroke="#93c5fd" stroke-width="2"/>
    <!-- 卡片装饰纹理与文字线 -->
    <rect x="52" y="32" width="70" height="12" rx="4" fill="url(#heroBlueGrad)"/>
    <rect x="52" y="56" width="130" height="8" rx="3" fill="#94a3b8" opacity="0.5"/>
    <rect x="52" y="74" width="165" height="6" rx="3" fill="#cbd5e1"/>
    <rect x="52" y="90" width="145" height="6" rx="3" fill="#cbd5e1"/>
    <rect x="52" y="106" width="120" height="6" rx="3" fill="#cbd5e1"/>

    <!-- 迷你图表区域 -->
    <rect x="52" y="132" width="186" height="84" rx="8" fill="#f8fafc" stroke="#e2e8f0"/>
    <path d="M68 190 Q 110 160, 145 175 T 222 148" fill="none" stroke="url(#heroCyanGrad)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="145" cy="175" r="4.5" fill="#1e60d5"/>
    <circle cx="222" cy="148" r="4.5" fill="#10b981"/>

    <!-- 证据存证印章微章 -->
    <g transform="translate(160, 226)">
      <circle cx="36" cy="36" r="28" fill="#ecfdf5" stroke="#10b981" stroke-width="1.8" stroke-dasharray="3 2"/>
      <path d="M26 36 L33 43 L48 28" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
  </g>

  <!-- 动态知识网络节点系统 (右中) -->
  <g>
    <!-- 节点间曲线链路 -->
    <path d="M390 240 C 460 160, 560 180, 620 140" fill="none" stroke="#60a5fa" stroke-width="2.5" opacity="0.8"/>
    <path d="M620 140 C 690 110, 750 170, 760 250" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0.7"/>
    <path d="M620 140 C 600 230, 520 280, 530 360" fill="none" stroke="#93c5fd" stroke-width="2" stroke-dasharray="5 4"/>
    <path d="M530 360 C 590 410, 700 390, 750 330" fill="none" stroke="#34d399" stroke-width="2.2" opacity="0.8"/>
    <path d="M760 250 C 780 290, 770 310, 750 330" fill="none" stroke="#60a5fa" stroke-width="2"/>

    <!-- 知识节点 1 (核心顶) -->
    <g transform="translate(620, 140)" filter="url(#glowFilt)">
      <circle cx="0" cy="0" r="24" fill="url(#heroBlueGrad)"/>
      <circle cx="0" cy="0" r="32" stroke="#60a5fa" stroke-width="1.5" opacity="0.6"/>
      <!-- 学术图书小图标 -->
      <path d="M-8 -6 C-4 -8, 0 -7, 0 8 C0 -7, 4 -8, 8 -6 M0 -7 L0 8" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round"/>
    </g>

    <!-- 知识节点 2 (右侧网络) -->
    <g transform="translate(760, 250)">
      <circle cx="0" cy="0" r="18" fill="url(#heroCyanGrad)"/>
      <circle cx="0" cy="0" r="26" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="3 3"/>
      <circle cx="0" cy="0" r="6" fill="#ffffff"/>
    </g>

    <!-- 知识节点 3 (核验绿色节点) -->
    <g transform="translate(750, 330)" filter="url(#glowFilt)">
      <circle cx="0" cy="0" r="17" fill="url(#heroEmeraldGrad)"/>
      <path d="M-5 0 L-1 4 L6 -4" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- 知识节点 4 (下侧分支) -->
    <g transform="translate(530, 360)">
      <circle cx="0" cy="0" r="15" fill="#1e3a8a"/>
      <circle cx="0" cy="0" r="5" fill="#38bdf8"/>
    </g>

    <!-- 漂浮学术数据胶囊 -->
    <g transform="translate(680, 190)" filter="url(#shadowLight)">
      <rect x="0" y="0" width="110" height="32" rx="16" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
      <circle cx="16" cy="16" r="6" fill="#10b981"/>
      <text x="32" y="20" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="12" font-weight="600" fill="#1e3a8a">工学 · 0811</text>
    </g>

    <g transform="translate(480, 170)" filter="url(#shadowLight)">
      <rect x="0" y="0" width="124" height="32" rx="16" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
      <circle cx="16" cy="16" r="6" fill="#0284c7"/>
      <text x="30" y="20" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="12" font-weight="600" fill="#0f172a">客观证据溯源</text>
    </g>
  </g>

  <!-- 居中证据追踪放大镜 (Evidence Tracing Magnifier) -->
  <g transform="translate(440, 220)" filter="url(#shadowLight)">
    <!-- 镜柄 -->
    <path d="M55 55 L105 105" stroke="#1e293b" stroke-width="14" stroke-linecap="round"/>
    <path d="M55 55 L105 105" stroke="#3b82f6" stroke-width="6" stroke-linecap="round"/>
    <!-- 镜框 -->
    <circle cx="15" cy="15" r="62" fill="url(#paperGrad)" stroke="#1e3a8a" stroke-width="7"/>
    <circle cx="15" cy="15" r="58" stroke="#38bdf8" stroke-width="2.5" opacity="0.9"/>
    <!-- 透镜光泽 -->
    <path d="M-20 -15 A 40 40 0 0 1 35 -30" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" opacity="0.8"/>
    <!-- 镜中聚焦靶心 -->
    <circle cx="15" cy="15" r="14" stroke="#1e60d5" stroke-width="2.5" stroke-dasharray="3 2" fill="none"/>
    <circle cx="15" cy="15" r="4.5" fill="#10b981"/>
  </g>

  <!-- 微粒星点 -->
  <circle cx="340" cy="110" r="3" fill="#38bdf8" opacity="0.8"/>
  <circle cx="820" cy="180" r="3.5" fill="#60a5fa" opacity="0.8"/>
  <circle cx="580" cy="440" r="2.5" fill="#34d399" opacity="0.9"/>
  <circle cx="210" cy="380" r="3" fill="#93c5fd" opacity="0.7"/>
</svg>"""

# 2. 首页 Hero 移动端专版 (hero-academic-mobile.svg)
HERO_ACADEMIC_MOBILE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 320" width="500" height="320" fill="none">
  <defs>
    <linearGradient id="mBlueGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#1e3a8a"/>
    </linearGradient>
    <radialGradient id="mGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#1e60d5" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="250" cy="160" r="140" fill="url(#mGlow)"/>
  <!-- 简化文献卡 -->
  <g transform="translate(80, 50)">
    <rect x="0" y="15" width="160" height="210" rx="10" fill="#e2e8f0" transform="rotate(-4 80 110)"/>
    <rect x="15" y="0" width="170" height="220" rx="10" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
    <rect x="35" y="25" width="60" height="10" rx="3" fill="url(#mBlueGrad)"/>
    <rect x="35" y="45" width="100" height="6" rx="2" fill="#cbd5e1"/>
    <rect x="35" y="60" width="125" height="6" rx="2" fill="#cbd5e1"/>
    <rect x="35" y="75" width="90" height="6" rx="2" fill="#cbd5e1"/>
    <rect x="35" y="100" width="130" height="60" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
    <path d="M48 140 Q 80 120, 110 130 T 150 115" fill="none" stroke="#0284c7" stroke-width="2.5" stroke-linecap="round"/>
  </g>
  <!-- 放大镜与节点 -->
  <g transform="translate(260, 120)">
    <path d="M40 40 L80 80" stroke="#1e293b" stroke-width="10" stroke-linecap="round"/>
    <circle cx="10" cy="10" r="46" fill="#ffffff" stroke="#1e3a8a" stroke-width="5"/>
    <circle cx="10" cy="10" r="43" stroke="#38bdf8" stroke-width="2" opacity="0.9"/>
    <circle cx="10" cy="10" r="5" fill="#10b981"/>
  </g>
  <g transform="translate(380, 70)">
    <circle cx="0" cy="0" r="16" fill="url(#mBlueGrad)"/>
    <circle cx="0" cy="0" r="5" fill="#ffffff"/>
  </g>
</svg>"""

# 3. 学科导航横幅 (discipline-explore.svg)
DISCIPLINE_EXPLORE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 320" width="960" height="320" fill="none">
  <defs>
    <linearGradient id="discGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="50%" stop-color="#1e60d5"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <radialGradient id="discGlow" cx="60%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#1e60d5" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="960" height="320" fill="url(#discGlow)"/>

  <!-- 学科网状树状骨架 -->
  <g stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6">
    <line x1="280" y1="160" x2="420" y2="90"/>
    <line x1="280" y1="160" x2="420" y2="160"/>
    <line x1="280" y1="160" x2="420" y2="230"/>
    <line x1="420" y1="90" x2="560" y2="60"/>
    <line x1="420" y1="90" x2="560" y2="120"/>
    <line x1="420" y1="160" x2="560" y2="160"/>
    <line x1="420" y1="230" x2="560" y2="200"/>
    <line x1="420" y1="230" x2="560" y2="260"/>
    <line x1="560" y1="60" x2="720" y2="40"/>
    <line x1="560" y1="120" x2="720" y2="110"/>
    <line x1="560" y1="160" x2="720" y2="160"/>
    <line x1="560" y1="200" x2="720" y2="210"/>
    <line x1="560" y1="260" x2="720" y2="280"/>
  </g>

  <!-- 根节点：工学总类 -->
  <g transform="translate(280, 160)">
    <circle cx="0" cy="0" r="30" fill="url(#discGrad)"/>
    <circle cx="0" cy="0" r="38" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="3 3"/>
    <text x="0" y="5" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="14" font-weight="700" fill="#ffffff" text-anchor="middle">工学</text>
  </g>

  <!-- 二级分支群 -->
  <g transform="translate(420, 90)">
    <circle cx="0" cy="0" r="22" fill="#1e40af"/>
    <text x="0" y="4" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="11" font-weight="600" fill="#ffffff" text-anchor="middle">信息类</text>
  </g>
  <g transform="translate(420, 160)">
    <circle cx="0" cy="0" r="22" fill="#0284c7"/>
    <text x="0" y="4" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="11" font-weight="600" fill="#ffffff" text-anchor="middle">装备制造</text>
  </g>
  <g transform="translate(420, 230)">
    <circle cx="0" cy="0" r="22" fill="#0f766e"/>
    <text x="0" y="4" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="11" font-weight="600" fill="#ffffff" text-anchor="middle">材料化工</text>
  </g>

  <!-- 三级精细学科标签胶囊 -->
  <g transform="translate(560, 60)">
    <rect x="-10" y="-14" width="110" height="28" rx="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.2"/>
    <circle cx="4" cy="0" r="4" fill="#2563eb"/>
    <text x="18" y="4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="600" fill="#1e3a8a">0812 计算机</text>
  </g>
  <g transform="translate(560, 120)">
    <rect x="-10" y="-14" width="110" height="28" rx="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.2"/>
    <circle cx="4" cy="0" r="4" fill="#0284c7"/>
    <text x="18" y="4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="600" fill="#1e3a8a">0811 控制工程</text>
  </g>
  <g transform="translate(560, 160)">
    <rect x="-10" y="-14" width="110" height="28" rx="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.2"/>
    <circle cx="4" cy="0" r="4" fill="#10b981"/>
    <text x="18" y="4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="600" fill="#1e3a8a">0802 机械工程</text>
  </g>
  <g transform="translate(560, 200)">
    <rect x="-10" y="-14" width="110" height="28" rx="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.2"/>
    <circle cx="4" cy="0" r="4" fill="#0d9488"/>
    <text x="18" y="4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="600" fill="#1e3a8a">0805 材料科学</text>
  </g>
  <g transform="translate(560, 260)">
    <rect x="-10" y="-14" width="110" height="28" rx="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.2"/>
    <circle cx="4" cy="0" r="4" fill="#6366f1"/>
    <text x="18" y="4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="600" fill="#1e3a8a">0817 化学工程</text>
  </g>

  <!-- 38 学科总收录徽标 -->
  <g transform="translate(770, 130)">
    <rect x="0" y="0" width="150" height="60" rx="12" fill="#ffffff" stroke="#93c5fd" stroke-width="1.5"/>
    <text x="75" y="26" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="12" font-weight="600" fill="#64748b" text-anchor="middle">全景知识谱系</text>
    <text x="75" y="48" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="16" font-weight="700" fill="#1e60d5" text-anchor="middle">38 一级学科</text>
  </g>
</svg>"""

# 4. 导师检索空状态 (search-empty.svg)
SEARCH_EMPTY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 260" width="380" height="260" fill="none">
  <defs>
    <linearGradient id="seBlue" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#1e60d5"/>
    </linearGradient>
    <radialGradient id="seGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#0284c7" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="190" cy="130" r="110" fill="url(#seGlow)"/>

  <!-- 档案文件夹背景 -->
  <g transform="translate(100, 45)">
    <!-- 后封皮 -->
    <path d="M0 16 C0 7 7 0 16 0 L60 0 C68 0 74 6 78 12 L90 24 L164 24 C173 24 180 31 180 40 L180 154 C180 163 173 170 164 170 L16 170 C7 170 0 163 0 154 Z" fill="#cbd5e1"/>
    <!-- 内部文献纸张 -->
    <rect x="18" y="22" width="144" height="136" rx="6" fill="#ffffff" stroke="#e2e8f0"/>
    <rect x="36" y="42" width="54" height="8" rx="2" fill="url(#seBlue)"/>
    <rect x="36" y="58" width="108" height="5" rx="2" fill="#cbd5e1"/>
    <rect x="36" y="70" width="92" height="5" rx="2" fill="#cbd5e1"/>
    <rect x="36" y="82" width="100" height="5" rx="2" fill="#cbd5e1"/>
    <!-- 前封皮 -->
    <path d="M0 48 C0 39 7 32 16 32 L164 32 C173 32 180 39 180 48 L180 154 C180 163 173 170 164 170 L16 170 C7 170 0 163 0 154 Z" fill="#e2e8f0" opacity="0.95"/>
    <rect x="24" y="54" width="70" height="14" rx="4" fill="#ffffff" stroke="#93c5fd"/>
    <text x="32" y="65" font-family="-apple-system, sans-serif" font-size="9" font-weight="700" fill="#1e40af">导师调查档案</text>
  </g>

  <!-- 放大镜与聚焦 -->
  <g transform="translate(195, 115)">
    <path d="M38 38 L72 72" stroke="#1e293b" stroke-width="10" stroke-linecap="round"/>
    <circle cx="10" cy="10" r="44" fill="#ffffff" stroke="#1e40af" stroke-width="5"/>
    <circle cx="10" cy="10" r="41" stroke="#38bdf8" stroke-width="1.8"/>
    <!-- 聚焦标记 -->
    <circle cx="10" cy="10" r="10" stroke="#10b981" stroke-width="2" stroke-dasharray="3 2" fill="none"/>
    <path d="M6 10 L9 13 L15 7" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg>"""

# 5. 调查记录空状态 (records-empty.svg)
RECORDS_EMPTY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" height="220" fill="none">
  <defs>
    <linearGradient id="reBlue" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1e60d5"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>

  <!-- 调查记事本 -->
  <g transform="translate(85, 30)">
    <!-- 阴影 -->
    <rect x="10" y="10" width="140" height="160" rx="12" fill="#000000" opacity="0.06"/>
    <!-- 封面 -->
    <rect x="0" y="0" width="140" height="160" rx="12" fill="url(#reBlue)"/>
    <!-- 书脊装订线 -->
    <line x1="24" y1="0" x2="24" y2="160" stroke="#38bdf8" stroke-width="1.5" opacity="0.5"/>
    <!-- 缎带书签 -->
    <path d="M80 0 L80 90 L90 80 L100 90 L100 0 Z" fill="#38bdf8"/>
    <!-- 封面徽章 -->
    <circle cx="70" cy="80" r="26" fill="#ffffff" opacity="0.15"/>
    <circle cx="70" cy="80" r="20" stroke="#ffffff" stroke-width="1.5"/>
    <!-- 锁头/隐私保护图标 -->
    <rect x="63" y="76" width="14" height="10" rx="2" fill="#ffffff"/>
    <path d="M66 76 V71 C66 69 68 67 70 67 C72 67 74 69 74 71 V76" stroke="#ffffff" stroke-width="1.8" fill="none"/>
  </g>

  <!-- 书写笔 -->
  <g transform="translate(195, 110) rotate(-40)">
    <rect x="0" y="0" width="10" height="70" rx="3" fill="#ffffff" stroke="#94a3b8" stroke-width="1.2"/>
    <path d="M0 70 L5 82 L10 70 Z" fill="#0284c7"/>
    <circle cx="5" cy="81" r="1" fill="#0f172a"/>
  </g>
</svg>"""

# 6. 数据来源体系总览 (source-academic.svg)
SOURCE_ACADEMIC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 260" width="880" height="260" fill="none">
  <defs>
    <linearGradient id="srcGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#1e60d5"/>
    </linearGradient>
    <radialGradient id="srcGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#1e60d5" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="880" height="260" fill="url(#srcGlow)"/>

  <!-- 4 大来源流线汇聚至中央账本 -->
  <g stroke="#93c5fd" stroke-width="2" stroke-dasharray="4 4" opacity="0.7">
    <path d="M140 130 C 260 130, 320 130, 410 130"/>
    <path d="M740 130 C 620 130, 560 130, 470 130"/>
  </g>

  <!-- 左1: 学校官网 -->
  <g transform="translate(70, 75)">
    <rect x="0" y="0" width="130" height="110" rx="10" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
    <circle cx="65" cy="40" r="22" fill="#eff6ff"/>
    <text x="65" y="47" font-size="22" text-anchor="middle">🏛️</text>
    <text x="65" y="80" font-family="-apple-system, sans-serif" font-size="12" font-weight="700" fill="#1e3a8a" text-anchor="middle">高校官方信息</text>
    <text x="65" y="98" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">院系主页直录</text>
  </g>

  <!-- 左2: 招生简章 -->
  <g transform="translate(230, 75)">
    <rect x="0" y="0" width="130" height="110" rx="10" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
    <circle cx="65" cy="40" r="22" fill="#eff6ff"/>
    <text x="65" y="47" font-size="22" text-anchor="middle">📑</text>
    <text x="65" y="80" font-family="-apple-system, sans-serif" font-size="12" font-weight="700" fill="#1e3a8a" text-anchor="middle">研究生招生目录</text>
    <text x="65" y="98" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">年份严格标注</text>
  </g>

  <!-- 中央核心：证据核验节点 -->
  <g transform="translate(390, 65)">
    <circle cx="50" cy="65" r="50" fill="url(#srcGrad)"/>
    <circle cx="50" cy="65" r="60" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4 3"/>
    <!-- 盾牌印章 -->
    <path d="M50 38 L70 48 V66 C70 80, 50 90, 50 90 C50 90, 30 80, 30 66 V48 Z" fill="#ffffff" opacity="0.95"/>
    <path d="M42 64 L48 70 L58 58" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="50" y="145" font-family="-apple-system, sans-serif" font-size="13" font-weight="700" fill="#0f172a" text-anchor="middle">公开证据链路</text>
  </g>

  <!-- 右2: 学术论文库 -->
  <g transform="translate(520, 75)">
    <rect x="0" y="0" width="130" height="110" rx="10" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
    <circle cx="65" cy="40" r="22" fill="#eff6ff"/>
    <text x="65" y="47" font-size="22" text-anchor="middle">🗄️</text>
    <text x="65" y="80" font-family="-apple-system, sans-serif" font-size="12" font-weight="700" fill="#1e3a8a" text-anchor="middle">公开文献数据库</text>
    <text x="65" y="98" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">候选与归属分离</text>
  </g>

  <!-- 右1: 客观中立准则 -->
  <g transform="translate(680, 75)">
    <rect x="0" y="0" width="130" height="110" rx="10" fill="#ffffff" stroke="#bfdbfe" stroke-width="1.5"/>
    <circle cx="65" cy="40" r="22" fill="#eff6ff"/>
    <text x="65" y="47" font-size="22" text-anchor="middle">⚖️</text>
    <text x="65" y="80" font-family="-apple-system, sans-serif" font-size="12" font-weight="700" fill="#1e3a8a" text-anchor="middle">学术中立声明</text>
    <text x="65" y="98" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">不排名 · 不打分</text>
  </g>
</svg>"""

# 7. 关于说明页插画 (about-academic.svg)
ABOUT_ACADEMIC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 400" width="520" height="400" fill="none">
  <defs>
    <linearGradient id="abBlue" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#1e3a8a"/>
    </linearGradient>
    <radialGradient id="abGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#1e60d5" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <circle cx="260" cy="200" r="160" fill="url(#abGlow)"/>

  <!-- 本地工作台容器基底 -->
  <g transform="translate(90, 70)">
    <rect x="0" y="0" width="340" height="250" rx="16" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
    <rect x="0" y="0" width="340" height="38" rx="16" fill="#f8fafc"/>
    <circle cx="24" cy="19" r="5" fill="#f87171"/>
    <circle cx="40" cy="19" r="5" fill="#fbbf24"/>
    <circle cx="56" cy="19" r="5" fill="#34d399"/>
    <text x="170" y="24" font-family="-apple-system, sans-serif" font-size="11" font-weight="600" fill="#64748b" text-anchor="middle">循证知途 · 本地可复现工作台</text>

    <!-- 工作台内部结构：证据链路树 -->
    <rect x="30" y="60" width="80" height="150" rx="8" fill="#f1f5f9"/>
    <rect x="42" y="75" width="56" height="8" rx="2" fill="url(#abBlue)"/>
    <rect x="42" y="95" width="45" height="5" rx="2" fill="#cbd5e1"/>
    <rect x="42" y="110" width="50" height="5" rx="2" fill="#cbd5e1"/>

    <g transform="translate(130, 60)">
      <!-- 证据详情卡 -->
      <rect x="0" y="0" width="180" height="68" rx="8" fill="#f8fafc" stroke="#e2e8f0"/>
      <circle cx="20" cy="24" r="8" fill="#dbeafe"/>
      <path d="M16 24 L19 27 L25 21" stroke="#2563eb" stroke-width="1.8" stroke-linecap="round"/>
      <text x="36" y="28" font-family="-apple-system, sans-serif" font-size="11" font-weight="700" fill="#1e3a8a">事实公开可溯</text>
      <text x="16" y="52" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b">所有记录均直达官方原文出处</text>

      <rect x="0" y="80" width="180" height="68" rx="8" fill="#f8fafc" stroke="#e2e8f0"/>
      <circle cx="20" cy="104" r="8" fill="#dcfce7"/>
      <path d="M16 104 L19 107 L25 101" stroke="#16a34a" stroke-width="1.8" stroke-linecap="round"/>
      <text x="36" y="108" font-family="-apple-system, sans-serif" font-size="11" font-weight="700" fill="#15803d">保护调查隐私</text>
      <text x="16" y="132" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b">数据留存本机，无云端账户追踪</text>
    </g>
  </g>
</svg>"""

# 8. 全局背景轻量网络 (background-knowledge.svg)
BACKGROUND_KNOWLEDGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 900" width="1440" height="900" fill="none">
  <g opacity="0.04" stroke="#1e60d5" stroke-width="1.2">
    <circle cx="200" cy="200" r="180" stroke-dasharray="6 6"/>
    <circle cx="200" cy="200" r="90"/>
    <circle cx="1200" cy="250" r="220" stroke-dasharray="6 6"/>
    <circle cx="1200" cy="250" r="120"/>
    <circle cx="700" cy="700" r="260" stroke-dasharray="8 8"/>
    <line x1="200" y1="200" x2="700" y2="700"/>
    <line x1="1200" y1="250" x2="700" y2="700"/>
    <line x1="200" y1="200" x2="1200" y2="250"/>
  </g>
</svg>"""

ASSETS_SPEC = [
    ("hero-academic.svg", HERO_ACADEMIC_SVG, "hero-academic.webp", 900, 560),
    ("hero-academic-mobile.svg", HERO_ACADEMIC_MOBILE_SVG, "hero-academic-mobile.webp", 500, 320),
    ("discipline-explore.svg", DISCIPLINE_EXPLORE_SVG, "discipline-explore.webp", 960, 320),
    ("search-empty.svg", SEARCH_EMPTY_SVG, "search-empty.webp", 380, 260),
    ("records-empty.svg", RECORDS_EMPTY_SVG, "records-empty.webp", 320, 220),
    ("source-academic.svg", SOURCE_ACADEMIC_SVG, "source-academic.webp", 880, 260),
    ("about-academic.svg", ABOUT_ACADEMIC_SVG, "about-academic.webp", 520, 400),
    ("background-knowledge.svg", BACKGROUND_KNOWLEDGE_SVG, "background-knowledge.webp", 1440, 900),
]


def generate_all():
    print("=" * 60)
    print("开始生成《循证知途》全套高品质视觉素材与 WebP 图像...")
    print(f"目标目录: {OUT_DIR.resolve()}")
    print("=" * 60)

    # 1. 写入 SVG 文件
    for svg_name, svg_content, _, _, _ in ASSETS_SPEC:
        svg_path = OUT_DIR / svg_name
        svg_path.write_text(svg_content, encoding="utf-8")
        print(f"[SVG] 已写入: {svg_name} ({len(svg_content)} 字节)")

    # 2. 通过 Playwright Edge Headless 将 SVG 渲染为高清透明 WebP
    print("\n启动 Edge Headless 进行矢量渲染并导出 WebP (保持透明通道)...")
    temp_dir = Path("D:/Antigravity/temp_renders")
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        for svg_name, svg_content, webp_name, w, h in ASSETS_SPEC:
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1.5)
            html = f"""<!doctype html>
            <html>
            <head><meta charset="utf-8"><style>
            html, body {{ margin:0; padding:0; background: transparent; overflow: hidden; }}
            svg {{ display: block; width: {w}px; height: {h}px; }}
            </style></head>
            <body>{svg_content}</body>
            </html>"""
            page.set_content(html)
            png_tmp = temp_dir / f"{Path(webp_name).stem}.png"
            page.screenshot(path=str(png_tmp), omit_background=True)
            page.close()

            # 转换为优化后的 WebP
            im = Image.open(png_tmp)
            webp_out = OUT_DIR / webp_name
            im.save(str(webp_out), "WEBP", quality=92, method=6)
            print(f"[WEBP] 已生成: {webp_name} ({w}x{h}, {os.path.getsize(webp_out) // 1024} KB)")

        browser.close()

    print("\n所有视觉素材生成完成！全部具备完整透明通道与高保真矢量渲染。")


if __name__ == "__main__":
    generate_all()
