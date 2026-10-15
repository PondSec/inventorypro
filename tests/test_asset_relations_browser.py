from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live,new_asset


def test_searchable_relation_picker_and_shared_attachment_removal(unified_live,browser):
    page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,unified_live);workplace=new_asset(page,unified_live,'QA related workplace');pc=new_asset(page,unified_live,'QA relation PC')
    page.get_by_text('Beziehungen',exact=True).click();page.get_by_role('button',name='Beziehung hinzufügen',exact=True).click()
    dialog=page.get_by_role('dialog',name='Beziehungen zu Assets',exact=True)
    dialog.get_by_label('Assets im Bestand suchen',exact=True).fill('QA related workplace')
    dialog.get_by_role('checkbox',name='QA related workplace',exact=True).check()
    expect(dialog.get_by_label('Beziehungstyp',exact=True)).to_be_visible()
    page.route('**/api/inventory/assets/*/relations',lambda route:route.fulfill(status=503,json={'error':'QA relation unavailable'}))
    dialog.get_by_role('button',name='Beziehungen speichern',exact=True).click()
    expect(dialog.get_by_role('status')).to_have_text('QA relation unavailable')
    expect(dialog.locator('[data-component-selection]')).to_contain_text('QA related workplace')
    page.unroute('**/api/inventory/assets/*/relations');dialog.get_by_role('button',name='Beziehungen speichern',exact=True).click()
    expect(dialog).not_to_be_visible();page.get_by_text('Beziehungen',exact=True).click()
    expect(page.locator('[data-remove-relation]')).to_have_count(1)
    page.once('dialog',lambda item:item.accept());page.locator('[data-remove-relation]').click()
    expect(page.locator('[data-remove-relation]')).to_have_count(0)
    page.get_by_text('Dateien',exact=True).click()
    page.locator('[data-asset-file] input[type=file]').set_input_files({'name':'qa-shared.txt','mimeType':'text/plain','buffer':b'QA shared server attachment'})
    page.get_by_role('button',name='Datei hochladen',exact=True).click();page.wait_for_load_state('networkidle')
    page.get_by_text('Dateien',exact=True).click()
    expect(page.get_by_role('link',name='qa-shared.txt',exact=True)).to_be_visible()
    page.once('dialog',lambda item:item.accept());page.get_by_role('button',name='qa-shared.txt entfernen',exact=True).click()
    expect(page.get_by_role('link',name='qa-shared.txt',exact=True)).to_have_count(0)
    assert not errors,errors
    page.close()
