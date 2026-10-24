"""新版工作台页面（workbench/web/desk.html）的结构测试。

为什么要有这一组
----------------
界面改版最容易在"看起来对"的地方回退：把「无公开证据」又渲染成 0、把综合分区块
偷偷加回来、新增一个分区却忘了加 tab 或容器、正文缩回 12px、空状态被删掉只剩空白。
这些都不报错，只在打开页面时才看得见。这里用静态检查把它们钉住。

只检查**页面源码本身**（不跑浏览器），所以断言写的都是源码里真实存在的选择器与
文案；渲染行为由 test_frontend_wiring.py 与 test_student_observation.py 覆盖。
"""

from __future__ import annotations

import pathlib
import re
import unittest

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
DESK = WEB / "desk.html"
DESK_CSS = WEB / "assets" / "desk.css"

PANES = ("investigation", "identity", "papers", "admission",
         "network", "observation", "check")


def read() -> str:
    return DESK.read_text(encoding="utf-8")


def read_styles() -> str:
    """页面源码 + 外链样式：样式已经抽到 desk.css，检查必须合并后再断言。"""
    text = read()
    if DESK_CSS.is_file():
        text += "\n" + DESK_CSS.read_text(encoding="utf-8")
    return text


def static_markup(src: str) -> str:
    """`<body>` 之后、第一段内联脚本之前的部分：只含静态标签。"""
    body = src.find("<body>")
    script = src.find("<script", body)
    return src[body:script]


class ObservationViewTests(unittest.TestCase):
    """课题组公开信息观察：三态与"不打分"必须在页面上兑现。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()

    def test_three_states_are_all_rendered(self) -> None:
        for label in ("有公开证据", "有证据 · 记为 0", "无公开证据"):
            self.assertIn(label, self.src, f"三态文案缺失：{label}")

    def test_unknown_is_explicitly_not_zero(self) -> None:
        # 页面必须自己说明这一点，而不是只靠后端字段
        self.assertIn("无公开证据不会显示成 0", self.src)
        self.assertIn("无公开证据", self.src)
        # unknown 卡片用「无公开证据」占位，绝不能渲染成 0 或 0%
        self.assertIn('class="obs-value is-unknown">无公开证据', self.src)

    def test_no_composite_score_language_left(self) -> None:
        for banned in ("读研体验参考分", "权重", "score-number", "score-dims",
                       "confidence", "weights", "综合分 8"):
            self.assertNotIn(banned, self.src, f"页面仍残留旧「参考分」表达：{banned}")

    def test_observation_explains_it_has_no_ranking(self) -> None:
        self.assertIn("不提供跨导师排序", self.src)
        self.assertIn("衡量不了读研体验", self.src)

    def test_four_dimension_cards_have_evidence_blocks(self) -> None:
        # 每张卡片都带取数依据与边界说明（折叠展示）
        self.assertIn("取数依据与边界说明", self.src)
        self.assertIn("obs-card", self.src)
        self.assertIn("样本：", self.src)

    def test_observation_not_measured_is_folded(self) -> None:
        self.assertIn("这个观察不衡量什么", self.src)


class InformationArchitectureTests(unittest.TestCase):
    """分区容器、tab、id 必须一一对应，缺一个就会出现"点了没反应"。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()
        cls.markup = static_markup(cls.src)

    def test_every_pane_has_a_container_and_a_tab(self) -> None:
        for pane in PANES:
            self.assertEqual(self.markup.count(f'id="pane-{pane}"'), 1,
                             f"分区容器 id=pane-{pane} 应恰好出现一次")
            self.assertEqual(self.markup.count(f'data-pane="{pane}"'), 1,
                             f"缺少分区 tab：{pane}")
            self.assertIn(f'aria-controls="pane-{pane}"', self.markup,
                          f"tab 与控制的分区没有关联：{pane}")

    def test_tabs_are_real_tabs(self) -> None:
        nav = self.markup[self.markup.find('class="dossier-tabs"'):]
        nav = nav[:nav.find("</nav>")]
        self.assertEqual(nav.count('role="tab"'), len(PANES))
        self.assertEqual(nav.count('aria-selected='), len(PANES))

    def test_required_regions_exist(self) -> None:
        for marker in ('id="aiHints"', 'id="scoreBlock"', 'id="landing"', 'id="dossier"',
                       'id="loadingPanel"', 'id="catalogCoverage"', 'id="mentorTitle"',
                       'id="mentorSubtitle"', 'id="mentorBadges"', 'id="reportLink"',
                       'id="homepageLink"', 'id="breadcrumb"'):
            self.assertEqual(self.markup.count(marker), 1, f"缺少或重复：{marker}")

    def test_identity_pane_keeps_public_sources_host(self) -> None:
        # 用户保存的网页由 renderEvidenceList 追加，容器变了就会重复插入
        self.assertIn("evidenceHost", self.src)

    def test_two_entries_are_kept(self) -> None:
        self.assertIn('data-start="name"', self.markup)
        self.assertIn('data-start="discipline"', self.markup)
        self.assertIn('id="nameMode"', self.markup)
        self.assertIn('id="disciplineMode"', self.markup)


class LandingPageTests(unittest.TestCase):
    """首页四问 + 算法评测预留位 + 不写没有依据的宣传语。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()
        cls.markup = static_markup(cls.src)

    def test_four_questions_are_answered(self) -> None:
        for question in ("这是什么", "解决什么问题", "AI 用在哪"):
            self.assertIn(question, self.markup, f"首页缺少：{question}")
        self.assertIn("怎么开始调查一位导师", self.markup)

    def test_algorithm_evaluation_slot_links_to_eval_page(self) -> None:
        """评测位已经从「预留」升级为真实入口：必须链到 /eval，且不写死指标。"""
        self.assertIn('id="algoEvalEntry"', self.markup)
        self.assertIn("算法评测", self.markup)
        self.assertIn('href="/eval"', self.markup)
        self.assertIn("真实产物", self.markup)
        # 首页只放入口，不摆数字（数字在 /eval 页，来自评测产物）
        for pattern in ("召回率 9", "nDCG@10 0.", "Top-1 6"):
            self.assertNotIn(pattern, self.markup)

    def test_ai_section_says_pending_review(self) -> None:
        self.assertIn("待复核", self.src)

    def test_no_unsupported_marketing_claim(self) -> None:
        for claim in ("覆盖全国", "全国高校全覆盖", "权威", "官方认证"):
            self.assertNotIn(claim, self.markup, f"首页出现无依据宣传语：{claim}")

    def test_coverage_numbers_come_from_api(self) -> None:
        # 收录数字必须来自接口，不能写死
        self.assertIn("loadCoverage", self.src)
        self.assertIn("/api/catalog/coverage", self.src)


class ReadabilityTests(unittest.TestCase):
    """正文不小于 15px、空状态、加载态、折叠、响应式三档。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()
        cls.styles = read_styles()
        cls.markup = static_markup(cls.src)

    def test_body_font_is_at_least_15px(self) -> None:
        match = re.search(r"body\{[^}]*font:(\d+(?:\.\d+)?)px", self.styles)
        self.assertIsNotNone(match, "找不到 body 的 font 声明")
        self.assertGreaterEqual(float(match.group(1)), 15.0)

    def test_empty_state_helper_exists_and_is_used(self) -> None:
        self.assertIn("function emptyState(", self.src)
        self.assertIn(".empty-state{", self.styles)
        # 空状态文案至少要覆盖：论文、招生、来源、观察、关系、自保存网页
        for phrase in ("还没有找到当年的招生信息", "还没有自己保存的网页",
                       "暂无其他来源的论文记录", "四项观察都没有公开证据",
                       "当前未关联到既有关系网"):
            self.assertIn(phrase, self.src, f"缺少空状态文案：{phrase}")

    def test_loading_state_is_visible(self) -> None:
        self.assertIn('id="loadingPanel"', self.markup)
        self.assertIn('class="skeleton', self.markup)
        self.assertIn("正在加载导师档案", self.src)
        self.assertIn('aria-busy', self.src)

    def test_long_text_is_foldable(self) -> None:
        self.assertGreaterEqual(self.src.count("<details"), 3)
        self.assertGreaterEqual(self.src.count("detailBlock("), 2,
                                "取数依据、边界说明、不衡量什么等长文本应可折叠")

    def test_three_responsive_breakpoints(self) -> None:
        for width in (1240, 960, 860):
            self.assertIn(f"@media(max-width:{width}px)", self.styles,
                          f"缺少 {width}px 断点")

    def test_no_horizontal_overflow_guards(self) -> None:
        # 双栏骨架的两条防溢出措施：grid 子项 min-width:0 + 长词换行
        self.assertIn(".workspace>*{min-width:0}", self.styles)
        self.assertIn("overflow-wrap:anywhere", self.styles)


class AccessibilityTests(unittest.TestCase):
    """键盘可用、表单有 label、状态不只靠颜色。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()
        cls.styles = read_styles()
        cls.markup = static_markup(cls.src)

    def test_static_form_controls_have_labels(self) -> None:
        ids = re.findall(r'<(?:input|select|textarea)[^>]*\bid="([A-Za-z0-9_-]+)"', self.markup)
        self.assertGreater(len(ids), 5)

        def wrapped(element_id: str) -> bool:
            """该控件是否被某个 <label>…</label> 包住（如「显示非工科」）。"""
            position = self.markup.find(f'id="{element_id}"')
            opening = self.markup.rfind("<label", 0, position)
            if opening < 0:
                return False
            closing = self.markup.find("</label>", position)
            return closing != -1 and self.markup.rfind("</label>", 0, position) < opening

        for element_id in ids:
            labelled = (f'for="{element_id}"' in self.markup
                        or f'aria-label="{element_id}"' in self.markup
                        or wrapped(element_id))
            self.assertTrue(labelled, f"表单控件缺少 label：{element_id}")

    def test_skip_link_and_focus_style(self) -> None:
        self.assertIn('class="skip-link"', self.markup)
        self.assertIn(":focus-visible", self.styles)

    def test_status_is_announced(self) -> None:
        self.assertIn('id="resultStatus"', self.markup)
        self.assertIn('aria-live="polite"', self.markup)

    def test_state_is_not_colour_only(self) -> None:
        # 三态同时带文字与字形，不只靠颜色区分
        self.assertIn("state-glyph", self.src)
        for glyph in ("●", "○", "？"):
            self.assertIn(glyph, self.src)

    def test_tabs_support_arrow_keys(self) -> None:
        self.assertIn("bindTabKeys", self.src)
        self.assertIn("ArrowRight", self.src)


class DependencyTests(unittest.TestCase):
    """不引重型前端依赖：原生 DOM/CSS，离线可用。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = read()

    def test_no_cdn_scripts(self) -> None:
        for bad in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
                    "https://esm.sh", "googleapis.com"):
            self.assertNotIn(bad, self.src, f"不能引入 CDN 依赖：{bad}")

    def test_no_frontend_framework(self) -> None:
        for bad in ("react.production", "vue.global", "Chart.js", "d3.min.js", "echarts"):
            self.assertNotIn(bad, self.src, f"不能引入重型前端依赖：{bad}")

    def test_scripts_are_local_assets(self) -> None:
        srcs = re.findall(r'<script src="([^"]+)"', self.src)
        self.assertTrue(srcs)
        for path in srcs:
            self.assertTrue(path.startswith("/assets/"), path)
            name = path.split("?")[0].lstrip("/").split("/")[-1]
            self.assertTrue((WEB / "assets" / name).is_file(), f"脚本不存在：{path}")


if __name__ == "__main__":
    unittest.main()