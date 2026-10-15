import json
import app as inventory_app
from inventorypro.domains.catalog.seed import initialize_catalog
from inventorypro.domains.catalog.matching import sync_object
from inventorypro.domains.catalog.objects import resolve
from inventorypro.domains.catalog.service import delete_model
from test_inventory_workspace import client


def test_offline_seed_includes_real_m4_image_matches_exact_model_and_preserves_deletions(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();db.execute('DELETE FROM product_catalog_seed_history')
        db.execute('UPDATE devices SET specs=? WHERE id=1',(json.dumps({'Hersteller':'Apple','Modellkennung':'Mac16,12'}),))
        assert initialize_catalog(db,inventory_app.UPLOADS_DIR)==1
        state=resolve(db,inventory_app.UPLOADS_DIR,'device',1)
        assert state['source']=='catalog' and state['license_code']=='CC-BY-SA-4.0'
        assert 'Всемилостив' in state['attribution']
        assert state['product_name']=='MacBook Air 13″ M4'
        assert initialize_catalog(db,inventory_app.UPLOADS_DIR)==0
        db.execute('UPDATE devices SET specs=? WHERE id=2',(json.dumps({'Hersteller':'Apple','Modellkennung':'Mac16,13'}),))
        assert sync_object(db,'device',2)['product_id'] is None
        version=db.execute('SELECT updated_at FROM product_models WHERE id=?',(state['product_id'],)).fetchone()[0]
        delete_model(db,state['product_id'],version)
        assert initialize_catalog(db,inventory_app.UPLOADS_DIR)==0
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0]==40


def test_new_and_edited_devices_match_in_the_existing_write_transaction(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute('DELETE FROM product_catalog_seed_history')
        initialize_catalog(db,inventory_app.UPLOADS_DIR);db.commit()
        category=db.execute('SELECT id FROM categories LIMIT 1').fetchone()[0]
    data={'name':'QA New MacBook','category_id':category,'specs':{'Hersteller':'Apple','Modell':'MacBook Air 13 M4'}}
    # Legacy dynamic-field validator only preserves configured fields.
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute('UPDATE categories SET fields=? WHERE id=?',(json.dumps({'Hersteller':'text','Modell':'text'}),category));db.commit()
    created=client.post('/api/devices',json=data)
    assert created.status_code==201
    identifier=created.json['id']
    assert client.get(f'/api/inventory/device/{identifier}/photo').json['source']=='catalog'
    data['specs']['Modell']='MacBook Air 15 M4'
    assert client.put(f'/api/devices/{identifier}',json=data).status_code==200
    assert client.get(f'/api/inventory/device/{identifier}/photo').json['source']=='fallback'


def test_images_reach_real_inventory_and_panel_and_missing_cache_falls_back(client):
    from inventorypro.domains.catalog.media import media_path
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute('DELETE FROM product_catalog_seed_history')
        db.execute('UPDATE devices SET specs=? WHERE id=1',(json.dumps({'Hersteller':'Apple','Modellkennung':'Mac16,12'}),))
        initialize_catalog(db,inventory_app.UPLOADS_DIR);db.commit()
    state=client.get('/api/inventory/device/1/photo').json
    assert state['url'].encode() in client.get('/inventory').data
    assert state['large_url'].encode() in client.get('/api/inventory/device/1/panel?format=html').data
    with inventory_app.app.app_context():media_path(inventory_app.UPLOADS_DIR,state['hash'],'thumb').unlink()
    assert client.get('/api/inventory/device/1/photo').json['source']=='fallback'
    assert state['url'].encode() not in client.get('/inventory').data
