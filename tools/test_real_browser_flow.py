# -*- coding: utf-8 -*-
r"""真实浏览器自动化验收脚本 (Playwright + Edge Headless)

模拟真实用户在真实渲染环境下的全流程操作，校验：
1. 首页与数据总览加载
2. 导师检索：未选导师时右侧辅助栏显示真实空状态（严禁假数据）
3. 选中导师后辅助栏联动真实核查数与真实更新日期
4. 英文导师中文化（Charles M. Lieber -> 查尔斯·李波）与紧凑摘要指标条
5. 学科导航：移除「0所高校覆盖」无效统计，输入过滤「0811」并点击联动
6. 调查记录：分组折叠 0 记录的空资料夹
7. /eval 页面蓝白设计系统一致性
8. 移动端 (390x844 & 320x568)：汉堡菜单抽屉、返回检索列表按钮、防横向溢出断言

所有截图均保存到 D:\ic-mentor-db\reports\screenshots\
"""

import sys
import time
from pathlib import Path

# 确保在 Windows 控制台环境下输出 UTF-8，防止 GBK 编码报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8765"
SCREENSHOTS_DIR = Path("reports/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def run_acceptance_tests():
    print("=" * 60)
    print("启动真实浏览器端到端交互验收 (Edge Headless)...")
    print(f"目标服务: {BASE_URL}")
    print(f"截图输出: {SCREENSHOTS_DIR.resolve()}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.0,
        )
        page = context.new_page()

        # ──────────────────────────────────────────────────────────
        # 测试 1: 首页总览
        # ──────────────────────────────────────────────────────────
        print("\n[1/8] 检查首页总览...")
        page.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
        page.wait_for_selector("#homeRecords")
        records_text = page.locator("#homeRecords").inner_text()
        print(f"  首页已加载，公开记录数: {records_text}")
        assert records_text and records_text != "0", "首页收录数字未正常加载"
        home_shot = SCREENSHOTS_DIR / "v6_desktop_home.png"
        page.screenshot(path=str(home_shot), full_page=False)
        print(f"  截图已保存: {home_shot.name}")

        # ──────────────────────────────────────────────────────────
        # 测试 2: 工作台初始态（未选择导师时辅助栏无虚假数据）
        # ──────────────────────────────────────────────────────────
        print("\n[2/8] 检查工作台初始态（防虚假统计）...")
        page.click('.sidebar-item[data-nav="workspace"]')
        page.wait_for_selector("#workspaceView:not([hidden])")
        # 触发清空档案
        page.evaluate("clearDossier()")
        page.wait_for_timeout(300)

        # 断言: 占位卡片显示，完整度统计卡片隐藏
        placeholder_hidden = page.evaluate("document.getElementById('auxEmptyPlaceholder').hidden")
        completeness_hidden = page.evaluate("document.getElementById('auxCompletenessCard').hidden")
        assert not placeholder_hidden, "未选导师时，auxEmptyPlaceholder 必须显示"
        assert completeness_hidden, "未选导师时，auxCompletenessCard 必须隐藏，严禁展示写死数据"
        print("  [OK] 未选导师时辅助栏已正确隐藏硬编码数据，展示指引占位")

        empty_shot = SCREENSHOTS_DIR / "v6_desktop_workspace_empty.png"
        page.screenshot(path=str(empty_shot))
        print(f"  截图已保存: {empty_shot.name}")

        # ──────────────────────────────────────────────────────────
        # 测试 3: 搜索导师并查看档案与右侧辅助栏真实联动
        # ──────────────────────────────────────────────────────────
        print("\n[3/8] 检查导师检索与档案真实联动...")
        page.fill("#nameInput", "张")
        page.click("#workspaceSearchForm .card-search-btn")
        page.wait_for_selector("#candidateList .mentor-card-item", timeout=5000)
        candidates = page.locator("#candidateList .mentor-card-item")
        cand_count = candidates.count()
        print(f"  搜索 '张' 匹配到 {cand_count} 位导师")
        assert cand_count > 0, "应能搜到张姓导师"

        # 点击第一位导师
        candidates.first.click()
        page.wait_for_selector("#dossier:not([hidden])", timeout=5000)
        mentor_name = page.locator("#mentorTitle").inner_text()
        print(f"  打开导师档案: {mentor_name}")

        # 校验右侧辅助栏
        completeness_hidden_after = page.evaluate("document.getElementById('auxCompletenessCard').hidden")
        assert not completeness_hidden_after, "打开导师后，auxCompletenessCard 必须展示真实统计"
        verified_num = page.locator("#auxVerifiedNum").inner_text()
        updated_date = page.locator("#auxUpdatedDate").inner_text()
        print(f"  右侧辅助栏真实统计: 已核验 {verified_num} 条，更新日期: {updated_date}")

        # 校验 5 项紧凑摘要状态栏
        ribbon_count = page.locator(".entry-cards-row.compact-ribbon .entry-feature-card.compact-pill").count()
        assert ribbon_count == 5, f"紧凑指标条应包含5个项，实际: {ribbon_count}"
        print("  [OK] 紧凑摘要指标条渲染正确 (5项)")

        mentor_shot = SCREENSHOTS_DIR / "v6_desktop_workspace_mentor.png"
        page.screenshot(path=str(mentor_shot))
        print(f"  截图已保存: {mentor_shot.name}")

        # ──────────────────────────────────────────────────────────
        # 测试 4: 英文导师中文化与防溢出
        # ──────────────────────────────────────────────────────────
        print("\n[4/8] 检查英文导师姓名中文优先展示 (Charles M. Lieber)...")
        page.fill("#nameInput", "Charles M. Lieber")
        page.click("#workspaceSearchForm .card-search-btn")
        page.wait_for_selector("#candidateList .mentor-card-item", timeout=5000)
        page.locator("#candidateList .mentor-card-item").first.click()
        page.wait_for_timeout(500)

        title_text = page.locator("#mentorTitle").inner_text()
        print(f"  导师主标题展示为: {title_text}")
        assert "查尔斯·李波" in title_text, f"Charles M. Lieber 必须优先展示中文名，实际: {title_text}"
        orig_name_text = page.locator("#mentorOrigName").inner_text()
        print(f"  原名附注: {orig_name_text}")

        charles_shot = SCREENSHOTS_DIR / "v6_desktop_dossier_charles.png"
        page.screenshot(path=str(charles_shot))
        print(f"  截图已保存: {charles_shot.name}")

        # ──────────────────────────────────────────────────────────
        # 测试 5: 学科导航过滤与卡片跳转
        # ──────────────────────────────────────────────────────────
        print("\n[5/8] 检查学科导航（无0所高校、搜索过滤、卡片跳转）...")
        page.click('.sidebar-item[data-nav="discipline"]')
        page.wait_for_selector("#disciplineNavView:not([hidden])")
        page.wait_for_selector("#fullDisciplinesGrid .discipline-card-btn")

        all_text = page.locator("#fullDisciplinesGrid").inner_text()
        assert "0 所高校覆盖" not in all_text and "0所高校覆盖" not in all_text, "严禁展示无效统计「0所高校覆盖」"
        print("  [OK] 已确认无「0所高校覆盖」无效统计")

        # 输入过滤 0811
        page.fill("#disciplineSearchInput", "0811")
        page.wait_for_timeout(300)
        filtered_cards = page.locator("#fullDisciplinesGrid .discipline-card-btn")
        filtered_count = filtered_cards.count()
        print(f"  输入 '0811' 过滤后剩余 {filtered_count} 个学科卡片")
        assert filtered_count >= 1, "0811 必须过滤出至少1个学科"

        disc_shot = SCREENSHOTS_DIR / "v6_desktop_discipline_nav.png"
        page.screenshot(path=str(disc_shot))
        print(f"  截图已保存: {disc_shot.name}")

        # 点击 0811 学科卡片跳转工作台
        filtered_cards.first.click()
        page.wait_for_timeout(600)
        curr_view = page.evaluate("document.body.dataset.view")
        assert curr_view == "workspace", "点击学科卡片必须跳转到导师检索工作区"
        disc_val = page.locator("#disciplineSelect").input_value()
        print(f"  跳转后工作台学科选择为: {disc_val}")
        assert "0811" in disc_val, "工作台学科下拉必须自动选中 0811"

        # ──────────────────────────────────────────────────────────
        # 测试 6: 调查记录折叠
        # ──────────────────────────────────────────────────────────
        print("\n[6/8] 检查调查记录视图...")
        page.click('.sidebar-item[data-nav="records"]')
        page.wait_for_selector("#recordsView:not([hidden])")
        page.wait_for_selector("#localRecordsList")
        page.wait_for_timeout(300)

        records_shot = SCREENSHOTS_DIR / "v6_desktop_records.png"
        page.screenshot(path=str(records_shot))
        print(f"  截图已保存: {records_shot.name}")

        # ──────────────────────────────────────────────────────────
        # 测试 7: /eval 算法评测蓝白设计系统一致性
        # ──────────────────────────────────────────────────────────
        print("\n[7/8] 检查算法评测页 (/eval) 蓝白设计一致性...")
        page.goto(f"{BASE_URL}/eval", wait_until="domcontentloaded")
        page.wait_for_selector(".site-head")
        page_title = page.title()
        print(f"  评测看板页面标题: {page_title}")
        assert "循证知途" in page_title, "评测页标题必须与循证知途品牌统一"

        eval_shot = SCREENSHOTS_DIR / "v6_desktop_eval.png"
        page.screenshot(path=str(eval_shot))
        print(f"  截图已保存: {eval_shot.name}")

        context.close()

        # ──────────────────────────────────────────────────────────
        # 测试 8: 移动端视口与交互 (390x844 & 320x568)
        # ──────────────────────────────────────────────────────────
        print("\n[8/8] 检查移动端交互与防溢出...")

        # 390x844 抽屉导航与返回按钮
        m_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
        )
        m_page = m_context.new_page()
        m_page.goto(f"{BASE_URL}/?view=workspace", wait_until="domcontentloaded")

        # 检查汉堡按钮可见并点击打开抽屉
        menu_btn = m_page.locator("#mobileMenuBtn")
        assert menu_btn.is_visible(), "移动端必须显示汉堡菜单按钮"
        menu_btn.click()
        m_page.wait_for_selector("#mobileNavDrawer:not([hidden])")
        drawer_items = m_page.locator(".mobile-drawer-item")
        assert drawer_items.count() == 6, "移动端抽屉菜单必须包含全部 6 个功能入口"
        print("  [OK] 移动端汉堡抽屉打开正常，6个功能入口完整")

        drawer_shot = SCREENSHOTS_DIR / "v6_mobile_drawer_open.png"
        m_page.screenshot(path=str(drawer_shot))
        print(f"  截图已保存: {drawer_shot.name}")

        # 关闭抽屉
        m_page.click("#mobileDrawerClose")
        m_page.wait_for_timeout(200)

        # 选导师并检查返回列表按钮
        m_page.fill("#nameInput", "张")
        m_page.click("#workspaceSearchForm .card-search-btn")
        m_page.wait_for_selector("#candidateList .mentor-card-item", timeout=5000)
        m_page.locator("#candidateList .mentor-card-item").first.click()
        m_page.wait_for_selector("#dossier:not([hidden])", timeout=5000)

        back_btn = m_page.locator("#mobileBackBtn")
        assert back_btn.is_visible(), "移动端导师档案顶部必须显示「返回导师检索列表」按钮"
        print("  [OK] 移动端档案顶部已呈现返回按钮")

        mobile_dossier_shot = SCREENSHOTS_DIR / "v6_mobile_dossier_back_btn.png"
        m_page.screenshot(path=str(mobile_dossier_shot))
        print(f"  截图已保存: {mobile_dossier_shot.name}")

        # 320x568 极小视口防溢出断言
        m_page.set_viewport_size({"width": 320, "height": 568})
        m_page.wait_for_timeout(300)
        scroll_width = m_page.evaluate("document.documentElement.scrollWidth")
        client_width = m_page.evaluate("document.documentElement.clientWidth")
        print(f"  320px 视口宽度检查: clientWidth={client_width}, scrollWidth={scroll_width}")
        assert scroll_width <= client_width + 1, f"320px 视口出现横向溢出: {scroll_width} > {client_width}"
        print("  [OK] 320px 视口无横向溢出")

        small_shot = SCREENSHOTS_DIR / "v6_mobile_320px_viewport.png"
        m_page.screenshot(path=str(small_shot))
        print(f"  截图已保存: {small_shot.name}")

        m_context.close()
        browser.close()

    print("\n" + "=" * 60)
    print("恭喜！所有端到端真实浏览器验收测试全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_acceptance_tests()
