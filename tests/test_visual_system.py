"""The shared visual contract is checked in real browsers, using isolated data."""
from playwright.sync_api import expect
from pathlib import Path
from test_enterprise_browser import browser, live_inventory, sign_in


def test_shell_geometry_and_keyboard_controls(live_inventory, browser):
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page();sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    expect(page.locator('main h1')).to_have_text('Inventar')
    geometry=page.evaluate('''()=>({sidebar:document.querySelector('.app-sidebar').getBoundingClientRect().width,
      topbar:document.querySelector('.app-header').getBoundingClientRect().height,
      content:document.querySelector('.enterprise-page').getBoundingClientRect().width,
      logo:getComputedStyle(document.querySelector('[data-brand-logo]')).backgroundColor})''')
    assert 224<=geometry['sidebar']<=248
    assert geometry['topbar']==56
    assert geometry['content']>=1100
    assert geometry['logo']=='rgb(37, 99, 235)'
    page.keyboard.press('Control+k')
    expect(page.locator('.global-search input')).to_be_focused()
    page.get_by_label('Kontomenü').click()
    expect(page.get_by_role('link',name='Kontosicherheit',exact=True)).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('[data-account-menu]')).not_to_have_attribute('open','')
    context.close()


def test_docked_object_panel_tabs_row_switch_and_mobile_transition(live_inventory, browser):
    context = browser.new_context(viewport={'width':1672,'height':941})
    page = context.new_page(); sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    rows = page.locator('[data-preview-key]')
    rows.first.locator('[data-object-link]').click()
    dialog = page.get_by_role('dialog',name='Notebook 000',exact=True)
    expect(dialog.get_by_role('tab',name='Übersicht',exact=True)).to_be_visible()
    expect(dialog).to_have_attribute('aria-modal','false')
    geometry = page.evaluate('''()=>({panel:document.querySelector('dialog').getBoundingClientRect().width,
        edge:document.querySelector('dialog').getBoundingClientRect().left,
        list:document.querySelector('.inventory-workspace').getBoundingClientRect().right})''')
    assert 360 <= geometry['panel'] <= 430 and geometry['list'] <= geometry['edge']
    dialog.get_by_role('tab',name='Details',exact=True).focus()
    page.keyboard.press('Enter')
    expect(dialog.get_by_role('tabpanel',name='Details',exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role('tabpanel',name='Details',exact=True)).to_be_visible()
    rows.nth(1).locator('td').nth(4).click()
    dialog = page.get_by_role('dialog',name='Notebook 001',exact=True)
    expect(dialog.get_by_role('tab',name='Übersicht',exact=True)).to_have_attribute('aria-selected','true')
    page.set_viewport_size({'width':390,'height':844})
    expect(dialog).to_have_attribute('aria-modal','true')
    expect(page.locator('body')).not_to_have_class(__import__('re').compile('has-object-panel'))
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    # Switching rows replaced the preview state: one Back closes the whole panel.
    assert '#preview-' not in page.url
    context.close()


def test_object_panel_fetch_failure_retry_and_safe_user_text(live_inventory, browser, isolated_inventory):
    import app as inventory_app
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute('UPDATE devices SET specs=? WHERE id=1', ('{"Label":"<img src=x onerror=alert(1)>","RAM":"32 GB"}',))
        db.commit()
    context = browser.new_context(viewport={'width':1440,'height':900})
    page = context.new_page(); sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    page.route('**/api/inventory/device/1/panel?*',lambda route:route.fulfill(status=503,body='Offline'))
    page.locator('[data-object-link]').first.click()
    dialog = page.get_by_role('dialog',name='Notebook 000',exact=True)
    expect(dialog.get_by_role('alert')).to_contain_text('konnten nicht geladen')
    expect(dialog.get_by_role('link',name='Detailseite',exact=True)).to_have_attribute('href',live_inventory+'/inventory/devices/1')
    page.unroute('**/api/inventory/device/1/panel?*')
    dialog.get_by_role('button',name='Erneut laden').click()
    expect(dialog).to_contain_text('32 GB')
    expect(dialog.locator('img[src=x]')).to_have_count(0)
    expect(dialog).to_contain_text('<img src=x onerror=alert(1)>')
    context.close()


def test_module_groups_and_sidebar_footer_are_keyboard_operable(live_inventory, browser):
    context = browser.new_context(viewport={'width':1440,'height':900})
    page = context.new_page(); sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    sidebar = page.get_by_label('Hauptnavigation',exact=True)
    expect(sidebar.get_by_role('link',name='Bestand',exact=True)).to_be_visible()
    settings = sidebar.locator('.nav-group > summary').filter(has_text='Einstellungen')
    settings.focus(); page.keyboard.press('Enter')
    expect(sidebar.get_by_role('link',name='Server & Updates',exact=True)).to_be_visible()
    sidebar.get_by_role('link',name='Server & Updates',exact=True).click()
    expect(page.get_by_role('checkbox',name='Automatische Updates aktivieren')).to_be_visible()
    sidebar.get_by_role('button',name='Menü minimieren oder erweitern').click()
    expect(page.locator('body')).to_have_class(__import__('re').compile('sidebar-collapsed'))
    sidebar.locator('.nav-group > summary').filter(has_text='Inventar').click()
    expect(sidebar.get_by_role('link',name='Bestand',exact=True)).to_be_visible()
    context.close()


def test_inventory_pagination_stays_visible_with_large_page_and_row_menu(live_inventory, browser):
    context = browser.new_context(viewport={'width':1672,'height':941})
    page = context.new_page(); sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    expect(page.locator('[data-preview-key]')).to_have_count(10)
    footer = page.locator('.table-pagination')
    expect(footer).to_contain_text('1–10 von 40 Einträgen')
    assert footer.bounding_box()['y']+footer.bounding_box()['height'] <= 941
    page.get_by_role('link',name='Nächste Seite',exact=True).click()
    expect(footer).to_contain_text('11–20 von 40 Einträgen')
    expect(page.get_by_role('link',name='Notebook 010',exact=True)).to_be_visible()
    page.get_by_label('Einträge pro Seite',exact=True).select_option('100')
    expect(page.locator('[data-preview-key]')).to_have_count(40)
    assert footer.bounding_box()['y']+footer.bounding_box()['height'] <= 941
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight+1')
    page.locator('.inventory-table-scroll').evaluate('(table)=>table.scrollTop=table.scrollHeight')
    menu = page.locator('[data-preview-key]').last.locator('[data-row-menu]')
    menu.locator('summary').click()
    expect(menu.get_by_role('link',name='Detailseite',exact=True)).to_be_visible()
    rect = menu.locator('.row-menu-panel').bounding_box()
    assert rect['y']>=0 and rect['y']+rect['height']<=941
    page.keyboard.press('Escape');expect(menu).not_to_have_attribute('open','')
    context.close()


def test_inventory_filters_selection_export_and_create_menu(live_inventory, browser):
    context = browser.new_context(viewport={'width':1672,'height':941},accept_downloads=True)
    page = context.new_page(); sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    page.get_by_label('Kategorie',exact=True).select_option(label='Notebooks')
    expect(page.locator('[data-preview-key]')).to_have_count(10)
    assert 'category=device' in page.url
    page.get_by_role('searchbox',name='Bestand durchsuchen',exact=True).fill('QA-039')
    page.get_by_role('searchbox',name='Bestand durchsuchen',exact=True).press('Enter')
    expect(page.locator('[data-preview-key]')).to_have_count(1)
    page.get_by_role('checkbox',name='Notebook 039 auswählen',exact=True).check()
    expect(page.locator('[data-inventory-preview]')).not_to_be_visible()
    expect(page.locator('[data-selection-count]')).to_have_text('1 Eintrag dieser Seite ausgewählt')
    with page.expect_download() as download:
        page.get_by_role('link',name='Auswahl exportieren',exact=True).click()
    content = Path(download.value.path()).read_text(encoding='utf-8-sig')
    assert 'Notebook 039' in content and 'Notebook 038' not in content
    page.get_by_role('button',name='Auswahl aufheben',exact=True).click()
    expect(page.locator('[data-selection-toolbar]')).not_to_be_visible()
    page.locator('[data-create-menu] > summary').click()
    page.get_by_role('link',name='Gerät erfassen',exact=True).click()
    expect(page.get_by_test_id('device-modal')).to_be_visible()
    context.close()


def test_composite_filter_borders_are_never_covered_by_inner_fields(live_inventory,browser):
    context=browser.new_context(viewport={'width':1672,'height':941},reduced_motion='reduce')
    page=context.new_page();sign_in(page,live_inventory);page.goto(live_inventory+'/inventory')
    page.locator('[data-object-link]').first.click()
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':941})
        if width<1280:page.keyboard.press('Escape')
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            bounds=page.evaluate('''()=>[...document.querySelectorAll('.filter-search,.filter-select')].map(parent=>{
                const inner=parent.querySelector('input,select'),p=parent.getBoundingClientRect(),i=inner.getBoundingClientRect();
                return {top:i.top-p.top,bottom:p.bottom-i.bottom,border:getComputedStyle(parent).borderTopWidth,
                    innerBorder:getComputedStyle(inner).borderTopWidth};
            })''')
            assert bounds and all(item['top']>=.9 and item['bottom']>=.9 and item['border']=='1px' and item['innerBorder']=='0px' for item in bounds),(width,theme,bounds)
    page.get_by_role('searchbox',name='Bestand durchsuchen',exact=True).focus()
    assert page.locator('.filter-search').evaluate("el=>getComputedStyle(el).outlineStyle")=='solid'
    context.close()
