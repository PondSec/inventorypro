import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client,create
from test_product_catalog_routes import role


def test_reports_count_canonical_assets_and_both_maintenance_sources_once(unified_client,monkeypatch):
    client=unified_client;one=create(client,'QA report PC');create(client,'QA report RAM')
    assert client.post(f"/api/inventory/assets/{one['id']}/maintenance",json={'title':'QA report task','due_date':'2020-01-01'}).status_code==201
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute("INSERT INTO maintenance_tasks(device_id,title,status,due_date) VALUES (1,'QA old task','open','2020-01-01')");db.commit()
    captured={}
    def render(template,**context):captured.update(context);return 'QA report rendered'
    monkeypatch.setattr(inventory_app,'render_template',render)
    response=client.get('/stats')
    assert response.status_code==200
    assert captured['total_devices']==42 and captured['total_assets']==42
    assert captured['open_maintenance']==2 and captured['overdue_maintenance']==2
    assert sum(row['device_count'] for row in captured['categories'])==42
    role(client,'qa-stats-devices',['devices.view','stats.view'])
    assert client.get('/stats').status_code==200
    assert captured['total_devices']==40 and captured['total_assets']==40
    assert captured['open_maintenance']==0 and captured['ticket_total']==0


def test_reports_keep_own_ticket_boundary_for_legacy_requester_names(unified_client,monkeypatch):
    client=unified_client;role(client,'qa-report-requester',['stats.view','tickets.view_own'])
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        for name in ['QA-REPORT-REQUESTER','someone else']:
            db.execute('INSERT INTO tickets(title,description,requester_name) VALUES (?,?,?)',('QA report ticket','QA',name))
        db.commit()
    captured={}
    monkeypatch.setattr(inventory_app,'render_template',lambda template,**values:captured.update(values) or 'QA')
    assert client.get('/stats').status_code==200
    assert captured['total_assets']==0 and captured['ticket_total']==1
