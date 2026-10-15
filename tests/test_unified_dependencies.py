import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client,create
from test_product_catalog_routes import role


def test_graph_contains_nested_assets_once_and_normalizes_old_explicit_links(unified_client):
    client=unified_client;pc=create(client,'QA graph PC');ram=create(client,'QA graph RAM')
    assert client.put(f"/api/inventory/assets/{pc['id']}/components",json={'expectedRevision':pc['revision'],'items':[{'id':ram['id'],'quantity':2}]}).status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db();mapped=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        old=db.execute("INSERT INTO dependency_links(source_type,source_id,target_type,target_id,relation) VALUES ('asset',?,'device',1,'depends_on')",(pc['id'],)).lastrowid;db.commit()
    graph=client.get('/api/dependency-graph').json
    assert len([row for row in graph['nodes'] if row['type']=='asset'])==42
    assert not any(row['type']=='device' for row in graph['nodes'])
    assert any(row['source']==f"asset:{pc['id']}" and row['target']==f"asset:{ram['id']}" and row['relation']=='contains' for row in graph['edges'])
    assert any(row['source']==f"asset:{pc['id']}" and row['target']==f"asset:{mapped}" for row in graph['edges'])
    assert 'device' not in client.get('/api/dependency-nodes').json
    links=client.get('/api/dependency-links').json
    assert next(row for row in links if row['id']==old)['target_type']=='asset'
    with inventory_app.app.app_context():assert inventory_app.get_db().execute('SELECT target_type FROM dependency_links WHERE id=?',(old,)).fetchone()[0]=='device'
    impact=client.get(f"/api/impact-analysis?source_type=asset&source_id={ram['id']}")
    assert impact.status_code==200 and any(row['id']==pc['id'] for row in impact.json['impact'])
    alias=client.get('/api/impact-analysis?source_type=device&source_id=1')
    assert alias.status_code==200 and alias.json['source']['type']=='asset'


def test_dependency_graph_and_mutations_cannot_bypass_asset_scopes(unified_client):
    client=unified_client;secret=create(client,'QA hidden graph asset')
    with inventory_app.app.app_context():
        db=inventory_app.get_db();legacy=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        link=db.execute("INSERT INTO dependency_links(source_type,source_id,target_type,target_id,relation) VALUES ('asset',?,'device',1,'depends_on')",(secret['id'],)).lastrowid;db.commit()
    role(client,'qa-graph-device',['devices.view','dependencies.view','dependencies.manage'])
    graph=client.get('/api/dependency-graph').json
    assert len([row for row in graph['nodes'] if row['type']=='asset'])==40
    assert not any(row['id']==secret['id'] and row['type']=='asset' for row in graph['nodes'])
    assert client.get('/api/dependency-links').json==[]
    assert client.delete(f'/api/dependency-links/{link}').status_code==403
    assert client.get(f"/api/impact-analysis?source_type=asset&source_id={secret['id']}").status_code==403
    response=client.post('/api/dependency-links',json={'source_type':'asset','source_id':legacy,'target_type':'asset','target_id':secret['id']})
    assert response.status_code==403
    with inventory_app.app.app_context():assert inventory_app.get_db().execute('SELECT 1 FROM dependency_links WHERE id=?',(link,)).fetchone()
