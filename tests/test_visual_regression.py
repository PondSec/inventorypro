"""Reviewed macOS Playwright pixels; platform differences never silently rewrite goldens."""
import io
import json
import os
from pathlib import Path
import sys

import pytest
from PIL import Image,ImageChops
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live

BASE=Path(__file__).parent/'visual-baselines'/'darwin'


@pytest.mark.skipif(sys.platform!='darwin',reason='Reviewed pixel baselines are macOS-specific; Linux still runs geometry/theme/interaction contracts and captures artifacts.')
def test_reviewed_inventory_and_photo_drawer_pixels(unified_live,browser,tmp_path):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        db.execute('DELETE FROM product_catalog_seed_history')
        from inventorypro.domains.catalog.seed import initialize_catalog
        initialize_catalog(db,inventory_app.UPLOADS_DIR)
        identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        db.execute("UPDATE assets SET created_at='2026-06-30 10:14:00'")
        db.execute('UPDATE assets SET name=?,specs=? WHERE id=?',('MacBook Air 13″ M4',json.dumps({'Hersteller':'Apple','Modell':'MacBook Air 13″ M4','MPN':'Mac16,12','RAM':'16 GB','Speicher':'512 GB SSD'}),identifier))
        from inventorypro.domains.catalog.matching import sync_inventory
        sync_inventory(db);db.commit()
    page=browser.new_page(viewport={'width':1672,'height':941},locale='de-DE',timezone_id='Europe/Berlin',reduced_motion='reduce')
    sign_in(page,unified_live)
    page.goto(unified_live+'/inventory?q=MacBook')
    page.get_by_role('link',name='MacBook Air 13″ M4',exact=True).click()
    expect(page.get_by_role('dialog',name='MacBook Air 13″ M4',exact=True)).to_be_visible()
    for width,height in [(1672,941),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            page.evaluate('document.fonts.ready')
            page.evaluate("Promise.all([...document.images].filter(image=>image.complete).map(image=>image.decode().catch(()=>{})))")
            page.mouse.move(0,0);page.wait_for_timeout(200)
            actual=page.screenshot(animations='disabled')
            name=f'{browser.browser_type.name}-inventory-photo-{width}-{theme}.png'
            baseline=BASE/name
            if os.environ.get('INVENTORY_UPDATE_VISUAL_BASELINES')=='1':
                BASE.mkdir(parents=True,exist_ok=True);baseline.write_bytes(actual)
            assert baseline.exists(),f'Missing reviewed baseline {baseline}; generate and visually inspect explicitly.'
            expected=Image.open(baseline).convert('RGB');observed=Image.open(io.BytesIO(actual)).convert('RGB')
            assert expected.size==observed.size
            difference=ImageChops.difference(expected,observed)
            red,green,blue=difference.split()
            peak=ImageChops.lighter(ImageChops.lighter(red,green),blue)
            changed=sum(peak.histogram()[17:])
            ratio=changed/(expected.width*expected.height)
            if ratio>0.003:
                (tmp_path/name).write_bytes(actual);difference.save(tmp_path/('diff-'+name))
            assert ratio<=0.003,f'{name}: {ratio:.2%} changed pixels (allowed 0.3%); actual/diff in {tmp_path}'
    page.close()
