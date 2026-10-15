from pathlib import Path
import sqlite3
import pytest
import app as inventory_app
from inventorypro.migrations import apply_migrations, rollback_migrations


def test_product_schema_is_additive_versioned_and_rolls_back_without_inventory_loss(isolated_inventory):
    with isolated_inventory.app_context():
        db = inventory_app.get_db()
        original = [tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]
        assert db.execute('SELECT external_enabled,rights_reviewed,local_auto_match FROM product_catalog_settings').fetchone()[:] == (0,0,1)
        product = db.execute("INSERT INTO product_models(manufacturer,manufacturer_key,name,model_key) VALUES ('Example','example','QA Model','qamodel')").lastrowid
        db.execute("INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'mpn','example','qa1')",(product,))
        db.execute("INSERT INTO device_product_media(device_id,product_id,match_method) VALUES (1,?,'manual')",(product,))
        db.commit()
        db.execute('DELETE FROM product_models WHERE id=?',(product,));db.commit()
        assert db.execute('SELECT product_id FROM device_product_media WHERE device_id=1').fetchone()[0] is None
        assert db.execute('SELECT count(*) FROM product_identifiers').fetchone()[0] == 0
        assert [tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')] == original
        directory = Path(inventory_app.__file__).parent/'migrations'
        assert rollback_migrations(db,directory) == ['006_product_catalog']
        assert [tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')] == original
        assert apply_migrations(db,directory) == ['006_product_catalog']
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_media_constraints_reject_invalid_hashes_and_cross_entity_references(isolated_inventory):
    with isolated_inventory.app_context():
        db = inventory_app.get_db()
        for digest in ('../../outside','x'*64,'A'*64):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute('INSERT INTO product_media_files(hash,width,height,size_bytes) VALUES (?,40,40,100)',(digest,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO device_product_media(device_id,product_id) VALUES (1,99999)')
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO asset_product_media(asset_id) VALUES (99999)')
