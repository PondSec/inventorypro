import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client,create
from test_product_catalog_routes import role


def test_relations_are_atomic_versioned_and_do_not_change_composition(unified_client):
    c=unified_client;a=create(c,'QA relation PC');b=create(c,'QA related workplace')
    route=f"/api/inventory/assets/{a['id']}/relations"
    response=c.post(route,json={'expectedRevision':a['revision'],'targets':[b['id']]})
    assert response.status_code==201,response.json
    current=c.get(f"/api/inventory/assets/{a['id']}").json
    assert current['revision']>a['revision'] and current['components']==[]
    assert c.post(route,json={'expectedRevision':a['revision'],'targets':[b['id']]}).status_code==409
    assert c.post(route,json={'expectedRevision':current['revision'],'targets':[b['id'],a['id']]}).status_code==400
    assert c.post(route,json={'expectedRevision':current['revision'],'targets':[b['id']]}).status_code==201
    with inventory_app.app.app_context():
        rows=inventory_app.get_db().execute('SELECT * FROM asset_relations').fetchall();assert len(rows)==1;relation=rows[0]['id']
    current=c.get(f"/api/inventory/assets/{a['id']}").json
    assert c.delete(route+'/'+str(relation),json={'expectedRevision':current['revision']}).status_code==200
    assert c.get(f"/api/inventory/assets/{b['id']}").status_code==200


def test_relations_respect_hidden_targets_and_directional_write_scope(unified_client):
    c=unified_client;a=create(c,'QA private relation source')
    with inventory_app.app.app_context():
        db=inventory_app.get_db();legacy=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    assert c.post(f"/api/inventory/assets/{a['id']}/relations",json={'expectedRevision':a['revision'],'targets':[legacy]}).status_code==201
    with inventory_app.app.app_context():relation=inventory_app.get_db().execute('SELECT id FROM asset_relations').fetchone()[0]
    role(c,'qa-relation-devices',['devices.view','devices.manage'])
    current=c.get(f'/api/inventory/assets/{legacy}').json
    assert c.post(f'/api/inventory/assets/{legacy}/relations',json={'expectedRevision':current['revision'],'targets':[a['id']]}).status_code==403
    assert c.delete(f'/api/inventory/assets/{legacy}/relations/{relation}',json={'expectedRevision':current['revision']}).status_code==403
    assert 'QA private' not in c.get(f'/inventory/assets/{legacy}').get_data(as_text=True)
    assert c.get('/api/inventory/relation-types').status_code==200
