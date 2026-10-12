# -*- coding: utf-8 -*-
"""add_colors.py — 给 dump 出的布局补院校颜色，供渲染脚本使用"""
import io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORT = {'清华大学深圳国际研究生院': '清华深研院', '清华大学': '清华', '复旦大学': '复旦', '上海交通大学': '上交',
         '浙江大学': '浙大', '南京大学': '南大', '中国科学技术大学': '中科大', '北京大学': '北大', '东南大学': '东南',
         '西安电子科技大学': '西电', '电子科技大学': '成电', '哈尔滨工业大学': '哈工大', '天津大学': '天大',
         '华中科技大学': '华科', '北京航空航天大学': '北航', '西安交通大学': '西交',
         '中国科学院微电子研究所': '中科院微电子所', '中国科学院半导体研究所': '中科院半导体所',
         '中国科学院上海微系统与信息技术研究所': '中科院上海微系统所', '中国科学院计算技术研究所': '中科院计算所',
         '中国科学院自动化研究所': '中科院自动化所', '中国科学院上海高等研究院': '中科院上海高研院'}
COL = {'清华': '#8b5cf6', '清华深研院': '#a78bfa', '北大': '#ef4444', '复旦': '#3b82f6', '上交': '#06b6d4',
       '浙大': '#10b981', '南大': '#eab308', '中科大': '#ec4899', '东南': '#f97316', '西电': '#6366f1',
       '成电': '#14b8a6', '哈工大': '#a855f7', '天大': '#d97706', '华科': '#e11d48', '北航': '#2563eb',
       '西交': '#16a34a', '中科院微电子所': '#94a3b8', '中科院半导体所': '#a8a29e', '中科院上海微系统所': '#9ca3af',
       '中科院计算所': '#78716c', '中科院自动化所': '#6b7280', '中科院上海高研院': '#d4d4d8'}
view = sys.argv[1] if len(sys.argv) > 1 else 'school'
p = os.path.join(ROOT, 'data/processed/_layout_%s.json' % view)
d = json.load(io.open(p, encoding='utf-8'))
n = json.load(io.open(os.path.join(ROOT, 'data/processed/network_final.json'), encoding='utf-8'))
co = {}
for k in d['pos']:
    sch = n['nodes'].get(k, {}).get('school', '')
    co[k] = COL.get(SHORT.get(sch, sch), '#64748b')
d['colorOf'] = co
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False)
print('已为 %d 个节点补颜色 → %s' % (len(co), p))
