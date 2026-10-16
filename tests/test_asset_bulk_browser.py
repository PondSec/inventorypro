import pytest
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser, live_inventory, sign_in
from test_unified_assets_browser import unified_live, new_asset


def select_rows(page, base, names):
    page.goto(base+'/inventory?q=QA%20bulk')
    for name in names:page.get_by_role('checkbox',name=name+' auswählen',exact=True).check()


def test_bulk_edit_cancel_failure_retry_and_delete(unified_live,browser):
    context=browser.new_context(viewport={'width':1280,'height':900});page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)));sign_in(page,unified_live)
    a=new_asset(page,unified_live,'QA bulk one');b=new_asset(page,unified_live,'QA bulk two');keep=new_asset(page,unified_live,'QA retained')
    select_rows(page,unified_live,['QA bulk one','QA bulk two'])
    page.get_by_role('button',name='Gemeinsam bearbeiten',exact=True).click()
    dialog=page.get_by_role('dialog',name='Gemeinsam bearbeiten',exact=True)
    expect(dialog.get_by_text('2 Assets ausgewählt.',exact=True)).to_be_visible()
    field=dialog.locator('[data-bulk-field="cost_center"]')
    field.get_by_role('combobox').select_option('set');field.get_by_role('textbox').fill('QA shared cost')
    page.route('**/api/inventory/assets/bulk',lambda route:route.fulfill(status=503,json={'error':'QA retry later'}))
    dialog.get_by_role('button',name='Änderungen speichern').click()
    expect(dialog.get_by_role('alert')).to_have_text('QA retry later')
    expect(field.get_by_role('textbox')).to_have_value('QA shared cost')
    page.unroute('**/api/inventory/assets/bulk')
    dialog.get_by_role('button',name='Änderungen speichern').click();expect(dialog).not_to_be_visible()
    for identifier in [a,b]:assert context.request.get(unified_live+f'/api/inventory/assets/{identifier}').json()['cost_center']=='QA shared cost'
    select_rows(page,unified_live,['QA bulk one','QA bulk two'])
    page.get_by_role('button',name='Auswahl löschen',exact=True).click()
    delete=page.get_by_role('dialog',name='Auswahl löschen',exact=True)
    expect(delete.get_by_text('2 Assets ausgewählt.',exact=True)).to_be_visible()
    page.keyboard.press('Escape');expect(delete).not_to_be_visible()
    expect(page.get_by_role('button',name='Auswahl löschen',exact=True)).to_be_focused()
    page.get_by_role('button',name='Auswahl löschen',exact=True).click()
    expect(delete.get_by_text('2 Assets ausgewählt.',exact=True)).to_be_visible()
    delete.get_by_role('button',name='Ausgewählte Assets endgültig löschen',exact=True).click()
    expect(page.get_by_text('Keine passenden Einträge',exact=True)).to_be_visible()
    assert context.request.get(unified_live+f'/api/inventory/assets/{keep}').status==200
    assert not errors,errors
    context.close()


def test_bulk_selection_works_without_export_right_and_mobile_dialog_fits(unified_live,browser):
    from test_product_catalog_routes import role
    context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page();sign_in(page,unified_live)
    identifier=new_asset(page,unified_live,'QA bulk mobile')
    # Give the signed-in account only asset rights; export remains administrator-only.
    with inventory_app.app.app_context():
        db=inventory_app.get_db();user=db.execute("INSERT INTO users(username,password_hash,must_change_password) VALUES ('qa-bulk-editor',?,0)",(inventory_app.generate_password_hash('Synthetic-Test-Only-42!'),)).lastrowid
        r=db.execute("INSERT INTO roles(name) VALUES ('QA bulk editor')").lastrowid
        db.execute('INSERT INTO user_roles(user_id,role_id) VALUES (?,?)',(user,r))
        db.execute("INSERT INTO role_permissions(role_id,permission_id) SELECT ?,id FROM permissions WHERE key IN ('assets.view','assets.manage')",(r,));db.commit()
    page.goto(unified_live+'/login')
    page.get_by_label('Benutzername').fill('qa-bulk-editor');page.locator('input[name=password]').fill('Synthetic-Test-Only-42!')
    page.get_by_role('button',name='Anmelden',exact=True).click();page.wait_for_url('**/inventory')
    select_rows(page,unified_live,['QA bulk mobile'])
    expect(page.locator('[data-selection-export]')).to_have_count(0)
    page.get_by_role('button',name='Gemeinsam bearbeiten',exact=True).click()
    dialog=page.get_by_role('dialog',name='Gemeinsam bearbeiten',exact=True)
    expect(dialog.get_by_text('1 Asset ausgewählt.',exact=True)).to_be_visible()
    for theme in ['light','dark']:
        page.evaluate('(t)=>InventoryTheme.set(t)',theme)
        assert dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth+1')
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible();context.close()


def test_bulk_english_labels_keep_asset_names_and_save_fields(unified_live,browser):
    from test_interface_language_browser import set_language
    context=browser.new_context();page=context.new_page();sign_in(page,unified_live)
    identifier=new_asset(page,unified_live,'QA bulk Standort');set_language(page,'en')
    page.goto(unified_live+'/inventory?q=QA%20bulk')
    page.locator('[data-select-entry]').check()
    page.get_by_role('button',name='Edit selected assets',exact=True).click()
    dialog=page.get_by_role('dialog',name='Edit selected assets',exact=True)
    expect(dialog.get_by_text('1 asset selected.',exact=True)).to_be_visible()
    dialog.get_by_text('Selected assets',exact=True).click()
    expect(dialog.get_by_text('QA bulk Standort',exact=True)).to_be_visible()
    field=dialog.locator('[data-bulk-field="cost_center"]')
    field.get_by_role('combobox').select_option(label='Set value');field.get_by_role('textbox').fill('Standort')
    dialog.get_by_role('button',name='Save changes',exact=True).click();expect(dialog).not_to_be_visible()
    result=page.request.get(unified_live+f'/api/inventory/assets/{identifier}').json()
    assert result['name']=='QA bulk Standort' and result['cost_center']=='Standort'
    context.close()
