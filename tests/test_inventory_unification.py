import json
import pytest
import app as inventory_app
from inventorypro.domains.inventory.unification import convert_inventory,UnificationError


def test_conversion_preserves_all_legacy_rows_fields_and_asset_content(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        original={table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')] for table in ['devices','categories']}
        original_fields=json.dumps({'Capacity':{'type':'number','required':True}})
        old_category=db.execute("INSERT INTO asset_categories(name,fields) VALUES ('Notebooks',?)",(original_fields,)).lastrowid
        parent=db.execute("INSERT INTO assets(name,category_id,specs,purchase_cost,currency) VALUES ('QA Set',?,'{}',125,'EUR')",(old_category,)).lastrowid
        before_parent=tuple(db.execute('SELECT * FROM assets WHERE id=?',(parent,)).fetchone())
        # Simulate a historical database before the legacy unique-link index.
        db.execute('DROP INDEX idx_asset_devices_unique')
        db.execute("INSERT INTO asset_devices(asset_id,device_id,quantity,notes) VALUES (?,1,2,'First note')",(parent,))
        db.execute("INSERT INTO asset_devices(asset_id,device_id,quantity,notes) VALUES (?,1,3,'Second note')",(parent,))
        db.execute("UPDATE devices SET name='Notebook 000' WHERE id=2")
        original['devices']=[tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]
        result=convert_inventory(db)
        assert result=={'categories':len(original['categories']),'assets':40,'components':1,'pictures':0}
        assert convert_inventory(db)==dict.fromkeys(result,0)
        for table,rows in original.items():assert [tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')]==rows
        assert tuple(db.execute('SELECT * FROM assets WHERE id=?',(parent,)).fetchone())==before_parent
        category=db.execute("SELECT m.asset_category_id FROM asset_legacy_categories m JOIN categories c ON c.id=m.category_id WHERE c.name='Notebooks'").fetchone()[0]
        assert category!=old_category
        assert db.execute('SELECT name FROM asset_categories WHERE id=?',(category,)).fetchone()[0]=='Notebooks (2)'
        child=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        assert db.execute('SELECT serial_number FROM assets WHERE id=?',(child,)).fetchone()[0]=='QA-000'
        assert db.execute('SELECT quantity,notes FROM asset_components WHERE parent_asset_id=?',(parent,)).fetchone()[:]==(5,'First note\nSecond note')
        assert db.execute('SELECT count(*) FROM assets WHERE name=?',('Notebook 000',)).fetchone()[0]==2
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==1
        db.commit()
        inventory_app.init_db()
        assert db.execute('SELECT count(*) FROM assets WHERE name=?',('Notebook 000',)).fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM asset_devices').fetchone()[0]==2


def test_conversion_references_individual_photos_without_copying_private_files(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();digest='c'*64
        db.execute('INSERT INTO product_media_files(hash,width,height,size_bytes) VALUES (?,40,40,100)',(digest,))
        db.execute("INSERT INTO device_product_media(device_id,override_hash,match_method,override_attribution,override_license_code) VALUES (1,?,'manual','QA Owner','LicenseRef-UserProvided')",(digest,))
        assert convert_inventory(db)['pictures']==1
        row=db.execute('SELECT ap.* FROM asset_product_media ap JOIN asset_legacy_devices m ON m.asset_id=ap.asset_id WHERE m.device_id=1').fetchone()
        assert row['override_hash']==digest and row['override_attribution']=='QA Owner' and row['match_method']=='manual'
        assert db.execute('SELECT count(*) FROM product_media_files').fetchone()[0]==1


def test_invalid_existing_quantity_rolls_back_the_entire_conversion(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();parent=db.execute("INSERT INTO assets(name,specs) VALUES ('QA Broken Set','{}')").lastrowid
        db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,1,0)',(parent,));db.commit()
        with pytest.raises(UnificationError):convert_inventory(db)
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM asset_legacy_devices').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM asset_legacy_categories').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='idx_assets_category_name'").fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0]==40


def test_conversion_does_not_widen_or_rewrite_existing_permissions(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        tables=['users','roles','permissions','role_permissions','user_roles']
        before={table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in tables}
        convert_inventory(db)
        for table in tables:assert [tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]==before[table]
