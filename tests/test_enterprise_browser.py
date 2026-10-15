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
    page.get_by_role('searchbox', name='Suche', exact=True).fill('QA-039')
    page.get_by_role('button', name='Anwenden', exact=True).click()
    expect(page.locator('tbody tr')).to_have_count(1)
    page.get_by_role('link', name='Notebook 039', exact=True).click()
    expect(page.get_by_role('heading', name='Notebook 039', exact=True)).to_be_visible()
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
    expect(page.locator('.list-summary')).to_contain_text('40 Einträge')
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
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    label = '<img src=x onerror=alert(1)>'
    page.get_by_label('Name der Ansicht', exact=True).fill(label)
    page.get_by_role('button', name='Aktuelle Ansicht speichern').click()
    expect(page.locator('[data-view-status]')).to_have_text('Ansicht gespeichert.')
    expect(page.locator('[data-view-list] img')).to_have_count(0)
    page.goto(live_inventory + '/inventory')
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    page.locator('[data-view-list]').get_by_role('link', name=label, exact=True).click()
    expect(page.get_by_role('link', name='Notebook 039', exact=True)).to_be_visible()
    expect(page.get_by_role('link', name='Notebook 038', exact=True)).to_have_count(0)
    assert 'q=QA-039' in page.url and 'direction=desc' in page.url
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    page.locator('[data-view-list]').get_by_role('button').click()
    page.reload()
    page.get_by_text('Gespeicherte Ansichten', exact=True).click()
    expect(page.locator('[data-view-list] li')).to_have_count(0)
    context.close()


def test_inventory_preview_focus_escape_and_history(live_inventory, browser):
    context = browser.new_context(viewport={'width': 390, 'height': 900})
    page = context.new_page()
    sign_in(page, live_inventory)
    page.goto(live_inventory + '/inventory?q=QA-039')
    trigger = page.get_by_role('button', name='Notebook 039 kurz ansehen', exact=True)
    trigger.click()
    dialog = page.get_by_role('dialog', name='Kurzansicht')
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text('QA-039')
    expect(dialog.get_by_role('button', name='Schließen')).to_be_focused()
    for _ in range(5):
        page.keyboard.press('Tab')
        assert page.evaluate('document.querySelector("dialog").contains(document.activeElement)')
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(trigger).to_be_focused()
    trigger.click()
    page.go_back()
    expect(dialog).not_to_be_visible()
    page.go_forward()
    expect(dialog).to_be_visible()
    page.reload()
    expect(dialog).to_be_visible()
    dialog.get_by_role('link', name='Vollständige Details öffnen').click()
    expect(page.locator('.object-summary')).to_contain_text('QA-039')
    page.go_back()
    expect(dialog).to_be_visible()
    context.close()
