"""Batch capture multi-resolution screenshots and specific test cases.
Saves screenshots to reports/screenshots/ (repo-relative, derived from this file).
"""
import os
from pathlib import Path
import subprocess

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_URL = "http://127.0.0.1:8765"
OUT_DIR = str(Path(__file__).resolve().parent.parent / "reports" / "screenshots")  # 不写死盘符：克隆到任何位置都能跑
os.makedirs(OUT_DIR, exist_ok=True)

RESOLUTIONS = [
    ("res_1920x1080.png", 1920, 1080),
    ("res_1664x947.png", 1664, 947),
    ("res_1440x900.png", 1440, 900),
    ("res_1366x768.png", 1366, 768),
    ("res_1280x800.png", 1280, 800),
    ("res_1024x768.png", 1024, 768),
    ("res_768x1024.png", 768, 1024),
    ("res_390x844.png", 390, 844),
    ("res_375x812.png", 375, 812),
    ("res_320x568.png", 320, 568),
]

# 1. 10 种分辨率测试（以查尔斯·李波档案为高压力测试样本）
for filename, w, h in RESOLUTIONS:
    out_path = os.path.join(OUT_DIR, filename)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        f"--window-size={w},{h}",
        f"--screenshot={out_path}",
        f"{BASE_URL}/?mentor=legacy-70d0b480a18a3704f200",
    ]
    print(f"Capturing {filename} ({w}x{h})...")
    try:
        subprocess.run(cmd, capture_output=True, timeout=25)
        if os.path.exists(out_path):
            print(f"  OK: {os.path.getsize(out_path)} bytes")
    except Exception as e:
        print(f"  ERR: {e}")

# 2. 重点案例视图
CASES = [
    ("case_scenario_a_0811.png", 1440, 900, f"{BASE_URL}/?discipline=0811%20%E6%8E%A7%E5%88%B6%E7%A7%91%E5%AD%A6%E4%B8%8E%E5%B7%A5%E7%A8%8B"),
    ("case_scenario_b_lieber.png", 1440, 900, f"{BASE_URL}/?mentor=legacy-70d0b480a18a3704f200"),
    ("case_home_overview.png", 1440, 900, f"{BASE_URL}/?view=home"),
    ("case_discipline_grid.png", 1440, 900, f"{BASE_URL}/?view=discipline"),
    ("case_eval_dashboard.png", 1440, 900, f"{BASE_URL}/eval"),
]

for filename, w, h, url in CASES:
    out_path = os.path.join(OUT_DIR, filename)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        f"--window-size={w},{h}",
        f"--screenshot={out_path}",
        url,
    ]
    print(f"Capturing case {filename}...")
    try:
        subprocess.run(cmd, capture_output=True, timeout=25)
        if os.path.exists(out_path):
            print(f"  OK: {os.path.getsize(out_path)} bytes")
    except Exception as e:
        print(f"  ERR: {e}")

print("All screenshots successfully captured.")
