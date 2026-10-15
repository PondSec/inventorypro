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
