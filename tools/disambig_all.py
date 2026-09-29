# -*- coding: utf-8 -*-
"""disambig_all.py — 全库同校同名消歧（用院系/方向后缀保证键唯一）

注意：同校同名者的论文无法用「姓名+机构」区分，因此在 notes 中标注，
并让下游可据此提示"该姓名在本校有重名者，论文数据可能混入"。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), 'data', 'raw')

# 院系/单位 -> 简称
ABBR = {
    '微电子研究所': '微电子所', '半导体研究所': '半导体所', '上海微系统与信息技术研究所': '上海微系统所',
    '计算技术研究所': '计算所', '自动化研究所': '自动化所', '上海高等研究院': '上海高研院',
    '电子与信息学部 电子科学与工程学院': '电子科学与工程学院', '电子与信息学部 微电子学院': '微电子学院',
    '电子与信息学部 信息与通信工程学院': '信通学院', '电子与信息学部 计算机科学与技术学院': '计算机学院',
    '仪器科学与技术学院': '仪器学院', '前沿科学技术研究院': '前沿院',
    '北京大学集成电路学院 集成微纳电子系': '集成电路学院', '北京大学深圳研究生院 信息工程学院': '深研院',
    '杭州研究院': '杭州研究院', '集成电路学部（杭州研究院）': '杭州研究院',
    '电子工程学院（雷达信号处理全国重点实验室）': '雷达国重',
    '电子工程学院（本科生院）': '本科生院',
}

total = 0
for d in sorted(os.listdir(RAW)):
    p = os.path.join(RAW, d, f'roster_{d}.json')
    if not os.path.exists(p):
        continue
    with io.open(p, encoding='utf-8') as fh:
        j = json.load(fh)
    # 统一括号
    for f in j['faculty']:
        f['name_cn'] = re.sub(r'[（(]', '（', re.sub(r'[）)]', '）', str(f['name_cn'])))

    groups = {}
    for f in j['faculty']:
        base = re.sub(r'（[^）]*）', '', f['name_cn'])
        groups.setdefault(base, []).append(f)

    for base, arr in groups.items():
        if len(arr) < 2:
            continue
        used = set()
        for f in arr:
            if '（' in f['name_cn']:
                used.add(re.sub(r'^[^（]*（|）$', '', f['name_cn']))
        for f in arr:
            if '（' in f['name_cn']:
                continue
            dep = f.get('department') or ''
            tag = ABBR.get(dep)
            if not tag:
                tag = dep.split()[-1] if dep else ''
            # 同院系内还有重名 → 退化为研究方向首词
            if not tag or tag in used:
                kw = (f.get('research_keywords') or ['方向'])[0]
                tag = kw.split('/')[0].split('、')[0][:8] or '方向'
            used.add(tag)
            f['name_cn'] = f'{base}（{tag}）'
            note = f.get('notes') or ''
            f['notes'] = (note + '；' if note else '') + f'本校有同名者，已标注「{tag}」以区分；两人论文无法自动分离'
            print(f'  {j["school"]} | {base} -> {f["name_cn"]} | {f.get("title")} | {dep}')
            total += 1

    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)

print(f'\n共消歧 {total} 条')
