"""Import named, dated admission-directory evidence, without inferring quotas."""
import json
import re
from bs4 import BeautifulSoup
from . import catalog, public_research as research


def extract(html, url, profiles, fetched_at):
    soup=BeautifulSoup(html,'html.parser');dept='';result={}
    year=re.search(r'(20\d{2})年.*招生导师',soup.get_text(' ',strip=True))
    if not year:raise ValueError('招生名录缺少明确年份')
    year=int(year.group(1))
    for tr in soup.select('tr'):
        heading=tr.select_one('td[colspan="5"][id]')
        if heading:dept=heading.get_text(strip=True);continue
        cells=tr.find_all('td',recursive=False)
        if len(cells)<4:continue
        code=next((c.get_text(strip=True) for c in cells if re.fullmatch(r'\d{4}[A-Z\d]{2}',c.get_text(strip=True))),None)
        if not code:continue
        idx=next(i for i,c in enumerate(cells) if c.get_text(strip=True)==code)
        subject=cells[idx+1].get_text(strip=True)
        # The last two cells distinguish university staff from external supervisors.
        for a in cells[-2].select('a[href]'):
            name=re.sub(r'\s+','',a.get_text())
            matches=[p for p in profiles if p['name']==name and p['institution']=='中国科学技术大学'
                     and p.get('department','').startswith(dept)]
            if len(matches)!=1:continue
            p=matches[0];entry=result.setdefault(p['id'],{'profile':p,'link':research.urljoin(url,a['href']),'records':[]})
            entry['records'].append({'text':f'{year} 年博士招生导师名录：{dept}，{code} {subject}，列有{name}。名录未注明个人剩余名额。',
                'url':url,'year':year,'scope':'按姓名和院系核对的年度招生名录','source_kind':'学校招生导师名录','fetched_at':fetched_at})
    return result


def main():
    url='https://dslx.ustc.edu.cn/?menu=expertlist&year=2026'
    page=research.fetch(url);registry=research.source_registry()
    entries=extract(page['html'],url,catalog.static_catalog()[0],page['fetched_at'])
    for key,item in entries.items():
        p=item['profile'];entry=registry.setdefault(key,{'name':p['name'],'institution':p['institution']})
        entry.setdefault('records',{})['recruitment']=item['records']
        if not entry.get('homepage') and (research.load(key) or {}).get('status')!='ready':
            entry['homepage']=item['link'];entry['identity_url']=url
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'named_admission_profiles':len(entries),'records':sum(len(x['records']) for x in entries.values())}))


if __name__=='__main__':main()
