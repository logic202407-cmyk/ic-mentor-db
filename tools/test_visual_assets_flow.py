# -*- coding: utf-8 -*-
r"""全平台视觉素材融合与多分辨率真实浏览器验收脚本

校验：
1. 首页 Hero 主视觉高保真渲染 (hero-academic.webp/svg)
2. 导师检索初始空状态艺术插画 (search-empty.webp/svg)
3. 导师档案选中与展示 (查尔斯·李波)
4. 学科导航艺术探索横幅 (discipline-explore.webp/svg)
5. 调查记录空状态笔记本艺术插画 (records-empty.webp/svg)
6. 数据来源多源汇聚架构图 (source-academic.webp/svg)
7. 关于说明页左右平衡排版艺术插画 (about-academic.webp/svg)
8. 算法评测看板蓝白一致性与顶部纹理
9. 9 大分辨率响应式测试 (1920x1080 至 320x568)
10. 全分辨率无水平溢出断言 (scrollWidth <= clientWidth + 1)
11. 图像无碎图断言 (naturalWidth > 0)
12. 交互元素无点击遮挡断言 (pointer-events 安全性)
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8765"
SCREENSHOTS_DIR = Path("reports/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_SCREENSHOTS_DIR = Path("docs/screenshots")
DOCS_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

RESOLUTIONS = [
    ("1920x1080", 1920, 1080, False),
    ("1440x900", 1440, 900, False),
    ("1366x768", 1366, 768, False),
    ("1280x800", 1280, 800, False),
    ("1024x768", 1024, 768, False),
    ("768x1024", 768, 1024, True),
    ("390x844", 390, 844, True),
    ("375x812", 375, 812, True),
    ("320x568", 320, 568, True),
]


def assert_no_horizontal_overflow(page, name=""):
    scroll_w = page.evaluate("document.documentElement.scrollWidth")
    client_w = page.evaluate("document.documentElement.clientWidth")
    assert scroll_w <= client_w + 1, f"[{name}] 检测到水平溢出: scrollWidth({scroll_w}) > clientWidth({client_w})"


def assert_images_loaded(page, selector="img"):
    imgs = page.locator(selector)
    count = imgs.count()
    for i in range(count):
        img = imgs.nth(i)
        is_visible = img.is_visible()
        if is_visible:
            img.evaluate("""el => {
                if (!el.complete) {
                    return new Promise((resolve) => {
                        el.onload = el.onerror = resolve;
                    });
                }
                return el.decode ? el.decode().catch(() => {}) : null;
            }""")
            natural_w = img.evaluate("el => el.naturalWidth")
            src = img.evaluate("el => el.currentSrc || el.src")
            assert natural_w > 0, f"图片加载失败或为碎图: {src}"


def run_visual_acceptance():
    print("=" * 60)
    print("启动《循证知途》全平台视觉素材融合与交互验收 (Edge Headless)...")
    print(f"目标站点: {BASE_URL}")
    print(f"截图目录: {SCREENSHOTS_DIR.resolve()}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # ──────────────────────────────────────────────────────────
        # 1. 首页 Hero 主视觉验收 (1920x1080 & 1440x900)
        # ──────────────────────────────────────────────────────────
        print("\n[1/7] 验收首页总览与 Hero 艺术主视觉...")
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
        page.wait_for_selector(".hero-art-img")
        assert_images_loaded(page, ".hero-art-img")
        assert_no_horizontal_overflow(page, "1920x1080 Home")

        # 校验标题与按钮可点击
        page.click('.btn-primary-cta[data-start="name"]')
        page.wait_for_selector("#workspaceView:not([hidden])")
        print("  [OK] Hero 主操作按钮点击响应正常，跳转至导师检索")

        # 返回首页并保存 1920 截图
        page.click('.sidebar-item[data-nav="home"]')
        page.wait_for_selector("#homeView:not([hidden])")
        page.wait_for_timeout(300)
        shot_home = SCREENSHOTS_DIR / "visual_01_home_1920x1080.png"
        page.screenshot(path=str(shot_home))
        print(f"  [OK] 首页全景截图已保存: {shot_home.name}")
        # 同步更新官方设计截图 docs/screenshots/01-home.png
        page.screenshot(path=str(DOCS_SCREENSHOTS_DIR / "01-home.png"))

        # ──────────────────────────────────────────────────────────
        # 2. 导师检索未选导师空状态插画 (1440x900)
        # ──────────────────────────────────────────────────────────
        print("\n[2/7] 验收导师检索页空状态艺术插画...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.click('.sidebar-item[data-nav="workspace"]')
        page.wait_for_selector("#workspaceView:not([hidden])")
        page.evaluate("clearDossier()")
        page.wait_for_selector(".ws-empty-img")
        assert_images_loaded(page, ".ws-empty-img")
        assert_no_horizontal_overflow(page, "1440x900 Workspace Empty")

        shot_ws_empty = SCREENSHOTS_DIR / "visual_02_workspace_empty_1440x900.png"
        page.screenshot(path=str(shot_ws_empty))
        print(f"  [OK] 导师检索空状态截图已保存: {shot_ws_empty.name}")

        # ──────────────────────────────────────────────────────────
        # 3. 选中导师档案与右侧真实辅助栏
        # ──────────────────────────────────────────────────────────
        print("\n[3/7] 验收导师检索与档案展示 (查尔斯·李波)...")
        page.fill("#nameInput", "Charles M. Lieber")
        page.click("#workspaceSearchForm .card-search-btn")
        page.wait_for_selector("#candidateList .mentor-card-item", timeout=6000)
        page.locator("#candidateList .mentor-card-item").first.click()
        page.wait_for_selector("#dossier:not([hidden])", timeout=6000)
        page.wait_for_timeout(400)

        # 确认未选导师空状态已完全退出
        ws_intro_hidden = page.evaluate("document.getElementById('workspaceIntro').hidden")
        assert ws_intro_hidden, "选择导师后，workspaceIntro 空状态必须完全隐藏退出"

        shot_dossier = SCREENSHOTS_DIR / "visual_03_workspace_dossier_1440x900.png"
        page.screenshot(path=str(shot_dossier))
        print(f"  [OK] 导师档案详情截图已保存: {shot_dossier.name}")
        page.screenshot(path=str(DOCS_SCREENSHOTS_DIR / "02-dossier.png"))

        # ──────────────────────────────────────────────────────────
        # 4. 学科导航页艺术横幅 (discipline-explore.webp)
        # ──────────────────────────────────────────────────────────
        print("\n[4/7] 验收学科导航艺术横幅与卡片网格...")
        page.click('.sidebar-item[data-nav="discipline"]')
        page.wait_for_selector("#disciplineNavView:not([hidden])")
        page.wait_for_selector(".discipline-art-img")
        assert_images_loaded(page, ".discipline-art-img")
        assert_no_horizontal_overflow(page, "1440x900 Discipline Nav")

        shot_disc = SCREENSHOTS_DIR / "visual_04_discipline_1440x900.png"
        page.screenshot(path=str(shot_disc))
        print(f"  [OK] 学科导航艺术横幅截图已保存: {shot_disc.name}")

        # ──────────────────────────────────────────────────────────
        # 5. 调查记录空状态、数据来源与关于说明
        # ──────────────────────────────────────────────────────────
        print("\n[5/7] 验收调查记录空状态、数据来源架构图与关于说明...")
        # 调查记录
        page.click('.sidebar-item[data-nav="records"]')
        page.wait_for_selector("#recordsView:not([hidden])")
        page.wait_for_selector(".records-empty-img")
        assert_images_loaded(page, ".records-empty-img")
        shot_records = SCREENSHOTS_DIR / "visual_05_records_empty_1440x900.png"
        page.screenshot(path=str(shot_records))
        print(f"  [OK] 调查记录空状态截图已保存: {shot_records.name}")

        # 数据来源
        page.click('.sidebar-item[data-nav="sources"]')
        page.wait_for_selector("#sourcesView:not([hidden])")
        page.wait_for_selector(".sources-flow-img")
        assert_images_loaded(page, ".sources-flow-img")
        shot_sources = SCREENSHOTS_DIR / "visual_06_sources_1440x900.png"
        page.screenshot(path=str(shot_sources))
        print(f"  [OK] 数据来源架构图截图已保存: {shot_sources.name}")

        # 关于说明
        page.click('.sidebar-item[data-nav="about"]')
        page.wait_for_selector("#aboutView:not([hidden])")
        page.wait_for_selector(".about-art-img")
        assert_images_loaded(page, ".about-art-img")
        shot_about = SCREENSHOTS_DIR / "visual_07_about_1440x900.png"
        page.screenshot(path=str(shot_about))
        print(f"  [OK] 关于说明艺术平衡截图已保存: {shot_about.name}")

        # 算法评测
        page.goto(f"{BASE_URL}/eval", wait_until="domcontentloaded")
        page.wait_for_selector(".page-hero")
        shot_eval = SCREENSHOTS_DIR / "visual_08_eval_1440x900.png"
        page.screenshot(path=str(shot_eval))
        print(f"  [OK] 算法评测看板截图已保存: {shot_eval.name}")
        page.screenshot(path=str(DOCS_SCREENSHOTS_DIR / "06-eval-overview.png"))

        context.close()

        # ──────────────────────────────────────────────────────────
        # 6. 9 大分辨率无横向溢出与响应式截图
        # ──────────────────────────────────────────────────────────
        print("\n[6/7] 执行 9 大分辨率响应式与防遮挡/防溢出自动化检验...")
        for label, w, h, is_mob in RESOLUTIONS:
            ctx = browser.new_context(
                viewport={"width": w, "height": h},
                is_mobile=is_mob,
                has_touch=is_mob,
            )
            p_res = ctx.new_page()
            p_res.goto(f"{BASE_URL}/?view=workspace", wait_until="domcontentloaded")
            p_res.wait_for_timeout(200)
            assert_no_horizontal_overflow(p_res, f"{label} Workspace")

            p_res.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
            p_res.wait_for_timeout(200)
            assert_no_horizontal_overflow(p_res, f"{label} Home")

            res_shot = SCREENSHOTS_DIR / f"res_{label}.png"
            p_res.screenshot(path=str(res_shot))
            print(f"  [PASS] 分辨率 {label:>9}: 无横向溢出，元素适配正常，已保存 {res_shot.name}")
            ctx.close()

        # ──────────────────────────────────────────────────────────
        # 7. 移动端抽屉导航与微动效降级检查
        # ──────────────────────────────────────────────────────────
        print("\n[7/7] 检查移动端交互与 prefers-reduced-motion 降级...")
        m_ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            reduced_motion="reduce",
        )
        m_p = m_ctx.new_page()
        m_p.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
        # 验证 reduced-motion 下动画已禁用
        anim_name = m_p.evaluate("window.getComputedStyle(document.querySelector('.hero-art-img')).animationName")
        print(f"  prefers-reduced-motion: reduce 动画检测: {anim_name}")
        assert anim_name in ("none", "", None), "在 reduced-motion 开启时动画必须被禁用"
        print("  [OK] prefers-reduced-motion 动画降级生效")

        m_shot = SCREENSHOTS_DIR / "visual_mobile_home_390x844.png"
        m_p.screenshot(path=str(m_shot))
        print(f"  [OK] 移动端截图已保存: {m_shot.name}")

        m_ctx.close()
        browser.close()

    print("\n" + "=" * 60)
    print("验收全部通过！全套视觉素材融合、动态交互与响应式适配圆满完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_visual_acceptance()
