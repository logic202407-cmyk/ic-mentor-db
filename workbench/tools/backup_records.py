"""备份与恢复本机调查记录（资料夹 + 逐人档案）。

为什么单独做一个工具
--------------------
用户最重要的资产不是公开数据，而是**自己写下的核查记录**。它们散在
``.workbench-data/projects/*.json`` 与 ``.workbench-data/investigations/*.json``，
一旦目录被清理或文件损坏，重建不了。这里提供最小可用的三件事：

- ``--backup``：打包成一个 zip，内含 manifest（时间、条数、每个文件的 sha256）；
- ``--verify``：只读校验 zip（JSON 可解析、摘要与清单一致）；
- ``--restore``：先校验、再把现有记录另存一份 ``records-before-restore-*``，
  然后逐文件原子写回；任何一份坏 JSON 都会让整次恢复中止，不做"恢复一半"。

用法::

    python -m workbench.tools.backup_records --backup
    python -m workbench.tools.backup_records --list
    python -m workbench.tools.backup_records --verify backups/records-....zip
    python -m workbench.tools.backup_records --restore backups/records-....zip --yes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from workbench import core, storage  # noqa: E402

KINDS = ("projects", "investigations")
DEFAULT_BACKUP_DIR = ROOT / "backups"
MANIFEST = "manifest.json"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _entries(data_dir: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for kind in KINDS:
        folder = data_dir / kind
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            found.append((f"{kind}/{path.name}", path))
    return found


def backup(data_dir: Path | None = None, dest_dir: Path | None = None) -> Path:
    data_dir = Path(data_dir or core.DATA_DIR)
    dest_dir = Path(dest_dir or DEFAULT_BACKUP_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = _entries(data_dir)
    target = dest_dir / f"records-{_stamp()}.zip"
    manifest = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "source": str(data_dir), "files": {}, "counts": {}}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in files:
            blob = path.read_bytes()
            archive.writestr(name, blob)
            manifest["files"][name] = {
                "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
        manifest["counts"] = {kind: sum(1 for name, _ in files if name.startswith(kind + "/"))
                              for kind in KINDS}
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    return target


def verify(zip_path: Path) -> dict:
    """校验压缩包：清单齐全、每个 JSON 可解析、摘要一致。返回统计。"""
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if MANIFEST not in names:
            raise ValueError("备份缺少 manifest.json，无法确认完整性")
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
        declared = manifest.get("files") or {}
        missing = sorted(set(declared) - names)
        if missing:
            raise ValueError(f"备份缺少 {len(missing)} 个文件：{missing[:3]}")
        for name, meta in declared.items():
            blob = archive.read(name)
            if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
                raise ValueError(f"{name} 摘要与清单不符（文件可能损坏）")
            try:
                json.loads(blob.decode("utf-8"))
            except ValueError as error:
                raise ValueError(f"{name} 不是合法 JSON：{error}") from error
    return {"files": len(declared), "counts": manifest.get("counts") or {},
            "created_at": manifest.get("created_at")}


def backup_dir() -> Path:
    return Path(core.DATA_DIR).parent / "backups"


def list_backups() -> list[dict]:
    folder = DEFAULT_BACKUP_DIR if DEFAULT_BACKUP_DIR.is_dir() else backup_dir()
    rows = []
    for path in sorted(folder.glob("records-*.zip")):
        rows.append({"path": str(path), "bytes": path.stat().st_size,
                     "name": path.name})
    return rows


def restore(zip_path: Path, data_dir: Path | None = None) -> dict:
    """恢复备份：先校验 → 保存当前记录 → 逐文件原子写回。"""
    data_dir = Path(data_dir or core.DATA_DIR)
    stats = verify(zip_path)
    safety = None
    if _entries(data_dir):
        safety = backup(data_dir, data_dir.parent / "backups" / "before-restore")
    restored = 0
    with zipfile.ZipFile(zip_path) as archive:
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
        names = list((manifest.get("files") or {}))
        for kind in KINDS:
            (data_dir / kind).mkdir(parents=True, exist_ok=True)
        for name in names:
            payload = json.loads(archive.read(name).decode("utf-8"))
            storage.atomic_write_json(data_dir / name, payload)
            restored += 1
    return {"restored": restored, "safety_backup": str(safety) if safety else None,
            "counts": stats.get("counts")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="调查记录备份与恢复")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--backup", action="store_true", help="打包当前记录")
    group.add_argument("--list", action="store_true", help="列出已有备份")
    group.add_argument("--verify", metavar="ZIP", help="只校验备份")
    group.add_argument("--restore", metavar="ZIP", help="恢复备份")
    ap.add_argument("--yes", action="store_true", help="恢复前不再询问")
    args = ap.parse_args(argv)

    if args.list or not (args.backup or args.verify or args.restore):
        rows = list_backups()
        if not rows:
            print("还没有备份。运行 --backup 生成第一份。")
            return 0
        for row in rows:
            print(f"{row['name']}  {row['bytes'] / 1024:.0f} KB")
        return 0

    if args.backup:
        path = backup()
        print(f"已备份到 {path}（{path.stat().st_size / 1024:.0f} KB）")
        return 0

    if args.verify:
        stats = verify(Path(args.verify))
        print(f"校验通过：{stats['files']} 个文件，{stats['counts']}，生成于 {stats['created_at']}")
        return 0

    target = Path(args.restore)
    stats = verify(target)
    if not args.yes:
        print(f"将恢复 {stats['files']} 个文件（{stats['counts']}）到 {core.DATA_DIR}。")
        print("当前记录会先另存一份 before-restore 备份。确认请加 --yes。")
        return 1
    result = restore(target)
    print(f"已恢复 {result['restored']} 个文件；恢复前备份：{result['safety_backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())