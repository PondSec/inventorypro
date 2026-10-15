"""Settings tasks retain one safe form in both supported browser engines."""
from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in


def test_task_tabs_validation_network_retry_and_dirty_reload(live_inventory,browser):
    page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/settings')
    tabs=page.get_by_role('tablist',name='Servereinstellungen')
    general=tabs.get_by_role('tab',name='Allgemein',exact=True)
    expect(general).to_have_attribute('aria-selected','true')
    general.focus();page.keyboard.press('ArrowRight')
    expect(tabs.get_by_role('tab',name='Updates',exact=True)).to_be_focused()
    expect(page.get_by_label('Automatische Updates aktivieren',exact=True)).to_be_visible()
    page.keyboard.press('End');expect(tabs.get_by_role('tab',name='Terminalregeln',exact=True)).to_be_focused()
    page.keyboard.press('Home');expect(general).to_be_focused()
    page.get_by_label('Serverport',exact=True).fill('70000')
    tabs.get_by_role('tab',name='Updates',exact=True).click()
    page.get_by_role('button',name='Einstellungen speichern',exact=True).click()
    expect(page.get_by_label('Serverport',exact=True)).to_be_focused()
    expect(page.get_by_role('alert')).to_contain_text('Port muss zwischen')
    page.get_by_label('Serverport',exact=True).fill('5001')
    tabs.get_by_role('tab',name='Sicherung',exact=True).click()
    page.get_by_label('E-Mail-Adresse für Backup-Benachrichtigungen',exact=True).fill('qa@example.com')
    tabs.get_by_role('tab',name='Sicherheit',exact=True).click()
    page.get_by_label('Zulässige IP-Adressen und Netze',exact=True).fill('127.0.0.1')
    page.once('dialog',lambda dialog:dialog.dismiss())
    page.get_by_role('button',name='Neu laden',exact=True).click()
    expect(page.get_by_label('Zulässige IP-Adressen und Netze',exact=True)).to_have_value('127.0.0.1')
    page.route('**/api/settings/server',lambda route:route.fulfill(status=503,json={'error':'QA settings unavailable'}) if route.request.method=='PUT' else route.continue_())
    page.get_by_role('button',name='Einstellungen speichern',exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('QA settings unavailable')
    tabs.get_by_role('tab',name='Allgemein',exact=True).click();expect(page.get_by_label('Serverport',exact=True)).to_have_value('5001')
    page.unroute('**/api/settings/server')
    page.get_by_role('button',name='Einstellungen speichern',exact=True).click()
    expect(page.get_by_role('status')).to_have_text('Einstellungen gespeichert.')
    page.reload();expect(page.get_by_label('Serverport',exact=True)).to_have_value('5001')
    tabs.get_by_role('tab',name='Updates',exact=True).click();page.go_back()
    expect(general).to_have_attribute('aria-selected','true')
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            for name in ['Allgemein','Updates','Sicherung','Daten','Sicherheit','Verbindungen','Terminalregeln']:
                tabs.get_by_role('tab',name=name,exact=True).click()
                expect(page.get_by_role('button',name='Einstellungen speichern',exact=True)).to_be_visible()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),(width,theme,name)
                if width == 390:
                    bounds=page.locator('.settings-savebar').bounding_box()
                    assert bounds and bounds['y']>=56 and bounds['y']+bounds['height']<=900,(theme,name,bounds)
    assert not errors,errors
    page.close()
