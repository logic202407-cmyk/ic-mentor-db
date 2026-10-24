"""Batch capture screenshots across viewports and views for UI verification.
Saves all screenshots to D:\\ic-mentor-db\\reports\\screenshots\\
"""
import os
import subprocess
import time

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_URL = "http://127.0.0.1:8765"
OUT_DIR = r"D:\ic-mentor-db\reports\screenshots"
os.makedirs(OUT_DIR, exist_ok=True)

SHOTS = [
    ("01_home_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=home"),
    ("02_workspace_dossier_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("03_workspace_dossier_1440x900.png", 1440, 900, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("04_workspace_dossier_1280x800.png", 1280, 800, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("05_workspace_dossier_768x1024.png", 768, 1024, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("06_workspace_dossier_390x844.png", 390, 844, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("07_discipline_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=discipline"),
    ("08_records_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=records"),
    ("09_sources_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=sources"),
    ("10_about_1920x1080.png", 1920, 1080, f"{BASE_URL}/?view=about"),
]

for filename, w, h, url in SHOTS:
    out_path = os.path.join(OUT_DIR, filename)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        "--disable-sync",
        "--disable-extensions",
        "--no-first-run",
        "--no-sandbox",
        f"--window-size={w},{h}",
        f"--screenshot={out_path}",
        "--virtual-time-budget=2000",
        url,
    ]
    print(f"Capturing {filename} ({w}x{h}) from {url}...")
    try:
        subprocess.run(cmd, capture_output=True, timeout=20)
        if os.path.exists(out_path):
            size = os.path.getsize(out_path)
            print(f"  OK: {size} bytes -> {out_path}")
        else:
            print(f"  FAILED: {out_path} not created")
    except Exception as e:
        print(f"  ERROR: {e}")

print("Batch capture completed.")
