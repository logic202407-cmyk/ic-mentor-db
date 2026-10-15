"""Reviewed continuation for thin subjects, 2026-10-15.

The manifest contains named faculty checked against official directories. Publish
only with a concrete bibliography and a readable admissions source. Keep existing
identity keys and local investigation notes. Re-run with python -m workbench.collect_continued_depth.
"""
import hashlib
import json
import re
from bs4 import BeautifulSoup
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE, OUT, aggregate
from .collect_sparse_disciplines import roster_row
from .collect_thin_subject_depth import fetch

DATE='2026-10-15'
MANIFEST=REFERENCE/'continued_depth_candidates_20261015.json'
SUPPLEMENT=REFERENCE/'continued_depth_faculty.json'
AUDIT=REFERENCE/'continued_depth_audit_20261015.json'
SCU_DIRECTORY='https://yz.scu.edu.cn/bszyml/simpleiq/401;0;0;2026;;;'
NOTICES={
    '郑州大学':[
        ('https://sph.zzu.edu.cn/info/1212/5287.htm',2026,'公共卫生学院2026年博士研究生招生“申请-考核”制实施细则'),
    ],
    '四川大学':[
        ('https://jcfy.scu.edu.cn/info/1020/6051.htm',2026,'四川大学华西基础医学与法医学院2026年普通招考博士研究生招生简章'),
        ('https://jcfy.scu.edu.cn/info/1020/6412.htm',2027,'四川大学华西基础医学与法医学院2027年接收推荐免试攻读研究生复试通知'),
    ],
    '辽宁大学':[
        ('https://jjjcxy.lnu.edu.cn/info/1107/1572.htm',2026,'辽宁大学纪检监察学院2026年硕士研究生复试工作实施细则'),
        ('https://jjjcxy.lnu.edu.cn/info/1024/1712.htm',2027,'辽宁大学纪检监察学院2027年接收优秀应届本科毕业生免试攻读研究生复试工作实施细则'),
    ],
    '北京大学':[
        ('https://sph.pku.edu.cn/info/1022/44991.htm',2026,'北京大学公共卫生学院2026年博士研究生“申请-考核”招生细则'),
        ('https://sph.pku.edu.cn/info/1022/45651.htm',2026,'北京大学公共卫生学院2026年“申请-考核”博士研究生招生复试通知'),
    ],
}


def record(text,url,kind,year=None,**extra):
    return dict(text=text,url=url,source_kind=kind,year=year,
                fetched_at=fetch(url)['fetched_at'],**extra)


def prepare(row):
    page=fetch(row['homepage'])
    parsed=research.parse_page(page['html'],page['url'],row['name'])
    records={key:[{**r,'fetched_at':page['fetched_at'],'source_kind':'学院教师主页',
                   'identity_url':row['directory']} for r in parsed[key]]
             for key in ('papers','relations','biography','recruitment')}
    # This page lists concrete works but omits publication years. Do not substitute
    # its page update year for a paper's publication year.
    if row['institution']=='辽宁大学' and row['name']=='张毅':
        text=BeautifulSoup(page['html'],'html.parser').get_text(' ',strip=True)
        section=text.split('代表性论著成果：',1)[1].split('主持或完成的科研项目：',1)[0]
        citations=re.split(r'(?<!\d)\d+\.',section)[1:]
        records['papers']=[record(s.strip(),row['homepage'],'学院教师书目（原页未注明年份）')
                           for s in citations if '《' in s and '》' in s]
        assert len(records['papers'])==6
    records['admission_notices']=[]
    if row['institution']=='四川大学':
        # Names belong to a major-level pool; repeated “同上” rows do not
        # establish an individual supervisor's research direction or quota.
        soup=BeautifulSoup(fetch(SCU_DIRECTORY)['html'],'html.parser')
        major=''
        for tr in soup.select('tr'):
            heading=tr.find('h4')
            if heading:
                major=heading.get_text(' ',strip=True)
            cells=tr.find_all('td',recursive=False)
            if major and len(cells)>=2 and row['name'] in cells[1].get_text(' ',strip=True).split():
                records['recruitment'].append(record(
                    f"2026年四川大学博士招生专业目录在基础医学与法医学院的{major}专业导师名单中列有{row['name']}。目录按专业共用导师名单，未列个人招生名额；这是2026年度记录。",
                    SCU_DIRECTORY,'学校年度博士招生目录',2026,scope='实名年度名录，非个人名额'))
    for url,year,title in NOTICES[row['institution']]:
        notice=fetch(url)
        body=BeautifulSoup(notice['html'],'html.parser').get_text(' ',strip=True)
        assert len(body)>150 and str(year) in body and ('招生' in body or '研究生' in body),url
        records['admission_notices'].append(record(title,url,'院系招生公告',year,scope='院系公告，不代表个人名额'))
    assert records['papers'] and records['admission_notices'],row['name']
    # Qualifying job titles are identity evidence, never lineage or a yearly quota.
    records['biography'].insert(0,record(
        f"{row['institution']}{row['department']}的公开师资页面列有{row['name']}。",row['homepage'],'学院教师主页'))
    return {**row,'records':records}


def main():
    candidates=json.loads(MANIFEST.read_text(encoding='utf8'))
    before={d['name']:d['count'] for d in catalog.disciplines()}
    old_audit=json.loads(AUDIT.read_text(encoding='utf8')) if AUDIT.exists() else {}
    # Finish source verification before mutating the published catalog.
    prepared=[prepare(row) for row in candidates]
    rows=[]
    for p in prepared:
        row=roster_row(p['name'],p['institution'],p['department'],p['code'],p['direction'],p['homepage'],p['directory'])
        row['collected_at']=DATE
        rows.append(row)
    supplement={'profiles':aggregate(rows),'pages':[{'url':u,'collected_at':DATE}
        for u in sorted({p['directory'] for p in prepared})],'failures':[],'collected_at':DATE}
    current=json.loads(OUT.read_text(encoding='utf8'))
    by_key={(p['institution'],p['department'],p['name']):p for p in current['profiles']}
    new=0
    for p in supplement['profiles']:
        key=(p['institution'],p['department'],p['name'])
        if key not in by_key:
            current['profiles'].append(p);by_key[key]=p;new+=1
        else:
            for field in ('discipline_assignments','sources'):
                for item in p[field]:
                    if item not in by_key[key][field]:by_key[key][field].append(item)
    for page in supplement['pages']:
        if not any(p['url']==page['url'] for p in current['pages']):current['pages'].append(page)
    SUPPLEMENT.write_text(json.dumps(supplement,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    OUT.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry=dict(research.source_registry());ids=[]
    cache=research.core.DATA_DIR/'research-pages';cache.mkdir(parents=True,exist_ok=True)
    for row in prepared:
        p=next(p for p in catalog.static_catalog()[0] if all(p[k]==row[k] for k in ('name','institution','department')))
        reg=dict(registry.get(p['id'],{}))
        reg.update(name=p['name'],institution=p['institution'],homepage=row['homepage'],records=row['records'],
            sources=[{'url':row['homepage'],'identity_url':row['directory'],'source_kind':'学院教师主页'}])
        urls={row['homepage']}|{r['url'] for values in row['records'].values() for r in values}
        reg['verified_pages']=[{'url':u,'fetched_at':fetch(u)['fetched_at'],'source_kind':'高校公开资料'} for u in sorted(urls)]
        registry[p['id']]=reg;ids.append(p['id'])
        for url in urls:
            (cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')).write_text(json.dumps(fetch(url),ensure_ascii=False),encoding='utf8')
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    records=[]
    for ident in ids:
        data=research.enrich(ident,True,offline=True);p=catalog.entry_by_id(ident)
        assert data['papers'] and data['admission_notices'],ident
        records.append({'id':ident,'name':p['name'],'institution':p['institution'],
                        **{k:len(data[k]) for k in ('papers','relations','recruitment','admission_notices')}})
    audit={'date':DATE,'new_profiles':old_audit.get('new_profiles',new),'before':old_audit.get('before',before),
           'after':{d['name']:d['count'] for d in catalog.disciplines()},'records':records,
           'limits':['未公开的师承仍为空；导师称谓不当作师承。','院系招生公告不表示个人年度名额。',
                     '郑大荣休名单存在冲突的李文杰、田庆丰未新增；社会医学方向苗豫东留待单独核对。',
                     '郑大2026博士专业目录附件要求验证码，未读取附件，不据此填写个人年度招生。']}
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'new':audit['new_profiles'],'processed':len(records),'totals':{k:sum(r[k] for r in records)
        for k in ('papers','relations','recruitment','admission_notices')}},ensure_ascii=False))


if __name__=='__main__':main()
