"""Resolve old USTC directory entries against the current faculty portal.

Match name, university and department; save the directory URL as identity evidence.
Run explicitly, never as a consequence of an arbitrary user URL.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from . import catalog, public_research as research

OUT = Path(__file__).parent / 'reference' / 'research_sources.json'


def crawl(start):
    url=start; seen=set(); rows=[]
    while url and url not in seen and len(seen)<35:
        seen.add(url)
        for attempt in range(3):
            try:page=research.fetch(url);break
            except Exception:
                if attempt==2:raise
        soup=BeautifulSoup(page['html'],'html.parser')
        for a in soup.select('a[href]'):
            name=re.sub(r'\s+','',a.get_text())
            link=urljoin(page['url'],a['href'])
            if re.fullmatch(r'[\u3400-\u9fff·]{2,8}',name) and re.search(r'faculty.ustc.edu.cn/[^/]+/zh_CN/',link):
                rows.append((name,link,url))
        nxt=next((a for a in soup.select('a[href]') if a.get_text(strip=True)=='下页'),None)
        url=urljoin(page['url'],nxt['href']) if nxt else None
    return rows


def main():
    index='https://faculty.ustc.edu.cn/unit.jsp?urltype=tree.TreeTempUrl&wbtreeid=1003'
    soup=BeautifulSoup(research.fetch(index)['html'],'html.parser')
    groups={a.get_text(strip=True):urljoin(index,a['href']) for a in soup.select('a[href]')
            if a.get_text(strip=True) in ['数学科学学院','物理学院','化学与材料科学学院']}
    profiles=[p for p in catalog.static_catalog()[0] if p['institution']=='中国科学技术大学']
    registry=json.loads(OUT.read_text(encoding='utf8')) if OUT.exists() else {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={dept:pool.submit(crawl,url) for dept,url in groups.items()}
        for dept,job in jobs.items():
            rows=job.result(); found=0
            for p in profiles:
                if not p.get('department','').startswith(dept):continue
                matches={(link,source) for name,link,source in rows if name==p['name']}
                links={link for link,_ in matches}
                if len(links)!=1:continue
                link,source=sorted(matches)[0]
                candidate={'name':p['name'],'institution':p['institution'],
                    'homepage':link,'identity_url':source,'source_kind':'高校教师主页',
                    'checked_at':research.core.now()}
                # Preserve manually reviewed replacements, external sources and records.
                entry=registry.setdefault(p['id'],{})
                for key,value in candidate.items():entry.setdefault(key,value)
                found+=1
            print(json.dumps({'department':dept,'entries':len(rows),'matched':found}),flush=True)
            OUT.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf8')
    OUT.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
