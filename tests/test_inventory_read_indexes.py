from pathlib import Path
import app as inventory_app
from inventorypro.migrations import apply_migrations, rollback_migrations
from inventorypro.domains.inventory.service import list_inventory


def test_inventory_indexes_support_actual_read_paths_and_rollback_preserves_rows(isolated_inventory):
    with isolated_inventory.app_context():
        db = inventory_app.get_db()
        queries = [
            ('SELECT asset_id FROM asset_devices WHERE device_id=1','idx_inventory_asset_devices_device'),
            ('SELECT id FROM asset_assignment_history WHERE asset_id=1 ORDER BY created_at DESC,id DESC LIMIT 1','idx_inventory_assignment_latest'),
            ("SELECT max(created_at) FROM activity_log WHERE entity_type='device' AND entity_id=1",'idx_inventory_activity_modified'),
            ("SELECT action FROM activity_log WHERE entity_type='device' AND entity_id=1 ORDER BY id DESC LIMIT 100",'idx_inventory_activity_history'),
        ]
        for query,index in queries:
            plan = ' '.join(str(row['detail']) for row in db.execute('EXPLAIN QUERY PLAN '+query))
            assert index in plan, plan
        before = list_inventory(db,{},devices_allowed=True,assets_allowed=True,maintenance_allowed=True)
        directory = Path(inventory_app.__file__).parent/'migrations'
        assert rollback_migrations(db,directory) == ['005_inventory_read_indexes']
        assert list_inventory(db,{},devices_allowed=True,assets_allowed=True,maintenance_allowed=True) == before
        assert apply_migrations(db,directory) == ['005_inventory_read_indexes']
        assert list_inventory(db,{},devices_allowed=True,assets_allowed=True,maintenance_allowed=True) == before
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
