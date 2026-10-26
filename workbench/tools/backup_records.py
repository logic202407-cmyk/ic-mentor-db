"""备份与恢复本机调查记录（资料夹 + 逐人档案）。

为什么单独做一个工具
--------------------
用户最重要的资产不是公开数据，而是**自己写下的核查记录**。它们散在
``.workbench-data/projects/*.json`` 与 ``.workbench-data/investigations/*.json``，
一旦目录被清理或文件损坏，重建不了。这里提供最小可用的三件事：

- ``--backup``：打包成一个 zip，内含 manifest（时间、条数、每个文件的 sha256）；
- ``--verify``：只读校验 zip（条目名合法、无重复条目、JSON 是记录对象、摘要与清单一致）；
- ``--restore``：先校验、再把现有记录另存一份 ``records-before-restore-*``，
  然后逐文件原子写回。校验阶段能发现的问题（坏 JSON、坏摘要、非法条目）都会让整次
  恢复在写盘前中止；若**写盘过程中**被中断（断电、磁盘满），可能停在"部分文件已恢复"，
  此时用恢复前自动生成的安全备份再恢复一次即可回到原状。

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
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from workbench import core, storage  # noqa: E402

KINDS = ("projects", "investigations")
DEFAULT_BACKUP_DIR = ROOT / "backups"
MANIFEST = "manifest.json"
ENTRY_FILE = re.compile(r"^[^/\\]+\.json$")
# 单条记录都是几十 KB 级（5000 条导入上限也远小于这里），给足余量；
# 上限存在的意义是：别让一份被改过的备份把解压结果整包塞进内存撑爆进程。
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _checked_name(name: object) -> str:
    """只接受 ``<projects|investigations>/<文件名>.json`` 这种条目名。

    备份包是用户可以转发、也可以手工编辑的文件，manifest 里的名字**不可信**：
    一条 ``../x.json`` 就能让 ``--restore`` 把内容写到数据目录之外。
    """
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise ValueError(f"备份包含非法条目：{name!r}")
    parts = PurePosixPath(name).parts
    if (len(parts) != 2 or parts[0] not in KINDS
            or not ENTRY_FILE.fullmatch(parts[1])):
        raise ValueError(f"备份包含非法条目：{name!r}")
    return name


def _target_path(dest_dir: Path) -> Path:
    """挑一个不冲突的备份文件名。

    只精确到秒会让同一秒内的第二份备份 ``ZipFile(..., "w")`` 截断并覆盖第一份，
    用户以为有两份、其实只剩一份。同秒内重名时追加 ``-2``、``-3``。
    """
    stamp = _stamp()
    candidate = dest_dir / f"records-{stamp}.zip"
    index = 1
    while candidate.exists():
        index += 1
        candidate = dest_dir / f"records-{stamp}-{index}.zip"
    return candidate


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
    target = _target_path(dest_dir)
    manifest = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "source": str(data_dir), "files": {}, "counts": {}}
    # 先写临时文件再改名：备份中途失败（磁盘满、进程被杀）时不会留下一个
    # 名字看起来正常、内容却不完整的 records-*.zip。
    fd, partial_name = tempfile.mkstemp(prefix=".records-", suffix=".partial",
                                       dir=str(dest_dir))
    os.close(fd)
    partial = Path(partial_name)
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in files:
                blob = path.read_bytes()
                archive.writestr(name, blob)
                manifest["files"][name] = {
                    "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
            manifest["counts"] = {kind: sum(1 for name, _ in files
                                            if name.startswith(kind + "/"))
                                  for kind in KINDS}
            archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(partial, target)
    except BaseException:
        try:
            partial.unlink()
        except OSError:
            pass
        raise
    return target


def _check_duplicate_entries(archive: zipfile.ZipFile) -> None:
    """拒绝重复条目名。

    ZIP 允许同名条目，Python 的 ``read()`` 取**最后一份**，而资源管理器/7-Zip 等
    工具通常展示第一份——同一份备份在不同工具里内容不同，这种包不能算"已验证"。
    正常备份永远不会产生重复条目。
    """
    seen: set[str] = set()
    for info in archive.infolist():
        if info.filename in seen:
            raise ValueError(f"备份包含重复条目：{info.filename}")
        seen.add(info.filename)


def _load_validated(zip_path: Path) -> tuple[dict, dict[str, dict]]:
    """打开备份并完成全部校验，返回 ``(manifest, {条目名: 记录})``。

    ``verify()`` 与 ``restore()`` 共用这一份校验，避免两处规则随时间漂移；
    ``restore()`` 因此能在写盘之前拿到全部记录，校验失败绝不落到半套数据。
    """
    with zipfile.ZipFile(zip_path) as archive:
        _check_duplicate_entries(archive)
        names = set(archive.namelist())
        if MANIFEST not in names:
            raise ValueError("备份缺少 manifest.json，无法确认完整性")
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("备份的 manifest.json 不是 JSON 对象")
        declared = manifest.get("files") or {}
        if not isinstance(declared, dict):
            raise ValueError("备份的 manifest.json 文件清单格式不正确")
        for name in declared:
            _checked_name(name)
        missing = sorted(set(declared) - names)
        if missing:
            raise ValueError(f"备份缺少 {len(missing)} 个文件：{missing[:3]}")
        payloads: dict[str, dict] = {}
        total = 0
        for name, meta in declared.items():
            if not isinstance(meta, dict) or not isinstance(meta.get("sha256"), str):
                raise ValueError(f"{name} 清单条目格式不正确")
            # 用中央目录里的解压后大小先卡上限，别等 read() 把内容全解压进内存。
            size = archive.getinfo(name).file_size
            if size > MAX_ENTRY_BYTES:
                raise ValueError(
                    f"{name} 解压后 {size / 1048576:.1f} MB，超过单文件 "
                    f"{MAX_ENTRY_BYTES // 1048576} MB 上限")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ValueError(
                    f"备份解压总量超过 {MAX_TOTAL_BYTES // 1048576} MB 上限，"
                    "疑似压缩炸弹，已拒绝")
            blob = archive.read(name)
            if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
                raise ValueError(f"{name} 摘要与清单不符（文件可能损坏）")
            try:
                payload = json.loads(blob.decode("utf-8-sig"))
            except ValueError as error:
                raise ValueError(f"{name} 不是合法 JSON：{error}") from error
            if not isinstance(payload, dict):
                # 记录文件一定是 JSON 对象；写进一个数组会让 /api/projects 这类
                # 读接口直接 500（实测），所以在校验阶段就拒绝。
                raise ValueError(f"{name} 不是记录对象：顶层应为 JSON 对象")
            payloads[name] = payload
    return manifest, payloads


def verify(zip_path: Path) -> dict:
    """校验压缩包：无重复条目、清单齐全、条目名合法、记录是对象、摘要一致。返回统计。"""
    manifest, payloads = _load_validated(zip_path)
    return {"files": len(payloads), "counts": manifest.get("counts") or {},
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
    """恢复备份：先校验（含全部记录解析）→ 保存当前记录 → 逐文件原子写回。"""
    data_dir = Path(data_dir or core.DATA_DIR)
    manifest, payloads = _load_validated(zip_path)
    safety = None
    if _entries(data_dir):
        safety = backup(data_dir, data_dir.parent / "backups" / "before-restore")
    for kind in KINDS:
        (data_dir / kind).mkdir(parents=True, exist_ok=True)
    restored = 0
    for name, payload in payloads.items():
        storage.atomic_write_json(data_dir / name, payload)
        restored += 1
    return {"restored": restored, "safety_backup": str(safety) if safety else None,
            "counts": manifest.get("counts") or {}}


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