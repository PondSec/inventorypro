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
