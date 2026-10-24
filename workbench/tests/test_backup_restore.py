"""调查记录备份/恢复工具的行为测试。"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
import zipfile

from workbench import core, storage
from workbench.tools import backup_records as tool


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


if __name__ == "__main__":
    unittest.main()