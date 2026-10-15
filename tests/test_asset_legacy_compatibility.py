import json
import pytest
import app as inventory_app
from inventorypro.domains.inventory.unification import convert_inventory
from inventorypro.domains.inventory import assets
from test_unified_asset_mutations import callbacks,all_permissions,create


def test_bidirectional_device_fields_keep_one_canonical_asset_and_old_ids(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        device_count=db.execute('SELECT count(*) FROM devices').fetchone()[0]
        current=assets.get_asset(db,all_permissions,identifier)
        updated=assets.update_asset(db,all_permissions,identifier,{'name':'Canonical PC','serial_number':'QA-NEW','expectedRevision':current['revision']},**callbacks())
        assert db.execute('SELECT name,serial_number FROM devices WHERE id=1').fetchone()[:]==('Canonical PC','QA-NEW')
        db.execute("UPDATE devices SET name='Compatibility PC',specs=? WHERE id=1",(json.dumps({'RAM':'32 GB'}),))
        row=assets.get_asset(db,all_permissions,identifier)
        assert row['name']=='Compatibility PC' and row['specs']=={'RAM':'32 GB'}
        assert row['revision']>updated['revision']
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0]==device_count
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==device_count
        assert db.execute('SELECT busy FROM inventory_compat_sync').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_legacy_creation_and_category_mapping_are_atomic_and_not_duplicated(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        category=db.execute("INSERT INTO categories(name,fields) VALUES ('Legacy incoming','{}')").lastrowid
        identifier=db.execute("INSERT INTO devices(name,category_id,serial_number,specs) VALUES ('Legacy incoming PC',?,'OLD-API-ID','{}')",(category,)).lastrowid
        mapped=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=?',(identifier,)).fetchone()[0]
        assert assets.get_asset(db,all_permissions,mapped)['name']=='Legacy incoming PC'
        before=db.execute('SELECT count(*) FROM assets').fetchone()[0]
        assert convert_inventory(db)=={'categories':0,'assets':0,'components':0,'pictures':0}
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==before
        assert db.execute('SELECT busy FROM inventory_compat_sync').fetchone()[0]==0


def test_content_changes_and_removal_synchronize_both_interfaces_without_deleting_items(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();parent=db.execute("INSERT INTO assets(name,specs) VALUES ('Legacy set','{}')").lastrowid
        db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,1,2)',(parent,));convert_inventory(db)
        child=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        current=assets.get_asset(db,all_permissions,parent)
        current=assets.set_component(db,all_permissions,parent,child,3,'New canonical note',current['revision'])
        assert db.execute('SELECT quantity,notes FROM asset_devices WHERE asset_id=? AND device_id=1',(parent,)).fetchone()[:]==(3,'New canonical note')
        db.execute('UPDATE asset_devices SET quantity=4 WHERE asset_id=? AND device_id=1',(parent,))
        assert assets.get_asset(db,all_permissions,parent)['components'][0]['quantity']==4
        db.execute('DELETE FROM asset_devices WHERE asset_id=? AND device_id=1',(parent,))
        assert not assets.get_asset(db,all_permissions,parent)['components']
        current=assets.get_asset(db,all_permissions,parent)
        current=assets.set_component(db,all_permissions,parent,child,1,'',current['revision'])
        assets.remove_component(db,all_permissions,parent,child,current['revision'])
        assert not db.execute('SELECT 1 FROM asset_devices WHERE asset_id=?',(parent,)).fetchone()
        assert db.execute('SELECT 1 FROM devices WHERE id=1').fetchone()
        assert assets.get_asset(db,all_permissions,child)['name']=='Notebook 000'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_cycle_failure_rolls_back_compatibility_guard_and_original_links(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        ids=[row[0] for row in db.execute('SELECT asset_id FROM asset_legacy_devices ORDER BY device_id LIMIT 2')]
        first=assets.set_component(db,all_permissions,ids[0],ids[1],1,'',assets.version(db,ids[0]))
        with pytest.raises(assets.AssetError):assets.set_component(db,all_permissions,ids[1],ids[0],1,'',assets.version(db,ids[1]))
        assert db.execute('SELECT busy FROM inventory_compat_sync').fetchone()[0]==0
        assert len(assets.get_asset(db,all_permissions,ids[0])['components'])==1
        assert not assets.get_asset(db,all_permissions,ids[1])['components']
