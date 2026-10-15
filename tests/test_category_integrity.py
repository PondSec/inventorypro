"""Deleting taxonomy must preserve inventory, including related records."""
import json

import pytest
import app as inventory_app


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    for name, value in {
        'DATABASE': str(tmp_path / 'inventory.db'), 'UPLOADS_DIR': tmp_path / 'uploads',
        'APP_INSTANCE_PATH': tmp_path / 'instance', 'RUNTIME_CONFIG_PATH': tmp_path / 'runtime.json',
        'RUNTIME_SETTINGS_CACHE': {'host': '127.0.0.1', 'port': 0, 'debug': False},
        'INITIAL_ADMIN_CREDENTIALS_PATH': None,
    }.items():
        monkeypatch.setattr(inventory_app, name, value)
    inventory_app.init_db()
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        for table in ('categories', 'asset_categories'):
            db.execute(f"INSERT INTO {table} (id, name, fields) VALUES (901, 'Quelle', ?), (902, 'Ziel', ?)", ('{}', '{}'))
        db.execute("INSERT INTO devices (id, name, category_id, serial_number, specs) VALUES (901, 'Laptop', 901, 'SN-901', ?)", (json.dumps({'RAM': 32}),))
        db.execute("INSERT INTO device_tags (device_id, tag) VALUES (901, 'Test')")
        db.execute("INSERT INTO device_notes (device_id, note) VALUES (901, 'Erhalten')")
        db.execute("INSERT INTO maintenance_tasks (device_id, title) VALUES (901, 'Prüfung')")
        db.execute("INSERT INTO assets (id, name, category_id, specs, purchase_cost) VALUES (901, 'RAM', 901, ?, 100)", (json.dumps({'entries': [{'id': 'entry-1', 'quantity': 4}]}),))
        db.execute("UPDATE users SET must_change_password = 0 WHERE username = 'admin'")
        db.commit()
    client = inventory_app.app.test_client()
    with client.session_transaction() as session:
        session.update(logged_in=True, username='admin', mfa_verified=True)
    return client


@pytest.mark.parametrize('path,table', [('categories', 'devices'), ('asset-categories', 'assets')])
def test_used_category_blocks_plain_and_legacy_force_delete(inventory, path, table):
    for query in ('', '?force=true'):
        response = inventory.delete(f'/api/{path}/901{query}')
        assert response.status_code == 409
        assert response.json['code'] == 'category_in_use'
        assert response.json['references'][table] == 1
    with inventory_app.app.app_context():
        assert inventory_app.get_db().execute(f'SELECT category_id FROM {table} WHERE id=901').fetchone()[0] == 901


@pytest.mark.parametrize('path,table', [('categories', 'devices'), ('asset-categories', 'assets')])
def test_explicit_reassignment_preserves_every_object_column_and_children(inventory, path, table):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        before = dict(db.execute(f'SELECT * FROM {table} WHERE id=901').fetchone())
        children = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} WHERE device_id=901')]
                    for t in ('device_tags', 'device_notes', 'maintenance_tasks')}
    response = inventory.delete(f'/api/{path}/901', json={'target_category_id': 902})
    assert response.status_code == 200
    assert response.json['reassigned'] == 1
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        after = dict(db.execute(f'SELECT * FROM {table} WHERE id=901').fetchone())
        assert after == {**before, 'category_id': 902}
        for child, rows in children.items():
            assert [tuple(r) for r in db.execute(f'SELECT * FROM {child} WHERE device_id=901')] == rows


@pytest.mark.parametrize('target', [901, 999999, True, '902', -1, 902.5])
def test_invalid_target_does_not_mutate_inventory(inventory, target):
    response = inventory.delete('/api/categories/901', json={'target_category_id': target})
    assert response.status_code == 400
    with inventory_app.app.app_context():
        assert inventory_app.get_db().execute('SELECT category_id FROM devices WHERE id=901').fetchone()[0] == 901


def test_planning_reference_blocks_asset_taxonomy_removal(inventory):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        db.execute('UPDATE asset_categories SET binpacking_config=? WHERE id=902',
                   (json.dumps({'enabled': True, 'content_category_id': 901}),))
        db.commit()
    response = inventory.delete('/api/asset-categories/901', json={'target_category_id': 902})
    assert response.status_code == 409
    assert response.json['code'] == 'category_used_in_planning'


def test_empty_category_and_missing_category(inventory):
    assert inventory.delete('/api/categories/902').status_code == 200
    assert inventory.delete('/api/categories/902').status_code == 404


def test_reassignment_permission_is_separate_from_category_management(inventory):
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        user_id = db.execute("INSERT INTO users (username, password_hash) VALUES ('taxonomy', 'unused')").lastrowid
        role_id = db.execute("INSERT INTO roles (name) VALUES ('Taxonomie')").lastrowid
        db.execute('INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)', (user_id, role_id))
        db.execute("INSERT INTO role_permissions (role_id, permission_id) SELECT ?, id FROM permissions WHERE key='categories.manage'", (role_id,))
        db.commit()
    with inventory.session_transaction() as session:
        session['username'] = 'taxonomy'
    assert inventory.delete('/api/categories/901', json={'target_category_id': 902}).status_code == 403
    assert inventory.delete('/api/categories/901').status_code == 409
