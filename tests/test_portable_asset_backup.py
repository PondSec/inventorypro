from io import BytesIO
import json
import zipfile
import sqlite3
import pytest
import app as inventory_app
from test_inventory_workspace import client
from test_unified_asset_routes import unified_client,create
from test_product_catalog_routes import image_data
from inventorypro.domains.inventory.unification import convert_inventory


@pytest.mark.parametrize('format',['json','sqlite','xlsx','csv'])
def test_export_archive_restores_assets_contents_and_server_photos_in_second_instance(unified_client,tmp_path,monkeypatch,format):
    client=unified_client;parent=create(client,'QA portable PC');child=create(client,'QA portable CPU')
    assert client.put(f"/api/inventory/assets/{parent['id']}/components",json={'expectedRevision':parent['revision'],'items':[{'id':child['id'],'quantity':2}]}).status_code==200
    state=client.get(f"/api/inventory/asset/{parent['id']}/photo").json
    uploaded=client.post(f"/api/inventory/asset/{parent['id']}/photo/upload",data=image_data(expectedUpdatedAt=state['updated_at']))
    assert uploaded.status_code==201,uploaded.json
    photo=uploaded.json
    assert photo['source']=='individual'
    assert client.post(f"/api/inventory/assets/{parent['id']}/tags",json={'tag':'QA portable tag'}).status_code==201
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        db.execute('UPDATE server_settings SET allow_db_export=1,allow_db_import=1,export_format=?,include_uploads=1,import_mode=?',(format,'append'));db.commit()
    exported=client.get('/api/export')
    assert exported.status_code==200
    with zipfile.ZipFile(BytesIO(exported.data)) as archive:
        assert any(name.startswith('uploads/product-media/') and name.endswith('thumb.webp') for name in archive.namelist())
        if format=='json':
            payload=json.loads(archive.read('inventory_export.json'))
            assert payload['asset_components'] and payload['asset_product_media'] and payload['asset_tags']
    # A distinct database AND uploads directory model a new server, not just a
    # second request using the original files/cache.
    monkeypatch.setattr(inventory_app,'DATABASE',str(tmp_path/'restored.db'))
    monkeypatch.setattr(inventory_app,'UPLOADS_DIR',tmp_path/'restored-uploads')
    inventory_app.init_db()
    with inventory_app.app.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        db.execute('UPDATE users SET must_change_password=0')
        db.execute("UPDATE server_settings SET allow_db_import=1,include_uploads=1,import_mode='append'");db.commit()
    restored=client.post('/api/import',data={'file':(BytesIO(exported.data),'inventory_export.zip','application/zip')})
    assert restored.status_code==200,restored.json
    state=client.get(f"/api/inventory/assets/{parent['id']}").json
    assert state['name']=='QA portable PC' and state['components'][0]['id']==child['id'] and state['components'][0]['quantity']==2
    media=client.get(f"/api/inventory/asset/{parent['id']}/photo").json
    assert media['hash']==photo['hash'] and media['source']=='individual'
    assert client.get(media['url']).status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT tag FROM asset_tags WHERE asset_id=?',(parent['id'],)).fetchone()[0]=='QA portable tag'
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==42
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_merge_updates_rows_without_delete_cascades_and_bad_references_roll_back(unified_client):
    parent=create(unified_client,'QA merge PC')
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        db.execute('INSERT INTO asset_tags(asset_id,tag) VALUES (?,?)',(parent['id'],'QA keep'))
        inventory_app.import_data_payload(db,{'assets':[{'id':parent['id'],'name':'QA merged'}]},'merge',('assets',))
        assert db.execute('SELECT tag FROM asset_tags WHERE asset_id=?',(parent['id'],)).fetchone()[0]=='QA keep'
        assert db.execute('SELECT name FROM assets WHERE id=?',(parent['id'],)).fetchone()[0]=='QA merged'
        with pytest.raises(sqlite3.IntegrityError):inventory_app.import_data_payload(db,{'assets':[{'id':parent['id'],'name':'QA must rollback','location_id':999999}]},'merge',('assets',))
        assert db.execute('SELECT name FROM assets WHERE id=?',(parent['id'],)).fetchone()[0]=='QA merged'


def test_conflicting_uploaded_file_rejects_entire_archive_without_overwriting(unified_client):
    client=unified_client
    with inventory_app.app.app_context():
        db=inventory_app.get_db();db.execute('UPDATE server_settings SET allow_db_import=1,include_uploads=1');db.commit()
    path=inventory_app.UPLOADS_DIR/'attachments'/'qa.txt';path.parent.mkdir(parents=True);path.write_bytes(b'QA existing file')
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('inventory_export.json',json.dumps({'assets':[{'id':999,'name':'QA must not import'}]}))
        archive.writestr('uploads/attachments/qa.txt',b'QA conflicting file')
    response=client.post('/api/import',data={'file':(BytesIO(stream.getvalue()),'qa.zip')})
    assert response.status_code==400
    assert path.read_bytes()==b'QA existing file'
    with inventory_app.app.app_context():assert not inventory_app.get_db().execute('SELECT 1 FROM assets WHERE id=999').fetchone()
