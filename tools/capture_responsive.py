"""Batch capture remaining responsive viewport screenshots.
Saves to D:\\ic-mentor-db\\reports\\screenshots\\
"""
import os
import shutil
import subprocess

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_URL = "http://127.0.0.1:8765"
OUT_DIR = r"D:\ic-mentor-db\reports\screenshots"
TEMP_DIR = r"D:\ic-mentor-db\reports\edge_tmp"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

RESPONSIVE_SHOTS = [
    ("03_workspace_dossier_1440x900.png", 1440, 900, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("04_workspace_dossier_1280x800.png", 1280, 800, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("05_workspace_dossier_768x1024.png", 768, 1024, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
    ("06_workspace_dossier_390x844.png", 390, 844, f"{BASE_URL}/?view=workspace&mentor=official-8ad592f3d494dc89dcfb"),
]

for filename, w, h, url in RESPONSIVE_SHOTS:
    out_path = os.path.join(OUT_DIR, filename)
    profile_dir = os.path.join(TEMP_DIR, f"p_{w}x{h}")
    os.makedirs(profile_dir, exist_ok=True)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        "--disable-sync",
        "--disable-extensions",
        "--no-first-run",
        "--no-sandbox",
        f"--user-data-dir={profile_dir}",
        f"--window-size={w},{h}",
        f"--screenshot={out_path}",
        "--virtual-time-budget=2000",
        url,
    ]
    print(f"Capturing {filename} ({w}x{h})...")
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(out_path):
            size = os.path.getsize(out_path)
            print(f"  OK: {size} bytes -> {out_path}")
        else:
            print(f"  FAILED: {out_path} not created")
    except Exception as e:
        print(f"  ERROR: {e}")
    finally:
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass

print("Responsive capture completed.")
