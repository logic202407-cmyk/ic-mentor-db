"""Read the CAAS 2026 doctoral catalog's four-column PDF tables.

Optional collector dependency: pdfplumber. No PDF dependency is needed to run
the workbench. Supply the downloaded official PDF as the sole CLI argument.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .collect_discipline_catalog import CODES, REFERENCE, aggregate

URL='https://gri.caas.cn/docs/2025-12/df1559335e1d48e39f1dacdd2e69a146.pdf'
OUT=REFERENCE/'caas_admission_faculty.json'

def parse_tables(pages, checked):
    rows=[];department='';subject=''
    for page_no,tables in enumerate(pages,1):
        for table in tables:
            for cells in table:
                if len(cells)!=4 or cells[0]=='培养单位':continue
                unit,code,direction,names=cells
                if unit:
                    match=re.match(r'^\d{3}\s+([^\n]+)',unit)
                    if not match:raise ValueError('Unrecognised institute cell')
                    department=match.group(1);subject=''
                if code:subject=re.sub(r'\s+','',code)
                if subject[:4] not in CODES or not department or not names or not direction:continue
                if not re.match(r'^\d{4}[\dA-Z]{2}',subject):raise ValueError('Invalid subject code')
                subject_label=subject[:6]+' '+subject[6:]
                direction=re.sub(r'^\d+[.]?','',re.sub(r'\s+','',direction))
                for marked in re.sub(r'\s+','',names).split('、'):
                    name=marked.replace('*','')
                    if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}',name):raise ValueError('Invalid faculty name: '+name)
                    note=''
                    if '**' in marked:note='目录标记 **：2026 年拟录取直博生的接收导师。'
                    elif '*' in marked:note='目录标记 *：2026 年硕博连读推荐（非拟录取）的拟接收导师。'
                    rows.append({'name':name,'institution':'中国农业科学院','department':department,
                                 'homepage':'','collected_at':checked,'assignment':{
                                     'first_level_discipline':CODES[subject[:4]],'subject':subject_label,
                                     'direction':direction,'year':2026,'url':URL+'#page='+str(page_no),'note':note}})
    return rows

def main(path):
    import pdfplumber
    checked=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    with pdfplumber.open(path) as pdf:
        if '2026' not in (pdf.pages[0].extract_text() or ''):raise ValueError('Wrong catalog year')
        rows=parse_tables([p.extract_tables() for p in pdf.pages],checked)
    profiles=aggregate(rows)
    result={'description':'中国农业科学院2026年博士目录；保留姓名星号所代表的招生方式说明。',
            'profiles':profiles,'pages':[{'url':URL,'collected_at':checked,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'records_before_dedup':len(rows)}],'failures':[]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('CAAS profiles:',len(profiles))

if __name__=='__main__':main(sys.argv[1])
