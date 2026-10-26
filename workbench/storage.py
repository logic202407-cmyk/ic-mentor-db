"""本地 JSON 存储的可靠性基座：互斥、原子替换、备份与损坏恢复。

为什么需要这一层
----------------
工作台把「调查记录」和「资料夹」直接存成 JSON 文件。原实现有两个真实缺陷：

1. **固定临时文件名**：`path.with_suffix(".tmp")`。两个保存操作同时发生时，
   后一个会把前一个正在写的临时文件一起写坏，然后各自 `replace` 到正式文件——
   结果可能是半截 JSON。
2. **读—改—写没有互斥**：`load_project()` 与 `save_project()` 分属两次调用，
   两个并发 PATCH 都基于同一份旧数据修改，后写的覆盖先写的（丢失更新）。

这里提供三件小事，保持"就是 JSON 文件"的架构不变：

- :func:`file_lock`：按目标文件加一把 OS 级互斥锁（Windows 用 ``msvcrt.locking``，
  POSIX 用 ``flock``），超时给出可读错误，而不是无限等待。
- :func:`atomic_write_json`：唯一临时文件 + ``fsync`` + ``os.replace``，
  并在覆盖前留一份 ``.bak``。
- :func:`read_json`：解析失败时保留 ``.corrupt-<时间>`` 副本、尝试从 ``.bak`` 恢复；
  恢复不了就抛 :class:`DataCorruptError`，**绝不返回空对象让上层静默覆盖原文件**。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_LOCK_TIMEOUT = 8.0
LOCK_SUFFIX = ".lock"


class DataCorruptError(ValueError):
    """文件存在但无法解析。与"文件不存在"必须区分，否则会被静默重置。"""


class LockTimeoutError(RuntimeError):
    """等锁超时：通常意味着另一个保存操作还没结束。"""


def _ensure_byte(handle) -> None:
    """Windows 的 msvcrt.locking 需要一个存在的字节区间。"""
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)


@contextmanager
def file_lock(target: Path, timeout: float = DEFAULT_LOCK_TIMEOUT):
    """对 ``target`` 加排他锁；锁文件是 ``<target>.lock``。"""
    target = Path(target)
    lock_path = Path(str(target) + LOCK_SUFFIX)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    try:
        _ensure_byte(handle)
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(
                        "另一个保存操作仍在进行，请稍后重试") from error
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        handle.close()


def _write_backup(path: Path) -> None:
    backup = Path(str(path) + ".bak")
    try:
        data = path.read_bytes()
    except OSError:
        return
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".bak.", suffix=".tmp",
                                   dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, backup)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, payload, *, backup: bool = True) -> None:
    """写 JSON：唯一临时文件 → fsync → 原子替换；覆盖前保留 ``.bak``。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        _write_backup(path)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                                   dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _corrupt_copy_path(path: Path) -> Path:
    """给损坏文件挑一个不冲突的副本名。

    只精确到秒会让同一秒内的第二次损坏覆盖第一次的取证副本，最后只剩一份。
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = Path(f"{path}.corrupt-{stamp}")
    index = 1
    while candidate.exists():
        index += 1
        candidate = Path(f"{path}.corrupt-{stamp}-{index}")
    return candidate


def read_json(path: Path, *, recover: bool = True):
    """读 JSON；损坏时保留副本并尽量从 ``.bak`` 恢复，否则抛 DataCorruptError。

    解码用 ``utf-8-sig``：Windows 编辑器保存时可能加 UTF-8 BOM。按纯 utf-8 解码会
    把它判成「损坏」，而只要 ``.bak`` 存在，恢复分支就会用旧版本覆盖文件——
    用户刚写入的最新内容静默消失。BOM 只是编码前缀，不是损坏。
    """
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        corrupt = _corrupt_copy_path(path)
        try:
            shutil.copyfile(path, corrupt)
        except OSError:
            corrupt = None
        backup = Path(str(path) + ".bak")
        if recover and backup.exists():
            try:
                data = json.loads(backup.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                data = None
            if data is not None:
                atomic_write_json(path, data, backup=False)
                return data
        hint = f"（已保留副本 {corrupt.name}）" if corrupt else ""
        raise DataCorruptError(f"数据文件损坏：{path.name}{hint}") from error


def restore_backup(path: Path) -> bool:
    """把 ``<path>.bak`` 恢复到正式文件；成功返回 True。"""
    path = Path(path)
    backup = Path(str(path) + ".bak")
    if not backup.exists():
        return False
    data = json.loads(backup.read_text(encoding="utf-8-sig"))
    atomic_write_json(path, data, backup=False)
    return True