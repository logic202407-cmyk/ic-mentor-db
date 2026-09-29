# -*- coding: utf-8 -*-
"""prepare_names.py — 读取各校 roster，生成中英文姓名变体（用于 Crossref 作者匹配）

关键点：
1. 多音字姓氏纠错（曾=zeng 而非 ceng，解=xie，单=shan …）；
2. 用 pypinyin 的 heteronym（异读）生成**全部读音组合**作为匹配集合，
   避免"一个字读错 → 整条记录漏检"；
3. 查询用变体只取最可能的前 3 个，匹配集合则全量使用。

输出: E:\\ytm\\mentor-db\\data\\processed\\name_variants.json
"""
import json
import glob
import os
import re
import itertools

from pypinyin import pinyin, Style

# ── 仓库根目录解析（可移植：以本脚本上一级目录为根）──
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


RAW = os.path.join(REPO, 'data', 'raw')
OUT = os.path.join(REPO, 'data', 'processed')
os.makedirs(OUT, exist_ok=True)

# ── 多音字姓氏纠错表（作为姓氏时的正确读音）──
SURNAME_FIX = {
    "曾": "zeng", "解": "xie", "单": "shan", "仇": "qiu", "查": "zha", "区": "ou",
    "华": "hua", "乐": "yue", "朴": "piao", "覃": "qin", "盖": "ge", "繁": "po",
    "种": "chong", "召": "shao", "洗": "xian", "员": "yun", "秘": "bi", "折": "she",
    "过": "guo", "行": "xing", "应": "ying", "重": "chong", "台": "tai", "尉": "yu",
    "长": "zhang", "阚": "kan", "都": "du", "阚": "kan", "宁": "ning", "曲": "qu",
    "哈": "ha", "燕": "yan", "缪": "miao", "句": "gou", "莞": "guan", "迮": "ze",
}

SCHOOL_META = {
    "sigs":  {"name": "清华大学深圳国际研究生院", "query": "Tsinghua University", "include": r"tsinghua", "exclude": None},
    "fudan": {"name": "复旦大学", "query": "Fudan University", "include": r"fudan", "exclude": None},
    "sjtu":  {"name": "上海交通大学", "query": "Shanghai Jiao Tong University", "include": r"shanghai\s*jiao\s*tong|sjtu", "exclude": None},
    "zju":   {"name": "浙江大学", "query": "Zhejiang University", "include": r"zhejiang university", "exclude": r"zhejiang university of (technology|science)"},
    "nju":   {"name": "南京大学", "query": "Nanjing University", "include": r"nanjing university", "exclude": r"nanjing university of"},
    "ustc":  {"name": "中国科学技术大学", "query": "University of Science and Technology of China", "include": r"university of science and technology of china|ustc", "exclude": None},
    "tsinghua": {"name": "清华大学", "query": "Tsinghua University", "include": r"tsinghua", "exclude": r"shenzhen|SIGS|graduate school at shenzhen"},
    "pku":   {"name": "北京大学", "query": "Peking University", "include": r"peking university", "exclude": None},
    "seu":   {"name": "东南大学", "query": "Southeast University", "include": r"southeast university", "exclude": None},
    "xidian": {"name": "西安电子科技大学", "query": "Xidian University", "include": r"xidian", "exclude": None},
    "uestc": {"name": "电子科技大学", "query": "University of Electronic Science and Technology of China", "include": r"university of electronic science and technology of china|uestc", "exclude": None},
    # ── 第二批扩展院校 ──
    "cas":   {"name": "中国科学院", "query": "Chinese Academy of Sciences", "include": r"chinese academy of sciences|institute of microelectronics|institute of semiconductors", "exclude": r"university of chinese academy"},
    "hit":   {"name": "哈尔滨工业大学", "query": "Harbin Institute of Technology", "include": r"harbin institute of technology", "exclude": None},
    "tju":   {"name": "天津大学", "query": "Tianjin University", "include": r"tianjin university", "exclude": r"tianjin university of (technology|science|commerce)"},
    "hust":  {"name": "华中科技大学", "query": "Huazhong University of Science and Technology", "include": r"huazhong university of science and technology", "exclude": None},
    "xjtu":  {"name": "西安交通大学", "query": "Xi'an Jiaotong University", "include": r"xi[\s'’′´‘`]*an\s*jiao\s*tong|xjtu", "exclude": r"liverpool"},
    "buaa":  {"name": "北京航空航天大学", "query": "Beihang University", "include": r"beihang|beijing university of aeronautics", "exclude": None},
}

MAX_COMBOS = 40


def readings(name_cn):
    """返回 [ [读音1,读音2...], ... ]，首个汉字的姓氏读音已纠错并置于首位

    同校同名者会用「姓名（研究所）」消歧，括号内容不参与读音生成。
    """
    name_cn = re.sub(r"[（(][^）)]*[）)]", "", name_cn).strip()
    per_char = []
    for ch in name_cn:
        try:
            rs = pinyin(ch, heteronym=True, style=Style.NORMAL)[0]
        except Exception:
            rs = [ch]
        rs = [r for r in rs if r and r.isascii() and r.isalpha()]
        if not rs:
            rs = [ch.lower()]
        per_char.append(rs)
    if per_char and name_cn[0] in SURNAME_FIX:
        fix = SURNAME_FIX[name_cn[0]]
        rest = [r for r in per_char[0] if r != fix]
        per_char[0] = [fix] + rest
    return per_char


def name_forms(sylls):
    """由音节列表生成英文写法候选（含 given-first / family-first）"""
    forms = []
    family, given = sylls[0], sylls[1:]
    if not given:
        return [family.capitalize()]
    g_join = " ".join(given)
    forms.append(f"{g_join} {family}")           # Songping Mai   （最常见）
    forms.append(f"{family} {g_join}")           # Mai Songping
    forms.append(f"{'-'.join(given)} {family}")  # Song-Ping Mai
    forms.append(f"{family}{''.join(given)}")    # MaiSongping
    if len(given) > 1:
        forms.append(f"{given[0]} {family}")     # Song Mai
    return [re.sub(r"\s+", " ", f).strip() for f in forms]


def build(name_cn, name_en):
    out = []

    def add(s):
        s = re.sub(r"\s+", " ", (s or "").strip())
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)

    if name_en:
        add(name_en)
    if not name_cn:
        return out, out

    # 外文姓名（无汉字）：不能用拼音逐字拆分，直接用原名的词序变体
    if not re.search(r"[\u4e00-\u9fa5]", name_cn):
        base = re.sub(r"[（(][^）)]*[）)]", "", (name_en or name_cn)).strip()
        base = re.sub(r"\s+", " ", base)
        add(base)
        parts = base.split()
        if len(parts) >= 2:
            add(" ".join(parts[1:] + parts[:1]))          # Family Given...
            add(f"{parts[-1]}, {' '.join(parts[:-1])}")   # Family, Given
            if len(parts) >= 3:
                add(f"{parts[-1]} {parts[0]}")            # Family FirstGiven
        out = [x for x in out if x]
        return out, list(dict.fromkeys(out))

    per_char = readings(name_cn)
    combos = list(itertools.product(*per_char))
    # 主读音组合排在最前（每个字的第一个读音）
    primary = tuple(r[0] for r in per_char)
    combos.sort(key=lambda c: (c != primary,))
    combos = combos[:MAX_COMBOS]

    query_forms, match_forms = [], []
    for i, c in enumerate(combos):
        forms = name_forms(list(c))
        if i == 0:
            for f in forms:
                query_forms.append(f)
        for f in forms:
            match_forms.append(f)
    for f in query_forms:
        add(f)
    result_query = list(out)
    match_set = list(dict.fromkeys([*result_query, *match_forms]))
    return result_query, match_set


result = {}
for f in sorted(glob.glob(os.path.join(RAW, "*", "roster_*.json"))):
    if "draft" in os.path.basename(f).lower() or "stage" in os.path.basename(f).lower():
        continue
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        print("  跳过非对象结构:", f)
        continue
    key = data.get("school_key") or os.path.basename(os.path.dirname(f))
    meta = SCHOOL_META.get(key, {})
    people = []
    for fac in data.get("faculty", []):
        name_cn = (fac.get("name_cn") or "").strip()
        if not name_cn:
            continue
        qv, mv = build(name_cn, fac.get("name_en"))
        if not qv:
            continue
        people.append({
            "school_key": key, "school": data.get("school"),
            "name_cn": name_cn, "name_en": fac.get("name_en"),
            "title": fac.get("title"), "department": fac.get("department"),
            "is_phd_advisor": fac.get("is_phd_advisor"),
            "research_keywords": fac.get("research_keywords") or [],
            "homepage": fac.get("homepage"), "email": fac.get("email"), "notes": fac.get("notes"),
            "variants": qv[:4],                       # 查询用（前 4 个）
            "match_variants": mv,                     # 匹配用（全量组合）
        })
    result[key] = {"school": data.get("school"), "school_key": key,
                   "crossref_query": meta.get("query"), "include": meta.get("include"),
                   "exclude": meta.get("exclude"), "people": people}
    print(f"{key:6s} {data.get('school'):22s} people={len(people)}")

with open(os.path.join(OUT, "name_variants.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print("\nsaved name_variants.json ; total people =", sum(len(v["people"]) for v in result.values()))
# 抽查
for k in ("fudan",):
    for p in result[k]["people"][:6]:
        print("  样本:", p["name_cn"], "查询变体:", p["variants"][:3], "匹配数:", len(p["match_variants"]))
