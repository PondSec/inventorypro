import sqlite3
from pathlib import Path

from inventorypro.migrations import execute_migration_script


def test_plans_do_not_create_inventory_and_deleted_assets_leave_research_intact():
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    for table in ['users', 'assets', 'asset_categories']:
        db.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY)')
        db.execute(f'INSERT INTO {table} VALUES (1)')
    migration = Path(__file__).parents[1] / 'migrations/017_wishes_and_projects.sql'
    execute_migration_script(db, migration.read_text())
    db.execute("INSERT INTO wish_projects(id,owner_id,name,asset_id) VALUES (1,1,'Workshop',1)")
    db.execute("INSERT INTO wishes(id,owner_id,name,project_id,category_id) VALUES (1,1,'Workbench',1,1)")
    assert db.execute('SELECT count(*) FROM assets').fetchone()[0] == 1
    db.execute("INSERT INTO wish_acquisitions(wish_id,asset_id,asset_name,currency,actor_id,request_key) VALUES (1,1,'Workbench','EUR',1,'qa')")
    db.execute('DELETE FROM assets WHERE id=1')
    assert db.execute('SELECT asset_id FROM wish_acquisitions').fetchone()[0] is None
    assert db.execute('SELECT asset_id FROM wish_projects').fetchone()[0] is None
    db.execute('DELETE FROM wish_projects WHERE id=1')
    assert db.execute('SELECT project_id FROM wishes').fetchone()[0] is None
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    execute_migration_script(db, migration.with_suffix('.down.sql').read_text())
    assert db.execute('SELECT count(*) FROM assets').fetchone()[0] == 0


def test_feature_migrations_can_be_removed_without_losing_owned_assets(isolated_inventory):
    import app as inventory_app
    from inventorypro.migrations import rollback_migrations
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        db.execute("INSERT INTO assets(name,specs) VALUES ('Retain owned equipment','{}')")
        db.commit()
        result=rollback_migrations(db,Path(__file__).parents[1]/'migrations',steps=2)
        assert result==['018_wish_lookup_indexes','017_wishes_and_projects']
        assert db.execute("SELECT 1 FROM assets WHERE name='Retain owned equipment'").fetchone()
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wishes'").fetchone()
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
