"""调查记录备份/恢复工具的行为测试。"""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock

from workbench import core, storage
from workbench.tools import backup_records as tool


def _seed(data: pathlib.Path) -> None:
    (data / "projects").mkdir(parents=True, exist_ok=True)
    (data / "investigations").mkdir(parents=True, exist_ok=True)
    storage.atomic_write_json(data / "projects" / "a.json",
                              {"id": "a" * 32, "name": "资料夹", "profiles": []})
    storage.atomic_write_json(
        data / "investigations" / "b.json",
        {"mentor_id": "m1", "notes": "重要记录", "evidence": [{"id": "e1"}]})


class BackupRestoreTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.data = self.root / "data"
        self.backups = self.root / "backups"
        (self.data / "projects").mkdir(parents=True)
        (self.data / "investigations").mkdir(parents=True)
        storage.atomic_write_json(self.data / "projects" / "a.json",
                                  {"id": "a" * 32, "name": "资料夹", "profiles": []})
        storage.atomic_write_json(
            self.data / "investigations" / "b.json",
            {"mentor_id": "m1", "notes": "重要记录", "evidence": [{"id": "e1"}]})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_backup_and_restore_roundtrip(self) -> None:
        archive = tool.backup(self.data, self.backups)
        stats = tool.verify(archive)
        self.assertEqual(stats["counts"]["projects"], 1)
        self.assertEqual(stats["counts"]["investigations"], 1)

        for path in list((self.data / "projects").glob("*.json")):
            path.unlink()
        for path in list((self.data / "investigations").glob("*.json")):
            path.unlink()

        result = tool.restore(archive, self.data)
        self.assertEqual(result["restored"], 2)
        note = json.loads((self.data / "investigations" / "b.json").read_text(encoding="utf-8"))
        self.assertEqual(note["notes"], "重要记录")
        self.assertTrue(result["safety_backup"] is None or result["safety_backup"])

    def test_verify_rejects_tampered_entry(self) -> None:
        archive = tool.backup(self.data, self.backups)
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
            for name in src.namelist():
                blob = src.read(name)
                if name == "projects/a.json":
                    blob = b'{"id": "changed"}'
                dst.writestr(name, blob)
        with self.assertRaises(ValueError):
            tool.verify(tampered)

    def test_restore_keeps_safety_copy_of_current_records(self) -> None:
        archive = tool.backup(self.data, self.backups)
        storage.atomic_write_json(self.data / "projects" / "c.json",
                                  {"id": "c" * 32, "name": "新资料夹", "profiles": []})
        result = tool.restore(archive, self.data)
        self.assertIsNotNone(result["safety_backup"])
        safety = pathlib.Path(result["safety_backup"])
        self.assertTrue(safety.is_file())
        with zipfile.ZipFile(safety) as zf:
            self.assertIn("projects/c.json", zf.namelist())


class UnsafeEntryTests(unittest.TestCase):
    """备份包里的条目名必须受限，不能借 manifest 写到数据目录之外。

    缺陷：`verify()` 只核对摘要、`restore()` 直接 `data_dir / name`；
    一份被改过的备份在 manifest 里写 ``../x.json`` 就能把内容写到数据目录外，
    而校验阶段全部通过。备份是可以转发、可以被手工编辑的文件，必须当成不可信输入。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.data = self.root / "data"
        self.backups = self.root / "backups"
        _seed(self.data)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _tampered(self, name: str) -> pathlib.Path:
        archive = tool.backup(self.data, self.backups)
        with zipfile.ZipFile(archive) as src:
            entries = {entry: src.read(entry) for entry in src.namelist()}
        manifest = json.loads(entries["manifest.json"])
        payload = b'{"pwned": true}'
        manifest["files"][name] = {"sha256": hashlib.sha256(payload).hexdigest(),
                                   "bytes": len(payload)}
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(tampered, "w") as dst:
            for entry, blob in entries.items():
                if entry != "manifest.json":
                    dst.writestr(entry, blob)
            dst.writestr(name, payload)
            dst.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        return tampered

    def test_verify_rejects_entries_outside_the_data_dir(self):
        for name in ("../escaped/pwned.json", "/abs/pwned.json", "C:/pwned.json",
                     "projects/a:b.json", "projects/../../pwned.json",
                     "other/pwned.json", "projects/../../../../escaped.json"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    tool.verify(self._tampered(name))

    def test_verify_rejects_malformed_manifest_entry(self):
        """清单条目不是对象时必须给可读错误，而不是 AttributeError 崩栈。"""
        archive = tool.backup(self.data, self.backups)
        with zipfile.ZipFile(archive) as src:
            entries = {entry: src.read(entry) for entry in src.namelist()}
        manifest = json.loads(entries["manifest.json"])
        manifest["files"]["projects/a.json"] = "not-a-dict"
        entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
        broken = self.root / "broken-manifest.zip"
        with zipfile.ZipFile(broken, "w") as dst:
            for name, blob in entries.items():
                dst.writestr(name, blob)
        with self.assertRaises(ValueError):
            tool.verify(broken)

    def test_restore_refuses_traversal_and_writes_nothing(self):
        tampered = self._tampered("../escaped/pwned.json")
        escaped = self.root / "escaped" / "pwned.json"
        with self.assertRaises(ValueError):
            tool.restore(tampered, self.data)
        self.assertFalse(escaped.exists())


class BackupNameTests(unittest.TestCase):
    """备份文件名按秒生成：同一秒内的第二份会把第一份覆盖掉。

    缺陷：`records-<时间戳到秒>.zip` 直接作为目标文件名，`ZipFile(..., "w")` 会截断
    同名的旧文件——连跑两次 `--backup`（脚本、计划任务、恢复前的安全备份）时，
    前一份备份被静默丢掉，而用户以为有两份。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.data = self.root / "data"
        self.backups = self.root / "backups"
        self.data.mkdir(parents=True)
        storage.atomic_write_json(self.data / "projects" / "a.json",
                                  {"id": "a" * 32, "profiles": []})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_two_backups_in_one_second_are_both_kept(self):
        with mock.patch.object(tool, "_stamp", return_value="20261026-120000"):
            first = tool.backup(self.data, self.backups)
            storage.atomic_write_json(self.data / "projects" / "b.json",
                                      {"id": "b" * 32, "profiles": []})
            second = tool.backup(self.data, self.backups)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())
        with zipfile.ZipFile(first) as zf:
            self.assertNotIn("projects/b.json", zf.namelist())
        self.assertEqual(tool.verify(second)["counts"]["projects"], 2)

    def test_failed_backup_leaves_nothing_that_looks_like_a_backup(self):
        original = zipfile.ZipFile.writestr
        calls = {"n": 0}

        def flaky(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 1:
                raise OSError("磁盘已满")
            return original(self, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "writestr", flaky):
            with self.assertRaises(OSError):
                tool.backup(self.data, self.backups)
        self.assertEqual([p.name for p in self.backups.glob("records-*.zip")], [])
        self.assertEqual([p.name for p in self.backups.glob("*.partial")], [])


def _craft_zip(root: pathlib.Path, entries: list[tuple[str, bytes, int | None]],
               manifest_files: dict[str, bytes]) -> pathlib.Path:
    """手写一个备份 zip：可含重复条目名、任意外部属性、任意 manifest 清单。"""
    files = {name: {"sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
             for name, blob in manifest_files.items()}
    manifest = {"created_at": "2026-10-26T15:00:00+08:00", "source": "test",
                "files": files,
                "counts": {"projects": len(files), "investigations": 0}}
    path = root / "crafted.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, blob, attr in entries:
            info = zipfile.ZipInfo(name)
            if attr is not None:
                info.external_attr = attr
            archive.writestr(info, blob)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
    return path


class ZipEntryHardeningTests(unittest.TestCase):
    """ZIP 边界补齐：重复条目、非对象记录、压缩炸弹、符号链接条目、恢复中断。

    这些是上一轮"条目名白名单"之外的边界：名字合法不代表包是良性的。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.data = self.root / "data"
        (self.data / "projects").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_duplicate_entry_names_are_rejected(self):
        """同名条目不能算"已验证"：Python 取最后一份，别的工具可能展示第一份。"""
        first = b'{"id": "a", "name": "first", "profiles": []}'
        second = b'{"id": "a", "name": "second", "profiles": []}'
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # zipfile 会对重复名发 UserWarning
            archive = _craft_zip(self.root,
                                 [("projects/a.json", first, None),
                                  ("projects/a.json", second, None)],
                                 {"projects/a.json": second})
        with self.assertRaises(ValueError) as caught:
            tool.verify(archive)
        self.assertIn("重复条目", str(caught.exception))
        with self.assertRaises(ValueError):
            tool.restore(archive, self.data)
        self.assertFalse((self.data / "projects" / "a.json").exists())

    def test_non_object_record_is_rejected(self):
        """记录文件必须是 JSON 对象；写进数组会让 /api/projects 直接 500（实测）。"""
        archive = _craft_zip(self.root, [("projects/list.json", b'[1, 2, 3]', None)],
                             {"projects/list.json": b'[1, 2, 3]'})
        with self.assertRaises(ValueError) as caught:
            tool.verify(archive)
        self.assertIn("记录对象", str(caught.exception))
        with self.assertRaises(ValueError):
            tool.restore(archive, self.data)
        self.assertFalse((self.data / "projects" / "list.json").exists())

    def test_oversized_entry_is_rejected_before_decompressing(self):
        """压缩炸弹：按中央目录里的解压后大小先拒绝，不去 read() 撑内存。"""
        payload = json.dumps({"id": "big", "blob": "a" * 2048}).encode("utf-8")
        archive = _craft_zip(self.root, [("projects/big.json", payload, None)],
                             {"projects/big.json": payload})
        with mock.patch.object(tool, "MAX_ENTRY_BYTES", 1024):
            with self.assertRaises(ValueError) as caught:
                tool.verify(archive)
            self.assertIn("上限", str(caught.exception))
            with self.assertRaises(ValueError):
                tool.restore(archive, self.data)
        self.assertFalse((self.data / "projects" / "big.json").exists())

    def test_total_size_cap_is_enforced(self):
        payload = json.dumps({"id": "x", "blob": "a" * 2048}).encode("utf-8")
        archive = _craft_zip(
            self.root,
            [("projects/a.json", payload, None), ("projects/b.json", payload, None)],
            {"projects/a.json": payload, "projects/b.json": payload})
        with mock.patch.object(tool, "MAX_TOTAL_BYTES", 2048):
            with self.assertRaises(ValueError) as caught:
                tool.verify(archive)
            self.assertIn("压缩炸弹", str(caught.exception))

    def test_symlink_entry_cannot_create_a_link(self):
        """符号链接条目按普通 JSON 文件写出；路径型载荷直接被 JSON 校验挡掉。"""
        payload = b'{"id": "link", "profiles": []}'
        attrs = 0o120777 << 16
        archive = _craft_zip(self.root, [("projects/link.json", payload, attrs)],
                             {"projects/link.json": payload})
        self.assertEqual(tool.verify(archive)["files"], 1)
        result = tool.restore(archive, self.data)
        self.assertEqual(result["restored"], 1)
        target = self.data / "projects" / "link.json"
        self.assertTrue(target.is_file())
        self.assertFalse(target.is_symlink())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), json.loads(payload))

        hostile = b"../../secret.txt"
        hostile_dir = self.root / "hostile"
        hostile_dir.mkdir()
        hostile_zip = _craft_zip(hostile_dir, [("projects/link2.json", hostile, attrs)],
                                 {"projects/link2.json": hostile})
        with self.assertRaises(ValueError):
            tool.verify(hostile_zip)

    def test_restore_interruption_is_recoverable_from_safety_backup(self):
        """写盘中断会停在一半，但恢复前安全备份一定已经存在（本轮补的文档承诺）。"""
        storage.atomic_write_json(self.data / "projects" / "a.json",
                                  {"id": "a" * 32, "name": "备份A", "profiles": []})
        storage.atomic_write_json(self.data / "projects" / "b.json",
                                  {"id": "b" * 32, "name": "备份B", "profiles": []})
        archive = tool.backup(self.data, self.root / "backups")
        storage.atomic_write_json(self.data / "projects" / "a.json",
                                  {"id": "a" * 32, "name": "当前A", "profiles": []})
        storage.atomic_write_json(self.data / "projects" / "b.json",
                                  {"id": "b" * 32, "name": "当前B", "profiles": []})

        real = storage.atomic_write_json
        calls = {"n": 0}

        def flaky(path, payload, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("模拟写盘中断")
            return real(path, payload, **kwargs)

        with mock.patch.object(storage, "atomic_write_json", flaky):
            with self.assertRaises(OSError):
                tool.restore(archive, self.data)

        # 已写的一份是备份内容，未写的一份仍是当前内容：说明中断会留下"部分恢复"
        self.assertEqual(json.loads((self.data / "projects" / "a.json")
                                    .read_text(encoding="utf-8-sig"))["name"], "备份A")
        self.assertEqual(json.loads((self.data / "projects" / "b.json")
                                    .read_text(encoding="utf-8-sig"))["name"], "当前B")
        # 但恢复前的安全备份在写盘之前就已生成，且保存的是中断前的真实状态
        safety = sorted((self.root / "backups" / "before-restore").glob("*.zip"))
        self.assertTrue(safety)
        with zipfile.ZipFile(safety[-1]) as archive_file:
            self.assertEqual(json.loads(archive_file.read("projects/a.json")
                                        .decode("utf-8"))["name"], "当前A")
            self.assertEqual(json.loads(archive_file.read("projects/b.json")
                                        .decode("utf-8"))["name"], "当前B")


if __name__ == "__main__":
    unittest.main()