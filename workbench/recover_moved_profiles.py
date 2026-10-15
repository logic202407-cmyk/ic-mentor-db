"""Resolve moved SJTU pages using current public school directories.

Only exact, unique names within the recorded school are matched. The old
catalogue and mentor IDs are preserved; replacements go to the source registry.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from . import catalog, public_research as research
from .discover_sjtu_research import matches


def linked_rows(html, base, pattern):
    rows = set()
    for a in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = urljoin(base, a['href'])
        if urlsplit(url).netloc != urlsplit(base).netloc:
            continue
        if not re.fullmatch(pattern, urlsplit(url).path):
            continue
        label = a.select_one('.name') or a
        name = re.sub(r'\s+', '', label.get_text())
        if re.fullmatch(r'[\u3400-\u9fff·]{2,10}', name):
            rows.add((name, url))
    return rows


def agricultural_rows(html):
    # Public directory embeds the same published entries rendered in its UI.
    found = re.search(r'var\s+letterDataMap\s*=\s*', html)
    if not found:
        raise ValueError('Public faculty directory data not found')
    data, _ = json.JSONDecoder().raw_decode(html[found.end():])
    return {(p['name_cn'], f"https://www.agri.sjtu.edu.cn/faculty/{p['id']}")
            for group in data.values() for p in group
            if p.get('published') == 1 and p.get('status') == 1
            and re.fullmatch(r'[\u3400-\u9fff·]{2,10}', p.get('name_cn', ''))
            and isinstance(p.get('id'), int)}


def main():
    profiles = catalog.static_catalog()[0]
    registry = dict(research.source_registry())
    audit = []
    directories = [
        ('化学化工学院', 'https://scce.sjtu.edu.cn/teachers', r'/teachers/\d+\.html'),
        ('农业与生物学院', 'https://www.agri.sjtu.edu.cn/faculty/directory', None),
        ('浦江国际学院', 'https://gc.sjtu.edu.cn/cn/about/faculty-staff/faculty-directory/', r'/cn/about/faculty-staff/faculty-directory/faculty-detail/\d+/?'),
    ]
    for suffix in ['tdlee-chair-professors', 'distinguished-fellows', 'senior-fellows', 'tenured-fellows', 'tenure-track-fellows']:
        directories.append(('物理与天文学院', f'https://tdli.sjtu.edu.cn/people/fellows-professors/{suffix}', r'/people/\d+/[^/]*'))
    for department, index, pattern in directories:
        page = research.fetch(index)
        rows = agricultural_rows(page['html']) if pattern is None else linked_rows(page['html'], index, pattern)
        linked = matches(profiles, rows, department)
        added = 0
        for p, url in linked:
            old = registry.get(p['id'], {})
            current = research.load(p['id']) or {}
            # This recovery pass targets missing pages only, not curated working ones.
            if current.get('status') == 'ready' or old.get('homepage'):
                continue
            registry[p['id']] = {**old, 'name': p['name'], 'institution': p['institution'],
                                  'homepage': url, 'identity_url': index,
                                  'source_kind': '学院教师主页', 'checked_at': research.core.now()}
            audit.append({'id': p['id'], 'name': p['name'], 'department': p['department'],
                          'old_homepage': p.get('homepage'), 'homepage': url, 'identity_url': index})
            added += 1
        print(json.dumps({'department': department, 'directory': index, 'people': len(rows), 'added': added}, ensure_ascii=False), flush=True)
    research.SOURCE_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    target = Path(__file__).parent / 'reference' / 'moved_profiles_20261014.json'
    if target.exists():
        previous = json.loads(target.read_text(encoding='utf8'))
        combined = {p['id']: p for p in previous.get('profiles', [])}
        combined.update({p['id']: p for p in audit})
        audit = list(combined.values())
    target.write_text(json.dumps({'checked_at': research.core.now(), 'profiles': audit}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
