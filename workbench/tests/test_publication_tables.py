import unittest
from workbench.collect_publication_tables import parse
from workbench.collect_shisu_profiles import public_body


class PublicationTableTests(unittest.TestCase):
    def test_dynamic_profile_requires_public_visibility_and_matching_identity(self):
        d={'Data':{'Title':'张三','ID':'123','IsOnlyMember':False,'ContentInfo':'<p>Public biography</p>'}}
        self.assertIn('张三',public_body(d,'张三','123'))
        with self.assertRaises(ValueError):public_body(d,'李四','123')
        d['Data']['IsOnlyMember']=True
        with self.assertRaises(ValueError):public_body(d,'张三','123')

    def test_author_column_not_title_substring_and_skip_external_students(self):
        html='''<table><tr><td>论文题目</td><td>所有作者</td><td>发表/出版时间</td><td>发表刊物</td></tr>
        <tr><td>关于张三思想的研究</td><td>李四</td><td>2024-01-01</td><td>期刊甲</td></tr>
        <tr><td>第二篇</td><td>张三(外),李四(学)</td><td>2024-02-01</td><td>期刊乙</td></tr>
        <tr><td>第三篇</td><td>张三,李四</td><td>2024-03-01</td><td>期刊丙</td></tr></table>'''
        ps=[{'id':n,'name':n,'discipline_assignments':[{'url':'https://example.com/catalog'}]} for n in ['张三','李四']]
        d=parse(html,'https://example.com/papers',ps)
        self.assertEqual([r['title'] for r in d['张三']],['第三篇'])
        self.assertEqual(len(d['李四']),2)
        self.assertNotIn('第二篇',str(d))
        self.assertEqual(parse(html,'https://example.com/papers',[ps[0],ps[0]]),{})
