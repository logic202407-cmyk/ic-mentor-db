"""Collect reviewed thin-subject sources before publishing any new identity.

Source directories scope candidates. A new record needs a readable named personal
page and actual bibliography, rather than a faculty name alone.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE,OUT,aggregate
from .collect_sparse_disciplines import roster_row

CACHE=research.core.DATA_DIR/'thin-depth'
MANIFEST=REFERENCE/'thin_depth_candidates.json'
SUPPLEMENT=REFERENCE/'thin_depth_faculty.json'
AUDIT=REFERENCE/'thin_depth_audit_20261014.json'

def fetch(url):
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if path.exists():return json.loads(path.read_text(encoding='utf8'))
    response=requests.get(url,timeout=(8,20));response.raise_for_status()
    response.encoding='utf8'
    result={'url':response.url,'html':response.text,'fetched_at':research.core.now()}
    path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
    return result

def links(url):
    return [(re.sub(r'\s+','',a.get_text()),urljoin(url,a['href']))
            for a in BeautifulSoup(fetch(url)['html'],'html.parser').select('a[href]')]

def discover():
    rows=[]
    def add(name,url,index,school,department,code,notices):
        rows.append({'name':name,'homepage':url,'directory':index,'institution':school,
                     'department':department,'code':code,'admission_index':notices})
    index='https://med.nju.edu.cn/10886/list.htm'
    for name,url in links(index):
        if name!='首页' and re.fullmatch(r'[\u3400-\u9fff]{2,4}',name) and re.search(r'/(?:page|main)\.htm$',url):
            add(name,url,index,'南京大学','医学院·附属口腔医院','1003','https://med.nju.edu.cn/zsxx/list.htm')
    index='https://mks.ecnu.edu.cn/zgdsx/list.htm'
    for label,url in links(index):
        match=re.fullmatch(r'([\u3400-\u9fff]{2,4}?)(?:教授|副教授|讲师|副研究员|研究员|（系主任）)',label)
        if match and '/page.htm' in url:
            add(match[1],url,index,'华东师范大学','马克思主义学院·中共党史党建系','0307','https://mks.ecnu.edu.cn/cyxz/list2.htm')
    index='https://enr.zust.edu.cn/szdui_wu/qgjsygc.htm'
    indexes={index}|{u for n,u in links(index) if re.search(r'/qgjsygc/\d+\.htm$',u)}
    for page in sorted(indexes):
        for name,url in links(page):
            if re.fullmatch(r'[\u3400-\u9fff]{2,4}',name) and '/info/1029/' in url:
                add(name,url,page,'浙江科技大学','环境与资源学院','0822','https://enr.zust.edu.cn/yjsjy1/zsxx.htm')
    for name,url,school,dept in [
        ('杨立邦','https://fxxb.xtu.edu.cn/info/1043/6373.htm','湘潭大学','法学学部'),
        ('李尚翼','https://law.cufe.edu.cn/info/1133/49186.htm','中央财经大学','法学院'),
        ('王喜满','https://jjjcxy.lnu.edu.cn/info/1117/1629.htm','辽宁大学','纪检监察学院'),
    ]:add(name,url,url,school,dept,'0308','https://law.cufe.edu.cn/zsjy/zsxx.htm' if school=='中央财经大学' else '')
    unique={(r['institution'],r['name'],r['homepage']):r for r in rows}
    MANIFEST.write_text(json.dumps(list(unique.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('candidates',len(unique),flush=True)

def notices(url):
    if not url:return []
    page=fetch(url);result={}
    for a in BeautifulSoup(page['html'],'html.parser').select('a[href]'):
        text=re.sub(r'\s+',' ',a.get_text(' ',strip=True));link=urljoin(url,a['href'])
        years=re.findall(r'20\d{2}',text)
        if (urlsplit(link).hostname==urlsplit(url).hostname and years
            and re.search(r'硕士|博士|研究生|推免',text) and re.search(r'招生|招收|复试|申请|推免',text)
            and not re.search(r'名单|公示|录取结果|成绩|本科',text)):
            result[link]={'text':text[:180],'url':link,'year':max(map(int,years)),
                          'scope':'院系公告，不代表个人名额','source_kind':'院系招生栏目',
                          'fetched_at':page.get('fetched_at',research.core.now())}
    return sorted(result.values(),key=lambda r:r['year'],reverse=True)[:5]

def inspect(row):
    try:
        page=fetch(row['homepage']);facts=research.parse_page(page['html'],page['url'],row['name'])
        soup=BeautifulSoup(page['html'],'html.parser');root=soup.select_one('.wp_articlecontent') or soup.select_one('.v_news_content') or soup
        text=root.get_text(' ',strip=True)
        direction=re.search(r'(?:研究方向|研究领域|研究兴趣)\s*[：:]?\s*([^。\n]{5,150})',text)
        direction=re.split(r'联系方式|个人简介|学术兼职|学术研究|期刊论文|著作及|科研获奖|代表[性作]|科研项目|发表论文|主持|教育经历|工作经历',direction[1])[0].strip(' ：:为【】')[:90] if direction else '方向见个人主页'
        stamp=page.get('fetched_at',research.core.now())
        records={k:[{**v,'fetched_at':stamp,'source_kind':'学院教师主页'} for v in facts[k]] for k in ('papers','relations','biography','recruitment')}
        # The page's directory membership and named page provide identity evidence.
        records['biography'].insert(0,{'text':f"{row['institution']}{row['department']}公开师资页面列有{row['name']}；具体资格与任职日期请对照原文。",
                                      'url':row['homepage'],'source_kind':'学院教师主页','fetched_at':stamp,'year':None})
        records['admission_notices']=notices(row.get('admission_index',''))
        selected_notice={
            '华东师范大学':('https://mks.ecnu.edu.cn/ef/47/c2707a716615/page.htm','华东师范大学马克思主义学院2026年接收推免研究生（含直接攻博）预报名通知'),
            '湘潭大学':('https://fxxb.xtu.edu.cn/info/1091/7075.htm','湘潭大学法学学部2026年硕士研究生复试录取工作方案'),
        }.get(row['institution'])
        if selected_notice:
            link,title=selected_notice;notice_page=fetch(link)
            records['admission_notices'].insert(0,{'text':title,'url':link,'year':2026,'scope':'院系公告，不代表个人名额',
                                                   'source_kind':'院系招生公告','fetched_at':notice_page.get('fetched_at',stamp)})
        if row['name']=='李煌' and row['institution']=='南京大学':
            for statement,year in [('1999—2002 年在昆明医学院攻读硕士，导师徐芸。',2002),('2002—2005 年在四川大学华西口腔医学院攻读博士，导师陈扬熙。',2005),('2008—2010 年在南京大学生命科学学院从事博士后研究，导师华子春。',2010)]:
                advisor=statement.split('导师')[1].strip('。')
                if advisor in text:
                    records['relations'].append({'text':statement,'url':row['homepage'],'year':year,'fetched_at':stamp,'source_kind':'学院教师主页'})
        # Manually checked against pp.145 and 150 of the official 2026 catalog.
        # 1002Z2 and 105200 must not be silently rewritten as academic 100300.
        if row['institution']=='南京大学':
            catalog_url='https://yzb.nju.edu.cn/_upload/article/files/a0/4a/de3033964b05bdd212a674c83bdd/11a0b1dd-42aa-4cfb-9879-36ea575d4404.pdf'
            programs=[]
            if row['name'] in ('韩伟','李煌','牟永斌','王翔','闫福华'):programs.append('1002Z2 口腔科学（第145页）')
            if row['name'] in ('韩伟','李煌','牟永斌','王志勇','闫福华'):programs.append('105200 口腔医学专业学位（第150页）')
            if programs:
                statement=f"南京大学2026年博士招生目录列有{row['name']}："+'；'.join(programs)+'。按申请—考核制招生，不代表目前仍有名额。'
                if row['name']=='闫福华':statement+='目录注明联合招生导师为王翔；这是联合招生安排，不是师承关系。'
                records['recruitment'].append({'text':statement,'url':catalog_url,'year':2026,'source_kind':'学校博士招生目录','fetched_at':'2026-10-14'})
        return {**row,'direction':direction,'records':records,'verified_pages':[{'url':row['homepage'],'fetched_at':stamp,'source_kind':'学院教师主页'}]}
    except Exception as exc:return {**row,'error':type(exc).__name__+': '+str(exc)[:100]}

def collect():
    candidates=json.loads(MANIFEST.read_text(encoding='utf8'))
    before={d['name']:d['count'] for d in catalog.disciplines()}
    old_audit=json.loads(AUDIT.read_text(encoding='utf8')) if AUDIT.exists() else {}
    results=list(ThreadPoolExecutor(4).map(inspect,candidates))
    (CACHE/'inspection.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    selected=[p for p in results if not p.get('error') and p['records']['papers']]
    registry=dict(research.source_registry());rows=[]
    for p in selected:
        row=roster_row(p['name'],p['institution'],p['department'],p['code'],p['direction'],p['homepage'],p['directory'])
        existing=[q for q in catalog.static_catalog()[0] if q['name']==p['name'] and q['institution']==p['institution'] and q.get('homepage')==p['homepage']]
        if len(existing)==1:row['department']=existing[0]['department'];p['department']=row['department']
        rows.append(row)
    supplement={'profiles':aggregate(rows),'pages':[{'url':u,'collected_at':'2026-10-14'} for u in sorted({p['directory'] for p in selected})],
                'failures':[],'collected_at':'2026-10-14'}
    SUPPLEMENT.write_text(json.dumps(supplement,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    current=json.loads(OUT.read_text(encoding='utf8'));by_key={(p['institution'],p['department'],p['name']):p for p in current['profiles']}
    for p in supplement['profiles']:
        key=(p['institution'],p['department'],p['name'])
        if key not in by_key:current['profiles'].append(p)
        else:
            own_urls={a['url'] for a in p['discipline_assignments']}
            by_key[key]['discipline_assignments']=[a for a in by_key[key]['discipline_assignments'] if a['url'] not in own_urls]
            by_key[key]['direction_group']=p['direction_group'];by_key[key]['interests']=p['interests']
            for field in ('discipline_assignments','sources'):
                for item in p[field]:
                    if item not in by_key[key][field]:by_key[key][field].append(item)
    for page in supplement['pages']:
        if not any(p['url']==page['url'] for p in current['pages']):current['pages'].append(page)
    OUT.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8');catalog.static_catalog.cache_clear()
    ids=[]
    for row in selected:
        p=next(p for p in catalog.static_catalog()[0] if all(p[k]==row[k] for k in ('institution','department','name')))
        reg=dict(registry.get(p['id'],{}));reg.update(name=p['name'],institution=p['institution'],homepage=row['homepage'])
        reg['records']=row['records'];reg['verified_pages']=row['verified_pages']
        reg['sources']=[{'url':row['homepage'],'identity_url':row['directory'],'source_kind':'学院教师主页'}]
        registry[p['id']]=reg;ids.append(p['id'])
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    page_cache=research.core.DATA_DIR/'research-pages';page_cache.mkdir(parents=True,exist_ok=True)
    for p in selected:
        for url in (p['homepage'],p.get('admission_index','')):
            if not url:continue
            page=fetch(url);page.setdefault('fetched_at',research.core.now())
            (page_cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')).write_text(json.dumps(page,ensure_ascii=False),encoding='utf8')
    for ident in ids:research.enrich(ident,True,offline=True)
    audit={'before':old_audit.get('before',before),'after':{d['name']:d['count'] for d in catalog.disciplines()},'profile_ids':ids,
           'candidates':len(candidates),'published':len(ids),'not_published':[{'name':p['name'],'institution':p['institution'],'homepage':p['homepage'],'reason':p.get('error','尚未提取到具体书目')} for p in results if p not in selected]}
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(audit,ensure_ascii=False),flush=True)

if __name__=='__main__':
    import sys
    if '--discover' in sys.argv:discover()
    else:collect()
