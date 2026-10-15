"""Reproduce additions for the 31 disciplines left empty after the first expansion.

Only registered public pages are read. Manually checked PDF rows are stored in
reference/gap_catalog_manual.json; cached source pages stay outside the repository.
"""
from pathlib import Path
import hashlib
import json
import re
import requests
from bs4 import BeautifulSoup
from .collect_discipline_catalog import CODES, aggregate, clean, REFERENCE
from . import core

CACHE = core.DATA_DIR / 'gap-sources'
SOURCES = {
    'ams': ('https://yz.chsi.com.cn/sch/viewZszc--infoId-3417667180,categoryId-10462731,schId-367817,mindex-12.dhtml', '军事科学院', '硕士'),
    'smmu': ('https://ao.smmu.edu.cn/2025/0930/c428a4929/page.htm', '海军军医大学', '硕士'),
    'ucass': ('https://shymzxy.ucass.edu.cn/info/1032/5881.htm', '中国社会科学院大学', '博士'),
}
TARGETS = set('0304 0306 0307 0308 0806 0819 0820 0821 0822 0823 0826 0829 0837 0838 0907 0910 1009 1011 1012 1101 1102 1103 1104 1105 1106 1107 1108 1109 1110 1111 1407'.split())

def expand_table(table):
    """Expand row/column spans; never infer teacher columns from plain text."""
    grid = {}; output=[]
    for ri,tr in enumerate(table.find_all('tr')):
        col=0
        for cell in tr.find_all(['td','th'],recursive=False):
            while (ri,col) in grid: col+=1
            for dr in range(int(cell.get('rowspan',1))):
                for dc in range(int(cell.get('colspan',1))):
                    grid[ri+dr,col+dc]=clean(cell.get_text(' ',strip=True))
            col+=int(cell.get('colspan',1))
        columns=[c for r,c in grid if r==ri]
        output.append([grid.get((ri,c),'') for c in range(max(columns,default=-1)+1)])
    return output

def names(text):
    # A space within a two-character Chinese name is typography, not a separator.
    for part in re.split('[、,，;；]',text):
        name=re.sub(r'\s+','',part)
        if re.fullmatch(r'[\u3400-\u9fff·]{2,8}',name) and name not in {'导师组','不区分导师','指导导师','导师姓名'}:
            yield name

def parse_html(key,html):
    url,institution,level=SOURCES[key]
    soup=BeautifulSoup(html,'html.parser');result=[]
    header='导师姓名' if key=='ucass' else ('指导导师' if key=='ams' else '导师')
    tables=[t for t in soup.find_all('table') if any(clean(c.get_text())==header for c in t.find_all(['th','td']))]
    if len(tables)!=1:raise ValueError(f'{key}: expected one faculty table')
    for cells in expand_table(tables[0]):
        if key=='ucass':
            if len(cells)!=9:continue
            department='社会与民族学院';subject,direction,teachers=cells[0],cells[3],cells[4]
        else:
            if len(cells)!=(7 if key=='ams' else 5):continue
            department,subject,direction,teachers=cells[:4]
        code=re.match(r'^(\d{4}[0-9A-Z]{2})\s*(.*)',subject)
        if not code or code[1][:4] not in TARGETS:continue
        subject=code[1]+' '+re.sub(r'\(\d+\)$','',code[2]).strip()
        direction=re.sub(r'^\d{2}\s*','',direction)
        department=re.sub(r'^\d{3}\s*','',department)
        note=''
        if key=='ams':
            note=('军队计划；不面向教育部计划无军籍地方考生。' if cells[5]=='√' and cells[6]!='√'
                  else '招生对象须符合该目录所列军队计划或教育部计划条件。')
        if key=='smmu' and subject[:4]=='1107':note='军事学学科；须按简章核对军队计划报考资格。'
        for name in names(teachers):
            result.append({'name':name,'institution':institution,'department':department,'homepage':'','collected_at':'2026-10-14',
                           'assignment':{'first_level_discipline':CODES[subject[:4]],'subject':subject,'direction':direction,
                                         'year':2026,'degree_level':level,'url':url,'note':note}})
    if not result:raise ValueError(f'{key}: no target faculty rows')
    return result

def collect():
    CACHE.mkdir(parents=True,exist_ok=True);rows=[];pages=[]
    for key,(url,institution,level) in SOURCES.items():
        path=CACHE/(key+'.html')
        if not path.exists():
            r=requests.get(url,timeout=(8,30));r.raise_for_status();path.write_text(r.content.decode('utf8'),encoding='utf8')
        html=path.read_text(encoding='utf8');found=parse_html(key,html);rows.extend(found)
        pages.append({'url':url,'institution':institution,'collected_at':'2026-10-14','sha256':hashlib.sha256(html.encode()).hexdigest(),'records_before_dedup':len(found)})
    manual=json.loads((REFERENCE/'gap_catalog_manual.json').read_text(encoding='utf8'))
    for batch in manual['batches']:
        for row in batch['rows']:
            subject=row.get('subject',batch.get('subject'));code=subject[:4]
            assert code in CODES and code in TARGETS
            a={'first_level_discipline':CODES[code],'subject':subject,'direction':row['direction'],
               'year':batch.get('year'),'degree_level':batch.get('degree_level','博士'),
               'url':row.get('url',batch['url']),'note':row.get('note',batch.get('note',''))}
            if batch.get('record_kind'):a['record_kind']=batch['record_kind']
            for field in ('source_kind','evidence_level','identity_url'):
                if batch.get(field):a[field]=batch[field]
            for name in row['names']:
                if name in {'导师组','不区分导师','指导导师','指导教师','导师姓名','教师姓名'}:
                    raise ValueError(f'Unexpected faculty header: {name}')
                rows.append({'name':name,'institution':batch['institution'],'department':row.get('department',batch.get('department','')),
                             'homepage':row.get('homepages',{}).get(name,''),'assignment':a,'collected_at':'2026-10-14'})
        pages.append({k:v for k,v in batch.items() if k!='rows'}|{'collected_at':'2026-10-14'})
    profiles=aggregate(rows)
    result={'description':'对前轮31个空白学科逐项补充的实名导师；区分年度招生目录与无年份导师名录。',
            'collected_at':'2026-10-14','profiles':profiles,'pages':pages,'failures':[]}
    out=REFERENCE/'gap_admission_faculty.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    subjects={a['first_level_discipline'][:4] for p in profiles for a in p['discipline_assignments']}
    print(json.dumps({'profiles':len(profiles),'covered_gaps':len(subjects),'remaining':sorted(TARGETS-subjects)},ensure_ascii=False))

if __name__=='__main__':collect()
