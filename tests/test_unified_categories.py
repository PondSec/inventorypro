import json
import pytest
import app as inventory_app
from test_unified_asset_routes import unified_client
from test_inventory_workspace import client


def create(client,name,fields=None):
    response=client.post('/api/inventory/categories',json={'name':name,'fields':fields or {}})
    assert response.status_code==201,response.json
    return next(item for item in client.get('/api/inventory/categories').json['categories'] if item['id']==response.json['id'])


def test_used_converted_category_requires_target_and_keeps_all_physical_assets(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();source=db.execute('SELECT m.asset_category_id FROM asset_legacy_categories m WHERE EXISTS(SELECT 1 FROM assets a WHERE a.category_id=m.asset_category_id) LIMIT 1').fetchone()[0]
        legacy=db.execute('SELECT category_id FROM asset_legacy_categories WHERE asset_category_id=?',(source,)).fetchone()[0]
        originals=[tuple(row) for row in db.execute('SELECT id,name,serial_number,specs,created_at FROM assets ORDER BY id')]
        devices=[tuple(row) for row in db.execute('SELECT id,name,serial_number,specs,created_at FROM devices ORDER BY id')]
    category=next(item for item in client.get('/api/inventory/categories').json['categories'] if item['id']==source)
    target=create(client,'QA unified target')
    response=client.delete(f'/api/inventory/categories/{source}',json={'expectedRevision':category['revision']})
    assert response.status_code==409 and response.json['code']=='category_in_use'
    response=client.delete(f'/api/inventory/categories/{source}',json={'expectedRevision':category['revision'],'target_category_id':target['id']})
    assert response.status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert [tuple(row) for row in db.execute('SELECT id,name,serial_number,specs,created_at FROM assets ORDER BY id')]==originals
        assert [tuple(row) for row in db.execute('SELECT id,name,serial_number,specs,created_at FROM devices ORDER BY id')]==devices
        assert db.execute('SELECT count(*) FROM assets WHERE category_id=?',(target['id'],)).fetchone()[0]==40
        assert db.execute('SELECT asset_category_id FROM asset_legacy_categories WHERE category_id=?',(legacy,)).fetchone()[0]==target['id']
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_category_fields_versions_and_failed_deletion_keep_specs(unified_client):
    client=unified_client;category=create(client,'QA CPU fields',{'Taktrate':{'type':'number','unit':'GHz'},'Sockel':{'type':'select','options':['AM5','LGA1700']}})
    asset=client.post('/api/inventory/assets',json={'name':'QA CPU','category_id':category['id'],'specs':{'Taktrate':3.2,'Sockel':'AM5','Extra':'Kept'}}).json
    updated=client.put(f"/api/inventory/categories/{category['id']}",json={'name':'QA CPU fields new','expectedRevision':category['revision'],'fields':{}})
    assert updated.status_code==200
    assert client.put(f"/api/inventory/categories/{category['id']}",json={'name':'Stale','expectedRevision':category['revision']}).status_code==409
    assert client.get(f"/api/inventory/assets/{asset['id']}").json['specs']=={'Taktrate':3.2,'Sockel':'AM5','Extra':'Kept'}
    assert client.get('/inventory/categories').status_code==200


def test_category_management_keeps_historical_scope_boundaries(unified_client):
    from test_product_catalog_routes import role
    client=unified_client;original=create(client,'QA original asset category')
    with inventory_app.app.app_context():source=inventory_app.get_db().execute('SELECT asset_category_id FROM asset_legacy_categories LIMIT 1').fetchone()[0]
    role(client,'only-device-taxonomy',['categories.view','categories.manage','devices.view'])
    rows=client.get('/api/inventory/categories').json['categories'];source_row=next(item for item in rows if item['id']==source)
    assert source_row['can_edit'] and not next(item for item in rows if item['id']==original['id'])['can_edit']
    assert client.put(f"/api/inventory/categories/{original['id']}",json={'name':'Forbidden','expectedRevision':original['revision']}).status_code==403
    assert client.put(f'/api/inventory/categories/{source}',json={'name':'QA permitted template','fields':{},'expectedRevision':source_row['revision']}).status_code==200


def test_empty_legacy_category_can_be_removed_without_leaving_a_recreated_alias(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();legacy=db.execute("INSERT INTO categories(name,fields) VALUES ('QA empty legacy','{}')").lastrowid;db.commit()
        source=db.execute('SELECT asset_category_id FROM asset_legacy_categories WHERE category_id=?',(legacy,)).fetchone()[0]
    category=next(item for item in client.get('/api/inventory/categories').json['categories'] if item['id']==source)
    assert client.delete(f'/api/inventory/categories/{source}',json={'expectedRevision':category['revision']}).status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert not db.execute('SELECT 1 FROM categories WHERE id=?',(legacy,)).fetchone()
        assert not db.execute('SELECT 1 FROM asset_legacy_categories WHERE category_id=?',(legacy,)).fetchone()
