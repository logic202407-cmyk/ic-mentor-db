"""把逐人档案打包成仓库内的单个 gzip JSONL，供 clone 后使用。

生成 `workbench/reference/research/dossiers.json.gz`，每行一条精简档案
（id / status / biography / papers / relations / recruitment / admission_notices / sources）。

为什么精简：逐人档案 6503 个文件共 28.5 MB；只保留界面与报告用得到的字段并紧凑化后，
gzip 约 5 MB，可随仓库提交。**不精简就会因为体积放弃入库，那样 clone 后界面是空的。**

用法::

    python -m workbench.tools.pack_research_bundle
    python -m workbench.tools.pack_research_bundle --check   # 只比对是否落后
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC_DIR = ROOT / ".workbench-data/public-research"
OUT = ROOT / "workbench/reference/research/dossiers.json.gz"

# **保留全部字段**。最初只挑 7 个"界面用得到"的字段，结果漏了 checked_at，
# 直接让 /report.md 导出报 KeyError——这类缺字段的错很难靠肉眼穷举，
# 而全字段打包只比精简版大 0.36 MB（4.8 → 5.16 MB），不值得为这点体积冒险。
DROP = ()


def build() -> tuple[bytes, int, int]:
    from workbench import catalog

    pairs, _by, _raw, _net = catalog.static_catalog()
    id_by_hash = {hashlib.sha256(p["id"].encode()).hexdigest(): p["id"] for p in pairs}

    lines: list[str] = []
    skipped = 0
    for f in sorted(SRC_DIR.glob("*.json")):
        mid = id_by_hash.get(f.stem)
        if not mid:
            skipped += 1
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        slim = dict(data)
        slim["id"] = mid
        for key in DROP:
            slim.pop(key, None)
        lines.append(json.dumps(slim, ensure_ascii=False, separators=(",", ":")))

    blob = ("\n".join(lines) + "\n").encode("utf-8")
    # mtime=0：gzip 头默认会写入当前时间，导致每次压缩字节都不同，--check 会永远报不一致。
    return gzip.compress(blob, compresslevel=9, mtime=0), len(lines), skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="打包逐人档案")
    ap.add_argument("--check", action="store_true", help="只比对是否落后")
    args = ap.parse_args()

    if not SRC_DIR.is_dir():
        print(f"找不到 {SRC_DIR}（通常是没跑过 public_research）")
        return 1

    gz, count, skipped = build()
    if args.check:
        if not OUT.is_file():
            print(f"仓库打包缺失：{OUT}")
            return 1
        current = OUT.read_bytes()
        same = hashlib.sha256(current).hexdigest() == hashlib.sha256(gz).hexdigest()
        print(f"档案打包：本机 {count} 条 / 仓库 {OUT.stat().st_size/1024/1024:.1f} MB")
        print("结论:", "一致" if same else "仓库打包落后于本机档案，需重新打包")
        return 0 if same else 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gz)
    print(f"写出 {OUT.relative_to(ROOT)}：{count} 条 / {len(gz)/1024/1024:.1f} MB "
          f"（跳过 {skipped}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
