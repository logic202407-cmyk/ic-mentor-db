"""Read identity-checked public sources into source-linked research excerpts.

This is evidence extraction, never automatic certification of admission or lineage.
External pages require a maintained identity bridge; user-entered URLs are excluded.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
from pathlib import Path
from functools import lru_cache
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests
from . import core

VERSION = 2
PARSER_REVISION = 7
LOCK = threading.Lock()
HOST_TIMES = {}
PAGE_LOCKS = {}
PAPER_HEADING = re.compile(r'论文|代表作|代表性文章|代表性著作|代表性成果|学术发表|论著|专著|文章及专著|publications|representative papers|selected papers|journal papers|paper list|^preprints$|^papers$', re.I)
STOP_HEADING = re.compile(r'项目|奖励|获奖|荣誉|社会任职|社会服务|学术服务|学术兼职|学术任职|程序委员会|课程|联系方式|教育|工作经历|招生|专利|teaching|patents|projects|invited talks|AI4Math|visiting|miscellaneous|awards|honors|events|other writings|academic service', re.I)
RELATION = re.compile(r'师从|指导教师[：:]|(?:博士|硕士|博士后|合作|学术)导师[为是：:]|(?:博士|硕士|联合培养).{0,35}导师[：:]|(?:Ph\.?D\.?|postdoctoral).{0,70}(?:advisor|supervisor)|(?:advisor|supervisor)\s*(?::|was|is)|under the supervision of|under the direction of|advised by', re.I)
RECRUIT = re.compile(r'招收.{0,35}(?:硕士|博士|研究生)|招生.{0,12}(?:名额|要求|计划)|欢迎.{0,40}(?:报考|申请|加入)|(?:Ph\.?D\.?|graduate).{0,60}(?:positions|openings|students.{0,15}welcome)|(?:looking for|recruiting).{0,40}(?:students|Ph\.?D)', re.I)
CONTACT = re.compile(r'电话|邮箱|电子邮件|通讯地址|联系地址|办公地点|出生|籍贯|民族|性别|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\bat\b.{0,30}\bdot\b|^(?:office|address|phone|telephone|tel)\s*:', re.I)
SOURCE_REGISTRY = Path(__file__).parent / 'reference' / 'research_sources.json'


def source_registry():
    try:return _read_registry(str(SOURCE_REGISTRY),SOURCE_REGISTRY.stat().st_mtime_ns)
    except (OSError, ValueError):return {}


@lru_cache(maxsize=2)
def _read_registry(path, revision):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def registered_source(profile):
    row=source_registry().get(profile.get('id',''),{})
    return row if row.get('name')==profile['name'] and row.get('institution')==profile.get('institution') else {}


@lru_cache(maxsize=1)
def shared_catalog_homepages():
    from . import catalog
    names={}
    for profile in catalog.static_catalog()[0]:
        if profile.get('homepage'):names.setdefault(profile['homepage'],set()).add(profile['name'])
    return {url for url, people in names.items() if len(people)>1}


def trusted_url(url):
    if official_url(url):return True
    # External sources are exact URLs reviewed against an official identity bridge.
    return any(url == item.get('url') and item.get('identity_url')
               for entry in source_registry().values() for item in entry.get('sources',[]))


def same_person_path(base, link):
    a,b=urlsplit(base),urlsplit(link)
    if a.hostname != b.hostname:return False
    if a.hostname == 'faculty.ustc.edu.cn':
        return a.path.strip('/').split('/')[0] == b.path.strip('/').split('/')[0] and '/zh_CN/' in b.path
    # A nested personal site, never a university-wide sibling page.
    parent=a.path.rsplit('/',1)[0]+'/'
    return parent!='/' and b.path.startswith(parent)


def path_for(mentor_id):
    return core.DATA_DIR / 'public-research' / (hashlib.sha256(mentor_id.encode()).hexdigest()+'.json')


BUNDLE_PATH = Path(__file__).parent / 'reference' / 'research' / 'dossiers.json.gz'
# 打包兜底开关：默认开启，保证 clone 后仍能看到论文与招生记录。
# 测试要验证「没有逐人档案时如何从目录合成」这条路径时把它置 False。
USE_BUNDLE = True
_bundle_cache = None
_bundle_loaded = False


def _bundle():
    """仓库内的档案打包（gzip JSONL）。只在需要时读一次。"""
    global _bundle_cache, _bundle_loaded
    if _bundle_loaded:
        return _bundle_cache
    _bundle_loaded = True
    table = {}
    try:
        with gzip.open(BUNDLE_PATH, 'rt', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                mid = item.get('id')
                if mid:
                    table[mid] = item
    except (OSError, ValueError):
        table = {}
    _bundle_cache = table
    return table


def bundle_size():
    """仓库打包里有多少份档案（诊断用）。"""
    return len(_bundle())


def load(mentor_id):
    data=None
    try:
        data = json.loads(path_for(mentor_id).read_text(encoding='utf-8'))
        if data.get('version') != VERSION:data=None
    except (OSError, ValueError):
        pass
    if data is None and USE_BUNDLE:
        # 本机没有逐人档案（例如刚 clone 的仓库）时，从仓库打包里取。
        # USE_BUNDLE 可关闭：有测试要验证"没有档案时如何从目录合成"，若打包一直兜底，
        # 那条路径就永远走不到，保证会被悄悄绕过。
        # 打包里存的是精简后的关键字段，与逐人文件同构，足以支撑界面展示。
        bundled = _bundle().get(mentor_id)
        if bundled:
            data = dict(bundled)
            data.setdefault('version', VERSION)
            data['bundled'] = True
    return with_catalog_records(mentor_id, data)


def with_catalog_records(mentor_id, data):
    from . import catalog
    profile=catalog.entry_by_id(mentor_id)
    if not profile:return data
    assignments=profile.get('discipline_assignments', [])
    if not assignments:return data
    synthesized=data is None
    if data is None:
        # Discipline assignments exist for legacy rows too, and those carry no
        # collected_at; fall back to an explicit unknown date instead of raising.
        stamp=(profile.get('collected_at') or '').strip()
        data={'version':VERSION,'mentor_id':mentor_id,'status':'catalog',
              'checked_at':(stamp+'T00:00:00+08:00') if stamp else '',
              'collected_at_unknown':not stamp,'papers':[],
              'relations':[],'recruitment':[],'biography':[],'admission_notices':[],
              'admission_links':[],'pages':[],'errors':[]}
    registered=registered_source(profile)
    homepage=registered.get('homepage') or profile.get('homepage','')
    data['needs_enrichment']=bool(synthesized and homepage and trusted_url(homepage) and
        (registered.get('homepage') or homepage not in shared_catalog_homepages()))
    if data.get('status')=='unavailable':data['status']='catalog'
    data['catalog_kind']='faculty_directory' if all(r.get('record_kind')=='faculty_directory' for r in assignments) else 'admissions'
    existing={row['text'] for row in data['recruitment']+data['biography']}
    listed_at=profile.get('collected_at') or ''
    for row in assignments:
        directory=row.get('record_kind')=='faculty_directory'
        # Keyword-assigned legacy rows carry no subject code, so describe them as
        # navigation classification rather than as an admissions-catalogue entry.
        keyword_only=row.get('record_kind')=='legacy_keyword_assignment'
        if keyword_only:
            text=(f"学科归属按公开研究关键词归入「{row['first_level_discipline']}」，"
                  f"用于工学导航；方向：{row.get('direction') or '方向待补'}。"
                  f"不代替所在机构当年的招生专业认定。")
        else:
            text=(f"{row.get('source_kind','学校导师名录')}列有{profile['name']}；学科：{row['first_level_discipline']}；方向：{row['direction']}。未取得当年招生依据。" if directory else
                  f"{row['year']} 年{row.get('degree_level','博士')}招生目录：{profile['department']}，{row.get('source_subject') or row['subject']}；方向：{row['direction']}；列有{profile['name']}。不代表目前仍有名额。")
        if row.get('note'):text+=' '+row['note']
        if text not in existing:
            data['biography' if (directory or keyword_only) else 'recruitment'].append(
                {'text':text,'url':row['url'],'year':row.get('year'),
                 'source_kind':row.get('source_kind','学校导师名录' if directory else '学校招生目录'),
                 'identity_url':row.get('identity_url',''),'fetched_at':listed_at})
            existing.add(text)
    return data


# Universities whose public faculty pages may be read. The explicit list is the
# baseline; domains are also derived at runtime from the source registry, so adding
# a school to ``workbench/sources/`` is enough and no longer needs an edit here.
# (This was a repeated failure mode: cumt, muc, ustb and whu each needed a code
# change before that school's personal pages could be read at all.)
TRUSTED_UNIVERSITY_DOMAINS = (
    'pku.edu.cn','ustc.edu.cn','bnu.edu.cn','ecust.edu.cn','ecnu.edu.cn',
    'tsinghua.edu.cn','sjtu.edu.cn','ruc.edu.cn','fudan.edu.cn','cau.edu.cn',
    'tongji.edu.cn','caas.cn','ucas.ac.cn','ucas.edu.cn',
    'cumt.edu.cn','muc.edu.cn','ustb.edu.cn','whu.edu.cn',
)


@lru_cache(maxsize=1)
def _registrable_domains() -> tuple[str, ...]:
    """Institution domains seen in the source registry (e.g. ``whu.edu.cn``).

    Only entries already curated into ``research_sources.json`` contribute, so this
    does not widen access to arbitrary hosts — it just keeps the allowlist in step
    with the sources the project has actually registered.
    """
    found: set[str] = set()
    for entry in source_registry().values():
        urls = [entry.get('homepage', ''), entry.get('identity_url', '')]
        urls += [s.get('url', '') for s in entry.get('sources', []) if isinstance(s, dict)]
        for url in urls:
            host = urlsplit(url or '').hostname or ''
            if not host or not host.endswith(('.edu.cn', '.ac.cn', '.cn')):
                continue
            parts = host.split('.')
            # Keep the registrable part: <name>.edu.cn / <name>.ac.cn
            for i in range(len(parts) - 2):
                if parts[i + 1] in {'edu', 'ac'} and parts[i + 2] == 'cn':
                    found.add('.'.join(parts[i:i + 3]))
                    break
    return tuple(sorted(found))


def official_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    trusted = TRUSTED_UNIVERSITY_DOMAINS + _registrable_domains()
    return (parsed.scheme in {'http','https'}
            and any(host == root or host.endswith('.'+root) for root in trusted)
            and not parsed.username
            and parsed.port in {None,80,443})


def fetch(url, refresh=False, _depth=0, _visited=()):
    if url in _visited:raise ValueError('页面循环跳转')
    if _depth>4:raise ValueError('页面跳转次数过多')
    page=_fetch_html(url,refresh)
    # Resolve after releasing the page lock, including cross-page redirect cycles.
    if len(page['html'])<1000:
        match=re.search(r"location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",page['html'])
        if match:
            destination=urljoin(page['url'],match.group(1))
            if not trusted_url(destination):raise ValueError('页面跳转到未核对来源')
            return fetch(destination,refresh,_depth+1,(*_visited,url))
    return page


def _fetch_html(url, refresh=False):
    cache = core.DATA_DIR / 'research-pages'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (hashlib.sha256(url.encode()).hexdigest()+'.json')
    with LOCK:
        page_lock = PAGE_LOCKS.setdefault(url, threading.Lock())
    with page_lock:
        if not refresh and target.exists() and time.time()-target.stat().st_mtime < 86400:
            return json.loads(target.read_text(encoding='utf-8'))
        current = url
        for _ in range(5):
            if not trusted_url(current):
                raise ValueError('链接未列入已核对的资料来源')
            host = urlsplit(current).hostname
            addresses = socket.getaddrinfo(host, None)
            # The host's configured proxy DNS uses 198.18/15 for these registered sites.
            # Only the fixed university allowlist may use that mapping, never user URLs.
            def allowed(address):
                address=ipaddress.ip_address(address)
                return address.is_global or address in ipaddress.ip_network('198.18.0.0/15')
            if not addresses or any(not allowed(item[4][0]) for item in addresses):
                raise ValueError('官网地址不可访问')
            with LOCK:
                wait = max(0, HOST_TIMES.get(host,0)-time.monotonic())
                HOST_TIMES[host] = time.monotonic()+wait+0.4
            time.sleep(wait)
            response = requests.get(current, timeout=(5,12), allow_redirects=False,
                                    headers={'User-Agent':'MentorWorkbench/0.4 (academic profile research)'})
            if response.is_redirect:
                current = urljoin(current, response.headers['Location']); continue
            response.raise_for_status()
            if len(response.content) > 3_000_000 or 'html' not in response.headers.get('Content-Type','').lower():
                raise ValueError('页面不是可解析的 HTML')
            try:html=response.content.decode('utf-8-sig')
            except UnicodeDecodeError:
                response.encoding = response.apparent_encoding or 'gb18030'
                html=response.text
            result = {'url':current, 'html':html, 'fetched_at':core.now()}
            target.write_text(json.dumps(result, ensure_ascii=False),encoding='utf-8')
            return result
        raise ValueError('官网跳转次数过多')


def publication_year(text):
    """Ignore page ranges, DOI digits and article numbers when dating a citation."""
    chinese_title='《' in text
    value=re.sub(r'《[^》]*》', '', text)
    value=re.sub(r'https?://\S+|10\.\d{4,9}/\S+', '', value)
    value=re.sub(r'\b((?:19|20)\d{2})-\d{1,2}-\d{1,2}\b',r'\1',value)
    value=re.sub(r'\b\d+\s*[-–—]\s*\d+\b', '', value)
    value=re.sub(r'\b(?:pp?\.|pages?|article(?:\s+(?:no\.?|number))?)\s*:?\s*\d+', '', value, flags=re.I)
    # In journal citations a colon followed by a number normally introduces pages.
    value=re.sub(r'(?<=\d):\s*\d+|(?<=\))\s*:\s*\d+', '', value)
    years=[int(y) for y in re.findall(r'(?<![0-9A-Za-z_.])(?:19|20)\d{2}(?!\d)',value)]
    ceiling=int(core.now()[:4])+1
    valid=[y for y in years if y<=ceiling]
    # Chinese humanities bios often append a later reprint date. The first
    # date outside the title identifies the original publication.
    return (valid[0] if valid else None) if chinese_title else max(valid,default=None)


def cached_fetch(url, refresh=False, _visited=()):
    """Re-read saved source HTML without making a network request."""
    if url in _visited or len(_visited)>4:raise ValueError('页面循环跳转')
    if not trusted_url(url):raise ValueError('链接未列入已核对的资料来源')
    path=core.DATA_DIR/'research-pages'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    page=json.loads(path.read_text(encoding='utf8'))
    if len(page['html'])<1000:
        match=re.search(r"location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",page['html'])
        if match:return cached_fetch(urljoin(page['url'],match.group(1)),_visited=(*_visited,url))
    return page


def parse_page(html, url, name, *, continuation=False):
    soup = BeautifulSoup(html, 'html.parser')
    result = {key:[] for key in ('papers','relations','recruitment','biography','admission_links','follow_links')}
    compact = re.sub(r'\s+', '', soup.get_text())
    if len(compact)<60 or '你访问的主页没有开通' in compact:
        raise ValueError('个人主页尚未开通或没有正文')
    if not continuation and re.sub(r'\s+','',name) not in compact:
        raise ValueError('页面未找到导师姓名，未自动归入档案')
    # Admission navigation is institution-level context, never a person's quota.
    for a in soup.select('a[href]'):
        text = a.get_text(' ',strip=True); link = urljoin(url,a['href'])
        if not trusted_url(link): continue
        personal_tab=same_person_path(url,link) and re.fullmatch(r'科学研究|论文成果|论文发表|招生信息|招生计划|Publications|Selected Papers|Research|Biography|About me',text,re.I)
        if personal_tab and link!=url:result['follow_links'].append(link)
        if official_url(link) and not personal_tab and re.search(r'招生|硕士生招生|博士生招生',text) and not re.search(r'本科|博士后|留学',text) and 2 <= len(text) <= 60:
            result['admission_links'].append({'text':text,'url':link,'scope':'院系招生栏目'})
        if re.fullmatch(r'(?:Publications|Selected Papers|个人主页|个人网站)',text,re.I) and link != url and same_person_path(url,link):
            result['follow_links'].append(link)
    # Several faculty systems wrap the whole article in an ASP.NET form.
    for tag in soup.select('form'):tag.unwrap()
    for tag in soup.select('script,style,nav,header,footer,input,button,select,textarea,.bibtex.hidden'):
        tag.decompose()
    # Site chrome that survives the selectors above. Footer boilerplate is a real
    # source of false records: Wuhan University pages carry an ICP 备案号 line that
    # was previously captured as a publication.
    #
    # Collect the parents FIRST and decompose afterwards. Iterating the strings while
    # decomposing their ancestors invalidates the remaining nodes, and a page with two
    # or more footer matches then raised
    #   AttributeError: 'NavigableString' object has no attribute 'parent'.
    # Pages with a single match never hit it, which is why it survived until a bulk
    # --enrich run reached a two-match page.
    chrome_parents = []
    for text_node in soup.find_all(
            string=re.compile(r'ICP\s*备|公网安备|公安备案|版权所有|技术支持[:：]|工信部备案')):
        parent = text_node.find_parent(['p', 'div', 'li', 'td', 'footer', 'span'])
        if parent is not None:
            chrome_parents.append(parent)
    for parent in chrome_parents:
        if parent.parent is not None:      # not already removed as a descendant
            parent.decompose()
    root = soup.select_one('.wp_articlecontent') or soup.select_one('.v_news_content') or soup.select_one('.bs-page-body') or soup.select_one('article') or soup.body or soup
    # Some faculty templates render tab labels before all panel bodies. Restore
    # each label at its panel so awards/projects cannot inherit a paper heading.
    tabs=root.select('.teacher-menu .teacher-item')
    panels=root.select('.teacher-info-bot-con > .teacher-field')
    if tabs and len(tabs)==len(panels):
        for tab,panel in zip(tabs,panels):
            heading=soup.new_tag('h3');heading.string=tab.get_text(' ',strip=True)
            panel.insert(0,heading)
        for tab in tabs:tab.decompose()
    # Word-exported personal pages often split one citation into title/author/date
    # table cells. Keep each data row together, without merging nested layout tables.
    for table in root.find_all('table'):
        if table.find('table'):continue
        rows=table.find_all('tr')
        if len(rows)<2:continue
        for row in rows:
            cells=row.find_all(['td','th'],recursive=False)
            if len(cells)<2 or any(cell.get('colspan','1')!='1' for cell in cells):continue
            values=[re.sub(r'\s+',' ',c.get_text(' ',strip=True)) for c in cells]
            if any(len(v)>1200 for v in values):continue
            merged=soup.new_tag('p');merged.string=' ; '.join(values);row.replace_with(merged)
    # A soft line break inside a numbered title is not a second citation.
    for paragraph in root.find_all('p'):
        parts=paragraph.get_text('\n',strip=True).splitlines()
        numbered=r'^(?:\d+[.)）、]|\(\d+\))\s*\S'
        if (re.match(numbered,paragraph.get_text(' ',strip=True))
                and sum(bool(re.match(numbered,x.strip())) for x in parts)<=1):
            for br in paragraph.find_all('br'):br.replace_with(' ')
    for br in root.find_all('br'):br.replace_with('␞')
    # Keep paragraph text together even if the site splits each year into spans.
    blocks = root.find_all(['p','li','ul','ol','h1','h2','h3','h4','h5','div','td'])
    lines=[];consumed=set()
    for block in blocks:
        if any(id(parent) in consumed for parent in block.parents):continue
        if block.name=='li' and not block.find(['li','p','div','h1','h2','h3','h4','h5']):consumed.add(id(block))
        elif block.find(['p','li','ul','ol','h1','h2','h3','h4','h5','div','td']): continue
        for part in block.get_text(' ',strip=True).split('␞'):
            text = re.sub(r'\s+',' ',part).strip()
            if text and (not lines or lines[-1] != text): lines.append(text)
    # Numbered titles are sometimes followed by separate author and venue paragraphs.
    joined=[];i=0
    while i<len(lines):
        text=lines[i];end=i+1
        if ('师从' in text and not re.search(r'[。；;]$',text) and i+1<len(lines)
                and re.match(r'^(?:领域|的)?(?:权威|著名)?(?:专家|教授)',lines[i+1])):
            text+=' '+lines[i+1];end=i+2
        if re.match(r'^(?:\d+[.)）、]|\(\d+\))\s*\S',text) and not re.search(r'(?:19|20)\d{2}',text):
            for j in range(i+1,min(i+5,len(lines))):
                nxt=lines[j]
                if re.match(r'^(?:\[\d+\]|\d+[.)）、]|[（(]\d+[)）])',nxt) or CONTACT.search(nxt):break
                author_line=bool(re.fullmatch(r'[A-Za-zÀ-ž\s,.*#;+&\-]+',nxt) and re.search(r'[,;*]',nxt))
                if not author_line and not re.search(r'^(?:with\b|Preprint\b)|arXiv|(?:19|20)\d{2}',nxt,re.I):break
                text+=' '+nxt;end=j+1
                if re.search(r'(?:19|20)\d{2}',nxt):break
        joined.append(text);i=end
    paper_section=bool(root.select_one('.bibliography'));bio_section=False;paper_type=''
    for text in joined:
        if len(text)<180 and re.match(r'^Publications(?:\s|/|$)',text,re.I):
            paper_section=True;paper_type='';continue
        citation_line=bool(re.match(r'^(?:\[\d+\]|\d+[.)、]|[（(]\d+[)）])',text)
                           and re.search(r'《|(?:19|20)\d{2}|doi',text,re.I))
        if len(text) < 55 and not citation_line:
            if re.fullmatch(r'.{0,5}(?:教育经历|教育背景|工作经历|工作简历|学习经历|学术经历).{0,5}',text):bio_section=True
            elif re.fullmatch(r'.{0,5}(?:研究方向|科研项目|主讲课程|代表作|发表论文|获奖情况|联系方式).{0,5}',text):bio_section=False
            if PAPER_HEADING.search(text) and not re.search(r'奖|优秀|指导|课程|项目|学位',text):
                paper_section=True;bio_section=False
                paper_type='预印本' if re.search(r'preprints?|预印本',text,re.I) else ''
                continue
            if STOP_HEADING.search(text) or re.search(r'学术奖励|个人风采',text) or text in ('人才需求','文件共享'): paper_section=False
        # Numbered sections may put an award biography on the heading line.
        if re.match(r'^\d+[.、]\s*(?:学术奖励|个人风采)',text):
            paper_section=False
        # Bilingual faculty pages repeat the same bibliography in the English CV.
        if re.match(r'^Title\s*[:：]?\s*(?:Professor|Associate Professor|Lecturer)?\s*$',text,re.I) and any(re.search(r'[\u3400-\u9fff]',r['text']) for r in result['papers']):
            break
        if CONTACT.search(text):
            # A biography can contain contact/birth details and independent
            # education sentences. Keep only the latter, never the private bits.
            text=''.join(sentence for sentence in re.split(r'(?<=[。；])',text)
                         if not CONTACT.search(sentence)).strip()
            if not text:continue
        def add(kind, value, limit=260):
            if kind=='biography' and re.search(r'博士后科学基金|优秀.{0,8}学位论文',value):
                return
            paper_year=publication_year(value) if kind=='papers' else None
            value=core.clean_text(value,limit)
            if len(value)<12: return
            years=re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)',value)
            year=paper_year if kind=='papers' else (max(map(int,years)) if years else None)
            item={'text':value,'url':url,'year':year}
            if kind=='papers' and paper_type:item['publication_type']=paper_type
            doi=re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+',value)
            if kind=='papers' and doi:item['work_url']='https://doi.org/'+doi.group(0).rstrip('.,;)')
            result[kind].append(item)
        # Preserve the statement and its subject, rather than inventing graph edges.
        for sentence in re.split(r'(?<=[。；])|(?<=\.)\s+(?=I |My |Previously |Currently |Before |He |She )',text):
            third_party=re.match(r'^\[\d+\]\s*([\u3400-\u9fff]{2,4})[，,]',sentence)
            own_relation=not third_party or third_party.group(1)==name
            if own_relation and RELATION.search(sentence) and not re.search(r'竞赛|大赛|比赛|指导教师奖|教学成果|学年奖|担任.{0,50}(?:学术导师|指导老师)|\bstudents?\s+supervisors?\b|(?:博士|硕士)生导师[：:]\s*(?:博士|硕士|研究生|\d)',sentence,re.I):
                if '指导教师' not in sentence or re.search(r'博士|硕士|学位',sentence):
                    match=RELATION.search(sentence)
                    # Keep the named advisor even when the biography paragraph is long.
                    start=max(0,match.start()-130)
                    add('relations',('…' if start else '')+sentence[start:],450)
            if (len(sentence)>22 and RECRUIT.search(sentence)) or re.search(r'(?:博士|硕士|研究生).{0,10}(?:已招满|名额已满|暂停招生|不再招收)',sentence):
                add('recruitment',sentence,320)
        if bio_section and re.search(r'(?:19|20)\d{2}',text) and len(text)>15:
            add('biography',text,240)
        elif re.search(r'(?:19|20)\d{2}',text) and re.search(r'毕业|学位|师从|博士后|教育经历|工作经历|任教|任职',text) and not paper_section:
            for sentence in re.split(r'(?<=。)',text):
                if re.search(r'学位|毕业|博士后|任教|任职',sentence): add('biography',sentence,240)
        numbered_citation=re.match(r'^(?:\[\s*\d+\s*\]|\d+[.)])',text) and re.search(r'\b(?:Journal|Math\.|Phys\.|Nature|Science|Proc\.|Ergodic|Nonlinearity)\b',text)
        long_enough=len(text)>25 or (citation_line and '《' in text and '》' in text and len(text)>12)
        if (paper_section or numbered_citation or re.search(r'\[J\]|doi\s*:?\s*10\.\d{4,9}/',text,re.I)) and long_enough and (re.search(r'(?:19|20)\d{2}|accepted|in press|doi',text,re.I)):
            if not re.search(r'发表.{0,20}\d+\s*(?:篇|余)|主持|科研项目|版权所有|Copyright|优秀.{0,12}教师|教师奖|奖学金|教学奖|^Preprint\s*[,，]|^(?:.{0,8}[，,]\s*)?(?:特聘|长聘|助理|副|讲席)?(?:教授|研究员)[，,。]',text,re.I):
                add('papers',text,450)
    for key,limit in [('papers',12),('relations',5),('recruitment',4),('biography',5),('admission_links',3)]:
        seen=set(); unique=[]
        for row in result[key]:
            token=(row['text'],row['url'])
            if token not in seen:unique.append(row);seen.add(token)
        if key=='papers':unique.sort(key=lambda r:r['year'] or 0,reverse=True)
        if key=='admission_links':unique.sort(key=lambda r: not bool(re.search(r'硕士|博士|研究生',r['text'])))
        result[key]=unique[:limit]
    result['follow_links']=list(dict.fromkeys(result['follow_links']))[:4]
    return result


def admission_notices(url, refresh=False, *, offline=False):
    page=(cached_fetch if offline else fetch)(url,refresh);soup=BeautifulSoup(page['html'],'html.parser');rows=[]
    for a in soup.select('a[href]'):
        text=re.sub(r'\s+',' ',a.get_text(' ',strip=True));link=urljoin(page['url'],a['href'])
        years=re.findall(r'20\d{2}',text)
        if (official_url(link) and years and re.search(r'硕士|博士|研究生|推免',text)
                and re.search(r'招生|招收|复试|录取|推免|申请',text) and len(text)>12
                and not re.search(r'名单|公示|录取结果|成绩|本科',text)):
            rows.append({'text':core.clean_text(text,180),'url':link,'year':max(map(int,years)),
                         'scope':'院系公告，不代表个人名额','fetched_at':page['fetched_at']})
    unique={r['url']:r for r in rows}
    return sorted(unique.values(),key=lambda r:r['year'],reverse=True)[:5]


def enrich(mentor_id, force=False, refresh_pages=False, *, offline=False):
    from . import catalog
    profile=catalog.entry_by_id(mentor_id)
    if not profile: raise ValueError('找不到导师')
    old=load(mentor_id)
    # A synthesized catalog card is not a cached attempt to read a personal page.
    if old and not force and path_for(mentor_id).exists():return old
    result={'version':VERSION,'parser_revision':PARSER_REVISION,'mentor_id':mentor_id,'checked_at':core.now(),
            'status':'ready','papers':[],'relations':[],'recruitment':[],'biography':[],
            'admission_links':[],'admission_notices':[],'pages':[],'errors':[]}
    registered=registered_source(profile)
    homepage=registered.get('homepage') or profile.get('homepage','')
    is_directory = not registered.get('homepage') and (homepage in shared_catalog_homepages() or
        any(s.get('url') == homepage and '名录列出' in s.get('claim','') for s in profile.get('sources',[])))
    if mentor_id.startswith('project-') or not trusted_url(homepage) or is_directory:
        result['status']='unavailable';result['errors']=['暂未找到可确认身份的个人主页']
    else:
        first=next((s for s in registered.get('sources',[]) if s['url']==homepage),None)
        visited=set();queue=[first or {'url':homepage,'source_kind':registered.get('source_kind','高校或研究机构主页')}]
        queue.extend(registered.get('sources',[]))
        while queue and len(visited)<8:
            source=queue.pop(0);link=source['url']
            if link in visited:continue
            visited.add(link)
            try:
                page=(cached_fetch if offline else fetch)(link,refresh_pages)
                # Continuation is only allowed for curated, identity-linked sources
                # or a tab below the already validated personal page path.
                more=parse_page(page['html'],page['url'],profile['name'],
                                continuation=link!=homepage and bool(source.get('identity_url')))
                for key in ('papers','relations','recruitment','biography','admission_links'):
                    seen={re.sub(r'\s+','',r['text']) for r in result[key]}
                    for row in more[key]:
                        if re.sub(r'\s+','',row['text']) not in seen:
                            row['source_kind']=source.get('source_kind','个人主页栏目')
                            row['fetched_at']=page['fetched_at']
                            if source.get('identity_url'):row['identity_url']=source['identity_url']
                            result[key].append(row);seen.add(re.sub(r'\s+','',row['text']))
                result['pages'].append({'url':page['url'],'fetched_at':page['fetched_at'],
                                        'source_kind':source.get('source_kind','个人主页栏目')})
                for follow in more['follow_links']:
                    if follow not in visited and same_person_path(page['url'],follow):
                        queue.append({'url':follow,'identity_url':page['url'],'source_kind':'个人主页栏目'})
            except (requests.RequestException,ValueError,OSError) as exc:
                result['errors'].append('未读到页面：'+link+'（'+type(exc).__name__+'）')
        if not result['pages']:result['status']='unavailable'
        notices={}
        for item in result['admission_links'][:2]:
            try:
                for row in admission_notices(item['url'],refresh_pages,**({'offline':True} if offline else {})):notices[row['url']]=row
            except (requests.RequestException,ValueError,OSError):
                result['errors'].append('院系招生栏目暂时无法读取')
        result['admission_notices']=sorted(notices.values(),key=lambda r:r['year'],reverse=True)[:5]
        # If a source failed, retain only its previous records, with their original dates.
        read_urls={page['url'] for page in result['pages']}
        if old and result['status']=='ready':
            for key in ('papers','relations','recruitment','biography','admission_notices'):
                present={r['text'] for r in result[key]}
                result[key].extend(r for r in old.get(key,[]) if r.get('url') not in read_urls and r['text'] not in present)
        for key in ('papers','admission_notices'):
            result[key].sort(key=lambda r:r.get('year') or 0,reverse=True)
    for key,rows in registered.get('records',{}).items():
        if key in ('papers','relations','recruitment','biography','admission_notices'):
            seen={r['text'] for r in result[key]}
            result[key].extend(row for row in rows if row['text'] not in seen)
    if registered.get('records') and registered.get('verified_pages'):
        urls={p['url'] for p in result['pages']}
        result['pages'].extend(p for p in registered['verified_pages'] if p['url'] not in urls)
        result['status']='ready'
    # Apply the same notice scope to retained cache and curated records.
    result['admission_notices']=[row for row in result['admission_notices']
        if not re.search(r'名单|公示|录取结果|成绩|本科',row['text'])]
    # Older source snippets may survive an unavailable page or come from a saved
    # registry record. Correct impossible extracted years without changing dates
    # describing when those sources were actually read.
    result['papers']=[{**row,'year':publication_year(row['text'])}
        if (row.get('year') or 0)>int(core.now()[:4])+1 else row for row in result['papers']]
    result['papers'].sort(key=lambda r:r.get('year') or 0,reverse=True)
    for key,limit in [('papers',15),('relations',5),('biography',5),('recruitment',6)]:result[key]=result[key][:limit]
    # A failed refresh must not erase evidence already read successfully.
    if result['status']=='unavailable' and old and old['status']=='ready':
        old['refresh_error']=result['errors'];return old
    path=path_for(mentor_id);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.'+str(threading.get_ident())+'.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    return with_catalog_records(mentor_id,result)


def main():
    from . import catalog
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0);parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--cached-only',action='store_true',help='Reparse previously readable profiles without retrying failed homepages')
    parser.add_argument('--offline',action='store_true',help='Reparse saved HTML only; no network requests')
    args=parser.parse_args()
    profiles=[p for p in catalog.static_catalog()[0] if p.get('catalog_source') or p['id'].startswith('pilot-')]
    if args.cached_only or args.offline:
        profiles=[p for p in profiles if path_for(p['id']).exists() and
                  json.loads(path_for(p['id']).read_text(encoding='utf-8')).get('status')=='ready']
    if args.limit:profiles=profiles[:args.limit]
    counts={'processed':0,'read':0,'papers':0,'relations':0,'recruitment':0,'admission_notices':0}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(enrich,p['id'],args.refresh or args.offline,offline=args.offline):p for p in profiles}
        for future in as_completed(jobs):
            data=future.result();counts['processed']+=1;counts['read']+=data['status']=='ready'
            for key in ('papers','relations','recruitment','admission_notices'):counts[key]+=bool(data[key])
            if counts['processed']%25==0:print(json.dumps(counts),flush=True)
    print(json.dumps(counts),flush=True)


if __name__=='__main__':main()
