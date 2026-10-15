from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live


def test_dependency_tasks_search_data_alternative_and_installation_crud(unified_live,browser):
    page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_default_timeout(10000)
    sign_in(page,unified_live);page.goto(unified_live+'/dependencies');page.wait_for_load_state('networkidle')
    tabs=page.get_by_role('tablist',name='Abhängigkeitsbereiche')
    expect(page.get_by_role('heading',name='Abhängigkeiten',exact=True)).to_have_count(1)
    page.get_by_text('Daten als Tabelle anzeigen',exact=True).click()
    expect(page.locator('tbody tr:visible')).to_have_count(20)
    page.get_by_label('Diagramm durchsuchen',exact=True).fill('Notebook 000')
    expect(page.locator('tbody tr:visible')).to_have_count(1)
    expect(page.locator('tbody')).to_contain_text('Notebook 000')
    tabs.get_by_role('tab',name='Software & Installationen',exact=True).click()
    page.get_by_label('Software-Name',exact=True).fill('QA workspace software')
    page.route('**/api/software',lambda route:route.fulfill(status=503,json={'error':'QA software unavailable'}) if route.request.method=='POST' else route.continue_())
    page.get_by_role('button',name='Software anlegen',exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('QA software unavailable')
    expect(page.get_by_label('Software-Name',exact=True)).to_have_value('QA workspace software')
    page.unroute('**/api/software')
    with page.expect_response(lambda response:response.url.endswith('/api/software') and response.request.method=='POST') as created:
        page.get_by_role('button',name='Software anlegen',exact=True).click()
    assert created.value.status==201
    page.get_by_label('Installierte Software',exact=True).select_option(label='QA workspace software')
    selection=page.get_by_label('Zugeordnetes Asset',exact=True)
    selection.select_option(selection.locator('option').nth(1).get_attribute('value'))
    with page.expect_response(lambda response:response.url.endswith('/api/software-installations') and response.request.method=='POST') as installed:
        page.get_by_role('button',name='Installation hinzufügen',exact=True).click()
    assert installed.value.status==201
    expect(page.locator('#dependencies-panel-software')).to_contain_text('QA workspace software')
    tabs.get_by_role('tab',name='Organisation & Beziehungen',exact=True).focus();page.keyboard.press('Home')
    expect(tabs.get_by_role('tab',name='Diagramm & Analyse',exact=True)).to_be_focused()
    expect(page.get_by_label('Diagramm durchsuchen',exact=True)).to_have_value('Notebook 000')
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            for name in ['Diagramm & Analyse','Software & Installationen','Organisation & Beziehungen']:
                tabs.get_by_role('tab',name=name,exact=True).click()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),(width,theme,name)
    assert not errors,errors
    page.close()
