from pathlib import Path
import pytest
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser, live_inventory, sign_in


@pytest.fixture
def wishes_live(live_inventory, monkeypatch):
    monkeypatch.delitem(inventory_app.app.config, 'INVENTORY_UNIFIED_ASSETS_ENABLED', raising=False)
    inventory_app.init_db()
    return live_inventory


def test_project_research_partial_acquisition_and_assembly(wishes_live, browser):
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    sign_in(page, wishes_live)
    page.get_by_role('link', name='Wünsche & Projekte', exact=True).click()
    page.get_by_role('button', name='Projekt erstellen').first.click()
    project = page.locator('[data-project-dialog]')
    project.get_by_label('Projektname').fill('Garden workspace')
    project.get_by_label('Budget', exact=True).fill('200')
    project.get_by_role('button', name='Speichern', exact=True).click()
    page.wait_for_url('**/wishes/projects/*')
    expect(page.get_by_role('heading', name='Garden workspace', exact=True)).to_be_visible()
    page.get_by_role('button', name='Bestandteil hinzufügen', exact=True).click()
    wish = page.locator('[data-wish-dialog]')
    wish.get_by_label('Bezeichnung', exact=True).fill('Garden chair')
    wish.get_by_label('Gewünschte Menge').fill('2')
    wish.get_by_label('Preis pro Stück', exact=True).fill('35')
    with page.expect_response(lambda r: r.url.endswith('/api/wishes') and r.request.method == 'POST') as result:
        wish.get_by_role('button', name='Speichern', exact=True).click()
    assert result.value.status == 201
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('button', name='Garden chair', exact=True)).to_be_visible()
    for remaining in [1, 0]:
        page.get_by_role('button', name='Übernahme anpassen: Garden chair', exact=True).click()
        acquire = page.locator('[data-acquire-dialog]')
        expect(acquire.get_by_label('Menge jetzt vorhanden')).to_have_value('1')
        with page.expect_response(lambda r: r.url.endswith('/acquire')) as result:
            acquire.get_by_role('button', name='Im Bestand erfassen', exact=True).click()
        assert result.value.status == 200
        expect(acquire).not_to_be_visible()
        expect(page.locator('.wish-quantity')).to_have_text(f'{2-remaining} / 2')
    page.get_by_role('button', name='Als Asset zusammenstellen', exact=True).click()
    assemble = page.locator('[data-assemble-dialog]')
    with page.expect_response(lambda r: r.url.endswith('/assemble')) as result:
        assemble.get_by_role('button', name='Asset zusammenstellen', exact=True).click()
    assert result.value.status == 200
    expect(page.get_by_role('link', name='Asset ansehen', exact=True)).to_be_visible()
    page.get_by_role('link', name='Asset ansehen', exact=True).click()
    expect(page.get_by_role('heading', name='Garden workspace', exact=True)).to_be_visible()
    assert not errors
    page.close()


def test_standalone_wish_is_inventoried_with_one_click(wishes_live, browser):
    page = browser.new_page()
    sign_in(page, wishes_live)
    page.goto(wishes_live + '/wishes')
    page.get_by_role('button', name='Wunsch hinzufügen').first.click()
    dialog = page.locator('[data-wish-dialog]')
    dialog.get_by_label('Bezeichnung').fill('A cordless drill')
    dialog.get_by_role('button', name='Speichern', exact=True).click()
    expect(dialog).not_to_be_visible()
    with page.expect_response(lambda r: r.url.endswith('/acquire')) as response:
        page.get_by_role('button', name='Habe ich', exact=True).click()
    assert response.value.status == 200
    expect(page.locator('.wish-quantity')).to_have_text('1 / 1')
    expect(page.get_by_role('button', name='Habe ich', exact=True)).to_have_count(0)
    page.get_by_role('button', name='A cordless drill', exact=True).click()
    page.once('dialog',lambda confirmation:confirmation.accept())
    page.get_by_role('button',name='Zuordnung lösen',exact=True).click()
    expect(page.locator('.wish-quantity')).to_have_text('0 / 1')
    with inventory_app.app.app_context():
        assert inventory_app.get_db().execute("SELECT count(*) FROM assets WHERE name='A cordless drill'").fetchone()[0]==1
    page.close()


def test_english_planning_preserves_user_content(wishes_live, browser):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute("UPDATE server_settings SET ui_language='en' WHERE id=1")
        db.commit()
    page = browser.new_page()
    page.goto(wishes_live + '/login')
    page.get_by_label('Username').fill('admin')
    page.locator('input[name=password]').fill('Synthetic-Test-Only-42!')
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.wait_for_url(lambda url: url in {wishes_live+'/', wishes_live+'/inventory'})
    page.goto(wishes_live + '/wishes')
    expect(page.get_by_role('heading', name='Wishes & projects', exact=True)).to_be_visible()
    page.get_by_role('button', name='Add wish').first.click()
    dialog = page.locator('[data-wish-dialog]')
    dialog.get_by_label('Name', exact=True).fill('Nicht übersetzen')
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(page.get_by_role('button', name='Nicht übersetzen', exact=True)).to_be_visible()
    page.get_by_role('button', name='I have this', exact=True).click()
    expect(page.locator('.wish-quantity')).to_have_text('1 / 1')
    page.close()


def test_keyboard_dark_mobile_unsaved_input_and_validation(wishes_live, browser, tmp_path):
    page = browser.new_page(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    sign_in(page, wishes_live)
    page.goto(wishes_live + '/wishes')
    page.get_by_role('button', name='Wunsch hinzufügen').first.click()
    dialog = page.locator('[data-wish-dialog]')
    expect(dialog.get_by_label('Bezeichnung')).to_be_focused()
    dialog.get_by_label('Bezeichnung').fill('A future bicycle')
    page.once('dialog', lambda confirmation: confirmation.dismiss())
    page.keyboard.press('Escape')
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label('Bezeichnung')).to_have_value('A future bicycle')
    dialog.get_by_role('button', name='Speichern', exact=True).click()
    expect(dialog).not_to_be_visible()
    page.evaluate('InventoryTheme.toggle()')
    page.get_by_role('button', name='A future bicycle', exact=True).click()
    expect(dialog.get_by_label('Bezeichnung')).to_have_value('A future bicycle')
    page.screenshot(path=str(tmp_path / 'wish-mobile-dark.png'), full_page=True)
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button', name='A future bicycle', exact=True)).to_be_focused()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()
