from playwright.sync_api import expect
import app as inventory_app
from inventorypro.domains.catalog import jobs
from inventorypro.domains.catalog.matching import sync_object
from test_enterprise_browser import browser,live_inventory,sign_in
from test_product_lookup_jobs import provider,enable


def test_background_photo_appears_without_reloading_or_losing_search(live_inventory,browser,monkeypatch):
    provider(monkeypatch)
    page=browser.new_page()
    sign_in(page,live_inventory)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();enable(db)
        db.execute("UPDATE devices SET name='Apple AirPods 4 ANC',specs='{}' WHERE id=1")
        sync_object(db,'device',1);db.commit()
    page.goto(live_inventory+'/inventory?q=AirPods')
    page.wait_for_load_state('networkidle')
    row=page.locator('[data-preview-key="device-1"]')
    expect(row.locator('.product-thumbnail img')).to_have_count(0)
    search=page.locator('[data-inventory-filters] input[type=search]')
    search.fill('AirPods pending research')
    search.focus()
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert jobs.process_next(db,inventory_app.UPLOADS_DIR)
    expect(row.locator('.product-thumbnail img')).to_be_visible(timeout=15000)
    expect(search).to_have_value('AirPods pending research')
    expect(search).to_be_focused()
    assert page.url.endswith('/inventory?q=AirPods')
    page.close()
