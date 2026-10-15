import pytest
import app as inventory_app
from inventorypro.domains.inventory.service import list_inventory


@pytest.fixture
def client(isolated_inventory):
    client = isolated_inventory.test_client()
    with client.session_transaction() as session:
        session.update(logged_in=True, username='admin', mfa_verified=True)
    return client


def test_inventory_is_paginated_searchable_and_bookmarkable(client):
    first = client.get('/inventory?per_page=10')
    assert first.status_code == 200
    assert b'Seite 1 von 4' in first.data
    assert b'Notebook 009' in first.data and b'Notebook 010' not in first.data
    assert b'Notebook 010' in client.get('/inventory?per_page=10&page=2').data
    assert b'Notebook 039' in client.get('/inventory?q=QA-039').data
    assert b'Notebook 038' not in client.get('/inventory?q=QA-039').data
    assert b'Keine passenden Eintr' in client.get('/inventory?q=%25').data


def test_inventory_query_handles_invalid_and_injection_inputs(client):
    for query in ('page=-2&per_page=100000', 'page=99999&per_page=no', 'sort=name;DROP TABLE devices&direction=invalid'):
        assert client.get('/inventory?' + query).status_code == 200
    with inventory_app.app.app_context():
        assert inventory_app.get_db().execute('SELECT COUNT(*) FROM devices').fetchone()[0] == 40


def test_devices_and_assets_share_list_without_merging_models(client):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute("INSERT INTO assets (name, specs) VALUES ('Dock QA', '{}')")
        db.commit()
    assert b'Dock QA' in client.get('/inventory?kind=asset').data
    assert b'Notebook' not in client.get('/inventory?kind=asset').data
    assert b'Dock QA' not in client.get('/inventory?kind=device').data


def test_detail_tabs_preserve_hardware_and_escape_user_content(client):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        device_id = db.execute('SELECT id FROM devices LIMIT 1').fetchone()[0]
        db.execute('UPDATE devices SET specs=? WHERE id=?', ('{"RAM":"32 GB","Label":"<script>alert(1)</script>"}',device_id))
        db.commit()
    for tab in ('overview','hardware','accessories','assignment','maintenance','history'):
        response = client.get(f'/inventory/devices/{device_id}?tab={tab}')
        assert response.status_code == 200
        if tab == 'hardware':
            assert b'32 GB' in response.data
            assert b'&lt;script&gt;' in response.data
    assert client.get(f'/inventory/devices/{device_id}?tab=invalid').status_code == 404
    assert client.get('/inventory/devices/99999').status_code == 404


def test_list_does_not_return_objects_without_domain_permission(client):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute("INSERT INTO assets (name, specs) VALUES ('SecretComponent', '{}')")
        db.commit()
        result = list_inventory(db, {}, devices_allowed=True, assets_allowed=False)
        assert all(row['kind'] == 'device' for row in result['rows'])
        assert result['total'] == 40
        result = list_inventory(db, {}, devices_allowed=False, assets_allowed=False)
        assert result['total'] == 0 and not result['rows']


def test_real_device_only_role_cannot_read_asset_list_or_detail(client):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        user_id = db.execute("INSERT INTO users (username,password_hash) VALUES ('device-only','unused')").lastrowid
        role_id = db.execute("INSERT INTO roles (name) VALUES ('Devices only')").lastrowid
        db.execute('INSERT INTO user_roles (user_id,role_id) VALUES (?,?)',(user_id,role_id))
        db.execute("INSERT INTO role_permissions (role_id,permission_id) SELECT ?,id FROM permissions WHERE key='devices.view'",(role_id,))
        asset_id=db.execute("INSERT INTO assets (name,specs) VALUES ('RestrictedComponent','{}')").lastrowid
        db.commit()
    with client.session_transaction() as session:
        session['username']='device-only'
    response = client.get('/inventory?kind=asset')
    assert b'RestrictedComponent' not in response.data
    assert b'href="/inventory?kind=device"' in response.data
    assert b'href="/inventory?kind=asset"' not in response.data
    assert b'Link hinzuf' not in response.data
    assert client.get(f'/inventory/assets/{asset_id}').status_code == 403
    assert client.get('/inventory/new').status_code == 403


def test_missing_identity_filter_is_exact(client):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        location_id=db.execute("INSERT INTO locations(name) VALUES ('QA Room')").lastrowid
        db.execute("UPDATE devices SET location_id=? WHERE name='Notebook 000'",(location_id,))
        db.commit()
    response=client.get('/inventory?filter=missing_identity&per_page=100')
    assert b'Notebook 000' not in response.data
    assert b'Notebook 001' in response.data


def test_asset_detail_uses_existing_full_domain_payload(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        asset_id=db.execute("INSERT INTO assets(name,specs) VALUES ('QA Component','{}')").lastrowid
        db.commit()
    response=client.get(f'/inventory/assets/{asset_id}')
    assert response.status_code==200
    assert b'QA Component' in response.data


def test_dashboard_counts_each_incomplete_device_once_and_links_exact_filter(client):
    response=client.get('/api/workspace/tasks')
    assert response.status_code==200
    task=next(task for task in response.json['tasks'] if task['key']=='identity')
    assert task['count']==40
    assert task['url']=='/inventory?kind=device&filter=missing_identity'
    assert client.get(task['url']).status_code==200


def test_task_counts_do_not_leak_other_users_tickets(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        user_id=db.execute("INSERT INTO users(username,password_hash) VALUES ('own-tickets','unused')").lastrowid
        role_id=db.execute("INSERT INTO roles(name) VALUES ('Own tickets')").lastrowid
        db.execute('INSERT INTO user_roles(user_id,role_id) VALUES (?,?)',(user_id,role_id))
        db.execute("INSERT INTO role_permissions(role_id,permission_id) SELECT ?,id FROM permissions WHERE key='tickets.view_own'",(role_id,))
        category=db.execute('SELECT id FROM ticket_categories LIMIT 1').fetchone()[0]
        for owner in ['own-tickets','someone-else']:
            db.execute("INSERT INTO tickets(title,description,category_id,status,priority,created_by) VALUES ('Synthetic','',?,'open','normal',?)",(category,owner))
        db.commit()
    with client.session_transaction() as session:
        session['username']='own-tickets'
    tasks=client.get('/api/workspace/tasks').json['tasks']
    assert {t['key'] for t in tasks}=={'tickets','overdue_tickets'}
    assert next(t['count'] for t in tasks if t['key']=='tickets')==1
