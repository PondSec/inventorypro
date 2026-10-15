import pytest
import app as inventory_app
from test_inventory_workspace import client
from inventorypro.domains.inventory.unification import convert_inventory


@pytest.fixture
def unified_client(client):
    with inventory_app.app.app_context():db=inventory_app.get_db();convert_inventory(db);db.commit()
    return client


def create(client,name):
    response=client.post('/api/inventory/assets',json={'name':name})
    assert response.status_code==201,response.json
    return response.json


def test_asset_api_lists_converted_records_once_and_supports_real_crud(unified_client):
    client=unified_client
    before=client.get('/api/inventory/assets').json
    assert before['total']==40 and all(row['kind']=='asset' for row in before['rows'])
    one=create(client,'Mini PC');two=create(client,'RAM')
    updated=client.put('/api/inventory/assets/'+str(one['id']),json={'name':'Mini PC XY','expectedRevision':one['revision']})
    assert updated.status_code==200 and updated.json['name']=='Mini PC XY'
    assert client.get('/api/inventory/assets?q=Mini%20PC').json['total']==1
    assert client.delete('/api/inventory/assets/'+str(two['id']),json={'expectedRevision':two['revision']}).status_code==200
    assert client.get('/api/inventory/assets/'+str(two['id'])).status_code==404


def test_components_batch_is_atomic_and_rejects_a_later_cycle(unified_client):
    client=unified_client;a=create(client,'PC');b=create(client,'RAM');c=create(client,'CPU')
    route=f"/api/inventory/assets/{a['id']}/components"
    result=client.put(route,json={'expectedRevision':a['revision'],'items':[{'id':b['id'],'quantity':2},{'id':c['id'],'quantity':1}]})
    assert result.status_code==200 and len(result.json['components'])==2
    cycle=client.put(f"/api/inventory/assets/{b['id']}/components",json={'expectedRevision':b['revision'],'items':[{'id':c['id']},{'id':a['id']}]})
    assert cycle.status_code==409
    assert client.get(f"/api/inventory/assets/{b['id']}").json['components']==[]
    removed=client.delete(route+'/'+str(b['id']),json={'expectedRevision':result.json['revision']})
    assert removed.status_code==200 and len(removed.json['components'])==1
    assert client.get(f"/api/inventory/assets/{b['id']}").json['used_in']==[]


def test_converted_device_reader_keeps_access_without_seeing_old_assets(unified_client):
    from test_product_catalog_routes import role,image_data
    client=unified_client;secret=create(client,'Private old asset')
    role(client,'device-manager',['devices.view','devices.manage'])
    assert client.get('/api/inventory/assets').json['total']==40
    assert client.get(f"/api/inventory/assets/{secret['id']}").status_code==403
    with inventory_app.app.app_context():identifier=inventory_app.get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    assert client.get(f'/api/inventory/assets/{identifier}').status_code==200
    assert client.get(f'/api/inventory/asset/{identifier}/panel').status_code==200
    assert client.get(f'/inventory/assets/{identifier}/edit').status_code==200
    assert client.post(f'/api/inventory/asset/{identifier}/photo/upload',data=image_data(expectedUpdatedAt='')).status_code==201
    assert client.get(f'/api/inventory/asset/{identifier}/photo').json['source']=='individual'


def test_canonical_routes_keep_csrf_enforced(unified_client,monkeypatch):
    monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert unified_client.post('/api/inventory/assets',json={'name':'Blocked'}).status_code==403
    token=unified_client.get('/api/csrf-token').json['csrfToken']
    assert unified_client.post('/api/inventory/assets',json={'name':'Allowed'},headers={'X-CSRF-Token':token}).status_code==201


def test_legacy_photo_routes_use_same_canonical_server_image_after_conversion(unified_client):
    from test_product_catalog_routes import image_data
    client=unified_client
    with inventory_app.app.app_context():identifier=inventory_app.get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    legacy='/api/inventory/device/1/photo';canonical=f'/api/inventory/asset/{identifier}/photo'
    initial=client.get(legacy).json
    uploaded=client.post(legacy+'/upload',data=image_data(expectedUpdatedAt=initial['updated_at']))
    assert uploaded.status_code==201 and uploaded.json['url'].startswith(f'/media/inventory/asset/{identifier}/')
    same=client.get(canonical).json
    assert same['hash']==uploaded.json['hash']
    replacement=client.post(canonical,json={'action':'hide','expectedUpdatedAt':same['updated_at']})
    assert replacement.status_code==200 and client.get(legacy).json['source']=='fallback'
    assert client.get(uploaded.json['url']).status_code==404
