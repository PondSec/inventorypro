import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client,create
from test_product_catalog_routes import role


def test_timeline_counts_assets_once_and_preserves_old_events(unified_client):
    client=unified_client;create(client,'QA timeline PC')
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute("INSERT INTO activity_log(username,action,entity_type,entity_id,details) VALUES ('admin','update','device',1,'{}')");db.commit()
    response=client.get('/api/time-machine/state?timestamp=2099-01-01')
    assert response.status_code==200
    assert response.json['assets']==41 and response.json['devices']==0
    response=client.get('/api/time-machine/changes')
    assert response.status_code==200
    old=[row for row in response.json['changes'] if row['entity_type']=='device']
    assert old and all(row['layer']=='assets' and row['layer_label']=='Asset' for row in old)


def test_timeline_scope_does_not_reveal_foreign_assets_tickets_or_roadmaps(unified_client):
    client=unified_client;secret=create(client,'QA secret timeline asset')
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        for kind,identifier,name in [('asset',secret['id'],'QA secret timeline asset'),('device',1,'QA visible old PC')]:
            db.execute('INSERT INTO activity_log(username,action,entity_type,entity_id,details) VALUES (?,?,?,?,?)',('admin','update',kind,identifier,'{"name":"'+name+'"}'))
        db.execute("INSERT INTO tickets(title,description,requester_name) VALUES ('QA secret ticket','QA','elsewhere')")
        db.execute("INSERT INTO roadmaps(title) VALUES ('QA secret roadmap')");db.commit()
    role(client,'qa-timeline-devices',['timemachine.view','devices.view','activity.view'])
    response=client.get('/api/time-machine/state?timestamp=2099-01-01')
    assert response.status_code==200
    assert response.json['assets']==40 and response.json['devices']==0
    assert response.json['tickets']==0 and response.json['roadmaps']==0
    changes=client.get('/api/time-machine/changes')
    assert changes.status_code==200
    assert changes.json['tickets']==[] and changes.json['roadmaps']==[]
    assert any(row['entity_type']=='device' for row in changes.json['changes'])
    assert not any(row['entity_type']=='asset' and row['entity_id']==secret['id'] for row in changes.json['changes'])
    assert 'QA secret' not in changes.get_data(as_text=True)


def test_date_selection_includes_records_created_during_that_day(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute("UPDATE assets SET created_at='2026-10-15 16:30:00'");db.commit()
    assert client.get('/api/time-machine/state?timestamp=2026-10-15').json['assets']==40
    assert client.get('/api/time-machine/state?timestamp=2026-10-15T12:00:00').json['assets']==0
