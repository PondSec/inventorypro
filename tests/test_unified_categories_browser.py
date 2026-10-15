from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live
import app as inventory_app


def test_category_field_editor_safe_delete_reassignment_and_inputs(unified_live,browser):
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();sign_in(page,unified_live)
    page.goto(unified_live+'/inventory/categories');page.get_by_role('button',name='Asset-Kategorie hinzufügen').click()
    modal=page.get_by_role('dialog',name='Asset-Kategorie',exact=True)
    modal.get_by_label('Name',exact=True).fill('QA fields browser')
    modal.get_by_role('button',name='Feld hinzufügen').click()
    modal.get_by_label('Feldname',exact=True).fill('Kapazität');modal.get_by_label('Feldtyp',exact=True).select_option('number');modal.get_by_label('Einheit',exact=True).fill('GB')
    modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('button',name='QA fields browser bearbeiten',exact=True).click()
    expect(modal.get_by_label('Feldname',exact=True)).to_have_value('Kapazität');expect(modal.get_by_label('Einheit',exact=True)).to_have_value('GB')
    modal.get_by_role('button',name='Schließen',exact=True).click()
    with inventory_app.app.app_context():
        db=inventory_app.get_db();source=db.execute('SELECT c.name FROM asset_categories c JOIN asset_legacy_categories m ON m.asset_category_id=c.id WHERE EXISTS(SELECT 1 FROM assets a WHERE a.category_id=c.id) LIMIT 1').fetchone()[0]
    page.get_by_role('searchbox',name='Asset-Kategorien durchsuchen',exact=True).fill(source)
    page.get_by_role('button',name=source+' löschen',exact=True).click()
    deletion=page.get_by_role('dialog',name='Asset-Kategorie löschen',exact=True)
    deletion.get_by_role('button',name='Kategorie löschen',exact=True).click()
    expect(deletion.get_by_role('alert')).to_contain_text('Zielkategorie')
    deletion.get_by_label('Zielkategorie',exact=True).select_option(label='QA fields browser')
    deletion.get_by_role('button',name='Kategorie löschen',exact=True).click();expect(deletion).not_to_be_visible()
    page.get_by_role('searchbox',name='Asset-Kategorien durchsuchen',exact=True).fill('QA fields browser')
    expect(page.locator('tbody tr:visible')).to_have_count(1);expect(page.locator('tbody tr:visible')).to_contain_text('40')
    for width in [1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme);page.wait_for_function('document.documentElement.scrollWidth<=innerWidth+1')
    context.close()
