from pathlib import Path
import sqlite3
import pytest
import app as inventory_app
from inventorypro.migrations import rollback_migrations,apply_migrations


def assets(db,count=5):
    return [db.execute("INSERT INTO assets(name,specs) VALUES (?, '{}')",(f'QA Asset {index}',)).lastrowid for index in range(count)]


def test_asset_composition_is_additive_and_down_up_keeps_business_records(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();ids=assets(db)
        before=[tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]
        db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity,notes) VALUES (?,?,3,?)',(ids[0],ids[1],'QA quantities'))
        assert db.execute('SELECT quantity,notes FROM asset_components').fetchone()[:]==(3,'QA quantities')
        db.commit();directory=Path(inventory_app.__file__).parent/'migrations'
        later=[row[0] for row in db.execute("SELECT id FROM schema_migrations WHERE id>='009_asset_composition' ORDER BY id")]
        assert rollback_migrations(db,directory,steps=len(later))==list(reversed(later))
        assert [tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]==before
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==5
        assert apply_migrations(db,directory)==later
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_database_blocks_self_links_cycles_and_invalid_quantities(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();a,b,c,d,e=assets(db)
        for parent,child in [(a,b),(b,c),(d,e)]:db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity) VALUES (?,?,1)',(parent,child))
        for parent,child in [(a,a),(c,a),(c,b)]:
            with pytest.raises(sqlite3.IntegrityError):db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity) VALUES (?,?,1)',(parent,child))
        with pytest.raises(sqlite3.IntegrityError,match='cycle'):db.execute('UPDATE asset_components SET parent_asset_id=?,child_asset_id=? WHERE parent_asset_id=?',(c,a,d))
        # The same child can be referenced by more than one assembly, preserving
        # existing multi-set relationships rather than deleting duplicate links.
        db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity) VALUES (?,?,2)',(d,b))
        for quantity in [0,-1,1.5,1000001,'invalid']:
            with pytest.raises(sqlite3.IntegrityError):db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity) VALUES (?,?,?)',(a,e,quantity))
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_removing_a_container_keeps_children_but_contained_assets_require_detachment(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();parent,child=assets(db,2)
        db.execute('INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity) VALUES (?,?,2)',(parent,child))
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM assets WHERE id=?',(child,))
        db.execute('DELETE FROM assets WHERE id=?',(parent,))
        assert db.execute('SELECT name FROM assets WHERE id=?',(child,)).fetchone()[0]=='QA Asset 1'
        assert db.execute('SELECT count(*) FROM asset_components').fetchone()[0]==0
