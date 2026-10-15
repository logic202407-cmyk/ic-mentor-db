"""Small, manually reviewed publisher/association supplement for sparse subjects.

Only bibliography and public academic identity are stored. Historical/reposted
supervisor rosters remain secondary evidence, independent of publisher evidence.
Sources were read through web retrieval on 2026-10-14.
"""
import json
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE,OUT,aggregate
from .collect_sparse_disciplines import roster_row

NUDT_ROSTER='https://www.lingboyan.com/academicinfo-7-2174'
AEU_ROSTER='https://kaoyan.xdf.cn/202311/13544384.html'
NUDT_NOTICE='https://yjszs.nudt.edu.cn/attached/file/20260427/20260427091123_719.pdf'
AEU_NOTICE='https://yz.chsi.com.cn/sch/viewZszc--infoId-3274452846,categoryId-10462633,schId-368162,mindex-12.dhtml'
BOOK='https://www.xduph.com/pages/BookDetail.aspx?doi=17b64071-ade6-457f-88c0-002390ce843c'
ASSOCIATION='https://www.c2.org.cn/h-nd-1864.html'
OU_PAPER='https://www.sciengine.com/doi/pdfView/7CC2617DB5614090B045254617D9AC48'
HAN_PAPER='https://www.sciengine.com/doi/pdf/CDA6930DFA454AC588DBF67C921B8A97'
MA_PAPER='https://tykj.cbpt.cnki.net/portal/journal/portal/client/paper/9729a5d0151d584349d3360fea059a4f'
LI_PAPER='https://www.zhkzyfz.cn/EN/article/downloadArticleFile.do?attachType=PDF&id=346'

NEW=[
    ('丁锋','国防科技大学','电子对抗学院','1104','电磁态势分析',NUDT_ROSTER,ASSOCIATION),
    ('马继政','陆军工程大学','军事基础系','1110','军兵种训练（2024目录）',AEU_ROSTER,MA_PAPER),
    ('李功淼','陆军工程大学','军事基础系','1110','外军作战与训练研究（2024目录）',AEU_ROSTER,LI_PAPER),
]

def record(text,url,year,kind,**extra):
    return dict(text=text,url=url,year=year,source_kind=kind,fetched_at='2026-10-14',**extra)

def main():
    rows=[]
    for name,school,dept,code,direction,directory,identity in NEW:
        row=roster_row(name,school,dept,code,direction,'',directory)
        row['assignment'].update(evidence_level='secondary',identity_url=identity,
            source_kind='2024年招生目录转载（新东方）' if school=='陆军工程大学' else '导师名录转载（考博猫）',
            note=('学科对应来自2024年招生目录转载，面向军队在职干部；不表示当前招生资格或名额。论文署名单位另与期刊原文核对。' if school=='陆军工程大学' else
                  '学科对应来自转载名录；2025年学会报道核对姓名与单位，不代替当前学科与招生资格核验。'))
        rows.append(row)
    supplement={'profiles':aggregate(rows),'pages':[{'url':u,'collected_at':'2026-10-14'} for u in (NUDT_ROSTER,AEU_ROSTER)],'failures':[],'collected_at':'2026-10-14'}
    (REFERENCE/'thin_reviewed_faculty.json').write_text(json.dumps(supplement,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    data=json.loads(OUT.read_text(encoding='utf8'));keys={(p['institution'],p['department'],p['name']) for p in data['profiles']}
    for p in supplement['profiles']:
        if (p['institution'],p['department'],p['name']) not in keys:data['profiles'].append(p)
    for p in supplement['pages']:
        if not any(q['url']==p['url'] for q in data['pages']):data['pages'].append(p)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');catalog.static_catalog.cache_clear()
    book=record('丁锋、薛磊、毛毅主编：《电磁态势分析》，西安电子科技大学出版社，2022年9月。ISBN 978-7-5606-6596-2。',BOOK,2022,'出版社书目',publication_type='专著')
    facts={
        ('丁锋','国防科技大学'):{'papers':[book], 'biography':[record('中国指挥与控制学会2025年论坛报道列明：丁锋为国防科技大学电子对抗学院副教授。',ASSOCIATION,2025,'学会活动报道')]},
        ('薛磊','国防科技大学'):{'papers':[book], 'biography':[record('中国指挥与控制学会2025年论坛报道列明：薛磊为国防科技大学电子对抗学院教授。',ASSOCIATION,2025,'学会活动报道')]},
        ('欧宗伟','国防科技大学'):{'papers':[record('王宇、欧宗伟、程立：网络层次分析法在光电防护战斗效能评估中的应用。国防科技大学学报，2023，45(6):48–55。doi:10.11887/j.cn.202306007',OU_PAPER,2023,'期刊原文',work_url='https://doi.org/10.11887/j.cn.202306007')]},
        ('韩道文','国防科技大学'):{'papers':[record('鲍俊臣、韩道文、程立、陈林、罗金亮：强对抗环境下电子防空光电干扰目标分配。兵器装备工程学报，2024，45(9):145–151。doi:10.11809/bqzbgcxb2024.09.018',HAN_PAPER,2024,'期刊原文',work_url='https://doi.org/10.11809/bqzbgcxb2024.09.018')]},
        ('马继政','陆军工程大学'):{'papers':[record('刘思宁、王哲、彭丽、夏铁城、徐盛嘉、白荣雁、黄健灵、马继政：15 km长距离大强度负重跑对青年学员下肢肌力变化的研究。体育科技，2025，46(3):1–3。doi:10.14038/j.cnki.tykj.2025.03.053',MA_PAPER,2025,'期刊出版页',work_url='https://doi.org/10.14038/j.cnki.tykj.2025.03.053')],
             'biography':[record('2025年论文的作者单位将马继政列于陆军工程大学军事基础系军人体能训练与机能评定实验室。',MA_PAPER,2025,'期刊出版页')]},
        ('李功淼','陆军工程大学'):{'papers':[record('李功淼、何红悦、张斌、王勇、吴春晓：军地联动应急指挥体系的不确定性及其管理策略。指挥控制与仿真，2018，40(6):16–19。doi:10.3969/j.issn.1673-3819.2018.06.004',LI_PAPER,2018,'期刊原文',work_url='https://doi.org/10.3969/j.issn.1673-3819.2018.06.004')],
             'biography':[record('2018年论文作者简介列明陆军工程大学副教授、博士研究生，研究危机管理。这是历史任职信息。',LI_PAPER,2018,'期刊原文')]},
    }
    registry=dict(research.source_registry());ids=[]
    for (name,school),records in facts.items():
        p=next(p for p in catalog.static_catalog()[0] if p['name']==name and p['institution']==school)
        if school=='陆军工程大学':
            records['recruitment']=[record(f'2024年硕士招生目录转载列有{name}，专业为111000军事训练学，招生对象为军队在职干部。该历史目录不代表2026或2027年个人名额。',AEU_ROSTER,2024,'历史招生目录转载')]
        notice_url=AEU_NOTICE if school=='陆军工程大学' else NUDT_NOTICE
        records['admission_notices']=[record(school+'2026年硕士研究生招生简章',notice_url,2026,'学校招生简章',scope='学校公告，不代表个人名额')]
        reg=dict(registry.get(p['id'],{}));reg.update(name=name,institution=school)
        saved=reg.setdefault('records',{})
        for key,items in records.items():
            saved.setdefault(key,[])
            for item in items:
                if not any(q['text']==item['text'] and q['url']==item['url'] for q in saved[key]):saved[key].append(item)
        reg.setdefault('verified_pages',[])
        for item in (q for items in records.values() for q in items):
            if not any(q['url']==item['url'] for q in reg['verified_pages']):
                reg['verified_pages'].append({'url':item['url'],'source_kind':item['source_kind'],'fetched_at':'2026-10-14'})
        registry[p['id']]=reg;ids.append(p['id'])
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for ident in ids:research.enrich(ident,True,offline=True)
    (REFERENCE/'thin_reviewed_audit_20261014.json').write_text(json.dumps({'new_profiles':3,'enriched_profile_ids':ids},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('New profiles: 3; enriched public bibliography and admissions:',len(ids))

if __name__=='__main__':main()
