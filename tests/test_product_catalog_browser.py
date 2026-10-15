from io import BytesIO
from PIL import Image
from playwright.sync_api import expect
from test_enterprise_browser import browser, live_inventory, sign_in
import app as inventory_app
from inventorypro.domains.catalog.service import create_model


def upload_file():
    out=BytesIO();Image.new('RGB',(160,100),'navy').save(out,format='PNG')
    return {'name':'synthetic-photo.png','mimeType':'image/png','buffer':out.getvalue()}


def test_real_catalog_create_upload_assign_and_remove_image(live_inventory,browser):
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/inventory/catalog')
    page.get_by_role('button',name='Modell hinzufügen',exact=True).click()
    dialog=page.get_by_role('dialog',name='Produktmodell hinzufügen')
    expect(dialog.get_by_label('Hersteller',exact=True)).to_be_focused()
    dialog.get_by_label('Hersteller',exact=True).fill('QA Maker')
    dialog.get_by_label('Modell',exact=True).fill('QA Model Browser 123')
    dialog.get_by_role('button',name='Modell anlegen').click()
    page.wait_for_url('**/inventory/catalog/*')
    expect(page.get_by_role('heading',name='QA Model Browser 123',exact=True)).to_be_visible()
    page.get_by_text('Bild hinzufügen',exact=True).click()
    page.get_by_label('Bilddatei',exact=True).set_input_files(upload_file())
    page.get_by_role('checkbox').check()
    page.get_by_role('button',name='Bild speichern',exact=True).click()
    expect(page.get_by_text('Hauptbild',exact=True)).to_be_visible()
    image=page.locator('.catalog-image-item img')
    expect(image).to_be_visible();assert image.evaluate('img=>img.complete && img.naturalWidth>0')
    page.goto(live_inventory+'/inventory/device/1/photo')
    page.get_by_role('searchbox',name='Im Katalog suchen').fill('QA Model Browser')
    page.get_by_role('button',name='Suchen',exact=True).click()
    page.get_by_role('button',name='Zuordnen',exact=True).click()
    expect(page.locator('.photo-preview img')).to_be_visible()
    page.goto(live_inventory+'/inventory')
    first=page.locator('[data-object-link]').first
    expect(first.locator('img')).to_be_visible()
    first.click();expect(page.locator('.object-header img')).to_be_visible()
    page.get_by_role('link',name='Bild verwalten',exact=True).click()
    page.get_by_role('button',name='Nur Symbol anzeigen',exact=True).click()
    expect(page.locator('.photo-preview img')).to_have_count(0)
    page.get_by_role('button',name='Bilder anzeigen',exact=True).click()
    expect(page.locator('.photo-preview img')).to_be_visible()
    page.get_by_label('Bilddatei',exact=True).set_input_files(upload_file())
    page.get_by_role('checkbox').check();page.get_by_role('button',name='Foto speichern',exact=True).click()
    expect(page.get_by_role('button',name='Eigenes Foto entfernen')).to_be_visible()
    page.get_by_role('button',name='Eigenes Foto entfernen').click()
    expect(page.get_by_role('button',name='Eigenes Foto entfernen')).to_have_count(0)
    expect(page.locator('.photo-preview img')).to_be_visible()
    assert not errors,errors
    context.close()


def test_catalog_mobile_keyboard_and_model_names_are_safe(live_inventory,browser):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();create_model(db,{'manufacturer':'QA','name':'<img src=x onerror=alert(1)> Model 99'});db.commit()
    context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
    sign_in(page,live_inventory);page.goto(live_inventory+'/inventory/catalog')
    page.get_by_role('button',name='Modell hinzufügen',exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible();page.keyboard.press('Escape')
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.get_by_role('button',name='Modell hinzufügen',exact=True)).to_be_focused()
    for theme in ['light','dark']:
        page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        assert page.locator('img[src=x]').count()==0
        page.get_by_role('link',name='<img src=x onerror=alert(1)> Model 99',exact=True).click()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        page.go_back()
    context.close()
