"""Fill two empty publication lists via identity-linked TDLI sources."""
import json
from pathlib import Path

import requests

from . import catalog, public_research as research


def main():
    registry = dict(research.source_registry())
    ids = []
    for name in ('梅华林', '王界双'):
        candidates = [p for p in catalog.static_catalog()[0]
                      if p['name'] == name and p['institution'] == '上海交通大学'
                      and p['department'].startswith('物理与天文学院')]
        if len(candidates) != 1:
            raise ValueError('Ambiguous identity')
        p = candidates[0]
        entry = dict(registry[p['id']])
        original = research.cached_fetch(entry['homepage'])
        if name == '梅华林':
            # The Chinese personal page explicitly links this English counterpart.
            if '/en/people/41063' not in original['html']:
                raise ValueError('English counterpart link changed')
            url = 'https://tdli.sjtu.edu.cn/en/people/41063'
            page = research.fetch(url)
            if 'Hualin Mei' not in page['html']:
                raise ValueError('English name not found')
            records = research.parse_page(page['html'], url, name, continuation=True)['papers']
            records = [{**x, 'source_kind': '研究所英文主页', 'fetched_at': page['fetched_at']} for x in records]
        else:
            author_url = 'https://inspirehep.net/authors/1469384'
            if author_url not in original['html'] or '0000-0002-2662-6912' not in original['html']:
                raise ValueError('Official identity links changed')
            response = requests.get('https://inspirehep.net/api/authors/1469384', timeout=(5, 20))
            response.raise_for_status()
            author = response.json()
            if not any(x.get('value') == '0000-0002-2662-6912' for x in author['metadata']['ids']):
                raise ValueError('ORCID mismatch')
            response = requests.get('https://inspirehep.net/api/literature',
                                    params={'q': 'a Jieshuang.Wang.1', 'sort': 'mostrecent', 'size': 20}, timeout=(5, 20))
            response.raise_for_status()
            data = response.json()
            cache = research.core.DATA_DIR / 'depth-sources' / 'inspire-wang-jieshuang.json'
            cache.parent.mkdir(parents=True, exist_ok=True)
            stamp = research.core.now()
            cache.write_text(json.dumps({'fetched_at': stamp, 'author': author, 'literature': data}, ensure_ascii=False), encoding='utf8')
            records = []
            for hit in data['hits']['hits']:
                m = hit['metadata']
                if not any(a.get('record', {}).get('$ref') == 'https://inspirehep.net/api/authors/1469384' for a in m.get('authors', [])):
                    continue
                published = next((x for x in m.get('publication_info', []) if x.get('year') and x.get('journal_title')), None)
                if not published:
                    continue
                doi = next((x['value'] for x in m.get('dois', [])), '')
                names = '; '.join(a['full_name'] for a in m['authors'][:12])
                text = f"{names}. {m['titles'][0]['title']}. {published['journal_title']}, {published['year']}, {published.get('journal_volume', '')}: {published.get('artid', published.get('page_start', ''))}."
                records.append({'text': text, 'url': f"https://inspirehep.net/literature/{hit['id']}",
                                'work_url': 'https://doi.org/' + doi if doi else f"https://inspirehep.net/literature/{hit['id']}",
                                'year': published['year'], 'source_kind': 'INSPIRE书目（校方主页关联作者）',
                                'identity_url': entry['homepage'], 'fetched_at': stamp})
                if len(records) == 5:
                    break
        saved = dict(entry.get('records', {}))
        papers = {x['text']: x for x in saved.get('papers', [])}
        papers.update({x['text']: x for x in records})
        saved['papers'] = list(papers.values())
        entry['records'] = saved
        registry[p['id']] = entry
        ids.append(p['id'])
        print(name, len(records), flush=True)
    research.SOURCE_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    for ident in ids:
        research.enrich(ident, True, offline=True)


if __name__ == '__main__':
    main()
