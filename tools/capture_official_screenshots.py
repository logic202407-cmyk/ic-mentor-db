# -*- coding: utf-8 -*-
"""Capture official 1440x900 screenshots for docs/screenshots/ and README."""

from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "docs" / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = "http://127.0.0.1:8765"

def capture():
    print(f"Capturing official 1440x900 screenshots to {SHOT_DIR}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="zh-CN"
        )
        page = context.new_page()

        # 1. 01-home.png
        print("1. Capturing 01-home.png...")
        page.goto(f"{BASE_URL}/?view=home", wait_until="domcontentloaded")
        page.wait_for_selector("#homeView:not([hidden])")
        page.wait_for_selector(".hero-art-img")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_DIR / "01-home.png"))

        # 2. 02-dossier.png
        print("2. Capturing 02-dossier.png...")
        page.goto(f"{BASE_URL}/?view=workspace&mentor=legacy-70d0b480a18a3704f200", wait_until="domcontentloaded")
        page.wait_for_selector("#dossier:not([hidden])")
        page.wait_for_selector("#pane-identity:not([hidden])")
        page.wait_for_timeout(600)
        page.screenshot(path=str(SHOT_DIR / "02-dossier.png"))

        # 3. 03-evidence.png (公开来源 Tab)
        print("3. Capturing 03-evidence.png...")
        page.click("#tab-investigation")
        page.wait_for_selector("#pane-investigation:not([hidden])")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_DIR / "03-evidence.png"))

        # 4. 04-discipline.png
        print("4. Capturing 04-discipline.png...")
        page.goto(f"{BASE_URL}/?view=discipline", wait_until="domcontentloaded")
        page.wait_for_selector("#disciplineNavView:not([hidden])")
        page.wait_for_selector(".discipline-card-btn")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_DIR / "04-discipline.png"))

        # 5. 05-records.png
        print("5. Capturing 05-records.png...")
        page.goto(f"{BASE_URL}/?view=records", wait_until="domcontentloaded")
        page.wait_for_selector("#recordsView:not([hidden])")
        page.wait_for_selector(".records-empty-img")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_DIR / "05-records.png"))

        # 6. 06-sources.png
        print("6. Capturing 06-sources.png...")
        page.goto(f"{BASE_URL}/?view=sources", wait_until="domcontentloaded")
        page.wait_for_selector("#sourcesView:not([hidden])")
        page.wait_for_selector(".sources-flow-img")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_DIR / "06-sources.png"))

        # 7. 07-eval.png
        print("7. Capturing 07-eval.png...")
        page.goto(f"{BASE_URL}/eval", wait_until="domcontentloaded")
        page.wait_for_selector(".site-head")
        page.wait_for_selector(".page-hero")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SHOT_DIR / "07-eval.png"))

        browser.close()
    print("All 7 official screenshots captured successfully!")

if __name__ == "__main__":
    capture()
