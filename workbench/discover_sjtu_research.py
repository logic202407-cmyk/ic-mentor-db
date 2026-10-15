"""Recover personal pages from four public SJTU school directories.

The read-only POST endpoints and parameters are declared by each directory page.
Match exact names within the same school; ambiguous links are never assigned.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import requests
from . import catalog, public_research as research

SCHOOLS = {
    'see': ('电气工程学院', 'jiaoshiml', {'cat_id':'40','type':2}),
    'cs': ('计算机学院', 'jiaoshiml', {'cat_id':'20','type':1,'zm':'All','zc':'全部','search':''}),
    'sais': ('自动化与感知学院', 'faculty', {'cat_id':'18','type':1,'zm':'All','search':''}),
    'icisee': ('集成电路学院', 'jiaoshiml', {'yjszxfl':'全部','name':'','zm':'All'}),
}


def directory_rows(html, host, section):
    result=set()
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
        link=a['href']; parts=urlsplit(link)
        if parts.scheme!='https' or parts.netloc!=f'{host}.sjtu.edu.cn' or not parts.path.startswith(f'/{section}/'):continue
        label=a.select_one('.name')
        if label:
            # Titles and party posts are separate child nodes, not part of the name.
            name=''.join(label.find_all(string=True,recursive=False))
        else:name=a.get_text()
        name=re.sub(r'\s+','',name)
        if re.fullmatch(r'[\u3400-\u9fff·]{2,10}',name):result.add((name,link))
    return result


def matches(profiles, rows, department):
    eligible=[p for p in profiles if p['institution']=='上海交通大学' and p.get('department','').startswith(department)]
    result=[]
    for p in eligible:
        if sum(q['name']==p['name'] for q in eligible)!=1:continue
        links={url for name,url in rows if name==re.sub(r'\s+','',p['name'])}
        if len(links)==1:result.append((p,next(iter(links))))
    return result


def main():
    cache=research.core.DATA_DIR/'depth-sources';cache.mkdir(parents=True,exist_ok=True)
    registry=dict(research.source_registry());audit=[]
    for host,(department,section,params) in SCHOOLS.items():
        index=f'https://{host}.sjtu.edu.cn/{section}.html'
        endpoint=f'https://{host}.sjtu.edu.cn/active/ajax_teacher_list.html'
        page=research.fetch(index)
        if endpoint not in page['html']:raise ValueError('Directory endpoint changed: '+index)
        rows=set();number=1;last=1
        while number<=last:
            path=cache/f'sjtu-{host}-directory{("-"+str(number)) if number>1 else ""}.json'
            if path.exists():data=json.loads(path.read_text(encoding='utf8'))
            else:
                time.sleep(.4)
                response=requests.post(endpoint,data={**params,'cat_code':section,'page':number},timeout=(5,20))
                response.raise_for_status();data=response.json()
                if not isinstance(data.get('content'),str):raise ValueError('Missing directory content')
                path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
            rows.update(directory_rows(data['content'],host,section))
            total=re.search(r'max_page\s*=\s*"(\d+)"',data.get('page',''))
            if total:last=min(int(total.group(1)),50)
            number+=1
        linked=matches(catalog.static_catalog()[0],rows,department)
        for profile,url in linked:
            existing=registry.get(profile['id'],{})
            # Preserve a separately curated homepage and all manually collected facts.
            if existing.get('homepage') and existing['homepage']!=url:continue
            registry[profile['id']]={**existing,'name':profile['name'],'institution':profile['institution'],
                'homepage':url,'identity_url':index,'source_kind':'学院教师主页','checked_at':research.core.now(),
                'directory_api':{'url':endpoint,'parameters':{**params,'cat_code':section}},
            }
            audit.append({'id':profile['id'],'name':profile['name'],'department':profile['department'],
                'old_homepage':profile.get('homepage'),'homepage':url,'identity_url':index})
        print(json.dumps({'school':department,'directory_people':len(rows),'matched':len(linked)},ensure_ascii=False),flush=True)
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    target=Path(__file__).parent/'reference'/'sjtu_homepage_recovery_20261014.json'
    target.write_text(json.dumps({'checked_at':research.core.now(),'profiles':audit},ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
