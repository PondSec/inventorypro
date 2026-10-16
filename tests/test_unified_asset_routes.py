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
    assert client.get(f'/inventory/assets/{identifier}/edit').location==f'/inventory/assets/{identifier}?edit=1'
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


def test_explicit_converted_asset_deletion_handles_backing_rows_atomically(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        db.execute("INSERT INTO device_notes(device_id,note) VALUES (1,'QA owned note')");db.commit()
    state=client.get(f'/api/inventory/assets/{identifier}').json
    assert client.delete(f'/api/inventory/assets/{identifier}',json={'expectedRevision':state['revision']}).status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert not db.execute('SELECT 1 FROM devices WHERE id=1').fetchone()
        assert not db.execute('SELECT 1 FROM assets WHERE id=?',(identifier,)).fetchone()
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0]==39
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==39
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_old_asset_api_and_assignment_paths_cannot_bypass_converted_scope(unified_client):
    from test_product_catalog_routes import role
    client=unified_client
    with inventory_app.app.app_context():identifier=inventory_app.get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    role(client,'original-assets-only',['assets.view','assets.manage','asset.assign'])
    assert client.get(f'/api/asset-entries/{identifier}').status_code==403
    assert client.post(f'/assets/{identifier}/assign',json={}).status_code==403
    assert client.delete(f'/api/devices/1').status_code==403


def test_unknown_legacy_reference_rolls_back_owned_cleanup_and_mapping(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        db.execute('CREATE TABLE qa_independent_device_ref(id INTEGER PRIMARY KEY,device_id INTEGER REFERENCES devices(id))')
        db.execute('INSERT INTO qa_independent_device_ref(device_id) VALUES (1)')
        db.execute("INSERT INTO device_notes(device_id,note) VALUES (1,'QA keep after blocked delete')");db.commit()
    state=client.get(f'/api/inventory/assets/{identifier}').json
    response=client.delete(f'/api/inventory/assets/{identifier}',json={'expectedRevision':state['revision']})
    assert response.status_code==409
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert db.execute('SELECT 1 FROM devices WHERE id=1').fetchone()
        assert db.execute('SELECT 1 FROM asset_legacy_devices WHERE device_id=1 AND asset_id=?',(identifier,)).fetchone()
        assert db.execute('SELECT 1 FROM device_notes WHERE note=?',('QA keep after blocked delete',)).fetchone()
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==40
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_tags_notes_and_files_keep_scoped_access_after_conversion(unified_client):
    from io import BytesIO
    from test_product_catalog_routes import role
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        old=db.execute("INSERT INTO device_tags(device_id,tag) VALUES (1,'QA legacy tag')").lastrowid;db.commit()
    assert client.post(f'/api/inventory/assets/{identifier}/tags',json={'tag':'QA new tag'}).status_code==201
    assert client.delete(f'/api/inventory/assets/{identifier}/extras/tag/legacy-{old}').status_code==200
    uploaded=client.post('/attachments/upload',data={'entity_type':'asset','entity_id':str(identifier),'file':(BytesIO(b'QA shared file'),'qa.txt','text/plain')})
    assert uploaded.status_code==201
    url=uploaded.json['download_url']
    assert client.get(url).data==b'QA shared file'
    role(client,'file-converted-reader',['devices.view','attachment.download'])
    assert client.get(url).status_code==200
    role(client,'file-original-reader',['assets.view','attachment.download'])
    assert client.get(url).status_code==403


def test_location_delete_keeps_new_asset_location_until_explicit_reassignment(unified_client):
    client=unified_client
    assert client.post('/api/locations',json={'name':'QA canonical place'}).status_code==201
    location=next(row['id'] for row in client.get('/api/locations').json if row['name']=='QA canonical place')
    response=client.post('/api/inventory/assets',json={'name':'QA location asset','location_id':location})
    assert response.status_code==201
    asset=response.json
    blocked=client.delete(f'/api/locations/{location}')
    assert blocked.status_code==409 and blocked.json['references']['devices']==1
    assert client.get(f"/api/inventory/assets/{asset['id']}").json['location_id']==location
    moved=client.put(f"/api/inventory/assets/{asset['id']}",json={'location_id':None,'expectedRevision':asset['revision']})
    assert moved.status_code==200
    assert client.delete(f'/api/locations/{location}').status_code==200


def test_historical_device_links_open_canonical_detail_tabs_and_maintenance(unified_client):
    client=unified_client
    with inventory_app.app.app_context():mapped=inventory_app.get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    redirected=client.get('/inventory/devices/1?tab=hardware')
    assert redirected.status_code==302 and redirected.location==f'/inventory/assets/{mapped}?tab=details'
    assert client.get(redirected.location).status_code==200
    assert client.post(f'/api/inventory/assets/{mapped}/maintenance',json={'title':'QA canonical preview task','due_date':'2026-11-01'}).status_code==201
    panel=client.get('/api/inventory/device/1/panel').json
    assert panel['id']==mapped and panel['kind']=='asset' and panel['unified']
    assert panel['tasks'][0]['title']=='QA canonical preview task'
    assert b'QA canonical preview task' in client.get('/api/inventory/device/1/panel?format=html').data
    assert client.get('/?location=1&view=devices').location=='/inventory?location=1'
    assert client.get('/?view=taxonomy').location=='/inventory/categories'


def test_legacy_mutation_guard_cannot_bypass_csrf_or_mfa(unified_client,monkeypatch):
    client=unified_client;monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert client.delete('/api/devices/1').status_code==403
    token=client.get('/api/csrf-token').json['csrfToken']
    with client.session_transaction() as session:session['mfa_required']=True;session['mfa_verified']=False
    assert client.delete('/api/devices/1',headers={'X-CSRF-Token':token}).status_code==403
    with inventory_app.app.app_context():assert inventory_app.get_db().execute('SELECT 1 FROM devices WHERE id=1').fetchone()


@pytest.mark.parametrize('legacy_endpoint',[False,True])
def test_delete_detaches_container_contents_tickets_and_order_references(unified_client,legacy_endpoint):
    client=unified_client;parent=create(client,'QA workstation');child=create(client,'QA RAM retained')
    with inventory_app.app.app_context():middle=inventory_app.get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    state=client.get(f'/api/inventory/assets/{middle}').json
    assert client.put(f"/api/inventory/assets/{parent['id']}/components",json={'expectedRevision':parent['revision'],'items':[{'id':middle}]}).status_code==200
    linked=client.put(f'/api/inventory/assets/{middle}/components',json={'expectedRevision':state['revision'],'items':[{'id':child['id'],'quantity':2}]})
    assert linked.status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        ticket=db.execute("INSERT INTO tickets(title,description,status,created_by) VALUES ('QA retain ticket','Synthetic','open','admin')").lastrowid
        db.execute('INSERT INTO ticket_assets(ticket_id,asset_id) VALUES (?,?)',(ticket,middle))
        order=db.execute("INSERT INTO purchase_orders(po_number) VALUES ('QA-DELETE-RETAIN')").lastrowid
        line=db.execute("INSERT INTO purchase_order_items(purchase_order_id,item_name,asset_id,device_id) VALUES (?,'QA keep order line',?,1)",(order,middle)).lastrowid
        db.commit()
    path=f'/api/asset-entries/{middle}' if legacy_endpoint else f'/api/inventory/assets/{middle}'
    response=client.delete(path,json={'expectedRevision':linked.json['revision']})
    assert response.status_code==200,response.json
    assert client.get(f'/api/inventory/assets/{middle}').status_code==404
    assert client.get(f"/api/inventory/assets/{parent['id']}").json['components']==[]
    assert client.get(f"/api/inventory/assets/{child['id']}").json['used_in']==[]
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT title FROM tickets WHERE id=?',(ticket,)).fetchone()[0]=='QA retain ticket'
        assert db.execute('SELECT item_name,asset_id,device_id FROM purchase_order_items WHERE id=?',(line,)).fetchone()[:]==('QA keep order line',None,None)
        assert db.execute('SELECT 1 FROM purchase_orders WHERE id=?',(order,)).fetchone()
        assert not db.execute('SELECT 1 FROM devices WHERE id=1').fetchone()
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_legacy_asset_delete_keeps_csrf_and_object_permissions(unified_client,monkeypatch):
    from test_product_catalog_routes import role
    item=create(unified_client,'QA protected asset')
    monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert unified_client.delete(f"/api/asset-entries/{item['id']}").status_code==403
    token=unified_client.get('/api/csrf-token').json['csrfToken']
    role(unified_client,'asset-reader',['assets.view'])
    assert unified_client.delete(f"/api/asset-entries/{item['id']}",headers={'X-CSRF-Token':token}).status_code==403
    assert unified_client.get(f"/api/inventory/assets/{item['id']}").status_code==200
