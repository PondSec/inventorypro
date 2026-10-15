import pytest
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from inventorypro.domains.inventory.unification import convert_inventory


@pytest.mark.parametrize('width,height',[(1672,941),(1440,900),(1280,800),(390,844)])
def test_reports_have_compact_tabs_accessible_chart_data_and_both_themes(live_inventory,browser,width,height):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();convert_inventory(db);db.commit()
    page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory)
    assert page.goto(live_inventory+'/stats').status==200
    expect(page.get_by_role('heading',name='Auswertungen',exact=True)).to_be_visible()
    expect(page.locator('#growthChart')).to_be_visible()
    assert page.locator('canvas').count()==5
    page.locator('.report-data').first.locator('summary').click()
    expect(page.locator('.report-data').first.get_by_role('table')).to_be_visible()
    tab=page.get_by_role('tab',name='Bestand',exact=True);tab.focus();tab.press('ArrowRight')
    expect(page.get_by_role('tab',name='Service & Wartung',exact=True)).to_have_attribute('aria-selected','true')
    expect(page.get_by_role('heading',name='Tickets nach Asset',exact=True)).to_be_visible()
    expect(page.locator('#growthChart')).not_to_be_visible()
    page.get_by_role('tab',name='Aktivität & Hinweise',exact=True).click()
    expect(page.get_by_role('heading',name='Hinweise aus den vorhandenen Daten',exact=True)).to_be_visible()
    page.get_by_role('tab',name='Bestand',exact=True).click()
    for theme in ['light','dark']:
        page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
        expect(page.locator('#growthChart')).to_be_visible()
        assert page.locator('#growthChart').bounding_box()['height']>=190
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
    assert not errors,errors
    page.close()
