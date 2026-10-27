# -*- coding: utf-8 -*-
"""Test interactive 3D parallax tilt, mouse events, and click behaviors."""

import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8765"

def test_interactions():
    print("Testing visual 3D interactions and click feedbacks...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        # 1. Test Home Hero interaction
        page.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
        page.wait_for_selector("#homeView:not([hidden])")
        page.wait_for_selector(".hero-art-img")
        hero_box = page.locator(".hero-art-img").bounding_box()
        assert hero_box is not None, "Hero visual missing"
        
        # Move mouse across hero to trigger parallax 3D tilt
        page.mouse.move(hero_box["x"] + 30, hero_box["y"] + 30)
        page.wait_for_timeout(150)
        transform_val = page.evaluate("document.querySelector('.hero-art-img').style.transform")
        print(f"Hero tilt transform: {transform_val}")
        assert "perspective" in transform_val or "rotate" in transform_val, "Hero should have 3D perspective tilt on hover"
        
        # Test click bounce on Hero
        page.locator(".hero-art-img").click(force=True)
        page.wait_for_timeout(100)
        has_bounce = page.evaluate("document.querySelector('.hero-art-img').classList.contains('interactive-bounce')")
        print(f"Hero interactive bounce applied: {has_bounce}")
        assert has_bounce, "Hero should trigger interactive bounce on click"
        
        # 2. Test Workspace Empty state interaction
        page.click('.sidebar-item[data-nav="workspace"]')
        page.wait_for_selector("#workspaceView:not([hidden])")
        page.evaluate("clearDossier()")
        page.wait_for_selector(".ws-empty-img")
        
        # Test 3D tilt on empty state
        ws_box = page.locator(".ws-empty-img").bounding_box()
        assert ws_box is not None, "Workspace empty graphic missing"
        page.mouse.move(ws_box["x"] + 20, ws_box["y"] + 20)
        page.wait_for_timeout(150)
        ws_transform = page.evaluate("document.querySelector('.ws-empty-img').style.transform")
        print(f"Workspace empty tilt transform: {ws_transform}")
        assert "perspective" in ws_transform, "Workspace empty should have 3D tilt"
        
        # Test clicking empty state illustration to focus search input
        page.locator(".ws-empty-img").click(force=True)
        page.wait_for_timeout(150)
        is_focused = page.evaluate("document.activeElement === document.getElementById('nameInput')")
        print(f"Search input focused upon clicking ws-empty-img: {is_focused}")
        assert is_focused, "Search input should be focused upon clicking empty graphic"
        
        # 3. Test Discipline exploration interaction
        page.click('.sidebar-item[data-nav="discipline"]')
        page.wait_for_selector("#disciplineNavView:not([hidden])")
        page.wait_for_selector(".discipline-art-img")
        
        # Test 3D tilt on discipline banner
        disc_box = page.locator(".discipline-art-img").bounding_box()
        assert disc_box is not None, "Discipline banner missing"
        page.mouse.move(disc_box["x"] + 30, disc_box["y"] + 20)
        page.wait_for_timeout(150)
        disc_transform = page.evaluate("document.querySelector('.discipline-art-img').style.transform")
        print(f"Discipline tilt transform: {disc_transform}")
        assert "perspective" in disc_transform, "Discipline banner should have 3D tilt"
        
        # Test click on discipline banner to focus filter search input
        page.locator(".discipline-art-img").click(force=True)
        page.wait_for_timeout(150)
        is_disc_focused = page.evaluate("document.activeElement === document.getElementById('disciplineSearchInput')")
        print(f"Discipline search input focused on click: {is_disc_focused}")
        assert is_disc_focused, "Discipline search input should be focused upon clicking banner image"
        
        # 4. Test Records empty interaction (records-empty.png)
        page.click('.sidebar-item[data-nav="records"]')
        page.wait_for_selector("#recordsView:not([hidden])")
        page.wait_for_selector(".records-empty-img")
        
        # Test 3D tilt on records empty
        rec_box = page.locator(".records-empty-img").first.bounding_box()
        assert rec_box is not None, "Records empty visual missing"
        page.mouse.move(rec_box["x"] + 20, rec_box["y"] + 20)
        page.wait_for_timeout(150)
        rec_transform = page.evaluate("document.querySelector('.records-empty-img').style.transform")
        print(f"Records empty tilt transform: {rec_transform}")
        assert "perspective" in rec_transform, "Records empty should have 3D tilt"
        
        # Test click on records illustration to trigger friendly privacy note
        page.locator(".records-empty-img").first.click(force=True)
        page.wait_for_timeout(200)
        toast_text = page.locator("#resultStatus").text_content()
        print(f"Records toast message shown: {toast_text}")
        assert "本地调查手记" in toast_text, "Clicking records illustration should show friendly privacy toast"
        
        # 5. Test Sources Flow interaction (source-academic.png)
        page.click('.sidebar-item[data-nav="sources"]')
        page.wait_for_selector("#sourcesView:not([hidden])")
        page.wait_for_selector(".sources-flow-img")
        sources_box = page.locator(".sources-flow-img").bounding_box()
        assert sources_box is not None, "Sources visual wrap missing"
        page.mouse.move(sources_box["x"] + 50, sources_box["y"] + 30)
        page.wait_for_timeout(150)
        sources_transform = page.evaluate("document.querySelector('.sources-flow-img').style.transform")
        print(f"Sources tilt transform: {sources_transform}")
        assert "perspective" in sources_transform or "rotate" in sources_transform, "Sources should have tilt on hover"
        
        # 6. Test About Visual interaction (about-academic.png)
        page.click('.sidebar-item[data-nav="about"]')
        page.wait_for_selector("#aboutView:not([hidden])")
        page.wait_for_selector(".about-art-img")
        about_box = page.locator(".about-art-img").bounding_box()
        assert about_box is not None, "About visual side missing"
        page.mouse.move(about_box["x"] + 30, about_box["y"] + 30)
        page.wait_for_timeout(150)
        about_transform = page.evaluate("document.querySelector('.about-art-img').style.transform")
        print(f"About tilt transform: {about_transform}")
        assert "perspective" in about_transform or "rotate" in about_transform, "About should have tilt on hover"
        
        browser.close()
    print("\n" + "=" * 60)
    print("ALL 6 VISUAL ASSETS INTERACTION TESTS PASSED! 交互感圆满达成！")
    print("=" * 60)

if __name__ == "__main__":
    test_interactions()
