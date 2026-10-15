"""Attribute rows in registered university publication tables, not entire pages."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
from . import catalog, public_research as research

SOURCES={
    'shisu2024':'https://info.shisu.edu.cn/a9/5a/c11a43354/page.htm',
    'shisu2023':'https://info.shisu.edu.cn/a2/8a/c11a41610/page.htm',
}


def parse(html, url, profiles):
    people=defaultdict(list)
    for p in profiles:people[p['name']].append(p)
    result=defaultdict(list)
    for table in BeautifulSoup(html,'html.parser').find_all('table'):
        columns=None
        for tr in table.find_all('tr'):
            cells=[re.sub(r'\s+',' ',c.get_text(' ',strip=True)).strip() for c in tr.find_all(['td','th'],recursive=False)]
            if '论文题目' in cells:
                columns=cells;continue
            if not columns or len(cells)!=len(columns):continue
            row=dict(zip(columns,cells))
            date=row.get('发表/出版时间',row.get('发表时间',''))
            if not re.match(r'^20\d{2}',date):continue
            authors=row.get('所有作者',row.get('作者',''))
            # The source distinguishes external authors and students. Neither may
            # be mapped to a faculty record merely because the Chinese name matches.
            names=[n.strip() for n in re.split('[,，、;；]',authors) if not re.search(r'[（(](?:外|学)[）)]',n)]
            for name in names:
                if len(people[name])!=1:continue
                p=people[name][0]
                title=row['论文题目'];venue=row.get('发表刊物/论文集/会议名称',row.get('发表刊物',''))
                result[p['id']].append({'text':f'{authors}：《{title}》，{venue}，{date}。',
                    'title':title,'authors':authors,'venue':venue,'url':url,'year':int(date[:4]),
                    'source_kind':'学校年度论文成果表（按作者列匹配）',
                    'identity_url':p['discipline_assignments'][0]['url'],'fetched_at':research.core.now()})
    return dict(result)


def collect():
    profiles=[p for p in catalog.static_catalog()[0] if p['institution']=='上海外国语大学']
    cache=research.core.DATA_DIR/'depth-sources';cache.mkdir(parents=True,exist_ok=True)
    registry=json.loads(research.SOURCE_REGISTRY.read_text(encoding='utf8'));pages=[]
    for key,url in SOURCES.items():
        path=cache/(key+'.html')
        if not path.exists():
            r=requests.get(url,timeout=(5,20));r.raise_for_status();path.write_text(r.content.decode('utf8'),encoding='utf8')
        html=path.read_text(encoding='utf8');matched=parse(html,url,profiles)
        pages.append({'url':url,'sha256':hashlib.sha256(html.encode()).hexdigest(),'matched_profiles':len(matched)})
        for p in profiles:
            if p['id'] not in matched:continue
            entry=registry.setdefault(p['id'],{'name':p['name'],'institution':p['institution']})
            papers=entry.setdefault('records',{}).setdefault('papers',[])
            papers[:]=[r for r in papers if r['url']!=url]+matched[p['id']]
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for p in profiles:
        if registry.get(p['id'],{}).get('records'):research.enrich(p['id'],force=True)
    print(json.dumps(pages,ensure_ascii=False))


if __name__=='__main__':collect()
