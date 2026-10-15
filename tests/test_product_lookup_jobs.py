from io import BytesIO
import json
from PIL import Image
import pytest
import app as inventory_app
from inventorypro.domains.catalog import jobs
from test_inventory_workspace import client


def enable(db):
    return jobs.update_settings(db,{'enabled':True,'rightsReviewed':True,'expectedUpdatedAt':jobs.settings(db)['updated_at']})


def identity():return {'manufacturer':'QA Maker','model':'QA Model 123','mpn':'','model_code':'','gtin':''}


def configure(db):
    enable(db);db.execute('UPDATE devices SET specs=? WHERE id IN (1,2)',(json.dumps(identity()),));db.commit()


def provider(monkeypatch,*,status='matched'):
    calls=[]
    def lookup(value):
        calls.append(value)
        if status!='matched':return {'status':status,'candidates':[]}
        return {'status':'matched','identity':value,'entity':{'source_ref':'Q123','source_url':'https://www.wikidata.org/wiki/Q123','name':'QA Model 123'},
            'image':{'image_url':'https://upload.wikimedia.org/wikipedia/commons/a/ab/File.png','source_kind':'commons','source_ref':'File:QA.png',
            'source_url':'https://commons.wikimedia.org/wiki/File:QA.png','license_code':'CC-BY-4.0','attribution':'QA Author','changes':'Reencoded'}}
    stream=BytesIO();Image.new('RGB',(30,20),'navy').save(stream,format='PNG')
    monkeypatch.setattr(jobs.commons,'lookup',lookup);monkeypatch.setattr(jobs,'fetch',lambda *args,**kwargs:(stream.getvalue(),'image/png'))
    return calls


def test_public_source_disabled_by_default_and_requires_explicit_review(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert not jobs.enabled(db)
        assert jobs.enqueue(db,'device',1,identity()) is None
        with pytest.raises(jobs.service.CatalogError):jobs.update_settings(db,{'enabled':True,'rightsReviewed':False,'expectedUpdatedAt':jobs.settings(db)['updated_at']})
    assert client.post('/api/catalog/external/queue',json={}).status_code==409


def test_verified_gtin_only_lookup_assigns_cached_image_without_inventing_identifiers(client,monkeypatch):
    provider(monkeypatch);original=jobs.commons.lookup
    def lookup(value):
        result=original(value);result['entity']['verified_gtin']=value['gtin'];return result
    monkeypatch.setattr(jobs.commons,'lookup',lookup)
    value={**identity(),'model':'','gtin':'4006381333931'}
    with inventory_app.app.app_context():
        db=inventory_app.get_db();enable(db)
        db.execute('UPDATE devices SET specs=? WHERE id=1',(json.dumps(value),))
        jobs.enqueue(db,'device',1,value);db.commit()
        assert jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert db.execute("SELECT value FROM product_identifiers WHERE kind='gtin'").fetchone()[0]==value['gtin']
    photo=client.get('/api/inventory/device/1/photo').json
    assert photo['source']=='catalog' and client.get(photo['url']).status_code==200


def test_deduplicated_lookup_downloads_once_and_survives_new_connection(client,monkeypatch):
    calls=provider(monkeypatch)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db)
        first=jobs.enqueue(db,'device',1,identity());second=jobs.enqueue(db,'device',2,identity());assert first==second
        db.commit();assert jobs.process_next(db,inventory_app.UPLOADS_DIR);assert not jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert len(calls)==1 and jobs.status(db)['counts']=={'matched':1}
    for identifier in [1,2]:
        photo=client.get(f'/api/inventory/device/{identifier}/photo').json
        assert photo['source']=='catalog' and photo['attribution']=='QA Author'
        assert client.get(photo['url']).status_code==200
    with inventory_app.app.app_context():
        db=inventory_app.get_db();jobs.enqueue(db,'device',1,identity());db.commit()
        assert not jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert len(calls)==1


@pytest.mark.parametrize('outcome',['no_match','ambiguous','unlicensed','no_image'])
def test_missing_or_unsafe_source_is_cached_without_fake_image(client,monkeypatch,outcome):
    provider(monkeypatch,status=outcome)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db);jobs.enqueue(db,'device',1,identity());db.commit()
        assert jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert jobs.status(db)['counts']=={outcome:1}
        assert not db.execute('SELECT 1 FROM product_models').fetchone()
    assert client.get('/api/inventory/device/1/photo').json['source']=='fallback'


def test_failed_network_keeps_inventory_unchanged_and_error_visible(client,monkeypatch):
    def fail(*args,**kwargs):raise jobs.ProviderError('QA network unavailable')
    monkeypatch.setattr(jobs.commons,'lookup',fail)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db);jobs.enqueue(db,'device',1,identity());db.commit()
        before=[tuple(row) for row in db.execute('SELECT * FROM devices')]
        jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert jobs.status(db)['recent'][0]['message']=='QA network unavailable'
        assert [tuple(row) for row in db.execute('SELECT * FROM devices')]==before
        assert not db.execute('SELECT 1 FROM product_models').fetchone()


def test_expired_worker_lease_reclaimed_and_other_workers_excluded(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db);jobs.enqueue(db,'device',1,identity());db.commit()
        first=jobs.claim(db);assert first and not jobs.claim(db)
        db.execute('UPDATE product_lookup_jobs SET lease_until=0');db.commit()
        second=jobs.claim(db);assert second['lease_token']!=first['lease_token']
        assert not jobs._current(db,first) and jobs._current(db,second)


def test_disabling_source_during_lookup_prevents_download_and_import(client,monkeypatch):
    provider(monkeypatch);original=jobs.commons.lookup
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db);jobs.enqueue(db,'device',1,identity());db.commit()
        def lookup(value):
            result=original(value)
            jobs.update_settings(db,{'enabled':False,'rightsReviewed':True,'expectedUpdatedAt':jobs.settings(db)['updated_at']});db.commit()
            return result
        monkeypatch.setattr(jobs.commons,'lookup',lookup)
        monkeypatch.setattr(jobs,'fetch',lambda *a,**k:pytest.fail('Disabled source must not download'))
        jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert not db.execute('SELECT 1 FROM product_models').fetchone()
        assert not jobs.claim(db)


def test_object_edited_during_lookup_is_not_assigned_old_result(client,monkeypatch):
    provider(monkeypatch);original=jobs.commons.lookup
    with inventory_app.app.app_context():
        db=inventory_app.get_db();configure(db);jobs.enqueue(db,'device',1,identity());db.commit()
        def lookup(value):
            result=original(value);db.execute("UPDATE devices SET specs='{}' WHERE id=1");db.commit();return result
        monkeypatch.setattr(jobs.commons,'lookup',lookup)
        jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert not db.execute('SELECT 1 FROM device_product_media WHERE device_id=1').fetchone()
        assert jobs.status(db)['counts']=={'matched':1}


def test_external_settings_require_management_and_version(client):
    from test_product_catalog_routes import role
    current=client.get('/api/catalog/external').json['settings']
    payload={'enabled':True,'rightsReviewed':True,'expectedUpdatedAt':current['updated_at']}
    assert client.put('/api/catalog/external',json=payload).status_code==200
    assert client.put('/api/catalog/external',json=payload).status_code==409
    assert client.post('/api/catalog/external/queue',json={'after':{'device':True}}).status_code==400
    role(client,'reader',['devices.view'])
    assert client.get('/api/catalog/external').status_code==403
    assert client.put('/api/catalog/external',json=payload).status_code==403
    assert client.post('/api/catalog/external/queue',json={}).status_code==403
