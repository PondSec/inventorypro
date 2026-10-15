"""Real browsers with CSRF enabled, synthetic inventory and isolated live server."""
import os
from pathlib import Path
import threading

import pytest
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server


@pytest.fixture
def live_inventory(isolated_inventory):
    previous = isolated_inventory.config['TESTING']
    isolated_inventory.config['TESTING'] = False
    server = make_server('127.0.0.1', 0, isolated_inventory, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        isolated_inventory.config['TESTING'] = previous


@pytest.fixture(params=['chromium', 'firefox'])
def browser(request):
    with sync_playwright() as playwright:
        instance = getattr(playwright, request.param).launch()
        yield instance
        instance.close()


def sign_in(page, base_url):
    page.goto(base_url + '/login')
    page.get_by_label('Benutzername').fill('admin')
    page.locator('input[name=password]').fill('Synthetic-Test-Only-42!')
    page.get_by_role('button', name='Anmelden', exact=True).click()
    page.wait_for_url(base_url + '/')
    page.wait_for_load_state('networkidle')


def test_shared_shell_routes_and_themes(live_inventory, browser, tmp_path):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    sign_in(page, live_inventory)
    for route in ['/', '/tickets', '/admin/tickets/categories', '/settings', '/procurement', '/health',
                  '/stats', '/dependencies', '/time-machine', '/knowledge', '/roadmap', '/locations', '/users', '/account/security']:
        response = page.goto(live_inventory + route)
        assert response.status == 200, route
        page.wait_for_load_state('networkidle')
        expect(page.locator('.app-shell')).to_have_count(1)
        expect(page.locator('.app-sidebar')).to_have_count(1)
        expect(page.locator('main')).to_have_count(1)
        expect(page.locator('.app-header')).to_be_visible()
        expect(page.get_by_role('button', name='Navigation umschalten')).to_be_visible()
        assert not errors, (route, errors)
    context.close()


def test_auto_updates_toggle_persists_with_csrf(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/settings')
    toggle = page.get_by_role('checkbox', name='Automatische Updates aktivieren')
    expect(toggle).to_be_visible()
    page.get_by_label('E-Mail-Adresse für Backup-Benachrichtigungen').fill('qa@example.com')
    for enabled in (True, False):
        toggle.set_checked(enabled)
        save = page.locator('form').filter(has=toggle).locator('button[type=submit]')
        with page.expect_response(lambda r: r.url.endswith('/api/settings/server') and r.request.method == 'PUT') as saved:
            save.click()
        assert saved.value.status == 200, saved.value.text()
        assert saved.value.json()['settings']['updates']['autoUpdateEnabled'] is enabled
        page.reload()
        expect(toggle).to_be_checked(checked=enabled)
    context.close()


def test_settings_tabs_select_real_sections_and_preserve_legacy_links(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/settings?section=branding')
    expect(page.locator("section[x-show=\"activeSection === 'customize'\"]")).to_be_visible()
    page.get_by_role('link', name='Server', exact=True).click()
    expect(page.get_by_role('checkbox', name='Automatische Updates aktivieren')).to_be_visible()
    page.go_back()
    expect(page.locator("section[x-show=\"activeSection === 'customize'\"]")).to_be_visible()
    page.goto(live_inventory + '/settings?section=notifications')
    expect(page.get_by_role('checkbox', name='Automatische Updates aktivieren')).to_be_visible()
    context.close()


@pytest.mark.parametrize('width', [320, 390, 1440])
def test_shell_responsive_focus_and_theme(live_inventory, browser, tmp_path, width):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    sign_in(page, live_inventory)
    artifacts = Path(os.environ.get('QA_ARTIFACT_DIR', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    for theme in ('light', 'dark'):
        page.evaluate('(theme) => InventoryTheme.set(theme)', theme)
        for route in ('/', '/tickets', '/settings'):
            page.goto(live_inventory + route)
            assert page.locator('html').evaluate('(el) => el.classList.contains("dark")') is (theme == 'dark')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (route, theme, width)
            if route == '/tickets':
                action = page.get_by_test_id('open-ticket-modal').bounding_box()
                assert action and action['x'] + action['width'] <= width + 1
            page.screenshot(path=str(artifacts / f'{browser.browser_type.name}-{route.strip("/") or "dashboard"}-{width}-{theme}.png'), full_page=True)
        page.goto(live_inventory + '/')
        page.get_by_test_id('open-device-modal').click()
        panel = page.get_by_test_id('device-modal')
        expect(panel).to_be_visible()
        for _ in range(20):
            page.keyboard.press('Tab')
            assert panel.evaluate('(el) => el.contains(document.activeElement)')
        page.keyboard.press('Escape')
        expect(panel).not_to_be_visible()
    context.close()


def test_inventory_search_detail_and_existing_editor(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/inventory')
    page.get_by_role('searchbox', name='Bestand durchsuchen', exact=True).fill('QA-039')
    page.get_by_role('searchbox', name='Bestand durchsuchen', exact=True).press('Enter')
    expect(page.locator('tbody tr')).to_have_count(1)
    page.get_by_role('link', name='Notebook 039', exact=True).click()
    expect(page.get_by_role('heading', name='Notebook 039', exact=True)).to_be_visible()
    page.get_by_role('link', name='Detailseite', exact=True).click()
    page.get_by_role('link', name='Hardware', exact=True).click()
    expect(page.get_by_role('heading', name='Hardware', exact=True)).to_be_visible()
    page.go_back()
    expect(page.get_by_role('heading', name='Übersicht', exact=True)).to_be_visible()
    note = 'Synthetic note from browser'
    page.get_by_label('Neue Notiz', exact=True).fill(note)
    page.get_by_role('button', name='Notiz hinzufügen').click()
    expect(page.get_by_text(note, exact=True)).to_be_visible()
    page.get_by_role('link', name='Bearbeiten', exact=True).click()
    expect(page.get_by_test_id('device-modal')).to_be_visible(timeout=15000)
    context.close()


def test_dashboard_task_links_open_exact_work_list(live_inventory, browser):
    context=browser.new_context(viewport={'width':1280,'height':900})
    page=context.new_page()
    sign_in(page,live_inventory)
    task=page.locator('.task-list a').filter(has_text='Inventardaten vervollständigen')
    expect(task.locator('.task-count')).to_have_text('40')
    task.click()
    assert 'filter=missing_identity' in page.url
    expect(page.locator('.list-summary[role=status]')).to_contain_text('40 Einträge')
    context.close()


def test_quick_capture_preserves_unsaved_fields_and_saves(live_inventory, browser):
    context=browser.new_context(viewport={'width':1280,'height':900})
    page=context.new_page()
    sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory/new')
    modal=page.get_by_test_id('device-modal')
    expect(modal).to_be_visible()
    page.get_by_label('Name (Pflichtfeld)',exact=True).fill('QA new notebook')
    page.get_by_label('Vorlage (Pflichtfeld)',exact=True).select_option(label='Notebooks')
    page.get_by_label('Inventar-/Seriennummer',exact=True).fill('QA-CAPTURE')
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.get_by_test_id('device-modal-close').click()
    expect(modal).to_be_visible()
    expect(page.get_by_label('Name (Pflichtfeld)',exact=True)).to_have_value('QA new notebook')
    with page.expect_response(lambda response: response.url.endswith('/api/devices') and response.request.method=='POST') as created:
        modal.get_by_role('button',name='Speichern',exact=True).click()
    assert created.value.status==201,created.value.text()
    expect(modal).not_to_be_visible()
    page.goto(live_inventory+'/inventory?q=QA-CAPTURE')
    expect(page.get_by_role('link',name='QA new notebook',exact=True)).to_be_visible()
    context.close()


def test_device_selection_is_searchable_paginated_and_visible(live_inventory,browser):
    context=browser.new_context(viewport={'width':1280,'height':900})
    page=context.new_page()
    sign_in(page,live_inventory)
    page.get_by_test_id('dashboard-action-menu-toggle').click()
    page.get_by_role('button',name='Komponente oder Set erfassen',exact=True).click()
    picker=page.get_by_test_id('device-assignment-picker')
    expect(picker).to_be_visible()
    expect(picker.locator('.picker-result')).to_have_count(20)
    picker.get_by_role('searchbox').fill('QA-039')
    expect(picker.locator('.picker-result')).to_have_count(1)
    picker.locator('.picker-result input').check()
    expect(picker.get_by_role('button',name='Notebook 039 aus Auswahl entfernen')).to_be_visible()
    picker.get_by_role('searchbox').fill('QA-001')
    expect(picker.get_by_role('button',name='Notebook 039 aus Auswahl entfernen')).to_be_visible()
    context.close()


def test_storage_wizard_reuses_dimensions_saves_and_opens_existing_3d(live_inventory,browser,isolated_inventory,tmp_path):
    import json
    import app as inventory_app
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        fields={name:{'type':'number','unit':'cm'} for name in ['Breite','Höhe','Tiefe']}
        category=db.execute('INSERT INTO asset_categories(name,fields) VALUES (?,?)',('Planning QA',json.dumps(fields))).lastrowid
        for name,value in [('QA Container',10),('QA Box',2)]:
            db.execute('INSERT INTO assets(name,category_id,specs) VALUES (?,?,?)',(name,category,json.dumps({axis:value for axis in fields})))
        db.commit()
    context=browser.new_context(viewport={'width':1280,'height':1000},reduced_motion='reduce')
    page=context.new_page()
    sign_in(page,live_inventory)
    page.goto(live_inventory+'/inventory/planning')
    page.get_by_role('searchbox',name='Inventareinträge suchen').fill('QA Container')
    page.locator('.picker-result').filter(has_text='QA Container').get_by_role('button',name='Als Behälter wählen').click()
    page.get_by_role('button',name='Nächster Schritt').click()
    expect(page.get_by_label('Behälter Breite',exact=True)).to_have_value('100')
    expect(page.get_by_label('Behälter Höhe',exact=True)).to_have_value('100')
    page.get_by_role('button',name='Nächster Schritt').click()
    page.get_by_role('searchbox',name='Inventareinträge suchen').fill('QA Box')
    page.locator('.picker-result').filter(has_text='QA Box').get_by_role('button',name='Hinzufügen').click()
    expect(page.get_by_label('QA Box Breite',exact=True)).to_have_value('20')
    page.get_by_role('button',name='Nächster Schritt').click()
    page.get_by_label('Wandabstand',exact=True).fill('2')
    page.get_by_label('Abstand zwischen Gegenständen',exact=True).fill('3')
    page.get_by_role('button',name='Packliste berechnen').click()
    expect(page.locator('.planning-result')).to_contain_text('1 von 1 Stück eingeplant.')
    page.get_by_label('Planname',exact=True).fill('Browser QA plan')
    with page.expect_response(lambda response:response.url.endswith('/api/planning/plans') and response.request.method=='POST') as saved:
        page.get_by_role('button',name='Plan speichern',exact=True).click()
    assert saved.value.status==201,saved.value.text()
    page.screenshot(path=str(tmp_path/'planning-packlist.png'),full_page=True)
    page.get_by_role('button',name='3D-Ansicht öffnen',exact=True).click()
    expect(page.locator('.binpacking-modal-panel')).to_be_visible(timeout=15000)
    page.screenshot(path=str(tmp_path/'planning-3d.png'))
    context.close()


def test_saved_inventory_views_restore_filters_and_escape_names(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/inventory?q=QA-039&kind=device&sort=name&direction=desc')
    page.locator('[data-filter-menu] > summary').click()
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    label = '<img src=x onerror=alert(1)>'
    page.get_by_label('Name der Ansicht', exact=True).fill(label)
    page.get_by_role('button', name='Aktuelle Ansicht speichern').click()
    expect(page.locator('[data-view-status]')).to_have_text('Ansicht gespeichert.')
    expect(page.locator('[data-view-list] img')).to_have_count(0)
    page.goto(live_inventory + '/inventory')
    page.locator('[data-filter-menu] > summary').click()
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    page.locator('[data-view-list]').get_by_role('link', name=label, exact=True).click()
    expect(page.get_by_role('link', name='Notebook 039', exact=True)).to_be_visible()
    expect(page.get_by_role('link', name='Notebook 038', exact=True)).to_have_count(0)
    assert 'q=QA-039' in page.url and 'direction=desc' in page.url
    page.locator('[data-filter-menu] > summary').click()
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    page.locator('[data-view-list]').get_by_role('button').click()
    page.reload()
    page.locator('[data-filter-menu] > summary').click()
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    expect(page.locator('[data-view-list] li')).to_have_count(0)
    context.close()


def test_inventory_preview_focus_escape_and_history(live_inventory, browser):
    context = browser.new_context(viewport={'width': 390, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/inventory?q=QA-039')
    trigger = page.get_by_role('link', name='Notebook 039', exact=True)
    expect(page.locator('.data-table button')).to_have_count(0)
    expect(page.get_by_role('link', name='Öffnen', exact=True)).to_have_count(0)
    page.locator('[data-preview-key] td').nth(4).click()
    dialog = page.get_by_role('dialog', name='Notebook 039')
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text('QA-039')
    expect(dialog.get_by_role('button', name='Details schließen')).to_be_focused()
    for _ in range(5):
        page.keyboard.press('Tab')
        assert page.evaluate('document.querySelector("dialog").contains(document.activeElement)')
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(trigger).to_be_focused()
    trigger.focus()
    page.keyboard.press('Enter')
    page.go_back()
    expect(dialog).not_to_be_visible()
    page.go_forward()
    expect(dialog).to_be_visible()
    page.reload()
    expect(dialog).to_be_visible()
    dialog.get_by_role('link', name='Detailseite').click()
    expect(page.locator('.object-summary')).to_contain_text('QA-039')
    page.go_back()
    expect(dialog).to_be_visible()
    context.close()


def test_inventory_modified_click_multi_tab_and_no_script_navigation(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/inventory?q=QA-039')
    requests = []
    context.on('request', lambda request: requests.append(request.url) if request.url.endswith('/api/customize') else None)
    link = page.get_by_role('link', name='Notebook 039', exact=True)
    for modifier in ('ctrlKey', 'metaKey'):
        assert link.evaluate('''(link, modifier) => {
            let blocked;
            document.addEventListener('click', event => {
                blocked = event.defaultPrevented; event.preventDefault();
            }, {once:true});
            link.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, [modifier]:true}));
            return blocked;
        }''', modifier) is False
    # Follow the native link target in a second real tab. Cmd/middle-click popup
    # events are unreliable in the macOS headless Chromium protocol; the handlers'
    # default-prevention contract above is verified independently in both engines.
    detail = context.new_page()
    detail.goto(link.evaluate('link => link.href'))
    expect(detail.locator('.object-summary')).to_contain_text('QA-039')
    detail.wait_for_timeout(500)
    assert len(requests) <= 3, 'Two tabs must not repeatedly refresh each other’s customization cache'
    expect(page.locator('[data-inventory-preview]')).not_to_be_visible()
    detail.close()
    page.route('**/static/inventory-preview.js*', lambda route: route.abort())
    page.reload()
    page.get_by_role('link', name='Notebook 039', exact=True).click()
    expect(page.locator('.object-summary')).to_contain_text('QA-039')
    context.close()


def test_shared_tabs_keyboard_and_panel_semantics(live_inventory, browser, isolated_inventory):
    import app as inventory_app
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute("INSERT INTO tickets(title,description,created_by,status) VALUES ('QA keyboard ticket','Synthetic','admin','open')")
        db.commit()
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    for route in ('/procurement', '/users', '/health', '/tickets?queue=all-open'):
        page.goto(live_inventory + route)
        if route.startswith('/tickets'):
            page.locator('[data-ticket-index]').first.click()
        tabs = page.get_by_role('tablist').get_by_role('tab')
        expect(tabs.first).to_be_visible()
        tabs.first.focus()
        page.keyboard.press('End')
        expect(tabs.last).to_be_focused()
        expect(tabs.last).to_have_attribute('aria-selected', 'true')
        panel_id = tabs.last.get_attribute('aria-controls')
        expect(page.locator('#' + panel_id)).to_be_visible()
        assert page.locator('#' + panel_id).get_attribute('role') == 'tabpanel'
        page.keyboard.press('Home')
        expect(tabs.first).to_be_focused()
        expect(tabs.first).to_have_attribute('aria-selected', 'true')
        page.keyboard.press('ArrowLeft')
        expect(tabs.last).to_be_focused()
        page.keyboard.press('ArrowRight')
        expect(tabs.first).to_be_focused()
        assert tabs.evaluate_all('(nodes) => nodes.filter(node => node.tabIndex === 0).length') == 1
    context.close()


def test_shared_design_defaults_preserve_instance_customization(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    assert page.evaluate('InventoryCustomization.defaults().baseTokens.spacing.radius.md') == 6
    result = page.evaluate('''async () => {
        const response = await fetch('/api/customize', {method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({baseTokens: {spacing: {radius: {md: 11}}}})});
        return response.status;
    }''')
    assert result == 200
    page.reload()
    page.wait_for_load_state('networkidle')
    assert page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--radius-md").trim()') == '11px'
    page.goto(live_inventory + '/inventory')
    page.wait_for_load_state('networkidle')
    assert page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--radius-md").trim()') == '11px'
    context.close()


def test_knowledge_search_uses_current_query_and_pages(live_inventory, browser, isolated_inventory):
    import app as inventory_app
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        for index in range(60):
            db.execute('INSERT INTO knowledge_entries(title,content,summary) VALUES (?,?,?)',
                       (f'QA knowledge {index:03}', 'Synthetic content', 'Synthetic summary'))
        db.commit()
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/knowledge')
    search = page.get_by_label('Suche', exact=True)
    search.fill('QA knowledge')
    navigation = page.get_by_role('navigation', name='Seiten in der Wissensbasis')
    expect(navigation).to_contain_text('60 Einträge')
    navigation.get_by_role('button', name='Weiter', exact=True).click()
    expect(navigation).to_contain_text('Seite 2 von 3')
    search.fill('QA knowledge 059')
    expect(navigation).to_contain_text('Seite 1 von 1 · 1 Einträge')
    page.get_by_role('button').filter(has=page.locator('p', has_text='QA knowledge 059')).first.click()
    expect(page.locator('h3').filter(has_text='QA knowledge 059')).to_be_visible()
    context.close()


def test_semantic_status_contrast_and_theme_without_browser_storage(live_inventory, browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    def luminance(hex_color):
        channels = [int(hex_color[index:index+2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    for theme in ('light', 'dark'):
        page.evaluate('(theme) => InventoryTheme.set(theme)', theme)
        colors = page.evaluate('''() => {
            const css = getComputedStyle(document.documentElement);
            return Object.fromEntries(['surface','success','warning','danger','info'].map(name =>
                [name, css.getPropertyValue('--color-' + name).trim()]));
        }''')
        for state in ('success','warning','danger','info'):
            values = sorted([luminance(colors[state]), luminance(colors['surface'])])
            assert (values[1]+.05)/(values[0]+.05) >= 4.5, (theme, state, colors)
    context.close()
    blocked = browser.new_context()
    blocked.add_init_script('''Object.defineProperty(window, 'localStorage', {
        get() { throw new DOMException('Storage blocked', 'SecurityError'); }
    });''')
    page = blocked.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(live_inventory + '/login')
    expect(page.get_by_label('Benutzername')).to_be_visible()
    page.get_by_role('button', name='Dark Mode').click()
    assert page.evaluate('document.documentElement.classList.contains("dark")')
    assert not errors, errors
    blocked.close()
