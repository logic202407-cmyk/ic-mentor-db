import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench import catalog, core, public_research
from workbench.collect_discipline_catalog import parse, aggregate, OUT, CODES
from workbench.collect_caas_catalog import parse_tables
from workbench.collect_gap_catalog import parse_html


class DisciplineCatalogTests(unittest.TestCase):
    def test_all_schools_filter_keeps_subject_boundary(self):
        profiles=[{'id':'a','name':'甲','institution':'甲校','first_level_discipline':'0833 城乡规划学','direction_group':'规划'},
                  {'id':'b','name':'乙','institution':'乙校','first_level_discipline':'0833 城乡规划学','direction_group':'设计'},
                  {'id':'c','name':'丙','institution':'乙校','first_level_discipline':'0701 数学','direction_group':'代数'}]
        for profile in profiles: profile['department']='测试学院'
        with patch.object(catalog,'all_entries',return_value=profiles):
            self.assertEqual({p['id'] for p in catalog.mentors('0833 城乡规划学','__all__','__all__')},{'a','b'})
            self.assertEqual({p['name'] for p in catalog.directions('0833 城乡规划学','__all__')},{'规划','设计'})
            self.assertEqual([p['id'] for p in catalog.mentors('0833 城乡规划学','乙校','__all__')],['b'])

    def test_admission_rows_exclude_exam_tables_and_professional_degrees(self):
        html='''<table><tr><td>001 测试学院</td><td></td><td></td><td></td><td></td></tr>
        <tr><td>080100 力学</td><td></td><td></td><td></td><td></td></tr>
        <tr><td>01 （全日制）流体力学</td><td><a href="/a">测试甲</a><br>测试乙</td><td>测试</td><td></td><td></td></tr>
        <tr><td>085500 机械</td><td></td><td></td><td></td><td></td></tr>
        <tr><td>01 专业学位方向</td><td>测试丙</td><td></td><td></td><td></td></tr></table>
        <table><tr><td>3803</td><td>病原生物学</td><td></td></tr></table>'''
        rows=parse(html,'https://ga.sjtu.edu.cn/catalog','测试大学',kind='sjtu')
        self.assertEqual([r['name'] for r in rows],['测试甲','测试乙'])
        self.assertEqual(rows[0]['assignment']['direction'],'流体力学')

    def test_bnu_blank_direction_inherits_only_in_the_faculty_table(self):
        html='''<table><thead><th>导师</th></thead><tbody>
        <tr><td>026系统科学学院</td><td></td></tr>
        <tr><td>071101系统理论</td><td></td></tr>
        <tr><td>01复杂系统</td><td>测试甲</td></tr>
        <tr><td></td><td>测试乙</td></tr></tbody></table>
        <table><tbody><tr><td>01</td><td>历史教学论</td></tr></tbody></table>'''
        rows=parse(html,'https://yz.bnu.edu.cn/catalog','测试大学')
        self.assertEqual([r['name'] for r in rows],['测试甲','测试乙'])
        self.assertEqual(rows[1]['assignment']['direction'],'复杂系统')

    def test_caas_merged_cells_and_admission_markers(self):
        tables=[[[['培养单位','学科专业','研究方向','指导教师'],
                  ['001 测试所\n拟招生人数：10','090101 作物栽培学与耕作学','01.作物生理','测试甲*、测\n试乙**'],
                  [None,None,'02.耕作制度','测试丙'],
                  [None,'095100 农业','01.作物与种业','测试丁']]]]
        rows=parse_tables(tables,'2026-10-14')
        self.assertEqual([r['name'] for r in rows],['测试甲','测试乙','测试丙'])
        self.assertIn('非拟录取',rows[0]['assignment']['note'])
        self.assertIn('拟录取直博生',rows[1]['assignment']['note'])
        self.assertEqual(rows[2]['department'],'测试所')

    def test_cross_discipline_browsing_keeps_one_identity(self):
        profile={'id':'official-test','name':'测试甲','institution':'测试大学','department':'测试学院',
                 'first_level_discipline':'0801 力学','direction_group':'流体',
                 'discipline_assignments':[{'first_level_discipline':'0801 力学','direction':'流体'},
                     {'first_level_discipline':'0802 机械工程','direction':'机器人'}]}
        with patch.object(catalog,'all_entries',return_value=[profile]):
            self.assertEqual(catalog.institutions('0802 机械工程')[0]['count'],1)
            self.assertEqual(catalog.directions('0802 机械工程','测试大学')[0]['name'],'机器人')
            rows=catalog.mentors('0802 机械工程','测试大学','机器人')
            self.assertEqual(rows[0]['id'],'official-test')
            self.assertEqual(rows[0]['first_level_discipline'],'0802 机械工程')

    def test_admissions_survive_missing_homepage_and_export(self):
        p=next(p for p in catalog.static_catalog()[0] if p.get('admission_catalog') and not p.get('homepage'))
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)):
            data=public_research.load(p['id'])
            self.assertEqual(data['status'],'catalog')
            self.assertTrue(data['recruitment'])
            with patch.object(public_research,'fetch') as fetch:
                refreshed=public_research.enrich(p['id'],force=True)
                fetch.assert_not_called()
            self.assertEqual(refreshed['recruitment'],data['recruitment'])
            self.assertIn(data['recruitment'][0]['text'],catalog.report_markdown(p['id']))

    def test_published_collection_has_no_exam_names_and_valid_assignments(self):
        data=json.loads(OUT.read_text(encoding='utf8'))
        self.assertFalse(data['failures'])
        seen=set()
        for p in data['profiles']:
            key=(p['institution'],p['department'],p['name'])
            self.assertNotIn(key,seen);seen.add(key)
            self.assertTrue(p['department'])
            self.assertNotIn(p['name'],{'病原生物学','历史教学论','专业测试','考试科目','指导教师','导师姓名','指导导师'})
            for row in p['discipline_assignments']:
                self.assertEqual(row['first_level_discipline'],CODES[row['subject'][:4]])
                self.assertTrue(row['direction'])
                if row.get('record_kind')=='faculty_directory':
                    self.assertIsNone(row['year'])
                elif row.get('evidence_level')=='secondary':
                    # A dated historical roster must keep its actual year.
                    self.assertEqual(row['year'],2024)
                    self.assertIn('/202311/13544384.html',row['url'])
                    self.assertEqual(row['degree_level'],'硕士')
                elif row.get('source_subject')=='1107 军队政治工作学':
                    self.assertEqual(row['year'],2025)
                    self.assertEqual(row['first_level_discipline'],'1106 军队政治工作学')
                    self.assertEqual(row['degree_level'],'博士')
                    self.assertTrue(row['url'].endswith('/20241018/20241018203957_900.pdf'))
                else:self.assertEqual(row['year'],2026)
        self.assertGreaterEqual(len({r['first_level_discipline'] for p in data['profiles'] for r in p['discipline_assignments']}),80)

    def test_all_official_disciplines_have_browsable_teachers(self):
        for name in CODES.values():
            schools=catalog.institutions(name)
            self.assertTrue(schools,name)
            directions=catalog.directions(name,schools[0]['name'])
            self.assertTrue(directions,name)
            self.assertTrue(catalog.mentors(name,schools[0]['name'],directions[0]['name']),name)

    def test_source_subject_survives_navigation_code_mapping(self):
        from workbench.collect_six_teacher_depth import build_profiles
        profile=next(p for p in build_profiles() if p['name']=='龙方成')
        profile['id']='official-mapping-test'
        with patch.object(catalog,'entry_by_id',return_value=profile),patch.object(public_research,'registered_source',return_value={}):
            data=public_research.with_catalog_records(profile['id'],None)
        self.assertIn('1107 军队政治工作学',data['recruitment'][0]['text'])
        self.assertIn('仅招在职军官、文职人员',data['recruitment'][0]['text'])
        self.assertEqual(profile['first_level_discipline'],'1106 军队政治工作学')
        with patch.object(catalog,'all_entries',return_value=[profile]):
            self.assertTrue(catalog.mentors('1106 军队政治工作学','__all__','__all__'))
            self.assertFalse(catalog.mentors('1107 军事后勤学','__all__','__all__'))

    def test_integrative_navigation_does_not_change_placement_major(self):
        from workbench.collect_integrative_depth import PEOPLE, build_profiles, recruitment, PLAN
        huang=next(p for p in PEOPLE if p['name']=='黄熙')
        profile=next(p for p in build_profiles() if p['name']=='黄熙')
        self.assertEqual(profile['first_level_discipline'],'1006 中西医结合')
        self.assertTrue(all(a['record_kind']=='faculty_directory' and a['year'] is None
                            for a in profile['discipline_assignments']))
        rows=recruitment(huang)
        self.assertEqual([r['subject'] for r in rows],['105600 中药'])
        self.assertTrue(all(r['year']==2025 and r['url']==PLAN for r in rows))
        self.assertIn('双选阶段',rows[0]['text'])
        self.assertNotIn('100601',rows[0]['text'])

    def test_integrative_dossiers_preserve_research_in_export(self):
        from workbench.collect_integrative_depth import PEOPLE, SCHOOL
        for person in PEOPLE:
            profile=next(p for p in catalog.static_catalog()[0]
                         if p['name']==person['name'] and p['institution']==SCHOOL)
            with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)):
                data=public_research.enrich(profile['id'],True,offline=True)
                self.assertGreaterEqual(len(data['papers']),2)
                self.assertTrue(data['recruitment'])
                self.assertTrue(data['admission_notices'])
                report=catalog.report_markdown(profile['id'])
                for key in ('papers','relations','recruitment'):
                    for item in data[key]:self.assertIn(item['text'],report)

    def test_military_merged_rows_keep_master_level_and_eligibility(self):
        html='''<table><tr><th>单位</th><th>专业</th><th>方向</th><th>指导导师</th><th>人数</th><th>军队</th><th>教育部</th></tr>
        <tr><td rowspan="2">001测试所</td><td rowspan="2">110100军事思想与军事历史</td><td>01历史</td><td>测试甲</td><td>1</td><td>√</td><td></td></tr>
        <tr><td>02思想</td><td>测 试乙</td><td>2</td><td>√</td><td>√</td></tr></table>'''
        rows=parse_html('ams',html)
        self.assertEqual([r['name'] for r in rows],['测试甲','测试乙'])
        self.assertEqual(rows[1]['department'],'测试所')
        self.assertEqual(rows[0]['assignment']['degree_level'],'硕士')
        self.assertIn('不面向',rows[0]['assignment']['note'])
        self.assertNotIn('不面向',rows[1]['assignment']['note'])

    def test_rosters_do_not_become_admissions_or_official_evidence(self):
        profiles=catalog.static_catalog()[0]
        for institution in ('中国石油大学（北京）','中国人民公安大学','国防科技大学'):
            p=next(p for p in profiles if p['institution']==institution)
            with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)):
                data=public_research.load(p['id'])
            self.assertEqual(data['catalog_kind'],'faculty_directory')
            self.assertFalse(data['recruitment'])
            self.assertTrue(data['biography'])
            self.assertNotIn('学校博士生导师名录',data['biography'][0]['text'])
            if institution=='国防科技大学':
                self.assertTrue(p['secondary_source'])
                self.assertIn('转载',data['biography'][0]['source_kind'])
                self.assertTrue(data['biography'][0]['identity_url'])

if __name__=='__main__':unittest.main()
