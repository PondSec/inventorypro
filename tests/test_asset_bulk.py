import pytest
import app as inventory_app
from test_unified_asset_routes import unified_client, create
from test_inventory_workspace import client


def prepared(client, *rows):
    response=client.post('/api/inventory/assets/bulk/prepare',json={'items':[{'id':r['id']} for r in rows]})
    assert response.status_code==200,response.json
    return response.json['items']


def test_bulk_updates_explicit_fields_and_keeps_unique_data(unified_client):
    c=unified_client;a=create(c,'QA one');b=create(c,'QA two')
    c.put(f"/api/inventory/assets/{a['id']}",json={'expectedRevision':a['revision'],'serial_number':'QA serial','specs':{'Private':'keep'}})
    items=prepared(c,a,b)
    response=c.post('/api/inventory/assets/bulk',json={'action':'update','items':items,'changes':{'cost_center':'Research','location_id':None}})
    assert response.status_code==200 and response.json['changed']==2
    result=c.get(f"/api/inventory/assets/{a['id']}").json
    assert result['serial_number']=='QA serial' and result['specs']=={'Private':'keep'} and result['cost_center']=='Research'
    assert c.get(f"/api/inventory/assets/{b['id']}").json['name']=='QA two'


def test_bulk_stale_selection_changes_nothing(unified_client):
    c=unified_client;a=create(c,'QA one');b=create(c,'QA two');items=prepared(c,a,b)
    c.put(f"/api/inventory/assets/{b['id']}",json={'expectedRevision':b['revision'],'name':'New name'})
    for action in ['update','delete']:
        response=c.post('/api/inventory/assets/bulk',json={'action':action,'items':items,'changes':{'cost_center':'No'}})
        assert response.status_code==409
        assert c.get(f"/api/inventory/assets/{a['id']}").json['cost_center']==''
        assert c.get(f"/api/inventory/assets/{b['id']}").json['name']=='New name'


def test_bulk_delete_detaches_selected_parent_and_keeps_unselected_children(unified_client):
    c=unified_client;parent=create(c,'QA parent');child=create(c,'QA child');keep=create(c,'QA retained')
    c.put(f"/api/inventory/assets/{parent['id']}/components",json={'expectedRevision':parent['revision'],'items':[{'id':child['id']},{'id':keep['id']}]})
    response=c.post('/api/inventory/assets/bulk',json={'action':'delete','items':prepared(c,child,parent)})
    assert response.status_code==200
    assert c.get(f"/api/inventory/assets/{keep['id']}").json['used_in']==[]
    assert c.get(f"/api/inventory/assets/{parent['id']}").status_code==404
    with inventory_app.app.app_context():assert not inventory_app.get_db().execute('PRAGMA foreign_key_check').fetchall()


def test_bulk_later_reference_failure_rolls_back_entire_deletion(unified_client):
    c=unified_client;a=create(c,'QA one');b=create(c,'QA blocked');items=prepared(c,a,b)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute('CREATE TABLE qa_ref(asset_id INTEGER REFERENCES assets(id))')
        db.execute('INSERT INTO qa_ref VALUES (?)',(b['id'],));db.commit()
    response=c.post('/api/inventory/assets/bulk',json={'action':'delete','items':items})
    assert response.status_code==409
    assert c.get(f"/api/inventory/assets/{a['id']}").status_code==200
    with inventory_app.app.app_context():assert not inventory_app.get_db().execute("SELECT 1 FROM activity_log WHERE action='bulk_delete'").fetchone()


@pytest.mark.parametrize('changes',[{}, {'name':'Wrong'}, {'location_id':-1}, {'warranty_end':'invalid'}])
def test_bulk_rejects_invalid_fields_without_writes(unified_client,changes):
    c=unified_client;a=create(c,'QA one')
    assert c.post('/api/inventory/assets/bulk',json={'action':'update','items':prepared(c,a),'changes':changes}).status_code==400
    assert c.get(f"/api/inventory/assets/{a['id']}").json['revision']==a['revision']


@pytest.mark.parametrize('items',[[], [{'id':True}], [{'id':1},{'id':1}], [{'id':i} for i in range(1,102)]])
def test_bulk_rejects_malformed_selection(unified_client,items):
    assert unified_client.post('/api/inventory/assets/bulk/prepare',json={'items':items}).status_code==400


def test_bulk_scopes_and_csrf_are_enforced(unified_client,monkeypatch):
    from test_product_catalog_routes import role
    c=unified_client;a=create(c,'QA private');items=prepared(c,a)
    role(c,'QA device-only bulk',['devices.view','devices.manage'])
    assert c.post('/api/inventory/assets/bulk/prepare',json={'items':[{'id':a['id']}]}).status_code==403
    assert c.post('/api/inventory/assets/bulk',json={'action':'delete','items':items}).status_code==403
    monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert c.post('/api/inventory/assets/bulk',json={'action':'delete','items':items}).status_code==403
