"""Collect named supervisors from selected public university admission catalogs.

Only academic first-level codes in our navigation are included. Professional
degrees, unnamed groups and unrecognised codes are not silently mapped.
Raw pages remain local. Re-running uses cached pages unless --refresh is given.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from . import core

REFERENCE = Path(__file__).parent / 'reference'
OUT = REFERENCE / 'admission_faculty.json'
CACHE = core.DATA_DIR / 'discipline-pages'
SJTU = 'https://ga.sjtu.edu.cn/zsgl/zsmlgl/zsml_bs.aspx'
BNU = 'https://yz.bnu.edu.cn/content/zyml/2026/bsyx.html'
UCAS = 'https://admission.ucas.ac.cn/info/ZhaoshengZhuangye/30810fbd-9a35-4a03-8991-50c7a2c0c5f9'
CODES = {d['code']: d['code']+' '+d['name'] for d in json.loads((REFERENCE/'first_level_disciplines_2022.json').read_text(encoding='utf8'))['disciplines']}

def clean(text):
    return re.sub(r'\s+', ' ', text or '').strip()

def _soup(html: str):
    """惰性导入 BeautifulSoup：只统计来源数量时不需要 HTML 解析器。

    `report_facts` → `collect_engineering_scale` → 本模块 的导入链会在
    未安装 bs4 的 CI 环境里直接失败（真实发生过），所以把导入放到真正解析时。
    """
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def fetch(url, refresh=False, encoding=None):
    host=urlsplit(url).hostname
    if host not in {'ga.sjtu.edu.cn','yz.bnu.edu.cn','admission.ucas.ac.cn'}:
        raise ValueError('Unregistered catalog host')
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if path.exists() and not refresh:return json.loads(path.read_text(encoding='utf8'))
    time.sleep(.25)
    response=requests.get(url,timeout=(7,30),headers={'User-Agent':'MentorWorkbench/0.4 (academic directory)'})
    response.raise_for_status()
    if urlsplit(response.url).hostname!=host:raise ValueError('Unexpected catalog redirect')
    html=response.content.decode(encoding or 'utf-8')
    data={'url':url,'html':html,'collected_at':datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
          'sha256':hashlib.sha256(response.content).hexdigest()}
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    return data

def teacher_names(cell, page):
    links={re.sub(r'[\s●★*＊#]+','',a.get_text()):urljoin(page,a['href']) for a in cell.select('a[href]')}
    # Split only explicit list separators, not whitespace within two-character names.
    for part in re.split(r'[\n、,，;；]+',cell.get_text('\n',strip=True)):
        name=re.sub(r'[\s●★*＊#]+','',part)
        if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}',name) or name in {'指导教师','导师','导师组','不区分导师','招生导师','待定'}:continue
        link=links.get(name,'')
        if urlsplit(link).scheme not in {'http','https'} or not (urlsplit(link).hostname or '').endswith(('.edu.cn','.ac.cn','.cas.cn')):link=''
        yield name,link

def parse(html, url, institution, department='', kind='bnu', year=2026):
    soup=_soup(html);rows=[];subject='';direction=''
    if kind=='ucas':trs=soup.select('#detail tr')
    elif kind=='bnu':
        tables=[t for t in soup.select('table') if any(clean(th.get_text())=='导师' for th in t.select('th'))]
        trs=[tr for table in tables for tr in table.select('tbody tr')]
    else:trs=[tr for tr in soup.select('tr') if not tr.find('table')
              and len(tr.find_all('td',recursive=False))==5]
    for tr in trs:
        cells=tr.find_all('td',recursive=False)
        if len(cells)<2:continue
        first=clean(cells[0].get_text(' ',strip=True))
        unit=re.match(r'^(\d{3})\s*([^\d].*)',first)
        code=re.match(r'^(\d{4}[0-9A-Z]{2})\s*(.*)',first)
        if unit and kind!='ucas':
            department=re.split(r'[（(]拟招',unit.group(2))[0].strip();subject='';direction='';continue
        if code:
            subject=code.group(1)+' '+code.group(2)
            direction='';continue
        if first and re.match(r'^\d{2}\s*[^\d]',first):
            direction=re.sub(r'^\d{2}\s*','',first)
            direction=re.sub(r'^[（(]全日制[）)]\s*','',direction)
        if not department or not subject or subject[:4] not in CODES or not direction:continue
        for name,homepage in teacher_names(cells[1],url):
            rows.append({'name':name,'institution':institution,'department':department,'homepage':homepage,
                         'assignment':{'first_level_discipline':CODES[subject[:4]],'subject':subject,
                                       'direction':direction,'year':year,'url':url}})
    return rows

def aggregate(rows):
    people={}
    for row in rows:
        key=(row['institution'],row['department'],row['name']);a=row['assignment']
        if key not in people:
            people[key]={'name':row['name'],'institution':row['institution'],'department':row['department'],
                         'discipline':a['first_level_discipline'][5:],'first_level_discipline':a['first_level_discipline'],
                         'direction_group':a['direction'],'interests':a['direction'],'homepage':row['homepage'],
                         'classification_basis':'招生目录专业代码与实名导师对应；方向为目录所列',
                         'discipline_assignments':[],'sources':[],'collected_at':row.get('collected_at','')}
        p=people[key]
        if a not in p['discipline_assignments']:p['discipline_assignments'].append(a)
        if row['homepage'] and not p['homepage']:p['homepage']=row['homepage']
        if not any(s['url']==a['url'] for s in p['sources']):
            directory=a.get('record_kind')=='faculty_directory'
            p['sources'].append({'url':a['url'],'title':f"{row['institution']} · {a.get('source_kind','学校导师名录')}" if directory else f"{row['institution']}{a['year']} 年{a.get('degree_level','博士')}招生目录",
                                 'claim':f"导师名录列出{row['name']}及学科方向；未注明招生年份。" if directory else f"招生目录实名列出{row['name']}；专业、方向和年份见招生记录，不表示仍有名额。"})
        if a.get('record_kind')=='faculty_directory':
            p['classification_basis']=('学科对应来自转载名录，尚未取得学校原始导师页；无当年招生名额依据' if a.get('evidence_level')=='secondary'
                                       else a.get('classification_basis','学校导师名录明确的学科分组；无当年招生名额依据'))
        if a.get('identity_url') and not any(s['url']==a['identity_url'] for s in p['sources']):
            p['sources'].append({'url':a['identity_url'],'title':'公开任职线索核对','claim':'公布的教学成果完成人及单位，用于核对姓名与学校，不证明当前任职、学科归属或招生资格。'})
    return list(people.values())

def collect(refresh=False):
    all_rows=[];pages=[];failures=[]
    def add(data,institution,department='',kind='bnu'):
        rows=parse(data['html'],data['url'],institution,department,kind)
        if not rows:raise ValueError('No named academic supervisors parsed')
        for r in rows:r['collected_at']=data['collected_at']
        all_rows.extend(rows);pages.append({k:v for k,v in data.items() if k!='html'}|{'records_before_dedup':len(rows),'institution':institution,'department':department})
    add(fetch(SJTU,refresh,'gb18030'),'上海交通大学',kind='sjtu')
    index=fetch(BNU,refresh);soup=_soup(index['html'])
    bnu_urls=list(dict.fromkeys(urljoin(BNU,a['href']) for a in soup.select('a[href]') if re.fullmatch(r'bsxx_yxsm-0\d\d\.html',a['href'])))
    def read_one(url):
        try:return fetch(url,refresh)
        except (requests.RequestException,ValueError) as e:return {'url':url,'error':str(e)[:180]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for data in pool.map(read_one,bnu_urls):
            if data.get('error'):failures.append(data);continue
            try:add(data,'北京师范大学')
            except ValueError as e:failures.append({'url':data['url'],'error':str(e)})
    # Cover still-empty subjects with two distinct UCAS institutes when possible.
    existing=json.loads((REFERENCE/'official_faculty.json').read_text(encoding='utf8'))['profiles']
    covered={p['first_level_discipline'][:4] for p in existing}|{r['assignment']['subject'][:4] for r in all_rows}
    index=fetch(UCAS,refresh);soup=_soup(index['html']);choices=defaultdict(dict)
    for tr in soup.select('#detail tr'):
        tds=tr.find_all('td');a=tr.find('a',href=True)
        if len(tds)!=3 or not a:continue
        code=clean(tds[1].get_text())[:4]
        if code in CODES and code not in covered:choices[code][urljoin(UCAS,a['href'])]=clean(a.get_text())
    selected={}
    for code,units in choices.items():
        for url,department in list(units.items())[:2]:selected[url]=department
    with ThreadPoolExecutor(max_workers=3) as pool:
        for data in pool.map(read_one,selected):
            if data.get('error'):failures.append(data);continue
            try:add(data,'中国科学院大学',selected[data['url']],'ucas')
            except ValueError as e:failures.append({'url':data['url'],'error':str(e)})
    for file in ('caas_admission_faculty.json','medical_admission_faculty.json','gap_admission_faculty.json','sparse_discipline_faculty.json','forensic_faculty_supplement.json','thin_depth_faculty.json','thin_reviewed_faculty.json','continued_depth_faculty.json','four_teacher_depth_faculty.json','six_teacher_depth_faculty.json','integrative_depth_faculty.json'):
        path=REFERENCE/file
        if not path.exists():continue
        extra=json.loads(path.read_text(encoding='utf8'))
        if extra.get('failures'):raise ValueError('Incomplete supplement: '+file)
        for profile in extra['profiles']:
            for assignment in profile['discipline_assignments']:
                all_rows.append({**profile,'assignment':assignment})
        pages.extend(extra['pages'])
    profiles=aggregate(all_rows)
    result={'description':'公开硕博招生目录及导师名录中的实名记录；普通名录与年度招生分开，转载条目标明来源和核实范围，非实时名额。',
            'collected_at':max(p['collected_at'] for p in pages),'profiles':profiles,'pages':pages,'failures':failures}
    # Preserve the last published collection when any source fails; review draft first.
    destination=CACHE/'collection-draft.json' if failures else OUT
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    counts=Counter(a for p in profiles for a in {r['first_level_discipline'] for r in p['discipline_assignments']})
    print(json.dumps({'profiles':len(profiles),'pages':len(pages),'disciplines':dict(counts),'failures':failures,'output':str(destination)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');collect(parser.parse_args().refresh)
