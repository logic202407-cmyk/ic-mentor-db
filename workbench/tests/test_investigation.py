import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from workbench import catalog, core, investigation
from workbench.app import app


class InvestigationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(core, "DATA_DIR", Path(self.temp.name))
        self.data_patch.start()
        self.client = TestClient(app)
        self.mentor_id = catalog.search_name("唐仙")[0]["id"]
        self.base = f"/api/catalog/mentor/{self.mentor_id}"

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.temp.cleanup()

    def test_run_preserves_human_review_and_tracks_source_changes(self):
        with patch.object(investigation.requests, "get", side_effect=AssertionError("local run must be offline")):
            response = self.client.post(self.base + "/investigation", json={"modules": ["identity", "papers", "relations"]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(value == "待核查" for value in catalog.load_case(self.mentor_id)["section_status"].values()))
        self.assertFalse(self.client.get(self.base + "/investigation").json()["stale"])
        self.client.post(self.base + "/evidence", json={"category":"研究方向", "title":"追加来源", "url":"https://example.org/profile"})
        self.assertTrue(self.client.get(self.base + "/investigation").json()["stale"])
        report = self.client.get(self.base + "/report.md").text
        self.assertIn("资料已经变化", report)
        self.assertIn("最近一次调查任务", report)

    def test_unlisted_doi_and_excess_selection_are_rejected(self):
        with patch.object(investigation.requests, "get", side_effect=AssertionError("must reject before networking")):
            for ids in (["foreign-paper"], ["a", "b", "c", "d"]):
                response = self.client.post(self.base + "/investigation", json={"modules":["crossref"], "paper_ids":ids})
                self.assertEqual(response.status_code, 400)
        empty = self.client.post(self.base + "/investigation", json={"modules":["crossref"]}).json()
        self.assertEqual(empty["modules"][0]["status"], "等待选择论文")

    def test_doi_metadata_is_not_authorship_confirmation(self):
        paper = {"doi":"https://doi.org/10.1234/ABC", "title":"Original title"}
        self.assertEqual(investigation.normalize_doi(paper["doi"]), "10.1234/abc")
        response = Mock(status_code=429)
        with patch.object(investigation.requests, "get", return_value=response):
            self.assertEqual(investigation.check_doi(paper)["status"], "unavailable")
        response = Mock(status_code=404)
        with patch.object(investigation.requests, "get", return_value=response):
            self.assertEqual(investigation.check_doi(paper)["status"], "not_found")
        response = Mock(status_code=200)
        response.json.return_value = {"message":{"DOI":"10.1234/abc", "title":["Different title"],
                                                   "author":[{"given":"Someone", "family":"Else"}]}}
        with patch.object(investigation.requests, "get", return_value=response):
            found = investigation.check_doi(paper)
        self.assertEqual(found["status"], "found")
        self.assertFalse(found["title_exact_match"])
        self.assertIn("作者归属仍需人工核查", found["message"])

    def test_archive_requires_institution_and_excludes_contacts_and_verdicts(self):
        directory = Path(self.temp.name) / "tang-xian" / "data"
        directory.mkdir(parents=True)
        (directory / "profile.md").write_text(
            "调查日期：2026-08-22\n## 身份信息\n邮箱 test@example.org\n"
            "## 教育经历\n博士经历待核对\n## 个人评价\n不应自动继承的评价\n", encoding="utf-8")
        (directory / "scholar_data.json").write_text(json.dumps({"relationship_network":{}}), encoding="utf-8")
        with patch.object(investigation, "ARCHIVE_ROOT", Path(self.temp.name)):
            self.assertIsNone(investigation.archive_for({"name":"唐仙", "institution":"其他大学"}))
            archive = investigation.archive_for({"name":"唐仙", "institution":"清华大学深圳国际研究生院"})
        text = json.dumps(archive, ensure_ascii=False)
        self.assertIn("博士经历待核对", text)
        self.assertNotIn("test@example.org", text)
        self.assertNotIn("不应自动继承的评价", text)

    def test_duplicate_doi_aliases_keep_provenance(self):
        data = {"papers":[{"doi":"10.1234/ABC", "title":"Paper"}],
                "case":{"openalex_snapshot":{"papers":[{"doi":"https://doi.org/10.1234/abc", "title":"Paper"}]}}}
        papers = investigation.paper_candidates(data)
        self.assertEqual(len(papers), 1)
        self.assertEqual(len(papers[0]["origins"]), 2)

    def test_review_guide_uses_human_status_and_separates_not_applicable(self):
        self.client.patch(self.base + "/case", json={"section_status": {
            "身份与任职": "已人工核查", "公开声明对照": "不适用", "招生与培养": "需补证据"}})
        guide = self.client.get(self.base + "/investigation").json()["review_guide"]
        self.assertEqual((guide["reviewed"], guide["pending"], guide["not_applicable"]), (1, 6, 1))
        self.assertEqual(guide["total"], 8)
        report = self.client.get(self.base + "/report.md").text.split("## 后续核查清单")[1]
        self.assertIn("招生与培养（需补证据）", report)
        self.assertNotIn("身份与任职（", report)
        self.assertNotIn("公开声明对照（", report)

    def test_extra_evidence_does_not_complete_review_tasks(self):
        self.client.post(self.base + "/evidence", json={"category": "招生与培养",
            "title": "招生页面", "url": "https://example.org/admissions"})
        guide = self.client.get(self.base + "/investigation").json()["review_guide"]
        item = next(item for item in guide["items"] if item["section"] == "招生与培养")
        self.assertIn("1 条相关补充来源", item["available"])
        self.assertEqual(item["status"], "待核查")
        self.assertEqual(guide["reviewed"], 0)

    def test_manual_paper_enters_doi_selection_export_and_can_be_removed(self):
        response = self.client.post(self.base + "/papers", json={"title":"手动添加的论文",
            "doi":"https://doi.org/10.1234/ABC", "year":"2025"})
        self.assertEqual(response.status_code, 200)
        paper = response.json()["manual_papers"][0]
        self.assertEqual(paper["doi"], "10.1234/abc")
        overview = self.client.get(self.base + "/investigation").json()
        self.assertTrue(any(p["doi"] == "10.1234/abc" for p in overview["papers"]))
        self.assertIn("手动添加的论文", self.client.get(self.base + "/report.md").text)
        duplicate = self.client.post(self.base + "/papers", json={"title":"同 DOI", "doi":"10.1234/abc"})
        self.assertEqual(duplicate.status_code, 400)
        deleted = self.client.delete(self.base + "/papers/" + paper["id"])
        self.assertEqual(deleted.json()["manual_papers"], [])

    def test_manual_paper_requires_source_and_valid_year(self):
        for payload in ({"title":"无来源"}, {"title":"错误 DOI", "doi":"invalid"},
                        {"title":"错误年份", "url":"https://example.org/paper", "year":"NaN"}):
            self.assertEqual(self.client.post(self.base + "/papers", json=payload).status_code, 400)

    def test_remote_refresh_preserves_concurrent_notes_and_rejects_changed_author(self):
        catalog.update_case(self.mentor_id, {"openalex_author_id":"A123"})
        def snapshot(_):
            catalog.update_case(self.mentor_id, {"notes":"查询期间写下的笔记"})
            return {"papers":[]}
        with patch('workbench.openalex.works_snapshot', side_effect=snapshot):
            result = catalog.refresh_openalex(self.mentor_id)
        self.assertEqual(result["notes"], "查询期间写下的笔记")
        def changed(_):
            catalog.update_case(self.mentor_id, {"openalex_author_id":"A456"})
            return {"papers":[]}
        with patch('workbench.openalex.works_snapshot', side_effect=changed):
            with self.assertRaises(ValueError):
                catalog.refresh_openalex(self.mentor_id)
        self.assertEqual(catalog.load_case(self.mentor_id)["openalex_author_id"], "A456")
        self.assertIsNone(catalog.load_case(self.mentor_id)["openalex_snapshot"])


if __name__ == "__main__":
    unittest.main()
