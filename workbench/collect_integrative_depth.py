"""Reviewed NJUCM profiles. Navigation and historical placement plans are separate.

Run offline; bibliography is curated, not inferred from keyword matches.
"""
import hashlib
import json
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE, OUT, aggregate
from .collect_sparse_disciplines import roster_row
from .collect_four_teacher_depth import record, DATE

TEAM = 'https://zxy.njucm.edu.cn/2025/0305/c6575a152701/page.htm'
PLAN = 'https://zxy.njucm.edu.cn/_upload/article/files/03/af/e692d64040fe89ddcca565cbb96f/bd402c79-4e75-4b30-9172-e82218a85d27.pdf'
NOTICE = 'https://zxy.njucm.edu.cn/2026/0326/c6575a166715/page.htm'
THESIS = 'https://edoc.ub.uni-muenchen.de/26116/7/Hu_Yue.pdf'
JIA_2025 = 'https://zxy.njucm.edu.cn/2025/0703/c6597a158359/page.htm'
JIA_2026 = 'https://zxy.njucm.edu.cn/2026/0828/c6597a171085/page.htm'
SUPPLEMENT = REFERENCE / 'integrative_depth_faculty.json'
AUDIT = REFERENCE / 'integrative_depth_audit_20261015.json'
SCHOOL, DEPT = '南京中医药大学', '中西医结合学院'


def publication(text, year, doi='', url=TEAM):
    return record(text, url, year, '学院团队公开书目' if url == TEAM else '期刊出版或文献数据库记录',
                  publication_type='期刊论文', **({'work_url': 'https://doi.org/'+doi} if doi else {}))


PEOPLE = [
    dict(name='贾立军', page='149645', direction='中西医结合防治肿瘤基础与转化研究',
         bio='教授、硕博士生导师，研究新型抗肿瘤分子靶标与药物筛选。',
         plans=[('100601 中西医结合基础',1),('105600 中药',4)],
         papers=[
             publication('Ni S等（含Lijun Jia）：Pro-senescence neddylation inhibitor combined with a senescence activated β-galactosidase prodrug to selectively target cancer cells. Signal Transduction and Targeted Therapy, 2022, 7:313（Letter）。',2022,'10.1038/s41392-022-01128-2','https://www.nature.com/articles/s41392-022-01128-2'),
             publication('Cai L、Li L、Chen X、Jia L：Regulation of SKP2 protein stability by heat shock protein 90 chaperone machinery. Signal Transduction and Targeted Therapy, 2021, 6:276（Letter）。',2021,'10.1038/s41392-021-00624-1','https://www.nature.com/articles/s41392-021-00624-1')],
         relations=[record(f'博士后合作指导：{name}。学院{year}年报道明确写出合作导师贾立军；这是博士后阶段的指导关系，不作为博士学位导师记录。',url,year,'学院博士后报道',relation_type='postdoctoral_mentee',related_name=name)
                    for name,year,url in [('张玉萱',2025,JIA_2025),('丁乐乐',2026,JIA_2026),('李子剑',2026,JIA_2026),('吴焱亮',2026,JIA_2026)]]),
    dict(name='吕志刚',page='149643',direction='中西医结合干预疼痛临床与基础研究',
         bio='教授、硕博士生导师，研究中医药干预肿瘤和疼痛，曾在纪念斯隆凯特癌症中心任助理研究员。',
         plans=[('100601 中西医结合基础',1),('105600 中药',4)],
         papers=[publication('Lu Z、Xu J、Rossi GC等：Mediation of opioid analgesia by a truncated 6-transmembrane GPCR. Journal of Clinical Investigation, 2015, 125(7):2626–2630。题名按期刊原文核对。',2015,'10.1172/JCI81070','https://www.jci.org/articles/view/81070'),
                 publication('Sun Q等（含Lu ZG）：Immunosuppression by opioids: Mechanisms of action on innate and adaptive immunity. Biochemical Pharmacology, 2023, 209:115417。',2023)]),
    dict(name='陶伟伟',page='149647',direction='中西医结合防治情志病研究',
         bio='教授、硕博士生导师，研究中西医结合防治情志病。',
         plans=[('100601 中西医结合基础',1),('105600 中药',4)],
         papers=[publication('Tao W、Ruan J等：A natural carotenoid crocin exerts antidepressant action by promoting adult hippocampal neurogenesis through Wnt/β-catenin signaling. Journal of Advanced Research, 2023, 43:219–231。',2023,'10.1016/j.jare.2022.02.015'),
                 publication('Tao WW、Cheng XL等：Synthesis of multi-branched Au nanocomposites with distinct plasmon resonance in NIR-II window and controlled CRISPR-Cas9 delivery for synergistic gene-photothermal therapy. Biomaterials, 2022, 287:121621。',2022)]),
    dict(name='黄熙',page='149648',direction='中西医结合基础与临床、抑郁共病与方剂药理',
         bio='教授、主任医师、硕博士生导师，研究抑郁共病、方剂作用机理与方剂药学。',
         plans=[('105600 中药',5)],
         papers=[publication('Wu L等（含Xi Huang）：Rapid antidepressant-like effect of Fructus Aurantii depends on cAMP-response element binding protein/Brain-derived neurotrophic facto by mediating synaptic transmission. Phytotherapy Research, 2021, 35(1):404–414。题名保留PubMed记录的facto拼写。',2021,'10.1002/ptr.6812','https://pubmed.ncbi.nlm.nih.gov/33044778/'),
                 publication('Liu X等（含Huang X）：Mind shift I: Fructus Aurantii - Rhizoma Chuanxiong synergistically anchors stress-induced depression-like behaviours and gastrointestinal dysmotility cluster by regulating psycho-immune-neuroendocrine network. Phytomedicine, 2024, 128:155324。',2024)],
         relations=[record('博士后阶段师从陈可冀。学院2025年团队介绍与带教计划均明确记载，不能据此认定陈可冀是其博士学位导师。',TEAM,2025,'学院团队介绍',relation_type='postdoctoral_supervisor',related_name='陈可冀')]),
    dict(name='章轶立',page='149664',direction='中医药防治骨代谢疾病、循证评价',
         bio='副教授、硕士生导师，研究老年病的中医药防治与循证评价。',
         plans=[('100601 中西医结合基础',2),('105600 中药',5)],
         papers=[publication('章轶立、孙传睿、孙凯等：从“骨健康计划”视角观照中医药防治骨质疏松症的时代价值与新思路。中国中药杂志，2025，50(3):569–574。',2025),
                 publication('章轶立、齐保玉、孙传睿等：重视机体铁代谢对骨质疏松症的影响及中医药调控效用。中国中药杂志，2025，50(3):575–582。',2025)]),
    dict(name='成小兰',page='149662',direction='中西医结合治疗神经系统疾病基础研究',
         bio='副研究员、硕士生导师，研究中西医结合治疗神经系统疾病的基础机制。职称采用个人主页口径。',
         plans=[('100601 中西医结合基础',3),('105600 中药',5)],
         papers=[publication('Lu LD等（含Cheng XL）：Emodin Inhibits AIM2 Inflammasome Activation via Modulating K27-Linked Polyubiquitination to Attenuate Renal Fibrosis. Phytotherapy Research, 2024。',2024,'10.1002/ptr.8390'),
                 publication('Cheng XL、Ruan YL、Dai JY等：8-Shogaol derived from dietary ginger alleviated acute and inflammatory pain by targeting TRPV1. Phytomedicine, 2024, 128:155500。',2024)]),
    dict(name='胡玥',page='149663',direction='中西医结合防治脑病、血脑屏障与医学大数据',
         bio='副教授、硕士生导师，博士毕业于慕尼黑大学，研究中西医结合防治脑病及医学大数据。',
         plans=[('100601 中西医结合基础',3)],
         papers=[publication('Hu Y、Tao W：Current perspectives on microglia-neuron communication in the central nervous system: Direct and indirect modes of interaction. Journal of Advanced Research, 2024, 66:251–265。',2024,'10.1016/j.jare.2024.01.006'),
                 publication('Hu Y、Zhao M、Wang H等：Exosome-sheathed ROS-responsive nanogel to improve targeted therapy in perimenopausal depression. Journal of Nanobiotechnology, 2023, 21:261。',2023,'10.1186/s12951-023-02005-y'),
                 publication('Hu Y、Seker B、Exner C、Zhang J、Plesnila N、Schwarzmaier SM：Longitudinal Characterization of Blood–Brain Barrier Permeability after Experimental Traumatic Brain Injury by In Vivo 2-Photon Microscopy. Journal of Neurotrauma, 2021。学院书目误写的期刊名已按出版记录纠正。',2021,'10.1089/neu.2020.7271','https://journals.sagepub.com/doi/abs/10.1089/neu.2020.7271')],
         relations=[record('博士导师：Nikolaus Plesnila。2020年慕尼黑大学博士论文审批页及正文第89页致谢明确记载其博士指导；身份以学校简介中的慕尼黑经历、血脑屏障研究和同题发表论文交叉核对。',THESIS,2020,'大学学位论文库原文',relation_type='doctoral_supervisor',related_name='Nikolaus Plesnila',page=91),
                    record('博士共同指导者：Susanne Schwarzmaier。论文审批页列Mitbetreuung，正文第89页致谢明确称co-supervisor。',THESIS,2020,'大学学位论文库原文',relation_type='doctoral_cosupervisor',related_name='Susanne Schwarzmaier',page=91)])
]


def homepage(p):
    return f"https://zxy.njucm.edu.cn/2024/1114/c6581a{p['page']}/page.htm"


def recruitment(p):
    return [record(f"2025年硕士导师双选带教计划：{p['name']}列在{subject}下，见原表第{page}页。这是拟录取后双选阶段的历史带教计划，不代表2026或2027年个人招生名额。",
                   PLAN,2025,'学院2025年硕士导师双选带教计划',page=page,subject=subject,degree_level='硕士')
            for subject,page in p['plans']]


def build_profiles():
    rows=[]
    for p in PEOPLE:
        row=roster_row(p['name'],SCHOOL,DEPT,'1006',p['direction'],homepage(p),TEAM)
        row['collected_at']=DATE
        note='按学院导师团队与研究领域归入1006导航；2025年硕士双选带教专业在招生资料中单列。'
        if p['name']=='黄熙':note+='该年带教计划对应105600中药，不能认定为100601年度招生。'
        row['assignment'].update(source_kind='学院导师团队介绍',identity_url=homepage(p),note=note)
        rows.append(row)
    profiles=aggregate(rows)
    for p in profiles:
        for s in p['sources']:
            if s['title']=='公开任职线索核对':s.update(title='学院个人主页',claim='核对姓名、院系、导师身份与研究领域。')
    return profiles


def main():
    profiles=build_profiles()
    pages=[dict(url=url,collected_at=DATE) for url in (TEAM,PLAN,NOTICE)]
    SUPPLEMENT.write_text(json.dumps(dict(profiles=profiles,pages=pages,failures=[],collected_at=DATE),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    data=json.loads(OUT.read_text(encoding='utf8'));key=lambda p:(p['institution'],p['department'],p['name'])
    existing={key(p):p for p in data['profiles']};inserted=[]
    for p in profiles:
        if key(p) not in existing:data['profiles'].append(p);existing[key(p)]=p;inserted.append(p['name'])
        elif any(s['url']==TEAM for s in existing[key(p)]['sources']):existing[key(p)].update(p)
    for page in pages:
        if not any(p['url']==page['url'] for p in data['pages']):data['pages'].append(page)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry=dict(research.source_registry());audited=[]
    for p in PEOPLE:
        profile=next(q for q in catalog.static_catalog()[0] if key(q)==(SCHOOL,DEPT,p['name']))
        ident=profile['id'];reg=registry.setdefault(ident,{})
        reg.update(name=p['name'],institution=SCHOOL,homepage=homepage(p),source_kind='学院个人主页')
        source=dict(url=homepage(p),identity_url=TEAM,source_kind='学院个人主页')
        if not any(s['url']==source['url'] for s in reg.setdefault('sources',[])):reg['sources'].append(source)
        # Reuse the actual HTML fetched during review, never synthesize a page.
        filename=hashlib.sha256(homepage(p).encode()).hexdigest()+'.json'
        reviewed=research.core.DATA_DIR/'thin-depth'/filename
        cache=research.core.DATA_DIR/'research-pages'/filename
        if reviewed.exists() and not cache.exists():
            cache.parent.mkdir(parents=True,exist_ok=True)
            cache.write_bytes(reviewed.read_bytes())
        records=dict(papers=p['papers'],relations=p.get('relations',[]),recruitment=recruitment(p),
                     biography=[record(p['bio'],homepage(p),None,'学院个人主页')],
                     admission_notices=[record('中西医结合学院2026年硕士复试实施细则：中西医结合基础总分500，笔试300、综合200；中药综合考核500分。具体时间与要求见原公告。',NOTICE,2026,'学院复试公告',scope='学院年度规则，不是个人名额')])
        saved=reg.setdefault('records',{});verified=reg.setdefault('verified_pages',[])
        for kind,items in records.items():
            saved.setdefault(kind,[])
            for item in items:
                match=next((r for r in saved[kind] if (r['text'],r['url'])==(item['text'],item['url'])),None)
                if match is None:saved[kind].append(item)
                else:match.update(item)
                if not any(v['url']==item['url'] for v in verified):verified.append(dict(url=item['url'],source_kind=item['source_kind'],fetched_at=DATE))
        audited.append(dict(id=ident,name=p['name'],institution=SCHOOL))
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in audited:
        result=research.enrich(row['id'],True,offline=True)
        assert result['status']=='ready' and len(result['papers'])>=2 and result['recruitment']
        # Directory prose is generated from the current assignment at read time.
        # Do not retain an earlier generated sentence as a source excerpt.
        result['biography']=[r for r in result['biography']
                             if not (r['url']==TEAM and r['text'].startswith('学院导师团队介绍列有'))]
        research.path_for(row['id']).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        row['counts']={k:len(result[k]) for k in ('papers','relations','recruitment','admission_notices')}
    prior=json.loads(AUDIT.read_text(encoding='utf8')) if AUDIT.exists() else {}
    audit=dict(prior,checked_at=DATE,new_profiles=prior.get('new_profiles',len(inserted)),profiles=audited,
               subject_counts={d['name']:d['count'] for d in catalog.disciplines() if d['name'].startswith('1006')},
               limitations=['7位均有论文及2025硕士带教计划；未核实当前个人剩余名额。',
                            '黄熙2025硕士计划只在105600中药，不作为100601招生证据。',
                            '3位导师共7条明确指导关系；吕志刚、陶伟伟、章轶立、成小兰尚未取得足够公开师承证据。',
                            '胡玥学位论文原文已逐页核对；未从论文合著关系推断师承。未收录致谢中的私人关系。',
                            '15条期刊成果含贾立军2篇Letter；书目不等于全文阅读。'])
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(inserted=inserted,profiles=audited,subject_counts=audit['subject_counts']),ensure_ascii=False))


if __name__=='__main__':main()
