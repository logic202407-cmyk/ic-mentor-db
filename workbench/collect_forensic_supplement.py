"""Reviewed official-page facts, retained when direct HTTP retrieval is denied.

Sources read through web retrieval on 2026-10-14; summaries are not raw page copies.
"""
import json
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE, OUT, aggregate
from .collect_sparse_disciplines import roster_row

PEOPLE = [
    ('王小广','WangXiaoguang','法医精神病学',
     '学院主页列明硕士生导师资格。研究精神损伤的神经生物学机制；2005年取得中山大学本科学位，2010年取得博士学位。',
     "Asim M, Wang B, Hao B, Wang XG. Ketamine for post-traumatic stress disorders and it's possible therapeutic mechanism. Neurochem Int. 2021;146:105044. doi:10.1016/j.neuint.2021.105044.",2021),
    ('欧雪玲','OuXueling','法医物证学',
     '学院主页列明博士生导师资格。研究法医遗传与基因组技术、产前遗传检测；2002年获中山大学学士学位，2007年获法医学博士学位。',
     'Ou X, Qu N. Noninvasive prenatal paternity testing by target sequencing microhaps. Forensic Sci Int Genet. 2020;48:102338.',2020),
    ('赵虎','ZhaoHu','法医精神病学与法医临床学',
     '学院主页列明博士生导师资格。研究精神损伤、毒品相关精神障碍、诈病评定以及精神疾病的遗传和神经环路机制。',
     'Peng LQ, Guo Y, Wan L, Liu TA, Wang P, Zhao H, Wang YH. Forensic Bone Age Estimation of Adolescent Pelvis X-rays Based on Two-stage Convolutional Neural Network. Int J Legal Med. 2022;136(3):797-810.',2022),
    ('时燕薇','shiyanwei','法医精神病学',
     '学院导师介绍目录列为副教授，个人页注明所属法医精神病学教研室及研究方向；该页未列导师资格和年度招生安排。','',None),
]


def main():
    directory='https://zssom.sysu.edu.cn/graduate/faculty'
    rows=[]
    for name,slug,direction,bio,paper,year in PEOPLE:
        rows.append(roster_row(name,'中山大学','中山医学院·法医学系','1012',direction,
                               'https://zssom.sysu.edu.cn/teacher/'+slug,directory))
    supplement={'profiles':aggregate(rows),'pages':[{'url':directory,'collected_at':'2026-10-14'}],
                'failures':[],'collected_at':'2026-10-14','retrieval':'官方页面经网页检索读取并人工核对；直接抓取返回403，未绕过访问限制。'}
    (REFERENCE/'forensic_faculty_supplement.json').write_text(json.dumps(supplement,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    data=json.loads(OUT.read_text(encoding='utf8'))
    keys={(p['institution'],p['department'],p['name']) for p in data['profiles']}
    for p in supplement['profiles']:
        if (p['institution'],p['department'],p['name']) not in keys:data['profiles'].append(p)
    if not any(p['url']==directory for p in data['pages']):data['pages']+=supplement['pages']
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry=dict(research.source_registry());ids=[]
    for name,slug,direction,bio,paper,year in PEOPLE:
        p=next(p for p in catalog.static_catalog()[0] if p['institution']=='中山大学' and p['name']==name and p['department']=='中山医学院·法医学系')
        url='https://zssom.sysu.edu.cn/teacher/'+slug; stamp=research.core.now()
        def record(text,year=None):
            return {'text':text,'url':url,'year':year,'source_kind':'学院教师主页（网页检索核对）','identity_url':directory,'fetched_at':stamp}
        registry[p['id']]={'name':name,'institution':p['institution'],'homepage':url,
                           'sources':[{'url':url,'identity_url':directory,'source_kind':'学院教师主页'}],
                           'records':{'biography':[record(bio)],'papers':[record(paper,year)] if paper else []},
                           'verified_pages':[{'url':url,'fetched_at':stamp,'source_kind':'学院教师主页（网页检索核对）'}]}
        ids.append(p['id'])
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for ident in ids:research.enrich(ident,True,offline=True)
    print(json.dumps({'added_profiles':len(ids),'ids':ids},ensure_ascii=False))


if __name__=='__main__':main()
