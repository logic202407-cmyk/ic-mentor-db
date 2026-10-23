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
# 清单随副本一起提交。原因：干净 clone 上没有 `.workbench-data/public-research`（被 gitignore），
# 旧实现此时直接 `return 1`，于是"一条命令全绿"的验收在别人机器上永远不成立。
# 有了清单，干净 clone 至少能校验副本自身完整性（条数 + 摘要），有本地档案时再校验新鲜度。
MANIFEST = ROOT / "workbench/reference/research/dossiers.manifest.json"

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
    ap.add_argument("--manifest", action="store_true",
                    help="只按现有仓库副本重写清单（不重新打包）")
    ap.add_argument("--force", action="store_true",
                    help="允许把副本显著改小（默认拒绝，防止本机档案不完整时误覆盖）")
    args = ap.parse_args()

    if args.check:
        return check()

    if args.manifest:
        if not OUT.is_file():
            print(f"仓库副本不存在：{OUT.relative_to(ROOT)}")
            return 1
        blob = OUT.read_bytes()
        count = _count_lines(OUT)
        MANIFEST.write_text(_manifest_text(blob, count) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"重写 {MANIFEST.relative_to(ROOT)}：{count} 条 / "
              f"{len(blob)/1024/1024:.1f} MB")
        return 0

    if not SRC_DIR.is_dir():
        print(f"找不到 {SRC_DIR}（通常是没跑过 public_research）")
        return 1

    gz, count, skipped = build()
    # 防呆：本机 `.workbench-data/public-research` 可能只剩少量档案（例如被清理过），
    # 直接重打包会把仓库里数千份副本覆盖成个位数，而且 `--check` 还会把它说成"落后"。
    # 因此只要条数掉到原副本的一半以下就拒绝，必须显式 --force。
    if OUT.is_file() and not args.force:
        try:
            existing = _count_lines(OUT)
        except (OSError, EOFError):
            existing = 0
        if existing and count < existing * 0.5:
            print(f"拒绝写入：新打包只有 {count} 条，而仓库副本有 {existing} 条。"
                  "通常说明本机档案不完整（.workbench-data/public-research 被清理）。")
            print("如确认要缩小副本，请加 --force；只是想修清单请用 --manifest。")
            return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gz)
    MANIFEST.write_text(
        _manifest_text(gz, count) + "\n", encoding="utf-8", newline="\n")
    print(f"写出 {OUT.relative_to(ROOT)}：{count} 条 / {len(gz)/1024/1024:.1f} MB "
          f"（跳过 {skipped}）")
    print(f"写出 {MANIFEST.relative_to(ROOT)}（条数 + 摘要，供干净 clone 校验）")
    return 0


def _count_lines(path: pathlib.Path) -> int:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _manifest_text(gz: bytes, count: int) -> str:
    """清单内容：条数 + 摘要。时间戳只写在清单里，不写进 gzip 头（会破坏可比性）。"""
    payload = {
        "count": count,
        "sha256": hashlib.sha256(gz).hexdigest(),
        "size_bytes": len(gz),
        "note": "由 workbench.tools.pack_research_bundle 生成；用于干净 clone 上校验副本完整性。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def check() -> int:
    """校验仓库副本。分两级：

    1. 完整性（任何环境）：副本存在、可解压、条数与摘要与清单一致。
    2. 新鲜度（只有本机有 `.workbench-data/public-research` 时才做）：重新打包后逐字节比对。

    第 2 级在干净 clone 上无从执行——那不是失败，而是"判断不了"。把它当失败会让
    验收在评审机器上永远红，反而掩盖真正的问题。
    """
    if not OUT.is_file():
        print(f"FAIL 仓库打包缺失：{OUT.relative_to(ROOT)}")
        return 1
    if not MANIFEST.is_file():
        print(f"FAIL 清单缺失：{MANIFEST.relative_to(ROOT)}（无法校验副本完整性）")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"FAIL 清单不是合法 JSON：{exc}")
        return 1

    blob = OUT.read_bytes()
    actual_sha = hashlib.sha256(blob).hexdigest()
    try:
        actual_count = _count_lines(OUT)
    except (OSError, EOFError) as exc:
        print(f"FAIL 仓库副本无法解压：{exc}")
        return 1

    problems = []
    if manifest.get("sha256") != actual_sha:
        problems.append("副本摘要与清单不符（文件可能被改动或损坏）")
    if manifest.get("count") != actual_count:
        problems.append(f"副本条数 {actual_count} 与清单 {manifest.get('count')} 不符")

    print(f"仓库副本：{actual_count} 条 / {len(blob)/1024/1024:.1f} MB")

    if SRC_DIR.is_dir():
        gz, count, skipped = build()
        same = hashlib.sha256(gz).hexdigest() == actual_sha
        print(f"本机档案：{count} 条（跳过 {skipped}）")
        if count < actual_count * 0.5:
            # 本机档案反而比仓库副本少得多：这不是"副本落后"，而是本机不完整。
            # 把它报成失败会诱导维护者去"重新打包"，把仓库副本覆盖成个位数。
            print("新鲜度：SKIP（本机档案明显少于仓库副本，判断为本机不完整；"
                  "如确认要缩小副本请显式 --force）")
        else:
            if not same:
                problems.append("仓库副本落后于本机档案，需重新打包")
            print("新鲜度：", "一致" if same else "落后")
    else:
        print("新鲜度：SKIP（本机无原始档案，干净 clone 上无从比对；已校验完整性）")

    if problems:
        print("结论: 不一致 → " + "；".join(problems))
        return 1
    print("结论: 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
