"""算法评测页（workbench/web/eval.html）的结构、口径与接口契约测试。

为什么要有这一组
----------------
评测页最容易在三个地方「看起来对、其实坏了」，而且都不报错：

1. **写死数字。** 有人图省事把 0.84 打进 JS，产物换了页面还显示旧值；或者产物缺失时
   补一个 0 上去，读者会把「没跑过」读成「跑了但得零分」。
2. **产物缺失就崩。** directions / disambiguation 在干净 clone 上一定是 null，
   这时候页面必须说「待产出」并给出复现入口，而不是抛异常留一片空白。
3. **图和数字对不上。** 图表容器、数值表、文字替代三者缺一，键盘和读屏用户就拿不到值。

所以这里的断言分成四组：文件与结构、无写死指标、待产出口径、接口契约。
渲染行为本身（条形宽度、SVG 折线）由打开页面的自验覆盖，静态测试不假装能跑浏览器。
"""

from __future__ import annotations

import pathlib
import re
import unittest

from fastapi.testclient import TestClient

from workbench.app import app

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
EVAL = WEB / "eval.html"
EVAL_JS = WEB / "assets" / "eval.js"
EVAL_CSS = WEB / "assets" / "eval.css"

# 页面必须存在的容器 id：缺一个就会出现「有标题没内容」或「点了没反应」。
REQUIRED_IDS = (
    "evalStatus",
    "loadingPanel",
    "errorPanel",
    "errorRepro",
    "evalRoot",
    "summaryCards",
    "honestyText",
    "reproduceCommand",
    "sourceList",
    "chartMethodA",
    "chartMethodB",
    "methodTableA",
    "methodTableB",
    "calloutAb",
    "chartFilter",
    "filterTable",
    "chartSweep",
    "sweepTable",
    "chartLatency",
    "latencyTable",
    "resourcesBlock",
    "directionsBody",
    "disambiguationBody",
    "significanceBody",
    "failuresBody",
    "failuresMeta",
    "acronymBlock",
    "collisionsBlock",
    "offTopicBlock",
    "degenerateBlock",
)

# 布局常量白名单：允许出现在 JS 里的百分比字面量（条形宽度归一化用）。
LAYOUT_PERCENTAGES = {"0%", "25%", "50%", "75%", "100%"}


def html() -> str:
    return EVAL.read_text(encoding="utf-8")


def js() -> str:
    return EVAL_JS.read_text(encoding="utf-8")


def css() -> str:
    return EVAL_CSS.read_text(encoding="utf-8")


class PageFileTests(unittest.TestCase):
    """三个新文件都在，且页面骨架完整。"""

    def test_three_files_exist(self) -> None:
        for path in (EVAL, EVAL_JS, EVAL_CSS):
            self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_title_and_reproduce_wording(self) -> None:
        src = html()
        self.assertIn("算法评测", src, "页面必须出现「算法评测」")
        self.assertIn("<h1>算法评测</h1>", src, "h1 必须是「算法评测」")
        self.assertIn("复现", src, "页面必须出现「复现」字样")

    def test_key_containers_present_once(self) -> None:
        src = html()
        for element_id in REQUIRED_IDS:
            self.assertEqual(
                src.count(f'id="{element_id}"'), 1,
                f"容器 id={element_id} 应恰好出现一次",
            )

    def test_five_sections_and_navigation_back(self) -> None:
        src = html()
        for section_id in ("retrievalSection", "directionsSection",
                           "disambiguationSection", "failuresSection",
                           "limitsSection", "summarySection"):
            self.assertIn(f'id="{section_id}"', src, f"缺少分区：{section_id}")
        self.assertIn('href="/"', src, "导航必须能返回工作台")
        self.assertIn("返回工作台", src)

    def test_scripts_and_styles_are_local(self) -> None:
        src = html()
        srcs = re.findall(r'<script src="([^"]+)"', src)
        self.assertTrue(srcs, "页面必须加载本地的 eval.js")
        for path in srcs:
            self.assertTrue(path.startswith("/assets/"), path)
            name = path.split("?")[0].lstrip("/").split("/")[-1]
            self.assertTrue((WEB / "assets" / name).is_file(), f"脚本不存在：{path}")

        styles = re.findall(r'<link rel="stylesheet" href="([^"]+)"', src)
        self.assertTrue(styles, "页面必须加载本地的 eval.css")
        for path in styles:
            self.assertTrue(path.startswith("/assets/"), path)
            name = path.split("?")[0].lstrip("/").split("/")[-1]
            self.assertTrue((WEB / "assets" / name).is_file(), f"样式不存在：{path}")

    def test_no_cdn_or_chart_library(self) -> None:
        for src in (html(), js()):
            for bad in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
                        "googleapis.com", "esm.sh", "Chart.js", "chart.js",
                        "d3.min.js", "echarts", "highcharts", "plotly"):
                self.assertNotIn(bad, src, f"不能引入外部依赖：{bad}")

    def test_body_font_is_at_least_15px(self) -> None:
        match = re.search(r"body\{[^}]*font:(\d+(?:\.\d+)?)px", css())
        self.assertIsNotNone(match, "找不到 body 的 font 声明")
        self.assertGreaterEqual(float(match.group(1)), 15.0)

    def test_responsive_and_reduced_motion(self) -> None:
        src = css()
        for width in (960, 760, 560):
            self.assertIn(f"@media(max-width:{width}px)", src, f"缺少 {width}px 断点")
        self.assertIn("prefers-reduced-motion", src)
        self.assertIn(":focus-visible", src, "键盘焦点必须有可见样式")


class NoHardcodedMetricsTests(unittest.TestCase):
    """界面上每个数字都必须来自接口，源码里不许出现指标常量。"""

    def test_no_decimal_literals_in_js(self) -> None:
        found = sorted(set(re.findall(r"\d+\.\d+", js())))
        self.assertEqual(found, [], f"eval.js 出现小数常量，指标很可能被写死：{found}")

    def test_no_percentage_literals_beyond_layout_whitelist(self) -> None:
        found = set(re.findall(r"\d+(?:\.\d+)?\s*%", js()))
        extra = {item for item in found if item.replace(" ", "") not in LAYOUT_PERCENTAGES}
        self.assertEqual(extra, set(), f"eval.js 出现百分比字面量：{sorted(extra)}")

    def test_metric_names_are_read_from_payload(self) -> None:
        src = js()
        # 三个指标必须以「取字段」的形式出现，而不是以数字形式出现。
        for key in ('"ndcg@10"', '"recall@20"', '"mrr@10"'):
            self.assertIn(key, src, f"图表没有按产物字段名取数：{key}")
        self.assertIn("/api/evaluation/summary", src)

    def test_no_metric_value_next_to_metric_word(self) -> None:
        src = js()
        for word in ("ndcg", "recall", "mrr", "top1"):
            near = re.findall(rf"{word}[^\n]{{0,40}}?(\d+\.\d+)", src, re.IGNORECASE)
            self.assertEqual(near, [], f"{word} 附近出现疑似写死的数值：{near}")

    def test_page_text_has_no_fake_placeholder_numbers(self) -> None:
        src = html()
        # 骨架屏不能写「0」当占位，额度用破折号。
        for bad in ("0.0%", "0.00", "—%", "暂无数据 0"):
            self.assertNotIn(bad, src, f"页面出现占位假数字：{bad}")


class PendingStateTests(unittest.TestCase):
    """产物缺失必须优雅降级，不许显示 0。"""

    def test_pending_wording_exists(self) -> None:
        self.assertIn("待产出", js(), "必须为缺失产物准备「待产出」文案")

    def test_null_is_handled_for_both_artifacts(self) -> None:
        src = js()
        self.assertIn("data.directions", src)
        self.assertIn("data.disambiguation", src)
        self.assertIn("pendingBlock", src, "缺失产物应走统一的待产出分支")

    def test_pending_state_shows_reproduce_command(self) -> None:
        src = js()
        self.assertIn("workbench.infer_directions", src, "方向推断必须给出复现入口")
        self.assertIn("workbench.disambiguate_names", src, "同名消歧必须给出复现入口")

    def test_missing_values_render_as_dash(self) -> None:
        # 统一的格式化函数在拿到非数字时返回破折号，而不是 0。
        self.assertIn('return "—"', js())


class ChartAccessibilityTests(unittest.TestCase):
    """图必须有文字替代，键盘可达。"""

    def test_charts_expose_text_alternatives(self) -> None:
        self.assertIn("aria-describedby", html())
        self.assertIn("数值表", html(), "每张图都要有可展开的数值表")
        self.assertIn("aria-label", js(), "条形行要用 aria-label 带出完整数值")
        self.assertIn("tabindex", js(), "条形行要可键盘聚焦")

    def test_svg_charts_have_title_and_desc(self) -> None:
        src = js()
        self.assertIn('svgEl("title"', src)
        self.assertIn('svgEl("desc"', src)
        self.assertIn('role: "img"', src)

    def test_loading_and_error_states_are_announced(self) -> None:
        src = html()
        self.assertIn('aria-live="polite"', src)
        self.assertIn("skeleton", src)
        self.assertIn('aria-busy="true"', src)
        self.assertIn("errorPanel", src)


class SummaryApiTests(unittest.TestCase):
    """接口契约与页面路由：这是页面数据唯一的来源。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_summary_is_available(self) -> None:
        response = self.client.get("/api/evaluation/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("available"), f"评测产物不可用：{data.get('reason')}")
        self.assertTrue(data.get("retrieval", {}).get("methods"), "methods 不能为空")

    def test_summary_carries_honesty_and_reproduce_command(self) -> None:
        data = self.client.get("/api/evaluation/summary").json()
        self.assertTrue(data.get("generated_at"), "缺少评测生成时间")
        self.assertTrue(data.get("how_to_reproduce"), "缺少复现命令")
        self.assertTrue(data.get("honesty"), "缺少弱监督口径说明")
        self.assertTrue(data.get("sources", {}).get("retrieval"), "缺少产物来源路径")

    def test_methods_carry_the_three_charted_metrics(self) -> None:
        data = self.client.get("/api/evaluation/summary").json()
        methods = data["retrieval"]["methods"]
        self.assertGreaterEqual(len(methods), 3)
        for method in methods:
            for split in ("a_test", "b_test"):
                self.assertIn(split, method, f"{method.get('key')} 缺少 {split}")
            row = method["a_test"]
            for metric in ("ndcg@10", "recall@20", "mrr@10"):
                self.assertIsInstance(row.get(metric), (int, float),
                                      f"{method.get('key')} 的 A 类缺少 {metric}")

    def test_eval_page_is_served_as_html(self) -> None:
        response = self.client.get("/eval")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("算法评测", response.text)


if __name__ == "__main__":
    unittest.main()