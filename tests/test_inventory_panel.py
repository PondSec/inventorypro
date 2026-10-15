import json

import app as inventory_app
from test_inventory_workspace import client


def seed_panel():
    db = inventory_app.get_db()
    device_id = db.execute('SELECT id FROM devices ORDER BY id LIMIT 1').fetchone()[0]
    db.execute('UPDATE devices SET specs=? WHERE id=?',
               (json.dumps({'Hersteller':'Example','Modell':'QA Model','RAM':'32 GB','Label':'<script>x</script>'}),device_id))
    asset_id = db.execute("INSERT INTO assets(name,specs) VALUES ('QA Dock','{}')").lastrowid
    db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,?,2)',(asset_id,device_id))
    for owner in ('admin','someone-else'):
        ticket = db.execute("INSERT INTO tickets(title,description,created_by,status) VALUES (?, 'QA','admin','open')",(f'{owner} ticket',)).lastrowid
        db.execute('UPDATE tickets SET created_by=? WHERE id=?',(owner,ticket))
        db.execute('INSERT INTO ticket_assets(ticket_id,asset_id) VALUES (?,?)',(ticket,asset_id))
    db.execute("INSERT INTO maintenance_tasks(device_id,title,status,due_date) VALUES (?,'QA Inspection','open','2026-01-01')",(device_id,))
    db.commit()
    return device_id, asset_id


def test_panel_exposes_actual_product_fields_links_and_permitted_tabs(client):
    with inventory_app.app.app_context():
        device, asset = seed_panel()
    payload = client.get(f'/api/inventory/device/{device}/panel').json
    assert payload['manufacturer'] == 'Example' and payload['model'] == 'QA Model'
    assert payload['specs']['RAM'] == '32 GB'
    assert payload['links'][0]['quantity'] == 2
    assert payload['tasks'][0]['title'] == 'QA Inspection'
    assert len(payload['tickets']) == 2
    assert [tab[0] for tab in payload['tabs']] == ['overview','details','accessories','tickets','history']
    assert payload['can_edit'] is True
    assert client.get(f'/api/inventory/asset/{asset}/panel').json['links'][0]['id'] == device
    assert client.get('/api/inventory/device/999999/panel').status_code == 404
    assert client.get('/api/inventory/invalid/1/panel').status_code == 404
    fragment = client.get(f'/api/inventory/device/{device}/panel?format=html')
    assert fragment.status_code == 200
    assert b'object-panel-name' in fragment.data and b'32 GB' in fragment.data
    assert b'&lt;script&gt;' in fragment.data and b'<script>x</script>' not in fragment.data
    assert b'Kurzansicht' not in fragment.data


def test_panel_does_not_leak_other_domains_or_other_users_tickets(client):
    with inventory_app.app.app_context():
        device, asset = seed_panel()
        db = inventory_app.get_db()
        user = db.execute("INSERT INTO users(username,password_hash) VALUES ('panel-reader','unused')").lastrowid
        role = db.execute("INSERT INTO roles(name) VALUES ('Panel reader')").lastrowid
        db.execute('INSERT INTO user_roles(user_id,role_id) VALUES (?,?)',(user,role))
        for permission in ('devices.view','tickets.view_own'):
            db.execute('INSERT INTO role_permissions(role_id,permission_id) SELECT ?,id FROM permissions WHERE key=?',(role,permission))
        db.execute("UPDATE tickets SET created_by='panel-reader' WHERE title='admin ticket'")
        db.commit()
    with client.session_transaction() as session:
        session['username'] = 'panel-reader'
    payload = client.get(f'/api/inventory/device/{device}/panel').json
    assert payload['links'] == [] and payload['assignments'] == [] and payload['relations'] == []
    assert payload['tasks'] == [] and payload['history'] == [] and not payload['can_edit']
    assert [ticket['title'] for ticket in payload['tickets']] == ['admin ticket']
    assert [tab[0] for tab in payload['tabs']] == ['overview','details','tickets']
    assert client.get(f'/api/inventory/asset/{asset}/panel').status_code == 403
    fragment = client.get(f'/api/inventory/device/{device}/panel?format=html').data
    assert b'QA Dock' not in fragment and b'someone-else ticket' not in fragment
    assert b'QA Inspection' not in fragment and b'>Bearbeiten<' not in fragment


def test_device_assignments_keep_their_actual_source(client):
    with inventory_app.app.app_context():
        device, asset = seed_panel()
        db = inventory_app.get_db()
        user = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        db.execute("INSERT INTO asset_assignment_history(asset_id,assigned_to_user_id,status) VALUES (?,?,'assigned')",(asset,user))
        db.commit()
    assignments = client.get(f'/api/inventory/device/{device}/panel').json['assignments']
    assert assignments[0]['assigned_user'] == 'admin' and assignments[0]['asset_name'] == 'QA Dock'
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute("INSERT INTO asset_assignment_history(asset_id,status) VALUES (?,'available')",(asset,))
        db.commit()
    assert client.get(f'/api/inventory/device/{device}/panel').json['assignments'] == []


def test_full_asset_tabs_preserve_lifecycle_and_permission_scoped_links(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        asset=db.execute("INSERT INTO assets(name,specs,purchase_cost,currency,warranty_end) VALUES ('QA Full Set','{\"Power\":\"65 W\"}',125,'EUR','2028-01-01')").lastrowid
        db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,1,2)',(asset,))
        db.execute("INSERT INTO activity_log(action,username,entity_type,entity_id) VALUES ('QA lifecycle changed','admin','asset_entry',?)",(asset,));db.commit()
    for tab in ['overview','details','accessories','assignment','lifecycle','tickets','history']:
        response=client.get(f'/inventory/assets/{asset}?tab={tab}')
        assert response.status_code==200
        if tab=='details':assert b'65 W' in response.data
        if tab=='accessories':assert b'Notebook 000' in response.data
        if tab=='lifecycle':assert b'125' in response.data and b'EUR' in response.data
        if tab=='history':assert b'QA lifecycle changed' in response.data
    assert client.get(f'/inventory/assets/{asset}?tab=wrong').status_code==404
    from test_product_catalog_routes import role
    role(client,'assets-detail-only',['assets.view'])
    response=client.get(f'/inventory/assets/{asset}?tab=accessories')
    assert response.status_code==200 and b'Notebook 000' not in response.data
    assert b'Bild verwalten' not in response.data
    assert b'QA lifecycle changed' not in client.get(f'/inventory/assets/{asset}?tab=history').data
