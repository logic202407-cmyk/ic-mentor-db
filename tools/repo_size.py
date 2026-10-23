"""Report the repository's working-copy size, so docs can cite a measured number.

The README previously carried a hardcoded size that went stale as data grew (it was
wrong three times: 30 MB, then 67 MB, then 71 MB). This prints the current figure so
the claim can be refreshed mechanically instead of guessed.

Usage:
    .venv\\Scripts\\python.exe tools\\repo_size.py
"""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Directories that are local-only scratch, not part of what a clone receives.
SKIP = (".git", ".venv", ".workbench-data", "node_modules", "__pycache__")


def size_of(paths) -> tuple[int, int]:
    total = 0
    count = 0
    for rel in paths:
        p = ROOT / rel
        if p.is_file():
            total += p.stat().st_size
            count += 1
    return total, count


def main() -> int:
    # 见 workbench/tools/check_readme_badges.py 的同名说明：git 默认转义非 ASCII 路径。
    tracked = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace").stdout.split("\0")
    tracked = [p for p in tracked if p]
    total, count = size_of(tracked)
    print(f"tracked files: {count}")
    print(f"working copy (tracked): {total / 1024 / 1024:.1f} MB")

    # Largest contributors, so the figure can be explained rather than just stated.
    rows = []
    for rel in tracked:
        p = ROOT / rel
        if p.is_file():
            rows.append((p.stat().st_size, rel))
    rows.sort(reverse=True)
    print("\ntop 8 files:")
    for size, rel in rows[:8]:
        print(f"  {size / 1024 / 1024:>6.2f} MB  {rel}")

    # Directory roll-up.
    buckets: dict[str, int] = {}
    for size, rel in rows:
        top = rel.split("/", 1)[0] if "/" in rel else rel
        buckets[top] = buckets.get(top, 0) + size
    print("\nby top-level path:")
    for name, size in sorted(buckets.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {size / 1024 / 1024:>6.2f} MB  {name}")

    print("\n(the clone also fetches .git history; this measures working-copy bytes only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
