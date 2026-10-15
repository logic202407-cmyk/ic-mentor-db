import unittest
from workbench.discover_sjtu_research import directory_rows, matches
from workbench.recover_moved_profiles import linked_rows, agricultural_rows


class SjtuDirectoryTests(unittest.TestCase):
    def test_moved_directory_rejects_external_and_navigation_links(self):
        html='''<a href="/people/123/zhang"><div class="name">张 三</div>教授</a>
        <a href="https://other.example/people/123/li">李四</a>
        <a href="/people/directory">人员名录</a>'''
        self.assertEqual(linked_rows(html, 'https://tdli.sjtu.edu.cn/people', r'/people/\d+/[^/]*'),
                         {('张三', 'https://tdli.sjtu.edu.cn/people/123/zhang')})

    def test_agricultural_directory_only_uses_published_active_entries(self):
        html='''var letterDataMap = {"Z":[
            {"name_cn":"张三","id":123,"status":1,"published":1},
            {"name_cn":"张四","id":124,"status":1,"published":0},
            {"name_cn":"张五","id":125,"status":0,"published":1}]};'''
        self.assertEqual(agricultural_rows(html), {('张三', 'https://www.agri.sjtu.edu.cn/faculty/123')})

    def test_name_excludes_title_and_requires_person_path(self):
        html='''<a href="https://icisee.sjtu.edu.cn/jiaoshiml/test.html"><div class="name">张 三<span>教授</span><p>党委书记</p></div></a>
        <a href="https://icisee.sjtu.edu.cn/jiaoshiml.html">教师名录</a>
        <a href="https://other.example/jiaoshiml/test.html">李四</a>'''
        self.assertEqual(directory_rows(html,'icisee','jiaoshiml'),{('张三','https://icisee.sjtu.edu.cn/jiaoshiml/test.html')})

    def test_requires_unambiguous_name_and_school(self):
        profiles=[{'id':'a','name':'张三','institution':'上海交通大学','department':'电气工程学院'},
                  {'id':'b','name':'张三','institution':'上海交通大学','department':'计算机学院'},
                  {'id':'c','name':'李四','institution':'其他大学','department':'电气工程学院'}]
        rows={('张三','https://see.sjtu.edu.cn/jiaoshiml/a.html'),('李四','https://see.sjtu.edu.cn/jiaoshiml/c.html')}
        self.assertEqual([p['id'] for p,_ in matches(profiles,rows,'电气工程学院')],['a'])
        rows.add(('张三','https://see.sjtu.edu.cn/jiaoshiml/other.html'))
        self.assertFalse(matches(profiles,rows,'电气工程学院'))

