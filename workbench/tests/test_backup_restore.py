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


if __name__ == "__main__":
    unittest.main()