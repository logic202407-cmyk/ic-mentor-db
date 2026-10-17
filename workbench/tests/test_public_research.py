import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench import core, catalog, public_research as research


class ResearchTests(unittest.TestCase):
    def test_historical_title_and_reprint_dates_are_not_publication_dates(self):
        self.assertIsNone(research.publication_year('《1990年代以来的思想争论》'))
        self.assertEqual(research.publication_year('《历史事件（1929—1935）》,《历史期刊》2020年第3期；2021年转载。'),2020)

    def test_detached_faculty_tabs_keep_publications_in_their_panel(self):
        html='''<body><h1>测试老师</h1><div class="teacher-menu"><ul>
        <li class="teacher-item">代表性论文</li><li class="teacher-item">获奖情况</li></ul></div>
        <div class="teacher-info-bot-con"><div class="teacher-field"><div class="con">
        <p>Example Author. A sufficiently long paper title. Dent Mater. 2022;15:34-39.</p></div></div>
        <div class="teacher-field"><p>2023 年材料科学研究奖二等奖</p></div></div></body>'''
        data=research.parse_page(html,'https://example.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(data['papers'][0]['year'],2022)

    def test_numbered_heading_fullwidth_citations_and_mixed_biography(self):
        html='''<article><h1>测试老师</h1>
        <p>测试老师，1980年出生，联系电话：12345678。2008年师从测试甲教授攻读博士学位。</p>
        <p>2.代表性论文：</p>
        <p>（1）测试老师，测试乙。纸张材料制备性能的研究。材料期刊，2021，12(1): 20-30。</p>
        <p>（2）测试老师，测试丙。纤维素结构性能研究。材料期刊，2020，11(1): 31-40。</p>
        <p>3.授权专利</p><p>2022年授权纸张材料制备方法专利。</p></article>'''
        data=research.parse_page(html,'https://example.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),2)
        self.assertEqual(len(data['relations']),1)
        self.assertIn('测试甲',data['relations'][0]['text'])
        self.assertNotIn('出生',json.dumps(data,ensure_ascii=False))
        self.assertNotIn('12345678',json.dumps(data))

    def test_english_representative_papers_heading(self):
        html='''<article><h1>Example Person</h1><div><strong>Representative Papers And Monographs</strong></div>
        <ul><li>CMS Collaboration, An experimental result in particle physics, Physical Review Letters, 2020, 125:061801.</li></ul></article>'''
        data=research.parse_page(html,'https://tdli.sjtu.edu.cn/en/people/123','Example Person')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(data['papers'][0]['year'],2020)

    def test_list_layout_separates_citations_awards_and_closed_admissions(self):
        html='''<article><h1>测试老师</h1><ul><li><h3>代表性论文专著</h3><div>
        <p>1) A study of a well defined<br> scientific question</p><p>First Author, Second Author*</p>
        <p>Nature Communications, 2026, 17, 1234.</p>
        <p>2）A second independent scientific question</p><p>Second Author*, Third Author</p>
        <p>Science, 2025, 123, 45–50.</p></div></li>
        <li><h3>荣誉奖励</h3><div><p>2024年度 Journal of Materials Chemistry 新锐科学家</p></div></li>
        <li><h3>人才需求</h3><div><p>2027级博士研究生已招满，谢谢大家！</p></div></li></ul></article>'''
        data=research.parse_page(html,'https://scce.sjtu.edu.cn/teachers/123.html','测试老师')
        self.assertEqual(len(data['papers']),2)
        self.assertEqual([p['year'] for p in data['papers']],[2026,2025])
        self.assertIn('First Author',data['papers'][0]['text'])
        self.assertIn('scientific question',data['papers'][0]['text'])
        self.assertEqual(len(data['recruitment']),1)
        self.assertIn('已招满',data['recruitment'][0]['text'])

    def test_saved_registry_page_number_year_is_corrected_without_redating_source(self):
        p={'id':'official-old-year','name':'测试老师','institution':'测试大学','homepage':'https://math.pku.edu.cn/person.htm'}
        old={'text':'Old Author. A research paper, Journal, 2017, 2030-2044.','year':2044,
             'url':'https://math.pku.edu.cn/old.htm','fetched_at':'2020-01-01'}
        reg={'records':{'papers':[old]}}
        html='<article><h1>测试老师</h1><p>这里是这位测试老师的个人主页，介绍当前工作和研究兴趣。这段测试文本用于确认身份，不包含论文或师承表述。</p></article>'
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=p),patch.object(research,'registered_source',return_value=reg), \
             patch.object(research,'fetch',return_value={'html':html,'url':p['homepage'],'fetched_at':'2026-10-14'}):
            data=research.enrich(p['id'],True)
        self.assertEqual(data['papers'][0]['year'],2017)
        self.assertEqual(data['papers'][0]['fetched_at'],'2020-01-01')
        self.assertEqual(old['year'],2044)  # Do not mutate the source registry cache.

    def test_student_roster_advisors_and_job_titles_are_not_own_lineage(self):
        html='''<article><h1>测试老师</h1>
        <p>Present: Associate Professor, PhD and master student supervisor, Example University</p>
        <p>【国际联合培养研究生】</p><p>[1] 雷某某，Example University, 2020，合作导师：Prof. Example Other</p>
        <p>2018年取得博士学位，师从电子设计自动化领域</p>
        <p>权威专家测试甲教授；2020年加入某大学任教。</p>
        <h2>代表性论文著作</h2><p>特聘教授，从事物理研究，2005年加入学校，2017年入选某项人才计划。</p>
        </article>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['relations']),1)
        self.assertIn('测试甲教授',data['relations'][0]['text'])
        self.assertFalse(data['papers'])

    def test_offline_reparse_uses_saved_page_and_preserves_fetch_date(self):
        import hashlib
        p={'id':'official-offline','name':'测试老师','institution':'测试大学','homepage':'https://math.pku.edu.cn/person.htm'}
        html='''<article><h1>测试老师</h1><h2>论文</h2>
        <p>Example author. A sufficiently long research article, Journal, 2009, 2030-2036.</p></article>'''
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=p),patch.object(research,'fetch') as online:
            cache=Path(temp)/'research-pages';cache.mkdir()
            (cache/(hashlib.sha256(p['homepage'].encode()).hexdigest()+'.json')).write_text(
                json.dumps({'html':html,'url':p['homepage'],'fetched_at':'2025-01-01'}),encoding='utf8')
            data=research.enrich(p['id'],True,offline=True)
            online.assert_not_called()
            self.assertEqual(data['papers'][0]['year'],2009)
            self.assertEqual(data['papers'][0]['fetched_at'],'2025-01-01')

    def test_publication_year_ignores_pages_and_doi(self):
        examples={
            'Paper. Journal, 2009, (08): 2030-2036.':2009,
            'Paper. IEEE, vol.21, pp.2033–2042, March 2025.':2025,
            'Paper. Journal 11(2):2020, 2018. doi:10.2026/example.':2018,
            'Paper. Journal, 2017, article number 2024.':2017,
            '论文题目；2023-12-15；期刊名称；IF2024=4.1':2023,
            '某某著，某出版社2006年版。':2006,
        }
        for text,year in examples.items():
            with self.subTest(text=text):self.assertEqual(research.publication_year(text),year)

    def test_awards_and_academic_service_do_not_become_papers(self):
        html='''<article><h1>测试老师</h1><h2>论文</h2>
        <p>Example author. A sufficiently long research article, Journal, 2025.</p>
        <h2>获奖</h2><p>ACM SIGMOD 2022最佳论文优胜奖</p>
        <h2>学术服务</h2><p>ACM SIGOPS主席 (2023.7 - 2027.6)</p>
        <p>ACM EuroSys: 2025（程序委员会共同主席）</p></article>'''
        data=research.parse_page(html,'https://cs.sjtu.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(data['papers'][0]['year'],2025)

    def test_publication_table_keeps_title_author_venue_and_date_together(self):
        html='''<article><h1>测试老师</h1><h2>科研项目</h2><table>
        <tr><td>项目名称</td><td>时间</td></tr><tr><td>国家基金项目</td><td>2024</td></tr></table>
        <h2>代表性文章</h2><table>
        <tr><td>论文名称</td><td>作者</td><td>时间</td><td>期刊</td></tr>
        <tr><td>A sufficiently long synthetic article</td><td>Test Author</td><td>2023-12-15</td><td>Forestry Research</td></tr>
        <tr><td>Another sufficiently long synthetic article</td><td>Other Author</td><td>2022 年 09 月</td><td>Forests</td></tr>
        </table><h2>专利</h2><p>2025年林木育种装置专利</p></article>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),2)
        self.assertEqual(data['papers'][0]['year'],2023)
        self.assertIn('Test Author',data['papers'][0]['text'])
        self.assertIn('Forestry Research',data['papers'][0]['text'])

    def test_chemical_at_symbol_is_not_an_email_and_long_citation_keeps_year(self):
        html='<article><h1>测试老师</h1><h2>论文</h2><p>Mo/Ga@ZSM-11 catalyst. '+('A long author list. '*30)+'Journal, 2024.</p><p>Contact: private@example.com</p></article>'
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(data['papers'][0]['year'],2024)
        self.assertNotIn('private@example.com',str(data))

    def test_representative_articles_heading_captures_non_keyword_journals(self):
        html='''<article><h1>测试老师</h1><h3>代表性文章：</h3>
        <p>1) Example A. A sufficiently long article title. Forestry Research, 2024, 4: e012.</p>
        <h3>专利</h3><p>2025年用于林木培育的装置，授权发明专利。</p></article>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)
        self.assertIn('Forestry Research',data['papers'][0]['text'])

    def test_catalog_only_profile_can_read_personal_homepage(self):
        profile={'id':'official-test','name':'测试老师','institution':'测试大学','department':'学院',
            'collected_at':'2026-10-14','homepage':'https://math.pku.edu.cn/person.htm',
            'discipline_assignments':[{'first_level_discipline':'0701 数学','subject':'070100 数学',
                'direction':'代数','year':2026,'url':'https://math.pku.edu.cn/catalog'}]}
        html='<article><h1>测试老师</h1><h2>论文</h2><p>A sufficiently long synthetic paper, Forestry Research, 2024.</p></article>'
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=profile), \
             patch.object(research,'fetch',return_value={'html':html,'url':profile['homepage'],'fetched_at':'2026-10-14'}) as fetch:
            self.assertTrue(research.load(profile['id'])['needs_enrichment'])
            data=research.enrich(profile['id'])
            self.assertFalse(research.load(profile['id'])['needs_enrichment'])
        self.assertEqual(data['status'],'ready')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(len(data['recruitment']),1)
        fetch.assert_called_once()

    def test_registered_homepage_still_requires_person_name(self):
        p={'id':'official-test','name':'测试老师','institution':'测试大学','homepage':'https://math.pku.edu.cn/person.htm'}
        reg={'homepage':p['homepage'],'sources':[{'url':p['homepage'],'identity_url':'https://math.pku.edu.cn/catalog'}]}
        html='<article><h1>另一个老师</h1><h2>论文</h2><p>A sufficiently long synthetic paper from someone else, Forestry Research, 2024.</p></article>'
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=p),patch.object(research,'registered_source',return_value=reg), \
             patch.object(research,'fetch',return_value={'html':html,'url':p['homepage'],'fetched_at':'2026-10-14'}):
            data=research.enrich(p['id'])
        self.assertEqual(data['status'],'unavailable')
        self.assertFalse(data['papers'])

    def test_shared_directory_homepage_is_not_read_as_personal(self):
        p={'id':'official-test','name':'测试老师','institution':'测试大学','homepage':'https://math.pku.edu.cn/list.htm'}
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=p), \
             patch.object(research,'shared_catalog_homepages',return_value={p['homepage']}),patch.object(research,'fetch') as fetch:
            data=research.enrich(p['id'])
        self.assertEqual(data['status'],'unavailable')
        fetch.assert_not_called()

    def test_preprint_heading_is_preserved_without_labelling_journal_papers(self):
        html='''<article><h1>测试老师</h1><h2>Preprints</h2>
        <p>A sufficiently long mathematical research title, 2026.</p>
        <h2>Journal Papers</h2><p>Another sufficiently long paper, Journal of Testing, 2025.</p></article>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(data['papers'][0]['publication_type'],'预印本')
        self.assertNotIn('publication_type',data['papers'][1])

    def test_extraction_keeps_papers_separate_and_does_not_infer_lineage(self):
        html='''<body><nav>招生信息 硕士生招生 博士生招生</nav><article><h1>测试老师</h1>
        <h3>教育背景</h3><p>2018年博士毕业，师从测试甲教授。</p>
        <p>与测试乙共同发表论文，合作取得新成果。</p>
        <p>2024年比赛获奖。指导教师：测试丙教授。</p>
        <p>《汉学师承记笺释》，测试出版社2006年版。</p>
        <p>2024年教学成果一等奖，指导教师：测试丁。</p>
        <p>2025年招收博士研究生2名，欢迎相关专业学生报考。</p>
        <h3>代表作</h3><p>1. A synthetic scientific paper on systems, Journal A, 2024.<br>
        2. Another synthetic paper on computation, Journal B, 2023.</p>
        <h3>科研项目</h3><p>2025年主持某个科研项目的研究。</p>
        <p>邮箱：private@example.com</p></article></body>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),2)
        self.assertEqual(len(data['relations']),1)
        self.assertIn('师从测试甲',data['relations'][0]['text'])
        self.assertEqual(len(data['recruitment']),1)
        self.assertEqual(data['recruitment'][0]['year'],2025)
        self.assertNotIn('private@example.com',str(data))

    def test_name_mismatch_and_untrusted_url_are_rejected(self):
        with self.assertRaises(ValueError):
            research.parse_page('<h1>其他人</h1>','https://math.pku.edu.cn/person.htm','测试老师')
        for url in ['http://127.0.0.1/','https://pku.edu.cn.evil.org/','https://evil.edu.cn/','file:///etc/passwd']:
            self.assertFalse(research.official_url(url))

    def test_directory_cannot_be_used_as_one_persons_papers(self):
        profile={'name':'测试老师','homepage':'https://math.pku.edu.cn/list.htm',
                 'sources':[{'url':'https://math.pku.edu.cn/list.htm','claim':'名录列出测试老师'}]}
        with tempfile.TemporaryDirectory() as temp, patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(catalog,'entry_by_id',return_value=profile),patch.object(research,'fetch') as fetch:
            data=research.enrich('official-test')
            self.assertEqual(data['status'],'unavailable')
            fetch.assert_not_called()

    def test_failed_refresh_preserves_previous_results_and_notes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core,'DATA_DIR',Path(temp)):
            path=research.path_for('official-test');path.parent.mkdir(parents=True)
            previous={'version':research.VERSION,'status':'ready','papers':[{'text':'Saved publication'}]}
            path.write_text(json.dumps(previous),encoding='utf-8')
            with patch.object(catalog,'entry_by_id',return_value={'name':'测试老师','homepage':'https://math.pku.edu.cn/person.htm'}), \
                 patch.object(research,'fetch',side_effect=ValueError('offline')):
                result=research.enrich('official-test',True)
            self.assertTrue(result['refresh_error'])
            self.assertEqual(result['papers'],previous['papers'])
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),previous)

    def test_award_sections_and_teaching_roles_do_not_become_research(self):
        html='''<h1>测试老师</h1><h3>代表性论文</h3>
        <p>1. Example A. A synthetic research publication. Journal of Examples, 2025.</p>
        <p>3.学术奖励 测试老师 (2/5); 某科学研究奖, 某省人民政府, 自然科学奖, 三等奖, 2024.</p>
        <p>4.个人风采展示：2017年进行博士联合培养</p>
        <p>学术导师：担任多名本科生学术导师，及多项大学生创新创业项目指导老师。</p>'''
        data=research.parse_page(html,'https://example.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)
        self.assertEqual(data['relations'],[])

    def test_bilingual_faculty_cv_does_not_double_count_translations(self):
        html='''<h1>测试老师</h1><h3>代表性论文</h3>
        <p>1.《测试研究的一项论文成果》，《测试学报》，2025年第1期。</p>
        <p>Title: Professor</p><h3>Representative papers</h3>
        <p>1. A synthetic research publication. Journal of Examples, 2025.</p>'''
        data=research.parse_page(html,'https://example.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),1)

    def test_short_book_title_is_not_an_education_section_heading(self):
        html='''<h1>测试老师</h1><h3>代表性论著成果</h3>
        <p>1.《思想政治教育研究》，测试大学出版社，2024年。</p>
        <p>2.《课程建设研究》，测试大学出版社，2025年。</p>
        <h3>教育经历</h3><p>2010年进入测试大学攻读博士学位。</p>'''
        data=research.parse_page(html,'https://example.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['papers']),2)

    def test_admission_notices_remain_institution_level(self):
        html='''<a href="/a.htm">2027年博士研究生招生申请办法</a>
        <a href="/b.htm">2025年硕士研究生复试办法</a><a href="/c.htm">招生工作</a>
        <a href="/d.htm">2026年博士研究生复试成绩及总成绩</a>
        <a href="/e.htm">2026年硕士研究生拟录取名单公示</a>'''
        with patch.object(research,'fetch',return_value={'html':html,'url':'https://math.pku.edu.cn/admissions/','fetched_at':'2026-10-14'}):
            rows=research.admission_notices('https://math.pku.edu.cn/admissions/')
        self.assertEqual([row['year'] for row in rows],[2027,2025])
        self.assertTrue(all('不代表个人名额' in row['scope'] for row in rows))

    def test_form_wrapped_article_and_split_bibliography(self):
        html='''<form><input value="private"><article><h1>测试老师</h1>
        <h3>Publications</h3><p>1. A sufficiently long synthetic research title</p>
        <p>with A. Example and B. Sample</p><p>Preprint, arXiv:2603.01964 (2026).</p>
        <p>2. Another sufficiently long synthetic publication, Journal, 2025.</p>
        <h3>Teaching</h3><p>2025 teaching undergraduate and graduate courses</p>
        </article></form>'''
        rows=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')['papers']
        self.assertEqual(len(rows),2)
        self.assertIn('synthetic research title with A. Example',rows[0]['text'])
        self.assertIn('2603.01964',rows[0]['text'])

    def test_nested_list_keeps_title_and_english_advisor_name(self):
        html='''<body><h1>Example</h1><p>I received my PhD under the supervision of Prof. Jane Example.</p>
        <h2>Publications / Preprints</h2><ul><li><p>A synthetic publication title</p>
        <div>Journal of Examples, 2025.</div></li></ul>
        <h2>AI4Math</h2><p>AI generated research note, 2026, not a publication.</p></body>'''
        d=research.parse_page(html,'https://math.pku.edu.cn/person.htm','Example')
        self.assertEqual(len(d['papers']),1)
        self.assertIn('Jane Example',d['relations'][0]['text'])

    def test_supervisor_job_title_and_student_counts_are_not_lineage(self):
        html='''<body><h1>测试老师</h1><p>Example is a professor and doctoral supervisor at Example University.</p>
        <p>博士生导师：博士生1名；硕士生导师：硕士研究生13名。</p>
        <ul>I completed my PhD in 2019 under the supervision of Prof. Jane Example.</ul></body>'''
        data=research.parse_page(html,'https://math.pku.edu.cn/person.htm','测试老师')
        self.assertEqual(len(data['relations']),1)
        self.assertIn('Jane Example',data['relations'][0]['text'])

    def test_external_source_needs_exact_identity_checked_registration(self):
        registry={'one':{'name':'测试老师','institution':'测试大学','sources':[
            {'url':'https://example.org/person','identity_url':'https://pku.edu.cn/directory'}]}}
        with patch.object(research,'source_registry',return_value=registry):
            self.assertTrue(research.trusted_url('https://example.org/person'))
            self.assertFalse(research.trusted_url('https://example.org/someone-else'))
            self.assertEqual(research.registered_source({'id':'one','name':'同名老师','institution':'测试大学'}),{})
            self.assertEqual(research.registered_source({'id':'one','name':'测试老师','institution':'其他大学'}),{})

    def test_redirect_cycle_is_rejected_without_waiting_for_lock(self):
        a='https://math.pku.edu.cn/a';b='https://math.pku.edu.cn/b'
        def page(url,refresh):return {'url':url,'html':f'<script>location.href="{b if url==a else a}"</script>'}
        with patch.object(research,'_fetch_html',side_effect=page):
            with self.assertRaisesRegex(ValueError,'循环'):research.fetch(a)

    def test_utf8_page_does_not_use_incorrect_apparent_encoding(self):
        from unittest.mock import Mock
        response=Mock(is_redirect=False,content='<html>测试老师中文履历</html>'.encode('utf8'),
                      headers={'Content-Type':'text/html'},apparent_encoding='Windows-1251')
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'DATA_DIR',Path(temp)), \
             patch.object(research.socket,'getaddrinfo',return_value=[(0,0,0,'',('8.8.8.8',0))]), \
             patch.object(research.requests,'get',return_value=response):
            self.assertIn('中文履历',research.fetch('https://math.pku.edu.cn/encoding')['html'])

    def test_postdoc_funding_and_dissertation_award_are_not_employment(self):
        html='''<body><h1>测试老师</h1><h2>科研项目</h2>
        <p>中国博士后科学基金，面上资助，2024年至2026年，项目主持。</p>
        <p>2021年省优秀博士学位论文获得者，省教育厅。</p>
        <p>2019年至2021年在测试大学从事博士后研究工作。</p></body>'''
        rows=research.parse_page(html,'https://example.edu.cn/person','测试老师')['biography']
        self.assertEqual(len(rows),1)
        self.assertIn('从事博士后研究',rows[0]['text'])

    def test_named_admissions_match_department_and_exclude_external_column(self):
        from workbench.collect_admission_evidence import extract
        html='''<h1>2026年博士生招生导师</h1><table><tr><td colspan="5" id="math">数学科学学院</td></tr>
        <tr><td>0701</td><td>070101</td><td>基础数学</td>
        <td><a href="/person">测试甲</a></td><td><a href="/external">测试乙</a></td></tr></table>'''
        profiles=[{'id':'a','name':'测试甲','institution':'中国科学技术大学','department':'数学科学学院'},
                  {'id':'b','name':'测试甲','institution':'中国科学技术大学','department':'物理学院'},
                  {'id':'c','name':'测试乙','institution':'中国科学技术大学','department':'数学科学学院'}]
        rows=extract(html,'https://dslx.ustc.edu.cn/',profiles,'2026-10-14')
        self.assertEqual(list(rows),['a'])
        self.assertEqual(rows['a']['records'][0]['year'],2026)
        self.assertIn('未注明个人剩余名额',rows['a']['records'][0]['text'])


class FooterBoilerplateTests(unittest.TestCase):
    """页脚样板必须在到达记录之前被剔除，且不能在遍历中被"改成半截"。

    历史的错误写法是先 ``soup.find_all(string=...)`` 再对命中的父节点 ``decompose()``：
    一旦页面有**两处以上**页脚样板，第一个 decompose 会让其余 string 节点失去 parent，
    随后抛 ``AttributeError: 'NavigableString' object has no attribute 'parent'``。
    单处命中的页面不会触发，所以这个缺陷潜伏到批量 ``--enrich`` 跑到多命中页面才暴露。
    """

    BODY = "研究方向：机械设计与制造、机器人机构学。" * 6
    HTML = ("<html><body>"
            '<div class="wp_articlecontent">'
            "<p>张三</p>"
            f"<p>{BODY}</p>"
            "<p>[1] 张三, 李四. 机械设计方法研究[J]. 机械工程学报, 2020, 56(3): 1-10.</p>"
            "<p>[2] 张三, 王五. 机器人机构学分析[J]. 机械工程学报, 2021, 57(5): 20-30.</p>"
            "</div>"
            "<footer><p>版权所有 某某大学</p><p>ICP备12345678</p>"
            "<p>技术支持：某某网络</p></footer>"
            "</body></html>")

    def test_page_with_several_footer_matches_still_parses(self):
        data = research.parse_page(self.HTML, 'https://example.edu.cn/zhangsan.htm', '张三')
        self.assertEqual(len(data['papers']), 2)

    def test_footer_boilerplate_never_reaches_the_records(self):
        data = research.parse_page(self.HTML, 'https://example.edu.cn/zhangsan.htm', '张三')
        blob = repr(data)
        for marker in ('ICP', '版权所有', '技术支持'):
            self.assertNotIn(marker, blob)


if __name__=='__main__':unittest.main()
