"""本地 JSON 存储的可靠性测试：并发、原子写、损坏恢复。

这些测试针对的是**真实发生过**的两类缺陷：

1. 固定临时文件名 ``<name>.tmp``：并发保存会互相覆盖临时文件，可能写出半截 JSON；
2. 读—改—写没有互斥：两个 PATCH 各基于旧数据修改，后写的覆盖先写的。

另外还钉住一条安全底线：文件损坏时**不得静默返回空记录**（否则下一次保存
会把用户的调查记录整份覆盖成空白）。
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import threading
import unittest
from unittest import mock

from workbench import catalog, core, storage


class TempDataDirCase(unittest.TestCase):
    """把数据目录指到临时目录，避免碰用户的真实调查记录。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)
        self._patches = [
            mock.patch.object(core, "DATA_DIR", self.dir),
            mock.patch.object(core, "PROJECTS_DIR", self.dir / "projects"),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()


class AtomicWriteTests(TempDataDirCase):

    def test_write_creates_no_tmp_leftover(self) -> None:
        path = self.dir / "a.json"
        storage.atomic_write_json(path, {"x": 1})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"x": 1})
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])

    def test_previous_version_kept_as_bak(self) -> None:
        path = self.dir / "a.json"
        storage.atomic_write_json(path, {"x": 1})
        storage.atomic_write_json(path, {"x": 2})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"x": 2})
        backup = pathlib.Path(str(path) + ".bak")
        self.assertTrue(backup.is_file())
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), {"x": 1})

    def test_concurrent_writes_never_produce_broken_json(self) -> None:
        path = self.dir / "race.json"
        errors: list[Exception] = []

        def writer(index: int) -> None:
            try:
                for _ in range(5):
                    with storage.file_lock(path):
                        storage.atomic_write_json(path, {"writer": index, "payload": "x" * 2000})
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn(data["writer"], range(8))
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])


class CorruptFileTests(TempDataDirCase):

    def test_corrupt_file_is_kept_and_not_silently_reset(self) -> None:
        path = self.dir / "broken.json"
        path.write_text('{"half": ', encoding="utf-8")
        with self.assertRaises(storage.DataCorruptError):
            storage.read_json(path)
        # 原文件没有被覆盖成空对象，且留下了副本
        self.assertEqual(path.read_text(encoding="utf-8"), '{"half": ')
        self.assertTrue(list(self.dir.glob("broken.json.corrupt-*")))

    def test_recovers_from_valid_bak(self) -> None:
        path = self.dir / "recover.json"
        storage.atomic_write_json(path, {"ok": True})
        storage.atomic_write_json(path, {"ok": False})   # 生成 .bak = {"ok": true}
        path.write_text("{broken", encoding="utf-8")
        data = storage.read_json(path)
        self.assertEqual(data, {"ok": True})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"ok": True})


class ProjectConcurrencyTests(TempDataDirCase):

    def test_parallel_updates_do_not_lose_writes(self) -> None:
        project = core.create_project("并发测试")
        project_id = project["id"]
        rounds = 10
        workers = 6

        def worker() -> None:
            for _ in range(rounds):
                core.update_project(project_id, lambda p: p.__setitem__(
                    "counter", int(p.get("counter", 0)) + 1))

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        stored = core.load_project(project_id)
        self.assertEqual(stored["counter"], rounds * workers)
        self.assertGreaterEqual(stored["revision"], rounds * workers)

    def test_import_profiles_persist_false_does_not_touch_disk(self) -> None:
        project = core.create_project("导入测试")
        rows = [{"name": "张三", "institution": "示例大学"}]
        before = (core._project_path(project["id"])).read_text(encoding="utf-8")
        result = core.import_profiles(project, rows, "测试", persist=False)
        self.assertEqual(result["added"], 1)
        after = (core._project_path(project["id"])).read_text(encoding="utf-8")
        self.assertEqual(before, after)


class CaseConcurrencyTests(TempDataDirCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.mentor_id = catalog.static_catalog()[0][0]["id"]

    def test_parallel_evidence_adds_are_not_lost(self) -> None:
        workers = 5
        per_worker = 4

        def worker(index: int) -> None:
            for n in range(per_worker):
                catalog.add_evidence(self.mentor_id, {
                    "category": "官方身份与任职",
                    "title": f"并行来源 {index}-{n}",
                    "url": f"https://example.edu.cn/{index}/{n}",
                    "claim": "并发测试",
                })

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        record = catalog.load_case(self.mentor_id)
        self.assertEqual(len(record["evidence"]), workers * per_worker)

    def test_corrupt_case_is_not_reset_to_blank(self) -> None:
        path = catalog._case_path(self.mentor_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(storage.DataCorruptError):
            catalog.load_case(self.mentor_id)
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")


if __name__ == "__main__":
    unittest.main()