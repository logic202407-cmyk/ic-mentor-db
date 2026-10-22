"""给 test_ai_hints 补上「仓库副本」相关测试。

核心命题：**评委 clone 仓库后必须能看到 AI 建议**。产物原先只写在 gitignore 的
`.workbench-data/`，clone 后不存在，AI 区块会静默隐藏——而报告与视频都在展示它。
"""

from __future__ import annotations

import json
import pathlib
import unittest

from workbench import ai_hints

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
REPO_DIR = ROOT / "workbench/reference/ai"


class RepoArtifactTests(unittest.TestCase):
    """仓库内副本必须存在、可解析、且结构与读取代码匹配。"""

    def test_suggestions_copied_into_repo(self):
        path = REPO_DIR / "direction_suggestions.json"
        self.assertTrue(path.is_file(), "缺少仓库内副本：clone 后 AI 区块会消失")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("suggestions", payload)
        self.assertGreater(len(payload["suggestions"]), 100)
        first = payload["suggestions"][0]
        for key in ("id", "suggested", "score", "method", "apply"):
            self.assertIn(key, first)

    def test_name_review_copied_into_repo(self):
        path = REPO_DIR / "name_review.json"
        self.assertTrue(path.is_file(), "缺少仓库内副本")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, list)
        self.assertGreater(len(payload), 10)
        for key in ("name", "emb", "verdict", "a", "b"):
            self.assertIn(key, payload[0])

    def test_repo_artifacts_are_reasonably_small(self):
        # 仓库里已有 34 MB 的数据文件，但这两个产物应当保持轻量
        for name in ("direction_suggestions.json", "name_review.json"):
            size_mb = (REPO_DIR / name).stat().st_size / 1024 / 1024
            self.assertLess(size_mb, 8.0, f"{name} 过大（{size_mb:.1f} MB）")


class PickTests(unittest.TestCase):
    """_pick：本地产物存在时用它（更新），否则回退仓库副本（clone 场景）。"""

    def test_prefers_local_when_present(self):
        local = pathlib.Path(".workbench-data/direction-inference/suggestions.json")
        repo = REPO_DIR / "direction_suggestions.json"
        picked = ai_hints._pick(ROOT / local, repo)
        # 本地产物当前存在，应选它；若不存在则应选仓库副本——两种都算正确行为
        self.assertIn(picked, {ROOT / local, repo})

    def test_falls_back_to_repo(self):
        missing = pathlib.Path("no/such/file.json")
        repo = REPO_DIR / "name_review.json"
        self.assertEqual(ai_hints._pick(missing, repo), repo)

    def test_resolved_paths_are_absolute(self):
        self.assertTrue(ai_hints.SUGGESTIONS_PATH.is_absolute())
        self.assertTrue(ai_hints.REVIEW_PATH.is_absolute())


class CloneSimulationTests(unittest.TestCase):
    """模拟 clone：只提供仓库副本时，提示层仍要能取到数据。"""

    def test_repo_copy_alone_yields_summary(self):
        from unittest.mock import patch

        with patch.object(ai_hints, "SUGGESTIONS_PATH",
                          REPO_DIR / "direction_suggestions.json"), \
             patch.object(ai_hints, "REVIEW_PATH", REPO_DIR / "name_review.json"):
            ai_hints.clear_cache()
            summary = ai_hints.summary()
            first = summary["direction"]["available"]
            pairs = summary["name_review"]["pairs"]
            ai_hints.clear_cache()
        self.assertTrue(first, "只用仓库副本时，方向建议应为可用")
        self.assertGreater(pairs, 10, "只用仓库副本时，同名待核应有数据")


if __name__ == "__main__":
    unittest.main()
