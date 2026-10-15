"""Behavior checks for import identity, local persistence, and evidence workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from workbench import core
from workbench import catalog
from workbench.openalex import OpenAlexUnavailable
from workbench.app import app


class WorkbenchBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.old_data_dir = core.DATA_DIR
        self.old_projects_dir = core.PROJECTS_DIR
        core.DATA_DIR = Path(self.directory.name)
        core.PROJECTS_DIR = core.DATA_DIR / "projects"
        self.client = TestClient(app)
        self.project_id = self.client.post("/api/projects", json={"name": "跨学科核查"}).json()["id"]

    def tearDown(self) -> None:
        self.client.close()
        core.DATA_DIR = self.old_data_dir
        core.PROJECTS_DIR = self.old_projects_dir
        self.directory.cleanup()

    def test_same_name_different_department_is_preserved(self) -> None:
        rows = [
            {"姓名": "同名老师", "机构": "示例大学", "院系": "医学院", "学科": "医学"},
            {"姓名": "同名老师", "机构": "示例大学", "院系": "法学院", "学科": "法学"},
            {"姓名": "同名老师", "机构": "示例大学", "院系": "医学院", "学科": "医学"},
        ]
        response = self.client.post(
            f"/api/projects/{self.project_id}/import",
            json={"filename": "sample.json", "content": json.dumps(rows, ensure_ascii=False)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["added"], 2)
        self.assertEqual(response.json()["duplicates"], 1)
        profiles = self.client.get(f"/api/projects/{self.project_id}").json()["profiles"]
        self.assertEqual({p["department"] for p in profiles}, {"医学院", "法学院"})

    def test_manual_mentor_is_searchable_in_discipline_and_duplicate_is_rejected(self):
        payload = {"name":"测试导师", "institution":"测试大学", "department":"历史学院",
                   "first_level_discipline":"0602 中国史", "interests":"宋代史"}
        url = f"/api/projects/{self.project_id}/profiles"
        self.assertEqual(self.client.post(url, json=payload).status_code, 200)
        self.assertEqual(self.client.post(url, json=payload).status_code, 409)
        found = catalog.mentors("0602 中国史", "测试大学", "宋代史", self.project_id)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "测试导师")

    def test_source_notes_shortlist_export_persist(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/profiles",
            json={"name": "测试导师", "institution": "测试大学", "discipline": "历史学",
                  "interests": "宋代社会史", "homepage": "https://example.org/faculty"},
        )
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        profile_id = profile["id"]
        self.assertEqual(profile["sources"][0]["status"], "待人工核查")
        source_id = profile["sources"][0]["id"]
        self.assertEqual(self.client.patch(
            f"/api/projects/{self.project_id}/profiles/{profile_id}/sources/{source_id}",
            json={"status": "已人工核查"},
        ).status_code, 200)
        self.client.patch(f"/api/projects/{self.project_id}/profiles/{profile_id}",
                          json={"notes": "仍需核实招生信息", "shortlisted": True})
        found = self.client.post(f"/api/projects/{self.project_id}/search",
                                 json={"query": "宋代社会史", "mode": "keyword"}).json()["results"]
        self.assertEqual(found[0]["profile"]["id"], profile_id)
        exported = self.client.get(f"/api/projects/{self.project_id}/export").json()
        saved = exported["profiles"][0]
        self.assertTrue(saved["shortlisted"])
        self.assertEqual(saved["sources"][0]["status"], "已人工核查")
        self.assertEqual(saved["notes"], "仍需核实招生信息")

    def test_import_does_not_treat_external_notes_as_user_notes(self) -> None:
        rows = [{"name": "测试导师", "institution": "示例机构", "notes": "未经核实的评价",
                 "interests": "AI x 病理", "homepage": "javascript:alert(1)",
                 "summary": "contact@example.org"}]
        result = self.client.post(
            f"/api/projects/{self.project_id}/import",
            json={"filename": "untrusted.json", "content": json.dumps(rows, ensure_ascii=False)},
        )
        self.assertEqual(result.status_code, 200)
        saved = self.client.get(f"/api/projects/{self.project_id}").json()["profiles"][0]
        self.assertEqual(saved["notes"], "")
        self.assertEqual(saved["homepage"], "")
        self.assertNotIn("contact@example.org", saved["summary"])
        self.assertEqual(saved["imported_from"], "untrusted.json")

    def test_name_disambiguation_and_discipline_cascade(self) -> None:
        names = self.client.get("/api/catalog/name", params={"q": "张涛"}).json()
        self.assertGreaterEqual(len(names), 2)
        self.assertTrue(all(item["name"] == "张涛" for item in names[:2]))
        self.assertGreaterEqual(len({item["institution"] for item in names}), 2)
        subjects = self.client.get("/api/catalog/disciplines").json()
        self.assertIn("0811 控制科学与工程", [item["name"] for item in subjects])
        discipline = "0811 控制科学与工程"
        institutions = self.client.get("/api/catalog/institutions", params={"discipline": discipline}).json()
        self.assertIn("上海交通大学", [item["name"] for item in institutions])
        directions = self.client.get("/api/catalog/directions", params={
            "discipline": discipline, "institution": "上海交通大学"}).json()
        self.assertTrue(directions)
        mentors = self.client.get("/api/catalog/mentors", params={
            "discipline": discipline, "institution": "上海交通大学",
            "direction": "__all__"}).json()
        self.assertTrue(any(item["name"] == "张涛" for item in mentors))

    def test_evidence_is_local_scoped_and_exported(self) -> None:
        mentor = self.client.get("/api/catalog/name", params={"q": "张涛"}).json()[0]
        mentor_id = mentor["id"]
        endpoint = f"/api/catalog/mentor/{mentor_id}/evidence"
        invalid = self.client.post(endpoint, json={"category": "招生与培养",
                                                   "title": "测试", "url": "javascript:alert(1)"})
        self.assertEqual(invalid.status_code, 400)
        created = self.client.post(endpoint, json={"category": "招生与培养",
                                                   "title": "测试来源", "url": "https://example.org/notice",
                                                   "claim": "该页面应由人工核查"})
        self.assertEqual(created.status_code, 200)
        item = created.json()["evidence"][0]
        self.assertEqual(item["status"], "待人工核查")
        changed = self.client.patch(f"{endpoint}/{item['id']}", json={"status": "已人工核查"})
        self.assertEqual(changed.json()["evidence"][0]["status"], "已人工核查")
        self.assertIn("https://example.org/notice", self.client.get(
            f"/api/catalog/mentor/{mentor_id}/report.md").text)
        self.assertEqual(catalog.load_case(mentor_id)["evidence"][0]["id"], item["id"])
        self.assertEqual(self.client.delete(f"{endpoint}/{item['id']}").json()["evidence"], [])

    def test_author_record_requires_human_choice_before_snapshot(self) -> None:
        mentor_id = self.client.get("/api/catalog/name", params={"q": "张涛"}).json()[0]["id"]
        base = f"/api/catalog/mentor/{mentor_id}"
        self.assertEqual(self.client.post(base + "/openalex/refresh").status_code, 400)
        with patch("workbench.app.author_candidates", return_value=[{
                "id": "A1234567890", "name": "同名作者", "institutions": ["其他大学"],
                "works_count": 3, "url": "https://openalex.org/A1234567890"}]):
            candidates = self.client.get(base + "/openalex/authors").json()["results"]
        self.assertEqual(candidates[0]["institutions"], ["其他大学"])
        self.assertEqual(catalog.load_case(mentor_id)["openalex_author_id"], "")
        self.assertEqual(self.client.patch(base + "/case", json={
            "openalex_author_id": "invalid"}).status_code, 400)
        self.assertEqual(self.client.patch(base + "/case", json={
            "openalex_author_id": "A1234567890"}).status_code, 200)
        with patch("workbench.openalex.works_snapshot", return_value={
                "author_id": "A1234567890", "papers": [], "coauthors": [], "caveat": "测试样本"}):
            self.assertEqual(self.client.post(base + "/openalex/refresh").status_code, 200)
        self.assertEqual(catalog.load_case(mentor_id)["openalex_snapshot"]["caveat"], "测试样本")
        with patch("workbench.app.author_candidates", side_effect=OpenAlexUnavailable("测试限流")):
            unavailable = self.client.get(base + "/openalex/authors")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json()["detail"], "测试限流")

    def test_legacy_relationship_levels_and_external_clues_are_kept_separate(self) -> None:
        external_key = next(key for key, grouped in catalog.network_index().items()
                            if grouped.get("external"))
        mentor = next(item for item in catalog.static_catalog()[0]
                      if item.get("network_key") == external_key)
        data = self.client.get(f"/api/catalog/mentor/{mentor['id']}").json()
        self.assertTrue(data["relations"]["external"])
        self.assertIn("未附原始证据", data["relations"]["external"][0]["note"])
        self.assertIn("共同署名", data["relations"]["message"])


if __name__ == "__main__":
    unittest.main()
