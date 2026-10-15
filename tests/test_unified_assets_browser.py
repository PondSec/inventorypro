import pytest
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from inventorypro.domains.inventory.unification import convert_inventory


@pytest.fixture
def unified_live(live_inventory):
    with inventory_app.app.app_context():db=inventory_app.get_db();convert_inventory(db);db.commit()
    return live_inventory


def new_asset(page,base,name):
    page.goto(base+'/inventory/assets/new');page.get_by_label('Name *',exact=True).fill(name)
    page.get_by_role('button',name='Speichern',exact=True).click();page.wait_for_url('**/inventory/assets/*')
    expect(page.locator('.object-header h1')).to_have_text(name)
    return int(page.url.rsplit('/',1)[1])


def test_asset_editor_nested_picker_reverse_links_and_retained_error_inputs(unified_live,browser):
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)));sign_in(page,unified_live)
    cpu=new_asset(page,unified_live,'QA CPU XY');ram=new_asset(page,unified_live,'QA RAM XY');pc=new_asset(page,unified_live,'QA Mini PC XY')
    page.get_by_role('link',name='Enthaltene Assets',exact=True).click();page.get_by_role('button',name='Assets hinzufügen').click()
    dialog=page.get_by_role('dialog',name='Enthaltene Assets auswählen');search=dialog.get_by_role('searchbox',name='Assets im Bestand suchen')
    search.fill('QA CPU XY');dialog.get_by_role('checkbox',name='QA CPU XY',exact=True).check()
    search.fill('QA RAM XY');dialog.get_by_role('checkbox',name='QA RAM XY',exact=True).check()
    expect(dialog.get_by_role('button',name='QA CPU XY aus Auswahl entfernen')).to_be_visible()
    dialog.get_by_label('Menge für QA RAM XY',exact=True).fill('2')
    dialog.get_by_role('button',name='Assets übernehmen',exact=True).click();expect(dialog).not_to_be_visible()
    expect(page.locator('tbody')).to_contain_text('QA CPU XY');expect(page.locator('tbody')).to_contain_text('QA RAM XY')
    page.get_by_role('link',name='QA RAM XY',exact=True).click()
    expect(page.get_by_role('link',name='QA Mini PC XY Menge 2',exact=True)).to_be_visible()
    page.get_by_role('link',name='Bearbeiten',exact=True).click();page.get_by_label('Name *',exact=True).fill('QA RAM XY revised')
    page.route('**/api/inventory/assets/*',lambda route:route.fulfill(status=503,json={'error':'QA unavailable'}) if route.request.method=='PUT' else route.continue_())
    page.get_by_role('button',name='Speichern',exact=True).click();expect(page.get_by_role('alert')).to_contain_text('QA unavailable')
    expect(page.get_by_label('Name *',exact=True)).to_have_value('QA RAM XY revised')
    page.unroute('**/api/inventory/assets/*');page.get_by_role('button',name='Speichern',exact=True).click();page.wait_for_url('**/inventory/assets/*')
    expect(page.locator('.object-header h1')).to_have_text('QA RAM XY revised')
    for width in [1920,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme);page.wait_for_function('document.documentElement.scrollWidth<=innerWidth+1')
    assert not errors,errors
    context.close()


def test_canonical_asset_notes_maintenance_and_assignment_use_real_endpoints(unified_live,browser):
    context=browser.new_context(viewport={'width':1280,'height':900});page=context.new_page();sign_in(page,unified_live)
    identifier=new_asset(page,unified_live,'QA maintained asset')
    page.get_by_label('Neue Notiz',exact=True).fill('QA retained note')
    page.get_by_role('button',name='Notiz hinzufügen',exact=True).click()
    expect(page.get_by_text('QA retained note',exact=True)).to_be_visible()
    page.get_by_role('link',name='Wartung',exact=True).click()
    page.get_by_label('Aufgabe',exact=True).fill('QA inspect RAM')
    page.get_by_label('Fällig am',exact=True).fill('2026-11-01')
    page.get_by_role('button',name='Wartung hinzufügen',exact=True).click()
    expect(page.get_by_text('QA inspect RAM',exact=True)).to_be_visible()
    page.get_by_role('button',name='Erledigen',exact=True).click()
    expect(page.get_by_role('button',name='Erneut öffnen',exact=True)).to_be_visible()
    page.get_by_role('link',name='Zuweisung',exact=True).click()
    page.get_by_label('Ziel',exact=True).select_option(label='admin')
    page.get_by_role('button',name='Übernehmen',exact=True).click()
    expect(page.locator('.object-properties')).to_contain_text('admin')
    page.goto(unified_live+'/inventory?q=QA%20maintained%20asset')
    expect(page.locator('tbody')).to_contain_text('admin')
    context.close()
