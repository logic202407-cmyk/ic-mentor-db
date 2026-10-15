"""Collect minimal faculty facts from explicitly selected official directories.

No contact details, evaluations, admission claims or page bodies are published.
Raw HTML stays in the ignored local cache. Department-based direction labels
are identified as such, not presented as individual research statements.
Run: python -m workbench.collect_official [--refresh]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
from . import core

OUT = Path(__file__).parent / "reference" / "official_faculty.json"
CACHE = core.DATA_DIR / "source-cache"
SOURCES = [
    ("ustc_chem", "table_chem", "https://chem.ustc.edu.cn/2476/list.htm", "中国科学技术大学", "化学与材料科学学院化学系", "0703 化学"),
    ("ustc_math", "table_math", "https://math.ustc.edu.cn/_t1477/azcp/listm.htm", "中国科学技术大学", "数学科学学院", "0701 数学"),
    ("ustc_phys", "table_phys", "https://phys.ustc.edu.cn/17657/listm.htm", "中国科学技术大学", "物理学院", "0702 物理学"),
    ("pku_math", "pku_math", "https://math.pku.edu.cn/jsdw/js_20180628175159671361/index4.htm", "北京大学", "数学科学学院", "0701 数学"),
    ("pku_chinese", "pku_chinese", "https://chinese.pku.edu.cn/szdw/zzjs/gdwxjys1/index.htm", "北京大学", "中国语言文学系", "0501 中国语言文学"),
    ("bnu_history", "bnu_history", "https://history.bnu.edu.cn/szdw/index.htm", "北京师范大学", "历史学院", "0602 中国史"),
    ("ecust_chemeng", "ecust", "https://hgxy.ecust.edu.cn/zrjs2/list.htm", "华东理工大学", "化工学院", "0817 化学工程与技术"),
    ("ecnu_econ", "ecnu", "https://sem.ecnu.edu.cn/szdw/list1.htm", "华东师范大学", "经济与管理学院经济学系", "0201 理论经济学"),
    ("ecnu_finance", "ecnu", "https://sem.ecnu.edu.cn/42838/list.htm", "华东师范大学", "经济与管理学院金融学系", "0202 应用经济学"),
    ("ecnu_accounting", "ecnu", "https://sem.ecnu.edu.cn/42841/list.htm", "华东师范大学", "经济与管理学院会计与财务系", "1202 工商管理学"),
    ("ecnu_information", "ecnu", "https://sem.ecnu.edu.cn/42843/list.htm", "华东师范大学", "经济与管理学院信息管理系", "1205 信息资源管理"),
    ("ustc_cs", "cs", "https://cs.ustc.edu.cn/js_23235/list.psp", "中国科学技术大学", "计算机科学与技术学院", "0812 计算机科学与技术"),
]

def compact(value):
    return re.sub(r"\s+", "", value or "")

def valid_name(value):
    return bool(re.fullmatch(r"[\u3400-\u9fff·]{2,8}", value))

def group_direction(value):
    value = re.sub(r"^0?1\s*", "", value).strip()
    first = re.split(r"[，,、；;。]|\s+0?2\s+", value)[0].strip()
    return first[:70] if first else "方向待补"

def record(source, name, direction, link, page, *, department=None, discipline=None, basis="个人研究方向"):
    if not valid_name(name):
        return None
    domain = urlsplit(link).hostname or ""
    # Personal external sites are not copied into the official-homepage field.
    homepage = link if domain.endswith(".edu.cn") and urlsplit(link).scheme in {"http", "https"} and '@V_URL' not in link else page
    return {"name": name, "institution": source[3], "department": department or source[4],
            "discipline": (discipline or source[5])[5:], "first_level_discipline": discipline or source[5],
            "direction_group": group_direction(direction), "interests": core.clean_text(direction, 250),
            "homepage": homepage, "classification_basis": basis,
            "sources": [{"url": page, "title": source[3] + source[4] + "教师名录",
                         "claim": f"名录列出{name}" + (f"；{basis}：{core.clean_text(direction, 250)}。" if direction else "；页面未列研究方向。")}]}

def parse_table(soup, source, page):
    kind=source[1]; result=[]; rank=""
    for tr in soup.select('tr'):
        cells=tr.find_all('td', recursive=False)
        if len(cells)==1:
            rank=compact(cells[0].get_text())
        if len(cells)<4 or rank in {"博士后", "讲师", "特任副研究员"}:
            continue
        name=compact(cells[0].get_text())
        if not valid_name(name) or name in {"姓名", "博导姓名"}:
            continue
        direction=cells[2 if kind=='table_chem' else 1].get_text(' ',strip=True)
        if kind=='table_chem' and '教授' not in cells[1].get_text():
            continue
        a=cells[0].find('a', href=True)
        result.append(record(source,name,direction,urljoin(page,a['href']) if a else page,page))
    return [r for r in result if r]

def parse_pku_math(soup, source, page):
    result=[]
    for nameblock in soup.select('.left_info'):
        a=nameblock.select_one('h3 a[href]')
        right=nameblock.parent.parent.select_one('.right')
        if not a or not right: continue
        fields={compact(p.strong.get_text()).rstrip('：:'):p.i.get_text(' ',strip=True)
                for p in right.select('p') if p.strong and p.i}
        direction=fields.get('研究方向',''); section=fields.get('系','')
        result.append(record(source,compact(a.get_text()),direction,urljoin(page,a['href']),page,
            department=source[4]+(' / '+section if section else ''),
            discipline='0714 统计学' if section=='概率统计系' else None))
    return [r for r in result if r]

def parse_chinese(soup, source, page):
    result=[]
    # Only current-faculty cards, not names mentioned in the unit history.
    heading=soup.select_one('title').get_text(' ',strip=True)
    active=[a.get_text(strip=True) for a in soup.select('a[href="index.htm"]') if '教研室' in a.get_text()]
    direction=active[0] if active else "方向待补"
    for item in soup.select('.listName'):
        a=item.find_parent('a',href=True)
        if a: result.append(record(source,compact(item.get_text()),direction,urljoin(page,a['href']),page,basis="教研室归类"))
    return [r for r in result if r]

def parse_history(soup, source, page):
    result=[]
    # Many names link to one shared placeholder. Keep only personal records.
    names_by_url={}
    for a in soup.select('a.pd-name-card[href]'):
        names_by_url.setdefault(a['href'],set()).add(compact(a.get_text()))
    for block in soup.select('.pd-office-group'):
        heading=block.select_one('.pd-office-banner')
        if not heading:continue
        direction=heading.get_text(strip=True)
        if direction not in {'中国古代史教研室','历史文献学教研室','中国近代史教研室','中国现代史教研室',
                             '世界上古中古史教研室','世界近代史教研室','世界现代史教研室','国际关系史教研室',
                             '史学理论与中国史学史教研室','史学理论与外国史学史教研室'}: continue
        world='世界' in direction or '外国' in direction or '国际关系' in direction
        for a in block.select('a.pd-name-card[href]'):
            if len(names_by_url[a['href']])>1: continue
            result.append(record(source,compact(a.get_text()),direction,a['href'],page,
                          discipline='0603 世界史' if world else None,basis="教研室归类"))
    return [r for r in result if r]

def parse_ecust(soup, source, page):
    result=[]
    for a in soup.select('a[href]'):
        link=urljoin(page,a['href']);name=compact(a.get_text()).strip('*')
        if '/c1270a' not in link or not valid_name(name):continue
        result.append(record(source,name,'',link,page,basis="院系归类，个人方向未收录"))
    return [r for r in result if r]

def parse_cards(soup, source, page):
    rows=[]
    for block in soup.select('.rwjj' if source[1]=='ecnu' else '.news_box'):
        a=block.select_one('.name-pp a[href]' if source[1]=='ecnu' else '.news_title a[href]')
        if not a:continue
        if source[1]=='ecnu':
            title=block.select_one('.kzzd-1')
            if not title or '教授' not in title.get_text():continue
            part=block.select_one('.kzzd-2')
            direction=re.sub(r'^研究方向[：:]','',part.get_text(' ',strip=True)) if part else ''
        else: direction='、'.join(p.get_text(' ',strip=True) for p in block.select('.news_email'))
        rows.append(record(source,compact(a.get_text()),direction,urljoin(page,a['href']),page))
    return [r for r in rows if r]

def collect(refresh=False):
    CACHE.mkdir(parents=True,exist_ok=True)
    checked=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    profiles=[];audit=[];failures=[]; fetched_dates={}
    def fetch(url, alias=None):
        target=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        seed=CACHE/(str(alias)+'.html')
        if not refresh and (target.exists() or (alias and seed.exists())):
            cached=target if target.exists() else seed
            fetched_dates[url]=datetime.fromtimestamp(cached.stat().st_mtime, timezone(timedelta(hours=8))).date().isoformat()
            return cached.read_text(encoding='utf-8')
        time.sleep(.6)
        response=requests.get(url,timeout=25,headers={'User-Agent':'MentorWorkbench/0.3 (faculty directory index)'})
        response.raise_for_status();response.encoding='utf-8'
        if not (urlsplit(response.url).hostname or '').endswith('.edu.cn'):
            raise ValueError('redirected outside official domain')
        target.write_text(response.text,encoding='utf-8')
        fetched_dates[url]=checked
        return response.text
    for source in SOURCES:
        key,kind,base,*_=source
        try:
            initial=fetch(base,key);soup=BeautifulSoup(initial,'html.parser')
            pages={base:initial}
            if kind=='pku_math':
                urls={urljoin(base,a['href']) for a in soup.select('a[href]') if re.fullmatch(r'index\d?\.htm',a['href'])}
            elif kind=='pku_chinese':
                urls={urljoin(base,a['href']) for a in soup.select('a[href]')
                      if '教研室' in a.get_text() and a['href'].endswith('index.htm')}
            elif kind in {'ecnu','cs'}:
                urls={urljoin(base,a['href']) for a in soup.select('a[href]') if a.get_text(strip=True) in {'下一页>>','尾页'}}
            else: urls=set()
            urls = {url for url in urls if urlsplit(url).scheme in {'http', 'https'}
                    and urlsplit(url).hostname == urlsplit(base).hostname}
            for url in sorted(urls-{base})[:15]:
                try: pages[url]=fetch(url)
                except Exception as error: failures.append({'url':url,'error':str(error)[:180]})
            for page,html in pages.items():
                soup=BeautifulSoup(html,'html.parser')
                parser=parse_table if kind.startswith('table_') else {'pku_math':parse_pku_math,'pku_chinese':parse_chinese,'bnu_history':parse_history,'ecust':parse_ecust,'ecnu':parse_cards,'cs':parse_cards}[kind]
                rows=parser(soup,source,page)
                if not rows:failures.append({'url':page,'error':'Parser returned no faculty records; manual review required'})
                for row in rows:row['collected_at']=fetched_dates[page]
                profiles.extend(rows)
                audit.append({'url':page,'records_before_dedup':len(rows),'sha256':hashlib.sha256(html.encode()).hexdigest(),'collected_at':fetched_dates[page]})
                print(source[0],len(rows),page,flush=True)
        except Exception as error:failures.append({'url':base,'error':str(error)[:180]})
    unique={}
    for row in profiles:
        key=(row['institution'],row['department'],row['name'])
        if key in unique:
            old=unique[key]
            for source in row['sources']:
                if source not in old['sources']:old['sources'].append(source)
        else:unique[key]=row
    result={'description':'高校官网教师名录基本信息；非全国完整导师名单，不能据此确认当年招生。一级学科为导航归类。',
            'collected_at':checked,'profiles':list(unique.values()),'pages':audit,'failures':failures}
    # Fail closed: do not replace a good dataset with an empty or partial fetch.
    if failures or not result['profiles']:
        draft=CACHE/'collection-incomplete.json';draft.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError(f'Collection incomplete; inspect {draft}')
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'records':len(unique),'disciplines':dict(Counter(r['first_level_discipline'] for r in unique.values()))},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
    collect(parser.parse_args().refresh)
