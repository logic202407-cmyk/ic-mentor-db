"""Offline checks for directory parsing and catalog integration."""
import json
import re
import unittest
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from workbench import catalog, collect_official as collector
from workbench.app import app


class OfficialDirectoryTests(unittest.TestCase):
    def source(self, key):
        return next(source for source in collector.SOURCES if source[0] == key)

    def test_math_table_excludes_postdocs_and_contacts(self):
        source = self.source('ustc_math')
        html = '''<table><tr><td>教授</td></tr>
        <tr><td>测试甲</td><td>微分几何</td><td>5551234</td><td>test@example.org</td></tr>
        <tr><td>博士后</td></tr>
        <tr><td>测试乙</td><td>代数</td><td>5555678</td><td>other@example.org</td></tr></table>'''
        rows = collector.parse_table(BeautifulSoup(html, 'html.parser'), source, source[2])
        self.assertEqual([row['name'] for row in rows], ['测试甲'])
        self.assertEqual(rows[0]['interests'], '微分几何')
        self.assertNotIn('5551234', str(rows))
        self.assertNotIn('@', str(rows))

    def test_math_cards_use_their_own_direction(self):
        source = self.source('pku_math')
        html = ''.join(f'''<article><div><div class="left_info"><h3><a href="/{index}.htm">{name}</a></h3></div></div>
        <div class="right"><p><strong>研究方向：</strong><i>{direction}</i></p></div></article>'''
        for index, name, direction in [(1, '测试甲', '代数'), (2, '测试乙', '几何')])
        rows = collector.parse_pku_math(BeautifulSoup(html, 'html.parser'), source, source[2])
        self.assertEqual([row['interests'] for row in rows], ['代数', '几何'])

    def test_history_shared_placeholder_is_not_a_personal_page(self):
        source = self.source('bnu_history')
        html = '''<div class="pd-office-group"><h3 class="pd-office-banner">中国古代史教研室</h3>
        <a class="pd-name-card" href="/placeholder">测试甲</a>
        <a class="pd-name-card" href="/placeholder">测试乙</a>
        <a class="pd-name-card" href="https://history.bnu.edu.cn/person.htm">测试丙</a></div>'''
        rows = collector.parse_history(BeautifulSoup(html, 'html.parser'), source, source[2])
        self.assertEqual([row['name'] for row in rows], ['测试丙'])
        self.assertEqual(rows[0]['classification_basis'], '教研室归类')

    def test_published_dataset_has_traceable_minimal_facts(self):
        data = json.loads(collector.OUT.read_text(encoding='utf-8'))
        codes = {row['name'] for row in catalog.disciplines()}
        pages = {row['url'] for row in data['pages']}
        self.assertFalse(data['failures'])
        self.assertGreater(len(data['profiles']), 600)
        keys = set()
        for row in data['profiles']:
            key = (row['institution'], row['department'], row['name'])
            self.assertNotIn(key, keys)
            keys.add(key)
            self.assertIn(row['first_level_discipline'], codes)
            self.assertRegex(row['collected_at'], r'^\d{4}-\d{2}-\d{2}$')
            self.assertTrue(urlsplit(row['homepage']).hostname.endswith('.edu.cn'))
            self.assertNotIn('@V_URL', row['homepage'])
            self.assertFalse(re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', str(row)))
            self.assertTrue(all(source['url'] in pages for source in row['sources']))

    def test_browse_all_and_merged_legacy_identity(self):
        with TestClient(app) as client:
            coverage = client.get('/api/catalog/coverage').json()
            self.assertEqual(coverage['public_records'], coverage['official_records'] + coverage['secondary_records'])
            self.assertEqual(coverage['total_records'], coverage['public_records'] +
                             coverage['legacy_records'] - coverage['overlapping_records'])
            # 数学 is a non-engineering discipline, so it only returns rows when the
            # caller opts out of the default engineering scope.
            rows = client.get('/api/catalog/mentors', params={
                'discipline': '0701 数学', 'institution': '北京大学', 'direction': '__all__'}).json()
            self.assertEqual(rows, [])
            rows = client.get('/api/catalog/mentors', params={
                'discipline': '0701 数学', 'institution': '北京大学', 'direction': '__all__',
                'include_non_engineering': True}).json()
            self.assertGreater(len(rows), 50)
            self.assertEqual(len({row['id'] for row in rows}), len(rows))
            mentor_id = catalog.stable_id('legacy', '中国科学技术大学|安虹')
            detail = client.get('/api/catalog/mentor/' + mentor_id).json()
            # Legacy rows carry no first-level discipline in the source data; it is
            # assigned from research keywords, so it lands inside the engineering scope.
            self.assertEqual(detail['profile']['first_level_discipline'], '0812 计算机科学与技术')
            self.assertTrue(catalog.entry_by_id(mentor_id)['network_key'])
            self.assertEqual(len([p for p in catalog.search_name('安虹')
                                  if p['institution'] == '中国科学技术大学']), 1)


if __name__ == '__main__':
    unittest.main()
