"""Reviewed public bibliography and historical admissions for two thin subjects.

Run with python -m workbench.collect_four_teacher_depth. No live scraping occurs
here: each minimal bibliographic record was checked on its linked primary page.
The 1104 navigation assignment is secondary evidence, separate from the official
2025 doctoral roster's 0810 program. Never infer supervision from coauthorship.
"""
import json
from . import catalog, public_research as research
from .collect_discipline_catalog import REFERENCE, OUT, aggregate
from .collect_sparse_disciplines import roster_row
from .collect_thin_subject_reviewed import NUDT_ROSTER, AEU_ROSTER, NUDT_NOTICE, AEU_NOTICE

DATE = '2026-10-15'
DOCTOR = 'https://yjszs.nudt.edu.cn/attached/file/20241018/20241018203957_900.pdf'
AWARD = 'https://grs.ahpu.edu.cn/_upload/article/files/87/83/dd93d7cb4b159920e08c338610cd/95d8ce79-28ef-45d5-a610-1625e2d0b7f5.pdf'
SUN_ID = 'https://sgxy.jmi.edu.cn/a5/7b/c2249a107899/page.htm'
TANG_ID = 'https://www.nudt.edu.cn/kxyj/kydt/6fb74767f92648e9a73f281112afe7f3.htm'
SUPPLEMENT = REFERENCE / 'four_teacher_depth_faculty.json'
AUDIT = REFERENCE / 'four_teacher_depth_audit_20261015.json'


def record(text, url, year, kind='期刊出版页', **extra):
    return dict(text=text, url=url, year=year, source_kind=kind,
                fetched_at=DATE, **extra)


def paper(text, url, year, doi=''):
    return record(text, url, year, publication_type='期刊论文',
                  **({'work_url': 'https://doi.org/' + doi} if doi else {}))


PEOPLE = [
    dict(name='唐波', school='国防科技大学', dept='电子对抗学院', code='1104',
         direction='信息对抗（另见2025博士目录）', identity=DOCTOR,
         papers=[paper('唐波、吴文俊、史英春、王旭阳、李达：基于MIMO阵列的综合射频系统鲁棒波形设计算法研究。电子与信息学报，2023，45(11):3918–3926。',
                       'https://jeit.ac.cn/cn/article/pdf/preview/10.11999/JEIT220969.pdf', 2023, '10.11999/JEIT220969')],
         biography=[record('2021年学校报道介绍唐波在清华大学完成本、硕、博学习，当时为电子对抗学院副教授。原文未给出其导师姓名。', TANG_ID, 2021, '学校报道')]),
    dict(name='曾芳玲', school='国防科技大学', dept='电子对抗学院', code='1104',
         direction='信息对抗（另见2025博士目录）', identity=DOCTOR,
         papers=[paper('张海川、曾芳玲：非完备空际间叠干扰下星基导航信号捕获性能分析。电子与信息学报，2019，41(3):594–601。',
                       'https://jeit.ac.cn/cn/article/doi/10.11999/JEIT180355', 2019, '10.11999/JEIT180355'),
                 paper('曾芳玲、欧阳晓凤、徐浩、吕大千：基于时频融合的长码直接捕获优化算法研究。电子与信息学报，2019，41(2):309–316。',
                       'https://jeit.ac.cn/cn/article/doi/10.11999/JEIT180119?viewType=HTML', 2019, '10.11999/JEIT180119')],
         relations=[record('指导的博士生：张海川。安徽省2022年优秀博士学位论文名单（2022yxbsxwlw055）列明其论文《复杂环境下抗干扰阵列天线鲁棒自适应波束形成算法研究》的导师为曾芳玲，单位为国防科技大学电子对抗学院。2022是获评年份，不据此推断毕业年份。',
                           AWARD, 2022, '省教育厅名单（高校官网公开）', relation_type='doctoral_student', related_name='张海川', page=68)]),
    dict(name='计科峰', school='国防科技大学', dept='电子科学学院', code='1104',
         direction='空天遥感图像智能处理（另见2025博士目录）', identity=DOCTOR,
         papers=[paper('冷祥光、计科峰、熊博莅、匡纲要：面向舰船目标检测的单通道复值SAR图像统计建模方法研究。雷达学报，2020，9(3):477–496。',
                       'https://dds.sciengine.com/cfs/files/pdfs/view/2095-283X/542DA6319628463480A28DC95319D53E.pdf', 2020, '10.12000/JR20070')]),
    dict(name='施龙飞', school='国防科技大学', dept='电子科学学院', code='1104',
         direction='新体制雷达与智能电子防御（另见2025博士目录）', identity=DOCTOR,
         papers=[paper('施龙飞、全源、范金涛、马佳智：通信化雷达探测技术。雷达学报，2020，9(6):1056–1063。',
                       'https://www.sciengine.com/doi/pdf/F05C84D86C2A42949F6AF1AB934ED7CD', 2020, '10.12000/JR20088')]),
    dict(name='李永祯', school='国防科技大学', dept='电子科学学院', code='1104',
         direction='新体制雷达与智能电子防御（另见2025博士目录）', identity=DOCTOR,
         papers=[paper('李永祯、王雪松、施龙飞、肖顺平、庄钊文：基于IPPS的微弱信号检测。电子与信息学报，2006，28(2):335–339。',
                       'https://jeit.ac.cn/cn/article/pdf/preview/9e8a5b1e-2d79-403e-9534-04fc1ce7b47d.pdf', 2006)]),
    dict(name='葛武滇', school='陆军工程大学', dept='军事基础系', code='1110',
         direction='军兵种训练（2024目录）',
         identity='https://jyjs.cbpt.cnki.net/portal/journal/portal/client/paper/667027db918db9b83ccba6e33f58ac0c',
         papers=[paper('王梅娟、张海涛、葛武滇：基于URWPGSim仿真平台的机器人教学探索。计算机教育，2018(1):11–14。',
                       'https://jyjs.cbpt.cnki.net/portal/journal/portal/client/paper/667027db918db9b83ccba6e33f58ac0c', 2018, '10.16512/j.cnki.jsjjy.2018.01.004'),
                 paper('史涯晴、葛武滇、胡澄、乔正洪：基于网络环境的“四动”教学模式研究。计算机教育，2012(22):89–91,99。',
                       'https://jyjs.cbpt.cnki.net/portal/journal/portal/client/paper/105f758f7bfe22b959c3b38942cf96a4', 2012, '10.16512/j.cnki.jsjjy.2012.22.022')],
         biography=[record('2018年论文列明葛武滇署名单位为陆军工程大学指挥军官基础教育学院；导航中的军事基础系来自2024年招生目录，院系信息按来源年份分别保留。',
                           'https://jyjs.cbpt.cnki.net/portal/journal/portal/client/paper/667027db918db9b83ccba6e33f58ac0c', 2018)]),
    dict(name='孙天威', school='陆军工程大学', dept='军事基础系', code='1110',
         direction='军兵种训练（2024目录）', identity=SUN_ID,
         papers=[paper('张向葵、孙天威、缴润凯：阅读障碍学生创造力特征的研究。心理发展与教育，2004，20(2):1–6。作者单位将孙天威列于南京解放军理工大学理学院。',
                       'https://devpsy.bnu.edu.cn/CN/abstract/abstract820.shtml', 2004)],
         biography=[record('江苏海事职业技术学院2025年12月报道列明孙天威为陆军工程大学政治工作系主任，参与心理健康教育共建。导航中的军事基础系保留2024招生目录口径。',
                           SUN_ID, 2025, '高校活动报道')]),
]


def main():
    rows = []
    for p in PEOPLE:
        army = p['school'] == '陆军工程大学'
        directory = AEU_ROSTER if army else NUDT_ROSTER
        row = roster_row(p['name'], p['school'], p['dept'], p['code'], p['direction'], '', directory)
        row['collected_at'] = DATE
        row['assignment'].update(evidence_level='secondary', identity_url=p['identity'],
            source_kind='2024年招生目录转载（新东方）' if army else '导师名录转载（考博猫）',
            note=('2024年目录的军事训练学01军兵种训练方向；仅为历史记录，院系按该年目录展示。' if army else
                  '军兵种作战学对应来自转载名录；研究方向另据学校2025年0810博士目录，不能将其视为1104年度招生证据。'))
        if army:
            row['assignment'].update(year=2024, degree_level='硕士', record_kind='admission_catalog')
        rows.append(row)
    profiles = aggregate(rows)
    for p in profiles:
        army = p['institution'] == '陆军工程大学'
        if army:
            p['classification_basis'] = '2024年招生目录转载实名对应；院系为2024目录口径，不代表当前招生名额'
        for s in p['sources']:
            if s['title'] == '公开任职线索核对':
                s.update(title='身份核对来源', claim='通过学校博士目录、高校报道或论文作者单位核对姓名与学校；各事实的年份和范围见资料记录。')
    supplement = dict(profiles=profiles, pages=[dict(url=u, collected_at=DATE)
                      for u in (NUDT_ROSTER, AEU_ROSTER)], failures=[], collected_at=DATE)
    SUPPLEMENT.write_text(json.dumps(supplement, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    data = json.loads(OUT.read_text(encoding='utf8'))
    keys = {(p['institution'], p['department'], p['name']) for p in data['profiles']}
    inserted = []
    for p in profiles:
        key = (p['institution'], p['department'], p['name'])
        if key not in keys:
            data['profiles'].append(p); keys.add(key); inserted.append(p['name'])
    for page in supplement['pages']:
        if not any(p['url'] == page['url'] for p in data['pages']): data['pages'].append(page)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    catalog.static_catalog.cache_clear()
    registry = dict(research.source_registry())
    audit_rows = []
    for p in PEOPLE:
        profile = next(q for q in catalog.static_catalog()[0] if
                       (q['name'], q['institution'], q['department']) == (p['name'], p['school'], p['dept']))
        ident = profile['id']; army = p['school'] == '陆军工程大学'
        records = {k: p.get(k, []) for k in ('papers', 'relations', 'biography')}
        if army:
            records['recruitment'] = [record(f"2024年硕士招生目录转载列出{p['name']}：军事基础系，111000军事训练学，01军兵种训练，全日制，军队在职干部。目录注明以入学时导师名单为准；不表示今年仍有名额。", AEU_ROSTER, 2024, '历史招生目录转载')]
        else:
            page = 51 if p['dept'] == '电子对抗学院' else 25
            direction = p['direction'].split('（')[0]
            records['recruitment'] = [record(f"学校2025年博士招生简章第{page}页列出{p['name']}，专业为0810信息与通信工程，方向为{direction}。这是该专业的历史招生记录，不是1104军兵种作战学的年度招生依据，也不代表当前个人名额。", DOCTOR, 2025, '学校历史博士招生目录', page=page)]
        records['admission_notices'] = [record(
            '陆军工程大学2026年硕士招生简章下载入口（研招网学校发布；本次只核对公告和下载入口）' if army else '国防科技大学2026年硕士研究生招生简章',
            AEU_NOTICE if army else NUDT_NOTICE, 2026, '学校招生公告', scope='学校层面公告，不代表个人名额')]
        reg = registry.setdefault(ident, {})
        reg.update(name=p['name'], institution=p['school'])
        saved = reg.setdefault('records', {})
        pages = reg.setdefault('verified_pages', [])
        for key, items in records.items():
            saved.setdefault(key, [])
            for item in items:
                if not any((r['text'], r['url']) == (item['text'], item['url']) for r in saved[key]): saved[key].append(item)
                if not any(r['url'] == item['url'] for r in pages):
                    pages.append(dict(url=item['url'], source_kind=item['source_kind'], fetched_at=DATE))
        audit_rows.append(dict(id=ident, name=p['name'], institution=p['school'],
                               counts={k: len(v) for k, v in records.items()}))
    research.SOURCE_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    for row in audit_rows:
        result = research.enrich(row['id'], True, offline=True)
        assert result['status'] == 'ready' and result['papers'] and result['recruitment']
    # Keep the original baseline on a repeat run; a replay must not look like growth.
    prior = json.loads(AUDIT.read_text(encoding='utf8')) if AUDIT.exists() else {}
    audit = dict(prior, checked_at=DATE, new_profiles=prior.get('new_profiles', len(inserted)),
                 profiles=audit_rows, limitations=[
                     '1104学科对应依据仍为转载名录；学校2025博士目录核对的是0810招生。',
                     '1110新增两位的实名招生依据为2024历史目录转载。',
                     '仅曾芳玲补得明确博士指导关系；其余六位未发现足够的师承证据。',
                     '排除清华出版社05184702书页：作者栏与简介不一致，未将该书记给葛武滇。',
                     '排除JR15103：李永祯仅出现在参考文献，非该文作者。'])
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(inserted=inserted, profiles=audit_rows), ensure_ascii=False))


if __name__ == '__main__':
    main()
