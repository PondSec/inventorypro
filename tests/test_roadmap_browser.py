from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in


def test_roadmap_creation_board_step_and_save_errors(live_inventory,browser):
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/roadmap')
    page.get_by_test_id('open-roadmap-modal').click();modal=page.get_by_test_id('roadmap-modal')
    modal.get_by_label('Titel der Roadmap').fill('QA Visual Roadmap')
    modal.get_by_label('Ziel oder erwartetes Ergebnis der Roadmap').fill('Preserve real planning')
    modal.get_by_label('Status der Roadmap').select_option('in_progress')
    modal.get_by_role('button',name='Roadmap speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('button').filter(has=page.locator('strong',has_text='QA Visual Roadmap')).click()
    expect(page.locator('[x-text="selectedRoadmap.title"]')).to_have_text('QA Visual Roadmap')
    expect(page.locator('[x-model="selectedRoadmap.status"]')).to_have_value('in_progress')
    page.get_by_role('button',name='Schritt hinzufügen',exact=True).click()
    page.locator('[x-model="newStep.title"]').fill('QA Board Step')
    page.get_by_role('button',name='Schritt speichern',exact=True).click()
    card=page.locator('.board-card').filter(has_text='QA Board Step');expect(card).to_be_visible()
    card.locator('select').select_option('in_progress');card.get_by_role('button',name='Speichern',exact=True).click()
    expect(page.locator('.board-column').filter(has=page.locator('p[x-text="roadmapStatusLabels[status] || status"]').filter(has_text='In Arbeit')).locator('.board-card')).to_contain_text('QA Board Step')
    page.route('**/api/roadmaps/*',lambda route:route.fulfill(status=503,json={'error':'QA cannot save'}) if route.request.method=='PUT' else route.continue_())
    page.locator('[x-model="selectedRoadmap.title"]').fill('QA Unsaved Roadmap')
    page.get_by_role('button',name='Roadmap speichern',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('QA cannot save')
    expect(page.locator('[x-model="selectedRoadmap.title"]')).to_have_value('QA Unsaved Roadmap')
    page.unroute('**/api/roadmaps/*')
    for width in [1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
    assert not errors,errors
    context.close()
