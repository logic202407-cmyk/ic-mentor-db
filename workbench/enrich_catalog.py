"""Read existing, identity-linked personal pages and record actual additions.

No name-only author matching and no arbitrary URLs. Resume skips profiles already
attempted unless --retry is explicitly supplied. Audit snapshots stay local.
"""
import argparse
from collections import defaultdict, Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from . import catalog, public_research as research


def candidates(institutions=(), retry=False):
    groups=defaultdict(deque)
    for p in catalog.static_catalog()[0]:
        if not p.get('admission_catalog') or (institutions and p['institution'] not in institutions):continue
        registered=research.registered_source(p)
        homepage=registered.get('homepage') or p.get('homepage','')
        if not homepage or not research.trusted_url(homepage):continue
        if not registered.get('homepage') and homepage in research.shared_catalog_homepages():continue
        if not retry and research.path_for(p['id']).exists():continue
        groups[(p['institution'],p['department'])].append(p)
    # Interleave departments rather than completing only the first large school.
    result=[]
    while any(groups.values()):
        for group in groups.values():
            if group:result.append(group.popleft())
    return result


def run(institutions=(), limit=0, retry=False):
    profiles=candidates(institutions,retry)
    if limit:profiles=profiles[:limit]
    stamp=research.core.now().replace(':','').replace('+','_')
    audit=research.core.DATA_DIR/'enrichment-runs'/f'{stamp}.json'
    audit.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    def counts(data):
        return {k:len((data or {}).get(k,[])) for k in ('papers','relations','recruitment','biography','admission_notices')}
    before={p['id']:counts(research.load(p['id'])) for p in profiles}
    def save():
        result={'started_at':stamp,'planned':len(profiles),'completed':len(rows),'profiles':rows}
        temporary=audit.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        temporary.replace(audit)
    save()
    print(json.dumps({'planned':len(profiles),'audit':str(audit)},ensure_ascii=False),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(research.enrich,p['id'],True):p for p in profiles}
        for job in as_completed(jobs):
            p=jobs[job]
            try:
                data=job.result()
                rows.append({'id':p['id'],'name':p['name'],'institution':p['institution'],
                             'before':before[p['id']],'after':counts(data),'status':data['status'],
                             'sources':[r['url'] for r in data.get('pages',[])],'errors':data.get('errors',[])})
            except Exception as exc:
                rows.append({'id':p['id'],'name':p['name'],'institution':p['institution'],'error':type(exc).__name__})
            save()
            if len(rows)%20==0:
                print(json.dumps({'completed':len(rows),'planned':len(profiles),
                                  'with_papers':sum(bool(r.get('after',{}).get('papers')) for r in rows)},ensure_ascii=False),flush=True)
    print(json.dumps({'completed':len(rows),'statuses':dict(Counter(r.get('status','error') for r in rows)),
                      'audit':str(audit)},ensure_ascii=False),flush=True)
    return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--institution',action='append',default=[])
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--retry',action='store_true')
    args=parser.parse_args()
    run(args.institution,args.limit,args.retry)
