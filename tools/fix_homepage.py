# -*- coding: utf-8 -*-
"""fix_homepage.py — 规范化名录中的 homepage 字段

问题：部分条目里 homepage 存的是裸域名、"无"、或带中文前缀的文本，
会在报告中生成 `[主页](无)` 这类坏链接。
处理：能救的补 https:// 前缀并抽出 URL；救不了的置 null。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), 'data', 'raw')
URL = re.compile(r'https?://[^\s，。；、）)]+')
fixed = dropped = 0
for d in sorted(os.listdir(RAW)):
    p = os.path.join(RAW, d, f'roster_{d}.json')
    if not os.path.exists(p):
        continue
    with io.open(p, encoding='utf-8') as fh:
        j = json.load(fh)
    changed = False
    for f in j['faculty']:
        h = f.get('homepage')
        if not h or re.match(r'^https?://', h):
            continue
        m = URL.search(h)
        if m:
            f['homepage'] = m.group(0).rstrip('/')
            fixed += 1
            changed = True
            print(f'  抽取URL  {j["school"]} {f["name_cn"]}: {h[:40]!r} -> {f["homepage"][:60]}')
        elif re.match(r'^[a-z0-9.-]+\.[a-z]{2,}(/|$)', h, re.I):
            f['homepage'] = 'https://' + h
            fixed += 1
            changed = True
            print(f'  补协议   {j["school"]} {f["name_cn"]}: {h!r} -> {f["homepage"]}')
        else:
            f['homepage'] = None
            dropped += 1
            changed = True
            print(f'  置空     {j["school"]} {f["name_cn"]}: {h[:30]!r}')
    if changed:
        with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(j, fh, ensure_ascii=False, indent=1)
print(f'\n修正 {fixed} 条，置空 {dropped} 条')
