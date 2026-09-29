# -*- coding: utf-8 -*-
"""fill_name_en.py — 为外文姓名补齐 name_en（去掉括号备注即为英文名）"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), 'data', 'raw')
n = 0
for d in sorted(os.listdir(RAW)):
    p = os.path.join(RAW, d, f'roster_{d}.json')
    if not os.path.exists(p):
        continue
    with io.open(p, encoding='utf-8') as fh:
        j = json.load(fh)
    changed = False
    for f in j['faculty']:
        name = f.get('name_cn') or ''
        if re.search(r'[\u4e00-\u9fa5]', name):
            continue
        if f.get('name_en'):
            continue
        en = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
        en = re.sub(r'\s+', ' ', en)
        if len(en) >= 3:
            f['name_en'] = en
            n += 1
            changed = True
            print(f'  {j["school"]} | {name} -> {en}')
    if changed:
        with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(j, fh, ensure_ascii=False, indent=1)
print(f'\n补齐 {n} 条 name_en')
