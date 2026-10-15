"""Reviewed bibliography, supervision and dated admissions for subjects at six.

No live scraping: records contain only manually checked bibliographic facts.
Keep the source's 1107 political-work code separately from 1106 navigation.
"""
import json
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE, OUT, aggregate
from .collect_sparse_disciplines import roster_row
from .collect_four_teacher_depth import record, paper, DATE, DOCTOR
from .collect_thin_subject_reviewed import AEU_ROSTER, AEU_NOTICE, NUDT_NOTICE

SUPPLEMENT = REFERENCE / 'six_teacher_depth_faculty.json'
AUDIT = REFERENCE / 'six_teacher_depth_audit_20261015.json'
LONG_PAPER = 'https://deyu.usst.edu.cn/_upload/article/files/92/08/46b96f9c4b05a775f2aaab0cb01b/ce05f1e2-6c00-4389-9ae0-1972afc3ee6e.pdf'
LONG_RELATION = 'https://finance.sina.com.cn/jjxw/2025-01-11/doc-ineeqftf4759294.shtml'
LAN_BOOK = 'https://www.nudt.edu.cn/press/tszx/syts/6d11434764ee4917b828e728e918210e.htm'
GONG_BOOK = 'https://search.worldcat.org/title/489255572'
WANG_ARTICLE = 'https://www.nudt.edu.cn/xwgg/xydt/205381a7ad8c46b18f31755b829187fc.htm'
AEU_BOOK = 'https://lib.kmu.edu.cn/info/1101/5930.htm'
AEU_PAPER = 'https://cnki.istiz.org.cn/kcms/detail/detail.aspx?dbcode=CJFQ&dbname=CJFD2025&filename=GJYJ202504001'
ZHAO_ID = 'https://cdlt.cqu.edu.cn/jdxw/79.htm'


def book(text, url, year, kind):
    return record(text, url, year, kind, publication_type='专著或编著')


TRAINING_PAPER = record('周雷、张鹏、陈伟：坚持目标为纲：构建高质量为战育人体系的关键。军事高等教育研究，2025年第4期。书目记录的作者单位为陆军工程大学；本次未核对全文。',
                        AEU_PAPER, 2025, '中国知网书目记录（istiz.org.cn 平台）', publication_type='期刊论文')
TRAINING_BOOK = book('赵俭、张鹏主编：新时代院校教育转型实践研究。南京大学出版社，2019年10月。昆明学院图书馆索书号G649.21/128；本次核对馆藏书目，未通读全书。',
                     AEU_BOOK, 2019, '高校图书馆书目')
PEOPLE = [
    dict(name='龙方成', school='国防科技大学', dept='军政基础教育学院', code='1106',
         direction='军队组织工作、战时政治工作', identity=DOCTOR,
         papers=[record('栾纪文、龙方成、吴穹：新论网络思想政治教育主客体关系的“变”与“不变”。思想教育研究，2023年第11期。论文署名单位为国防科技大学军政基础教育学院。', LONG_PAPER, 2023, '期刊原文（高校官网公开）', publication_type='期刊论文')],
         relations=[record('指导的博士生：张秀波。2025年1月学校人物报道记述龙方成指导张秀波博士论文、要求其在预答辩后继续修改。报道年份不作为毕业年份。', LONG_RELATION, 2025,
                           '学校报道转载（新浪，原文标明转自国防科技大学）', relation_type='doctoral_student', related_name='张秀波')]),
    dict(name='兰军', school='国防科技大学', dept='军政基础教育学院', code='1106',
         direction='军队政治工作原理、军队思想工作', identity=DOCTOR,
         papers=[book('兰军：网络时代军队思想政治教育创新研究。国防科技大学出版社，2013年8月，ISBN 978-7-5673-0174-9。', LAN_BOOK, 2013, '出版社图书页')]),
    dict(name='龚波', school='国防科技大学', dept='军政基础教育学院', code='1106',
         direction='军队政治工作原理、军队思想工作', identity=DOCTOR,
         papers=[book('杨成平、吴勇、龚波：中美军队人才培养制度比较研究。国防科技大学出版社，2008年。OCLC书目489255572；本次核对书目，未通读全书。', GONG_BOOK, 2008, 'OCLC WorldCat联合目录')]),
    dict(name='王永昌', school='国防科技大学', dept='军政基础教育学院', code='1106',
         direction='军队政治工作原理、战时政治工作', identity=WANG_ARTICLE,
         papers=[record('王永昌：加快推进军队政治工作智能化建设。光明日报，2025年1月19日第7版。学校官网转载并注明作者为军政基础教育学院教授。', WANG_ARTICLE, 2025, '学校转载的署名报刊文章', publication_type='报刊理论文章')]),
    dict(name='赵俭', school='陆军工程大学', dept='军事基础系', code='1110',
         direction='军队院校教育', identity=ZHAO_ID, papers=[TRAINING_BOOK],
         biography=[record('重庆大学教师教学发展中心2023年教学技能工作坊报道将赵俭列为陆军工程大学军事教育研究与教师发展中心主任。此为2023年报道中的身份，导航院系采用2024年招生目录口径。', ZHAO_ID, 2023, '高校活动报道（新闻索引）')]),
    dict(name='张鹏', school='陆军工程大学', dept='军事基础系', code='1110',
         direction='军队院校教育', identity=AEU_PAPER, papers=[TRAINING_PAPER, TRAINING_BOOK]),
    dict(name='周雷', school='陆军工程大学', dept='军事基础系', code='1110',
         direction='外军作战与训练研究', identity=AEU_PAPER, papers=[TRAINING_PAPER]),
]


def build_profiles():
    rows = []
    for p in PEOPLE:
        army = p['code'] == '1110'
        row = roster_row(p['name'], p['school'], p['dept'], p['code'], p['direction'], '', AEU_ROSTER if army else DOCTOR)
        row['collected_at'] = DATE
        a = row['assignment']
        a.update(record_kind='admission_catalog', year=2024 if army else 2025,
                 degree_level='硕士' if army else '博士', identity_url=p['identity'],
                 source_kind='2024年招生目录转载（新东方）' if army else '学校2025年博士招生目录')
        if army:
            a.update(evidence_level='secondary', note='全日制，军队在职干部；以入学时导师名单为准。院系和方向按2024年目录展示，不代表当前个人名额。')
        else:
            a.update(source_subject='1107 军队政治工作学', page=55,
                     note='原目录第55页写作1107军队政治工作学；按学科名称归入工作台1106导航，原代码另行保留。仅招在职军官、文职人员。不代表当前个人名额。')
        rows.append(row)
    profiles = aggregate(rows)
    for p in profiles:
        p['classification_basis'] = ('2024年招生目录转载实名对应；院系为历史目录口径' if p['institution']=='陆军工程大学' else
                                    '学校2025博士目录实名对应；原1107代码保留，按军队政治工作学名称对应1106导航')
        for s in p['sources']:
            if s['title']=='公开任职线索核对':
                s.update(title='身份核对来源', claim='结合招生目录、出版署名单位或高校报道核对学校与研究领域；不据此推断当前名额或师承。')
    return profiles


def main():
    profiles = build_profiles()
    supplement = dict(profiles=profiles, pages=[dict(url=u,collected_at=DATE) for u in (DOCTOR,AEU_ROSTER)], failures=[], collected_at=DATE)
    SUPPLEMENT.write_text(json.dumps(supplement,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    data = json.loads(OUT.read_text(encoding='utf8'))
    key = lambda p: (p['institution'],p['department'],p['name'])
    existing = {key(p):p for p in data['profiles']}; inserted=[]
    for p in profiles:
        if key(p) not in existing:
            data['profiles'].append(p); existing[key(p)]=p; inserted.append(p['name'])
    for page in supplement['pages']:
        if not any(p['url']==page['url'] for p in data['pages']): data['pages'].append(page)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry = dict(research.source_registry()); audit_rows=[]
    for p in PEOPLE:
        profile = next(q for q in catalog.static_catalog()[0] if key(q)==(p['school'],p['dept'],p['name']))
        ident=profile['id']; army=p['code']=='1110'
        records = {k:p.get(k,[]) for k in ('papers','relations','biography')}
        records['admission_notices']=[record(
            '陆军工程大学2026年硕士招生简章下载入口（本次核对公告及下载入口）' if army else '国防科技大学2026年硕士研究生招生简章（学校层面）',
            AEU_NOTICE if army else NUDT_NOTICE,2026,'学校招生公告',scope='学校公告，不是该导师的个人名额')]
        reg=registry.setdefault(ident,{});reg.update(name=p['name'],institution=p['school'])
        saved=reg.setdefault('records',{}); pages=reg.setdefault('verified_pages',[])
        for kind, items in records.items():
            saved.setdefault(kind,[])
            for item in items:
                match=next((r for r in saved[kind] if (r['text'],r['url'])==(item['text'],item['url'])),None)
                if match is None: saved[kind].append(item)
                else: match.update(item)
                page=next((r for r in pages if r['url']==item['url']),None)
                if page is None: pages.append(dict(url=item['url'],source_kind=item['source_kind'],fetched_at=DATE))
                else: page.update(source_kind=item['source_kind'],fetched_at=DATE)
        audit_rows.append(dict(id=ident,name=p['name'],institution=p['school']))
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in audit_rows:
        result=research.enrich(row['id'],True,offline=True)
        assert result['status']=='ready' and result['papers'] and result['recruitment']
        row['counts']={k:len(result.get(k,[])) for k in ('papers','relations','recruitment','admission_notices','biography')}
    prior=json.loads(AUDIT.read_text(encoding='utf8')) if AUDIT.exists() else {}
    audit=dict(prior,checked_at=DATE,new_profiles=prior.get('new_profiles',len(inserted)),profiles=audit_rows,
               subject_counts={d['name']:d['count'] for d in catalog.disciplines() if d['name'][:4] in ('1106','1110')},
               limitations=['龙方成补到明确博士指导关系；其余6位的公开检索未取得足够师承证据，未从合著、共同编书或招生名单推断。',
                            '8条成果展示记录对应6项不同作品：2篇期刊论文、3部书、1篇报刊理论文章。',
                            '陆军工程大学的学科归属仍据2024目录转载；国防科技大学使用2025官方目录，原1107与导航1106分开保存。',
                            '学校招生公告与个人年度招生记录分开；没有核实当前个人名额。',
                            '排除浙江财经英语专业赵俭、湖南大学教育史兰军与武汉大学量子博弈兰军的同名学位论文。',
                            '排除ojs.s-p.sg的教学论文链接：搜索缓存显示论文，直接打开却为博彩页面，未入库。'])
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(inserted=inserted,profiles=audit_rows,subject_counts=audit['subject_counts']),ensure_ascii=False))


if __name__=='__main__':main()
