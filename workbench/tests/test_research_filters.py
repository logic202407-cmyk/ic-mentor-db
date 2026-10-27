"""Direction shortcuts must retrieve sourced research, never names or AI hints."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from workbench import catalog
from workbench.app import app


class ResearchRetrievalTests(unittest.TestCase):
    def test_every_shortcut_has_real_coverage_and_api_parity(self):
        with TestClient(app) as client:
            for query in catalog.RESEARCH_ALIASES:
                with self.subTest(query=query):
                    expected = catalog.search_research(query)
                    self.assertGreater(len(expected), 0)
                    response = client.get('/api/catalog/research', params={'q': query})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), expected)
                    self.assertEqual(catalog.search_name(query), [])

    def test_name_institution_and_ai_hints_are_not_research_evidence(self):
        profile = {'id': 'one', 'name': '计算机视觉', 'institution': '计算机视觉大学',
                   'department': '', 'first_level_discipline': '0812 计算机科学与技术',
                   'interests': '水利工程', 'ai_hints': '计算机视觉'}
        with patch.object(catalog, 'all_entries', return_value=[profile]):
            self.assertEqual(catalog.search_research('计算机视觉'), [])
            profile['interests'] = 'Computer Vision; machine learning'
            self.assertEqual(len(catalog.search_research('计算机视觉')), 1)

    def test_combined_filters_only_narrow_results(self):
        items = catalog.search_research('机器学习')
        selected = items[0]
        result = catalog.search_research('机器学习', selected['first_level_discipline'],
                                         selected['institution'])
        self.assertTrue(result)
        self.assertTrue({p['id'] for p in result} <= {p['id'] for p in items})
        self.assertTrue(all(p['institution'] == selected['institution'] for p in result))
        self.assertEqual(catalog.search_research('机器学习', institution='不存在的高校'), [])
        self.assertEqual(catalog.search_research('不存在的研究方向abcxyz'), [])

    def test_admissions_and_direction_match_recorded_fields(self):
        discipline = '0812 计算机科学与技术'
        profile = {'id': 'one', 'name': '测试', 'institution': '甲校', 'department': '',
                   'first_level_discipline': discipline, 'direction_group': '机器学习',
                   'admission_catalog': False}
        with patch.object(catalog, 'all_entries', return_value=[profile]):
            self.assertEqual(catalog.search_research('', discipline, direction='计算机视觉'), [])
            self.assertEqual(catalog.search_research('', discipline, admission_signal=True), [])
            profile['admission_catalog'] = True
            self.assertEqual(len(catalog.search_research('', discipline, direction='机器学习',
                                                        admission_signal=True)), 1)


if __name__ == '__main__':
    unittest.main()
