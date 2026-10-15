"""Add source-linked faculty to thinly covered disciplines without replacing IDs."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from . import catalog, public_research as research
from .collect_discipline_catalog import CODES, REFERENCE, OUT, aggregate


def clean_direction(value):
    text=BeautifulSoup(value or '', 'html.parser').get_text(' ',strip=True)
    text=re.split(r'欢迎|承担国家|（学术网页|\n',text,maxsplit=1)[0]
    return re.sub(r'\s+',' ',text).strip(' “”。;；') or '方向待补'


def roster_row(name, school, department, code, direction, homepage, source):
    if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}', name):
        raise ValueError('Unexpected name: ' + name)
    return {'name': name, 'institution': school, 'department': department, 'homepage': homepage,
            'collected_at': '2026-10-14', 'assignment': {
                'first_level_discipline': CODES[code], 'subject': code + '00 ' + CODES[code][5:],
                'direction': clean_direction(direction), 'year': None, 'degree_level': '',
                'url': source, 'record_kind': 'faculty_directory', 'source_kind': '学院在职教师名录',
                'classification_basis': '按公开院系名录和研究领域归入学科导航；不代替招生专业认定',
                'note': '按院系与研究领域归入学科导航；导师资格、招生专业与名额以当年招生公告为准。'}}


def main():
    audit_path=REFERENCE/'sparse_discipline_audit_20261014.json'
    before = (json.loads(audit_path.read_text(encoding='utf8'))['before'] if audit_path.exists()
              else {x['name']: x['count'] for x in catalog.disciplines()})
    rows = []; pages = []; dynamic = {}
    ruc = 'https://sis.ruc.edu.cn/ch/jzygzw/jxyyjzw/index.htm'
    soup = BeautifulSoup(research.fetch(ruc)['html'], 'html.parser')
    for a in soup.select('a.photoCardItem[name][source]'):
        if a['source'].strip('\u200b ') != '政治学系':
            continue
        rows.append(roster_row(a['name'], '中国人民大学', '国际关系学院·政治学系', '0302',
                               '政治学', urljoin(ruc, a['href']), ruc))
    pages.append({'url': ruc, 'collected_at': '2026-10-14'})

    pku = 'https://archaeology.pku.edu.cn/szdw/jxky1/jys/jsqsdkgjys.htm'
    soup = BeautifulSoup(research.fetch(pku)['html'], 'html.parser')
    indexes = {urljoin(pku, a['href']): a.get_text(strip=True) for a in soup.select('a[href]')
               if a.get_text(strip=True).endswith('教研室') and a['href'].endswith('jys.htm')}
    for index, group in indexes.items():
        soup = BeautifulSoup(research.fetch(index)['html'], 'html.parser')
        for a in soup.select('a[href]'):
            heading = a.select_one('h3 b')
            if not heading or '/info/' not in a['href']:
                continue
            direction = next((dt.find_next_sibling('dd').get_text(' ', strip=True)
                              for dt in a.select('dt') if '研究方向' in dt.get_text() and dt.find_next_sibling('dd')), group)
            rows.append(roster_row(heading.get_text(strip=True), '北京大学', '考古文博学院', '0601',
                                   direction, urljoin(index, a['href']), index))
        pages.append({'url': index, 'collected_at': '2026-10-14'})

    # Annual supervisor table supplies actual subject codes; only the school-internal column is used.
    ustc = 'https://dslx.ustc.edu.cn/?menu=expertlist&year=2026'
    soup = BeautifulSoup(research.fetch(ustc)['html'], 'html.parser'); department = ''
    thin = {name[:4] for name, count in before.items() if count <= 10}
    staff_index = 'https://hsta.ustc.edu.cn/2770/listm.htm'
    staff = BeautifulSoup(research.fetch(staff_index)['html'], 'html.parser')
    homepages = {re.sub(r'\s+', '', a.get_text()): urljoin(staff_index, a['href'])
                 for a in staff.select('a[href]') if re.search(r'/c277[01]a\d+/pagem.htm$', a['href'])}
    for tr in soup.select('tr'):
        if tr.find('table'):
            continue
        heading = tr.select_one('td[colspan="5"][id]')
        if heading:
            department = heading.get_text(strip=True); continue
        cells = tr.find_all('td', recursive=False)
        code_at = next((i for i,c in enumerate(cells) if re.fullmatch(r'\d{6}', c.get_text(strip=True))), None)
        if code_at is None or len(cells) < 4:
            continue
        code = cells[code_at].get_text(strip=True)
        if code[:4] not in thin:
            continue
        subject = cells[code_at+1].get_text(strip=True)
        for a in cells[-2].select('a[href]'):
            name = re.sub(r'\s+', '', a.get_text())
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}', name):
                continue
            row = roster_row(name, '中国科学技术大学', department, code[:4], subject,
                             homepages.get(name, urljoin(ustc, a['href'])), ustc)
            row['assignment'].update(subject=code+' '+subject, year=2026, degree_level='博士',
                                      source_kind='学校招生导师名录', note='2026年校内博士招生导师；不代表剩余名额。')
            row['assignment'].pop('record_kind')
            rows.append(row)
    pages.append({'url': ustc, 'collected_at': '2026-10-14'})

    tj = 'https://upd-caup.tongji.edu.cn/szx/list.htm'
    endpoint = 'https://oa-caup.tongji.edu.cn/ServiceApi/GetTeaInfo?types=2'
    if endpoint not in research.fetch(tj)['html']:
        raise ValueError('Public directory endpoint changed')
    cache = research.core.DATA_DIR / 'depth-sources'
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / 'tongji-planning-directory.json'
    if not path.exists():
        response = requests.post(endpoint, timeout=(5,20)); response.raise_for_status()
        path.write_text(response.text, encoding='utf8')
    for person in json.loads(path.read_text(encoding='utf8')):
        name = person['Name']; user = person['UserName']
        if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}', name) or not re.fullmatch(r'\d+', user):
            continue
        homepage = 'https://upd-caup.tongji.edu.cn/3d/a9/c20527a343465/page.htm?id=' + user
        row = roster_row(name, '同济大学', '建筑与城市规划学院·城市规划系', '0833',
                         person.get('Orientation') or '城乡规划', homepage, tj)
        rows.append(row); dynamic[name] = (user, homepage)
    pages.append({'url': tj, 'collected_at': '2026-10-14'})

    # One person can be listed under multiple institutes in the annual table.
    identity_departments={}
    for row in rows:
        key=(row['institution'],row['name'],row['homepage'])
        original=row['department']
        row['department']=identity_departments.setdefault(key,original)
        if original!=row['department']:row['assignment']['listed_department']=original
    # Reuse only matching department or exact homepage identities.
    existing = catalog.static_catalog()[0]
    for row in rows:
        matches = [p for p in existing if p['institution']==row['institution'] and p['name']==row['name']
                   and (p.get('homepage')==row['homepage'] or p['department'].split('·')[0]==row['department'].split('·')[0])]
        if len(matches)==1:
            row['department']=matches[0]['department']
    supplement = {'profiles': aggregate(rows), 'pages': pages, 'failures': [], 'collected_at': '2026-10-14'}
    for p in supplement['profiles']:
        if all(a.get('record_kind')=='faculty_directory' for a in p['discipline_assignments']):
            p['classification_basis']='按公开院系名录和研究领域归入学科导航；不代替招生专业认定'
    (REFERENCE/'sparse_discipline_faculty.json').write_text(json.dumps(supplement, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    current=json.loads(OUT.read_text(encoding='utf8'))
    by_key={(p['institution'],p['department'],p['name']):p for p in current['profiles']}
    for p in supplement['profiles']:
        key=(p['institution'],p['department'],p['name'])
        if key not in by_key:
            current['profiles'].append(p);by_key[key]=p
        else:
            target=by_key[key]
            for field in ('discipline_assignments','sources'):
                for item in p[field]:
                    if item not in target[field]:target[field].append(item)
            if not target.get('homepage'):target['homepage']=p['homepage']
    for page in pages:
        if not any(p['url']==page['url'] for p in current['pages']):current['pages'].append(page)
    OUT.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry=dict(research.source_registry()); selected=[]
    for row in supplement['profiles']:
        p=next(p for p in catalog.static_catalog()[0] if all(p[k]==row[k] for k in ('institution','department','name')))
        selected.append(p['id'])
        reg=dict(registry.get(p['id'],{}))
        reg.update(name=p['name'],institution=p['institution'])
        if not reg.get('homepage'):
            reg.update(homepage=row['homepage'],identity_url=row['sources'][0]['url'],source_kind='学院教师主页')
        if row['institution']=='同济大学':
            user,homepage=dynamic[p['name']];detail=cache/f'tongji-planning-{user}.json'
            if not detail.exists():
                try:
                    response=requests.post(endpoint+'&username='+user,timeout=(10,20));response.raise_for_status()
                    detail.write_text(response.text,encoding='utf8')
                except requests.RequestException as exc:
                    print('detail unavailable',p['name'],type(exc).__name__,flush=True)
                    registry[p['id']]=reg
                    continue
            data=json.loads(detail.read_text(encoding='utf8'))
            if data.get('Name')!=p['name'] or data.get('UserName')!=user:raise ValueError('Identity mismatch')
            html='<article><h1>'+escape(p['name'])+'</h1>'
            for section in data.get('List') or []:
                label={'学位教育':'教育经历','职业经历':'工作经历','主要成果':'代表性成果'}.get(section['Name'],section['Name'])
                html+='<h2>'+escape(label)+'</h2>'+(section.get('ZhInfo') or '')
            html+='</article>'
            if len(BeautifulSoup(html,'html.parser').get_text())>60:
                facts=research.parse_page(html,homepage,p['name'])
                stamp=research.core.now()
                reg['records']={k:[{**x,'source_kind':'学院公开教师主页','fetched_at':stamp} for x in facts[k]]
                                for k in ('papers','relations','biography','recruitment')}
                reg['verified_pages']=[{'url':homepage,'fetched_at':stamp,'source_kind':'学院公开教师主页'}]
        registry[p['id']]=reg
    research.SOURCE_REGISTRY.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    result={'before':before,'profile_ids':selected,'after':{x['name']:x['count'] for x in catalog.disciplines()}}
    (REFERENCE/'sparse_discipline_audit_20261014.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'profiles':len(selected),'changes':{k:[before.get(k,0),v] for k,v in result['after'].items() if v!=before.get(k,0)}},ensure_ascii=False),flush=True)
    with ThreadPoolExecutor(4) as pool:
        for i,data in enumerate(pool.map(lambda ident:research.enrich(ident,True),selected),1):
            if i%20==0:print('read',i,'/',len(selected),flush=True)


if __name__=='__main__':main()
