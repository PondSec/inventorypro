import json
from pathlib import Path
import sqlite3
import stat
import pytest
import app as inventory_app
from test_inventory_workspace import client
from test_product_catalog_routes import image_data
from inventorypro.domains.inventory.unification import UnificationError


def use_production_default(monkeypatch):
    monkeypatch.delitem(inventory_app.app.config,'INVENTORY_UNIFIED_ASSETS_ENABLED')


def test_existing_installation_upgrades_automatically_with_verified_snapshot_and_restart(client,monkeypatch):
    uploaded=client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt=''))
    assert uploaded.status_code==201
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        parent=db.execute("INSERT INTO assets(name,specs) VALUES ('QA upgrade PC',?)",(json.dumps({'Unknown existing field':'Keep'}),)).lastrowid
        db.execute('DROP INDEX idx_asset_devices_unique')
        db.execute("INSERT INTO asset_devices(asset_id,device_id,quantity,notes) VALUES (?,1,2,'QA first')",(parent,))
        db.execute("INSERT INTO asset_devices(asset_id,device_id,quantity,notes) VALUES (?,1,3,'QA second')",(parent,));db.commit()
        db.execute('UPDATE server_settings SET update_policy_json=?',(json.dumps({'autoUpdateEnabled':False,'maintenanceWindow':'04:15','channel':'stable','checkIntervalMinutes':90}),));db.commit()
        before={table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')] for table in ['devices','assets','asset_devices','users','user_roles','role_permissions','server_settings']}
    use_production_default(monkeypatch);inventory_app.init_db()
    backup_paths=list((Path(inventory_app.DATABASE).parent/'backups'/'pre-asset-conversion').glob('*.sqlite3'))
    assert len(backup_paths)==1 and stat.S_IMODE(backup_paths[0].stat().st_mode)==0o600
    with sqlite3.connect(backup_paths[0]) as backup:
        assert backup.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert backup.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==0
        for table,rows in before.items():assert backup.execute('SELECT * FROM '+table+' ORDER BY id').fetchall()==rows
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==41
        for table in ['devices','asset_devices','users','user_roles','role_permissions','server_settings']:
            assert [tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')]==before[table]
        assert tuple(db.execute('SELECT * FROM assets WHERE id=?',(parent,)).fetchone())==before['assets'][0]
        assert db.execute('SELECT quantity,notes FROM asset_components WHERE parent_asset_id=?',(parent,)).fetchone()[:]==(5,'QA first\nQA second')
        mapped=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
    photo=client.get(f'/api/inventory/asset/{mapped}/photo').json
    assert photo['hash']==uploaded.json['hash'] and client.get(photo['url']).status_code==200
    assert client.get('/').location=='/inventory'
    inventory_app.init_db()
    assert len(list(backup_paths[0].parent.glob('*.sqlite3')))==1
    assert client.get('/api/inventory/assets').json['total']==41


def test_invalid_legacy_quantity_stops_upgrade_without_partial_inventory(client,monkeypatch):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();parent=db.execute("INSERT INTO assets(name) VALUES ('QA invalid contents')").lastrowid
        db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,1,0)',(parent,));db.commit()
    use_production_default(monkeypatch)
    with pytest.raises(UnificationError):inventory_app.init_db()
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0]==40
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM asset_legacy_devices').fetchone()[0]==0
        assert db.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==0
        assert db.execute('SELECT quantity FROM asset_devices').fetchone()[0]==0
    assert list((Path(inventory_app.DATABASE).parent/'backups'/'pre-asset-conversion').glob('*.sqlite3'))


def test_backup_failure_stops_before_database_writes(client,monkeypatch):
    from inventorypro.domains.inventory import upgrade
    use_production_default(monkeypatch)
    def unavailable(*args):raise OSError('QA disk unavailable')
    monkeypatch.setattr(upgrade,'backup_before_conversion',unavailable)
    with pytest.raises(OSError,match='QA disk'):inventory_app.init_db()
    assert client.get('/api/inventory/assets').status_code==404
    with inventory_app.app.app_context():assert inventory_app.get_db().execute('SELECT count(*) FROM devices').fetchone()[0]==40


def test_new_installation_uses_canonical_assets_without_a_manual_switch(isolated_inventory,tmp_path,monkeypatch):
    monkeypatch.setattr(inventory_app,'DATABASE',str(tmp_path/'fresh.db'));use_production_default(monkeypatch)
    inventory_app.init_db()
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('SELECT count(*) FROM product_images').fetchone()[0]>=1
    assert not (tmp_path/'backups').exists()


def test_removed_empty_defaults_are_not_recreated_on_restart(client,monkeypatch):
    use_production_default(monkeypatch);inventory_app.init_db()
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        category=db.execute("SELECT m.asset_category_id,v.revision FROM categories c JOIN asset_legacy_categories m ON m.category_id=c.id JOIN asset_category_versions v ON v.category_id=m.asset_category_id WHERE c.name='Laptop'").fetchone()
        location=db.execute("SELECT id FROM locations WHERE name='Lager'").fetchone()[0]
    assert client.delete(f'/api/inventory/categories/{category[0]}',json={'expectedRevision':category[1]}).status_code==200
    assert client.delete(f'/api/locations/{location}').status_code==200
    inventory_app.init_db()
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert not db.execute("SELECT 1 FROM categories WHERE name='Laptop'").fetchone()
        assert not db.execute('SELECT 1 FROM asset_categories WHERE id=?',(category[0],)).fetchone()
        assert not db.execute('SELECT 1 FROM locations WHERE id=?',(location,)).fetchone()
