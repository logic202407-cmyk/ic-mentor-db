"""落地页（仓库根 index.html）的测试。

背景：它是早期「集成电路 / AI 芯片方向导师库」专题阶段的页面，里面原本**0 处**提到
当前作品「导师调查工作台」与 38 个工学学科。GitHub Pages 实测未启用（404），
所以它不是对外门户；但仓库里留着一份描述"另一个项目"的页面，翻到的人会困惑。

处理是在顶部加一条说明横幅，而不是重写整页（成本高、收益低）。
本测试钉住三件事：横幅必须在、必须提到当前作品、页面本地链接不能断。
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LANDING = ROOT / "index.html"


class LandingPageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = LANDING.read_text(encoding="utf-8")

    def test_landing_page_exists(self):
        self.assertTrue(LANDING.is_file())

    def test_legacy_banner_present(self):
        self.assertIn('id="legacy-note"', self.html,
                      "落地页缺少说明横幅：它展示的是旧专题，会误导读者")

    def test_banner_explains_the_page_is_legacy(self):
        self.assertIn("历史记录", self.html)
        self.assertIn("早期", self.html)

    def test_banner_points_to_current_work(self):
        self.assertIn("导师调查工作台", self.html,
                      "横幅必须提到当前作品名称")
        self.assertIn("38 个工学", self.html,
                      "横幅应说明当前覆盖范围")

    def test_title_marks_legacy(self):
        m = re.search(r"<title>(.*?)</title>", self.html, re.S)
        self.assertIsNotNone(m)
        self.assertIn("历史专题页", m.group(1))

    def test_local_links_resolve(self):
        hrefs = re.findall(r'href="([^"]+)"', self.html)
        missing = []
        for href in hrefs:
            if href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (ROOT / href.split("#")[0]).resolve()
            if not target.exists():
                missing.append(href)
        self.assertEqual(missing, [], f"落地页有断链：{missing}")

    def test_local_vendor_assets_not_required(self):
        # 页面不应依赖 CDN（离线可看），这一点与"本机运行"的定位一致
        self.assertNotIn("cdn.jsdelivr.net", self.html)
        self.assertNotIn("unpkg.com", self.html)


if __name__ == "__main__":
    unittest.main()
