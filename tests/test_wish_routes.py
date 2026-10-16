import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client


def test_crud_progress_and_inventory_are_real(unified_client):
    client = unified_client
    parent = client.post('/api/wishes/projects', json={'name': 'Garden', 'budget': '200'}).json
    response = client.post('/api/wishes', json={'name': 'Chair', 'quantity': 2, 'unit_price': '30', 'project_id': parent['id']})
    assert response.status_code == 201
    row = response.json
    assert client.get('/api/inventory/assets?q=Chair').json['total'] == 0
    acquired = client.post(f"/api/wishes/{row['id']}/acquire", json={'expectedRevision': row['revision'], 'requestKey': 'synthetic-request-01', 'quantity': 2})
    assert acquired.status_code == 200 and acquired.json['missing'] == 0
    assert client.get('/api/inventory/assets?q=Chair').json['total'] == 2
    overview = client.get(f"/api/wishes/projects/{parent['id']}").json
    assert overview['owned'] == 2 and overview['needed'] == 2 and overview['estimate'] == 6000 and overview['spent'] == 6000
    result = client.post(f"/api/wishes/projects/{parent['id']}/assemble", json={'expectedRevision': parent['revision']})
    assert result.status_code == 200 and result.json['asset_id']
    assert client.delete(f"/api/wishes/projects/{parent['id']}", json={'expectedRevision': result.json['revision']}).status_code == 200
    assert client.get(f"/api/wishes/{row['id']}").json['project_id'] is None
    assert client.get('/api/inventory/assets?q=Chair').json['total'] == 2


def test_csrf_and_permission_boundaries(unified_client, monkeypatch):
    from test_product_catalog_routes import role
    monkeypatch.setitem(inventory_app.app.config, 'TESTING', False)
    assert unified_client.post('/api/wishes', json={'name': 'Unsafe'}).status_code == 403
    token = unified_client.get('/api/csrf-token').json['csrfToken']
    assert unified_client.post('/api/wishes', json={'name': 'Safe'}, headers={'X-CSRF-Token': token}).status_code == 201
    monkeypatch.setitem(inventory_app.app.config, 'TESTING', True)
    role(unified_client, 'inventory-only', ['assets.view','assets.manage'])
    assert unified_client.get('/api/wishes/projects').status_code == 403
    assert unified_client.post('/api/wishes', json={'name': 'Not allowed'}).status_code == 403


def test_private_project_does_not_expose_its_wishes(unified_client):
    from test_product_catalog_routes import role
    parent = unified_client.post('/api/wishes/projects', json={'name': 'Private project'}).json
    row = unified_client.post('/api/wishes', json={'name': 'Private wish', 'project_id': parent['id'], 'visibility': 'team'}).json
    role(unified_client, 'research-manager', ['wishes.view','wishes.manage'])
    assert unified_client.get('/api/wishes/projects').json == []
    assert unified_client.get(f"/api/wishes/{row['id']}").status_code == 404
    assert unified_client.get(f"/api/wishes/projects/{parent['id']}").status_code == 404


def test_invalid_body_returns_json_and_cannot_modify_data(unified_client):
    for value in [None, [], 'data']:
        response = unified_client.post('/api/wishes', json=value)
        assert response.status_code == 400 and response.json['error']


def test_pages_pagination_and_literal_search(unified_client):
    client = unified_client
    for index in range(12):
        assert client.post('/api/wishes', json={'name': f'Garden chair {index:02}'}).status_code == 201
    response = client.get('/wishes')
    assert response.status_code == 200 and b'Garden chair 11' in response.data and b'Garden chair 00' not in response.data
    assert b'Garden chair 00' in client.get('/wishes?page=2').data
    assert b'Garden chair 11' not in client.get('/wishes?q=%25').data
    assert client.get('/wishes?tab=projects').status_code == 200
    parent = client.post('/api/wishes/projects', json={'name': 'Workshop'}).json
    assert client.get(f"/wishes/projects/{parent['id']}").status_code == 200
