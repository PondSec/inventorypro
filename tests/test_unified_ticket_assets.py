import app as inventory_app
from test_unified_asset_routes import unified_client,create
from test_inventory_workspace import client
from test_product_catalog_routes import role


def test_new_and_nested_assets_are_searchable_for_tickets(unified_client):
    client=unified_client
    pc=create(client,'QA mini PC');ram=create(client,'QA RAM')
    changed=client.put(f"/api/inventory/assets/{ram['id']}",json={'serial_number':'QA-RAM-serial','expectedRevision':ram['revision']}).json
    linked=client.put(f"/api/inventory/assets/{pc['id']}/components",json={'expectedRevision':pc['revision'],'items':[{'id':ram['id'],'quantity':2}]})
    assert linked.status_code==200
    found=client.get('/api/ticket-assets/search?search=QA-RAM-serial').json
    assert {row['id'] for row in found['items']}=={pc['id'],ram['id']}
    assert all('QA-RAM-serial' in row['serial_numbers'] for row in found['items'])
    response=client.post('/api/tickets',json={'title':'QA canonical link','description':'QA synthetic','asset_ids':[pc['id']]})
    assert response.status_code==201
    assert client.get('/api/tickets/'+str(response.json['id'])).json['asset_ids']==[pc['id']]


def test_ticket_links_respect_asset_scopes_and_preserve_hidden_existing_links(unified_client):
    client=unified_client
    secret=create(client,'QA original asset')
    with inventory_app.app.app_context():
        db=inventory_app.get_db();converted=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    created=client.post('/api/tickets',json={'title':'QA mixed ticket','description':'QA','asset_ids':[secret['id'],converted]})
    assert created.status_code==201
    ticket_id=created.json['id']
    role(client,'qa-scoped-ticket',['devices.view','tickets.view_all','tickets.create','tickets.update'])
    found=client.get('/api/ticket-assets/search').json
    assert found['total']==40 and secret['id'] not in {row['id'] for row in found['items']}
    blocked=client.post('/api/tickets',json={'title':'QA forbidden link','description':'QA','asset_ids':[secret['id']]})
    assert blocked.status_code==403
    state=client.get(f'/api/tickets/{ticket_id}').json
    assert state['asset_ids']==[converted]
    updated=client.put(f'/api/tickets/{ticket_id}',json={'updated_at':state['updated_at'],'asset_ids':[]})
    assert updated.status_code==200,updated.json
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert [row[0] for row in db.execute('SELECT asset_id FROM ticket_assets WHERE ticket_id=?',(ticket_id,))]==[secret['id']]
        assert not db.execute("SELECT 1 FROM tickets WHERE title='QA forbidden link'").fetchone()


def test_invalid_ticket_link_never_creates_partial_ticket(unified_client):
    for values in [[True],[-1],['invalid'],{},[999999]]:
        response=unified_client.post('/api/tickets',json={'title':'QA invalid link','description':'QA','asset_ids':values})
        assert response.status_code in {400,404},response.json
    with inventory_app.app.app_context():
        assert not inventory_app.get_db().execute("SELECT 1 FROM tickets WHERE title='QA invalid link'").fetchone()
