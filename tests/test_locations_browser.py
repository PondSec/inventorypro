from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser
from test_unified_assets_browser import unified_live
from test_enterprise_browser import live_inventory,sign_in


def test_location_table_pagination_dialog_errors_and_unsaved_inputs(unified_live,browser):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        for index in range(30):db.execute('INSERT INTO locations(name) VALUES (?)',(f'QA location {index:02}',))
        db.commit()
    page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,unified_live);page.goto(unified_live+'/locations')
    expect(page.locator('tbody tr')).to_have_count(10)
    page.get_by_role('button',name='Weiter',exact=True).click()
    expect(page.get_by_text('Seite 2 von 4',exact=True)).to_be_visible()
    page.get_by_role('button',name='Standort hinzufügen',exact=True).click()
    dialog=page.get_by_role('dialog',name='Standort hinzufügen',exact=True)
    expect(dialog.get_by_label('Name des Standorts',exact=True)).to_be_focused()
    dialog.get_by_label('Name des Standorts',exact=True).fill('QA added site')
    page.once('dialog',lambda item:item.dismiss());dialog.get_by_role('button',name='Abbrechen',exact=True).click()
    expect(dialog).to_be_visible()
    page.route('**/api/locations',lambda route:route.fulfill(status=503,json={'error':'QA temporarily unavailable'}) if route.request.method=='POST' else route.continue_())
    dialog.get_by_role('button',name='Speichern',exact=True).click()
    expect(dialog.get_by_role('alert')).to_have_text('QA temporarily unavailable')
    expect(dialog.get_by_label('Name des Standorts',exact=True)).to_have_value('QA added site')
    page.unroute('**/api/locations');dialog.get_by_role('button',name='Speichern',exact=True).click();expect(dialog).not_to_be_visible()
    page.get_by_role('searchbox',name='Standorte durchsuchen').fill('QA added site')
    expect(page.locator('tbody tr')).to_have_count(1)
    page.get_by_label('Aktionen für QA added site',exact=True).click();page.get_by_role('button',name='Bearbeiten',exact=True).click()
    dialog=page.get_by_role('dialog',name='Standort bearbeiten',exact=True)
    dialog.get_by_label('Beschreibung des Standorts',exact=True).fill('QA retained description');dialog.get_by_role('button',name='Speichern',exact=True).click()
    expect(page.locator('tbody')).to_contain_text('QA retained description')
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
    page.get_by_label('Aktionen für QA added site',exact=True).click();page.once('dialog',lambda item:item.accept());page.get_by_role('button',name='Löschen',exact=True).click()
    expect(page.get_by_text('Keine passenden Standorte.',exact=True)).to_be_visible()
    assert not errors,errors
    page.close()
