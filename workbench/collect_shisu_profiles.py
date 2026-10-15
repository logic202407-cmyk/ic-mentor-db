"""Read public profile bodies from the API used by the institute's own page.

The normal HTML is an empty JavaScript template. Match the official directory's
exact name and ID; refuse member-only or mismatched responses.
"""
import html
import json
from pathlib import Path
import re
import time
import requests
from . import catalog, public_research as research

BASE='https://saggas.shisu.edu.cn'
SECTION='26cd065b-4da2-4881-a7b4-16a601dacce0,7198b0b4-fd7c-49b1-bcd3-bfea7e3cd49d,6a1da6d2-4704-449f-af8a-f53964e067ed'


def public_body(data, name, article_id):
    row=data['Data']
    if row.get('IsOnlyMember') is not False or row.get('IsDelete') is True:
        raise ValueError('Profile is not publicly readable')
    if row.get('Title')!=name or row.get('ID')!=article_id:
        raise ValueError('Profile identity mismatch')
    return '<article><h1>'+html.escape(name)+'</h1>'+row['ContentInfo']+'</article>'


def collect():
    cache=research.core.DATA_DIR/'depth-sources';cache.mkdir(parents=True,exist_ok=True)
    response=requests.get(BASE+'/cms/getarticleslistbysectionid',params={'SectionID':SECTION,'pageSize':100},timeout=(5,20))
    response.raise_for_status();directory=response.json()
    (cache/'shisu-people.json').write_text(json.dumps(directory,ensure_ascii=False),encoding='utf8')
    registry=json.loads(research.SOURCE_REGISTRY.read_text(encoding='utf8'));ids=[];output=[]
    gap=Path(__file__).parent/'reference/gap_catalog_manual.json';manual=json.loads(gap.read_text(encoding='utf8'))
    for p in catalog.static_catalog()[0]:
        if p['institution']!='上海外国语大学':continue
        matches=[x for x in directory['Data']['obj'] if x['Title']==p['name']]
        if len(matches)!=1:continue
        aid=matches[0]['ID']
        if not re.fullmatch(r'[0-9a-f-]{36}',aid):raise ValueError('Unexpected article ID')
        path=cache/('shisu-'+aid+'.json')
        if path.exists():data=json.loads(path.read_text(encoding='utf8'))
        else:
            time.sleep(.4)
            r=requests.get(BASE+'/cms/articlesinfo',params={'ID':aid,'IsGetOperatorInfo':'false'},timeout=(5,20))
            r.raise_for_status();data=r.json();public_body(data,p['name'],aid)
            path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        url=BASE+'/ArticleDetail/ArticleDetail?ArticleId='+aid
        body=public_body(data,p['name'],aid)
        extracted=research.parse_page(body,url,p['name'])
        entry=registry.setdefault(p['id'],{'name':p['name'],'institution':p['institution']})
        entry['homepage']=url
        entry['sources']=[{'url':url,'identity_url':BASE+'/','source_kind':'学院教师主页'}]
        entry['verified_pages']=[{'url':url,'fetched_at':research.core.now(),
                                  'source_kind':'学院教师主页（公开正文接口）'}]
        for key in ('papers','relations','biography','recruitment'):
            rows=entry.setdefault('records',{}).setdefault(key,[])
            rows[:]=[x for x in rows if x['url']!=url]
            rows.extend({**x,'source_kind':'学院教师主页','identity_url':BASE+'/',
                         'fetched_at':research.core.now()} for x in extracted[key])
        for batch in manual['batches']:
            if batch['institution']=='上海外国语大学':
                for row in batch['rows']:
                    if p['name'] in row['names']:row.setdefault('homepages',{})[p['name']]=url
        output.append({'id':p['id'],'name':p['name'],'papers':len(extracted['papers']),
                       'relations':len(extracted['relations']),'url':url});ids.append(p['id'])
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    manual_text=json.dumps(manual,ensure_ascii=False,indent=2)+'\n';gap.write_text(manual_text,encoding='utf8')
    for mid in ids:research.enrich(mid,force=True)
    print(json.dumps(output,ensure_ascii=False),flush=True)


if __name__=='__main__':collect()
