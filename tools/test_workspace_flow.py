"""Real browser regression for the progressive mentor workspace.

Run against an isolated MENTOR_WORKBENCH_DATA directory: this test writes
synthetic notes/evidence. Output stays on D:; --screenshots updates only the
workspace's two formal images, after clearing the test record.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

PANES = ('identity', 'papers', 'admission', 'network', 'investigation')
SHORTCUTS = ('人工智能', '计算机视觉', '机器学习', '自然语言处理', '数据挖掘', '数字电路')


def run(base, output, screenshots=False):
    output.mkdir(parents=True, exist_ok=True)
    summary = {'shortcuts': {}, 'widths': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/?view=workspace')
        expect(page.locator('#dossier')).to_be_visible()
        expect(page.locator('#nameInput')).to_have_value('张')
        assert page.locator('#auxSidebar').count() == 0

        def submit(text):
            page.locator('#nameInput').fill(text)
            with page.expect_response(lambda r: '/api/catalog/name?' in r.url or '/api/catalog/research?' in r.url) as response:
                page.locator('.card-search-btn').click()
            return response.value.json()

        def ready():
            expect(page.locator('#dossier')).to_be_visible()
            page.wait_for_function('document.querySelector("#loadingPanel").hidden')

        page.locator('.popular-directions > summary').click()
        for query in SHORTCUTS:
            with page.expect_response(lambda r: '/api/catalog/research?' in r.url) as response:
                page.locator(f'[data-quick-interest="{query}"]').click()
            rows = response.value.json()
            assert rows, query
            ready()
            expect(page.locator('#btnFilterMode')).to_have_attribute('aria-selected', 'true')
            expect(page.locator('#nameInput')).to_have_value(query)
            expect(page.locator('.mentor-card-item')).to_have_count(len(rows))
            expected = {row['id'] for row in rows}
            actual = set(page.locator('[data-person]').evaluate_all('(nodes) => nodes.map(n => n.dataset.person)'))
            assert actual == expected
            summary['shortcuts'][query] = len(rows)

        # Free direction text, discipline, school and exact direction combine.
        submit('机器学习')
        ready()
        page.locator('#nameInput').fill('')
        option = page.locator('#disciplineSelect option').evaluate_all('(nodes) => nodes.find(n => n.value.startsWith("0812 ")).value')
        page.select_option('#disciplineSelect', option)
        expect(page.locator('#institutionSelect')).to_be_enabled()
        expect(page.locator('.mentor-card-item').first).to_be_visible()
        school = page.locator('#institutionSelect option').nth(1).get_attribute('value')
        page.select_option('#institutionSelect', school)
        page.wait_for_function('document.querySelector("#directionSelect").value === "__all__"')
        direction = page.locator('#directionSelect option').nth(1).get_attribute('value')
        with page.expect_response(lambda r: '/api/catalog/research?' in r.url) as response:
            page.select_option('#directionSelect', direction)
        rows = response.value.json()
        assert rows and all(row['institution'] == school for row in rows)
        ready()
        with page.expect_response(lambda r: '/api/catalog/research?' in r.url) as response:
            page.select_option('#admissionStatusSelect', 'signal')
        assert all(row['admission_catalog'] for row in response.value.json())

        # Name mode and selection reset the accordion predictably.
        page.locator('#btnSearchMode').click()
        rows = submit('张')
        ready()
        assert rows
        for pane in PANES:
            expect(page.locator('#tab-' + pane)).to_have_attribute('aria-expanded', str(pane == 'identity').lower())
        for pane in PANES:
            button = page.locator('#tab-' + pane)
            if pane == 'identity':
                button.click()
                expect(page.locator('#region-identity')).to_be_hidden()
            button.click()
            expect(page.locator('#region-' + pane)).to_be_visible()
            expect(button).to_have_attribute('aria-expanded', 'true')
            button.click()
            expect(page.locator('#region-' + pane)).to_be_hidden()
        page.locator('#tab-identity').focus()
        page.keyboard.press('ArrowDown')
        expect(page.locator('#tab-papers')).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#region-papers')).to_be_visible()
        page.locator('.mentor-card-item').nth(1).click()
        ready()
        expect(page.locator('#tab-papers')).to_have_attribute('aria-expanded', 'false')
        page.locator('.mentor-card-item').first.click()
        ready()

        # A failed dossier fetch shows the real loading state, then the retained
        # introduction; a later retry remains usable.
        target = page.locator('.mentor-card-item').nth(1).get_attribute('data-person')
        def fail_dossier(route):
            assert page.locator('#loadingPanel').is_visible()
            route.fulfill(status=503, json={'detail': '测试：档案加载失败'})
        page.route('**/api/catalog/mentor/' + target, fail_dossier)
        page.locator('.mentor-card-item').nth(1).click()
        expect(page.locator('#resultStatus')).to_contain_text('档案加载失败')
        expect(page.locator('#workspaceIntro')).to_be_visible()
        page.unroute('**/api/catalog/mentor/' + target)
        page.locator('.mentor-card-item').first.click()
        ready()

        # Real local persistence, evidence status and Markdown download.
        page.locator('#tab-investigation').click()
        expect(page.locator('#caseNotes')).to_be_visible()
        marker = '浏览器回归：仅用于隔离测试的合成记录'
        page.locator('#caseNotes').fill(marker)
        page.locator('#saveCaseNotes').click()
        expect(page.locator('#caseSaveStatus')).to_have_text('已保存到本机')
        mentor_id = page.evaluate('state.mentor.profile.id')
        saved = context.request.get(base + f'/api/catalog/mentor/{mentor_id}').json()
        assert saved['case']['notes'] == marker
        page.reload()
        ready()
        page.locator('#tab-investigation').click()
        expect(page.locator('#caseNotes')).to_have_value(marker)
        page.locator('#evidenceTitle').fill('回归测试来源')
        page.locator('#evidenceUrl').fill('https://example.org/workspace-regression')
        page.locator('#evidenceClaim').fill('合成测试，不作为导师事实')
        page.locator('#evidenceForm button').click()
        expect(page.locator('[data-evidence-status]')).to_have_count(1)
        expect(page.locator('#evidenceTitle')).to_be_visible()
        page.locator('[data-evidence-status]').select_option('已人工核查')
        expect(page.locator('#reviewSaveStatus')).to_have_text('核查状态已保存到本机')
        page.locator('summary', has_text='核查进度').click()
        page.locator('[data-section-status]').first.select_option('已人工核查')
        expect(page.locator('[data-section-status]').first).to_be_enabled()
        page.locator('summary', has_text='资料整理与核查任务').click()
        expect(page.locator('#reviewGuide')).to_be_visible()
        page.locator('summary', has_text='整理已有记录与核对 DOI').click()
        page.locator('#runInvestigation').click()
        expect(page.locator('#investigationStatus')).to_have_text('已保存。')
        assert context.request.get(base + f'/api/catalog/mentor/{mentor_id}/investigation').json()['last_run']
        with page.expect_download() as download:
            page.locator('#reportLink').click()
        path = output / 'synthetic-profile.md'
        download.value.save_as(path)
        assert marker in path.read_text(encoding='utf-8')

        # Missing data remains explicit, and no-result keeps the illustration.
        page.locator('#btnFilterMode').click()
        assert submit('不存在的研究方向abcxyz') == []
        expect(page.locator('#workspaceIntro')).to_be_visible()
        expect(page.locator('.ws-empty-img')).to_be_visible()
        expect(page.locator('#dossier')).to_be_hidden()
        expect(page.locator('#addMentorBox')).to_be_visible()
        expect(page.locator('#projectDetails')).to_be_visible()
        page.screenshot(path=str(output / 'workspace-empty.png'))
        page.route('**/api/catalog/research?**', lambda route: route.fulfill(status=503, json={'detail': '测试：查询服务暂不可用'}))
        submit('计算机视觉')
        expect(page.locator('#resultStatus')).to_contain_text('暂不可用')
        expect(page.locator('#workspaceIntro')).to_be_visible()
        page.unroute('**/api/catalog/research?**')

        # Restore and clean synthetic state before formal screenshots.
        context.request.patch(base + f'/api/catalog/mentor/{mentor_id}/case',
                              data={'notes': '', 'section_status': {'身份与任职': '待核查'}},
                              headers={'Origin': base})
        evidence = context.request.get(base + f'/api/catalog/mentor/{mentor_id}').json()['case']['evidence']
        for item in evidence:
            context.request.delete(base + f'/api/catalog/mentor/{mentor_id}/evidence/' + item['id'], headers={'Origin': base})
        page.locator('#btnSearchMode').click()
        submit('张')
        ready()
        page.locator('.popular-directions').evaluate('(e) => e.open = false')
        for width in (1920, 1440, 1024, 768, 390):
            page.set_viewport_size({'width': width, 'height': 900 if width > 390 else 844})
            page.evaluate('window.scrollTo(0,0)')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow at {width}'
            for pane in PANES:
                page.locator('#tab-' + pane).click()
                expect(page.locator('#region-' + pane)).to_be_visible() if pane != 'identity' else expect(page.locator('#region-identity')).to_be_hidden()
                page.locator('#tab-' + pane).click()
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output / f'workspace-{width}.png'))
            summary['widths'].append(width)

        page.emulate_media(reduced_motion='reduce')
        page.locator('#tab-papers').click()
        expect(page.locator('#region-papers')).to_be_visible()
        assert page.locator('#region-papers').evaluate('(e) => e.getAnimations().length') == 0
        page.locator('#tab-papers').click()
        expect(page.locator('#region-papers')).to_be_hidden()

        page.set_viewport_size({'width': 1440, 'height': 900})
        page.evaluate('window.scrollTo(0,0)')
        if screenshots:
            formal = Path(__file__).resolve().parents[1] / 'docs/screenshots'
            page.screenshot(path=str(formal / '02-dossier.png'))
            page.locator('#tab-identity').click()
            page.locator('#tab-investigation').click()
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(formal / '03-evidence.png'))
        assert not errors, errors
        browser.close()
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8766')
    parser.add_argument('--output', type=Path, default=Path('D:/Codex/tmp/workspace-browser-check'))
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    run(args.base, args.output, args.screenshots)
