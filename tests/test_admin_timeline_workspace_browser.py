from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live


def test_user_table_pagination_and_optional_create_with_retry(unified_live,browser):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();password=inventory_app.generate_password_hash('Synthetic-Test-Only-42!')
        for index in range(25):db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',(f'qa-member-{index:02}',password))
        db.commit()
    page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,unified_live);page.goto(unified_live+'/users')
    expect(page.locator('tbody tr:visible')).to_have_count(10)
    page.get_by_role('button',name='Weiter',exact=True).click();expect(page.get_by_text('Seite 2 von 3',exact=True)).to_be_visible()
    page.get_by_text('Benutzer hinzufügen',exact=True).click()
    form=page.locator('[data-user-create]');form.get_by_label('Benutzername',exact=True).fill('qa-new-member')
    form.get_by_label('Startpasswort',exact=True).fill('Synthetic-Test-Only-42!')
    page.route('**/api/users',lambda route:route.fulfill(status=503,json={'error':'QA user unavailable'}) if route.request.method=='POST' else route.continue_())
    form.get_by_role('button',name='Benutzer erstellen',exact=True).click();expect(form.get_by_role('alert')).to_have_text('QA user unavailable')
    expect(form.get_by_label('Benutzername',exact=True)).to_have_value('qa-new-member')
    page.unroute('**/api/users');form.get_by_role('button',name='Benutzer erstellen',exact=True).click()
    expect(page.get_by_role('status')).to_have_text('Benutzer erstellt.')
    expect(form).not_to_be_visible()
    page.get_by_label('Suche',exact=True).fill('qa-new-member');expect(page.locator('tbody tr:visible')).to_have_count(1)
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            for name in ['Benutzer','Rollen & Verzeichnis']:
                page.get_by_role('tab',name=name,exact=True).click()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),(width,theme,name)
    assert not errors,errors
    page.close()


def test_timeline_tasks_history_pages_and_comparison(unified_live,browser):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        for index in range(45):db.execute("INSERT INTO activity_log(username,action,entity_type,entity_id,details) VALUES ('admin','update','device',1,?)",('{"name":"QA event '+str(index)+'"}',))
        db.commit()
    page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,unified_live);page.goto(unified_live+'/time-machine');page.wait_for_load_state('networkidle')
    tabs=page.get_by_role('tablist',name='Zeitmaschinenbereiche')
    expect(page.get_by_role('heading',name='Bestand zum gewählten Datum',exact=True)).to_be_visible()
    tabs.get_by_role('tab',name='Verlauf',exact=True).click()
    events=page.locator('#timeline-panel-history button').filter(has=page.locator('[x-text="change.title"]'))
    expect(events).to_have_count(20)
    page.get_by_role('button',name='Weiter',exact=True).click();expect(page.get_by_text('Seite 2 von 3',exact=True)).to_be_visible()
    events.first.click();expect(page.locator('[x-text="selectedChange?.title"]')).to_contain_text('QA event')
    tabs.get_by_role('tab',name='Vergleich',exact=True).click()
    expect(page.get_by_label('Vergleichsdatum',exact=True)).to_be_enabled()
    expect(page.locator('#timeline-panel-comparison')).not_to_contain_text('Geräte')
    for width in [1920,1672,1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            for name in ['Bestand & Simulation','Verlauf','Vergleich']:
                tabs.get_by_role('tab',name=name,exact=True).click()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),(width,theme,name)
    assert not errors,errors
    page.close()
