"""The shared visual contract is checked in real browsers, using isolated data."""
from playwright.sync_api import expect
from test_enterprise_browser import browser, live_inventory, sign_in


def test_shell_geometry_and_keyboard_controls(live_inventory, browser):
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page();sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory')
    expect(page.locator('main h1')).to_have_text('Gesamter Bestand')
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
        list:document.querySelector('.workspace-panel').getBoundingClientRect().right})''')
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
