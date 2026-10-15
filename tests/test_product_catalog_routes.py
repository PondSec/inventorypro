from io import BytesIO
from PIL import Image
import pytest
import app as inventory_app
from test_inventory_workspace import client


def image_data(**extra):
    stream=BytesIO();Image.new('RGB',(100,80),'blue').save(stream,format='PNG');stream.seek(0)
    return {'image':(stream,'picture.png','image/png'),'rightsConfirmed':'true','attribution':'QA Author',**extra}


def create(client):
    response=client.post('/api/catalog/models',json={'manufacturer':'QA Maker','name':'QA Model 123'})
    assert response.status_code==201
    return response.json


def test_catalog_upload_resolution_override_and_authenticated_cache(client):
    model=create(client)
    uploaded=client.post(f"/api/catalog/models/{model['id']}/images",data=image_data(expectedUpdatedAt=model['updated_at']))
    assert uploaded.status_code==201
    picture=uploaded.json['images'][0]
    url=picture['url'];response=client.get(url)
    assert response.status_code==200 and response.mimetype=='image/webp'
    assert 'private, no-cache' in response.headers['Cache-Control']
    assert client.get(url,headers={'If-None-Match':response.headers['ETag']}).status_code==304
    state=client.get('/api/inventory/device/1/photo').json
    response=client.post('/api/inventory/device/1/photo',json={'action':'assign','product_id':model['id'],'expectedUpdatedAt':state['updated_at']})
    assert response.status_code==200 and response.json['source']=='catalog'
    old_version=response.json['updated_at']
    override=client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt=old_version))
    assert override.status_code==201 and override.json['source']=='individual'
    assert override.json['attribution']=='QA Author'
    state=override.json
    assert client.post('/api/inventory/device/1/photo',json={'action':'hide','expectedUpdatedAt':old_version}).status_code==409
    assert client.get(state['url']).status_code==200
    hidden=client.post('/api/inventory/device/1/photo',json={'action':'hide','expectedUpdatedAt':state['updated_at']}).json
    assert not hidden['url']
    assert client.get(state['url']).status_code==404
    client.post('/api/inventory/device/1/photo',json={'action':'show','expectedUpdatedAt':hidden['updated_at']})
    with client.session_transaction() as session:session.clear()
    assert client.get(url).status_code==302
    assert client.get(state['url'],headers={'If-None-Match':response.headers.get('ETag','')}).status_code==302


def role(client,name,permissions):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        uid=db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',(name,'unused')).lastrowid
        rid=db.execute('INSERT INTO roles(name) VALUES (?)',(name,)).lastrowid
        db.execute('INSERT INTO user_roles(user_id,role_id) VALUES (?,?)',(uid,rid))
        for permission in permissions:db.execute('INSERT INTO role_permissions(role_id,permission_id) SELECT ?,id FROM permissions WHERE key=?',(rid,permission))
        db.commit()
    with client.session_transaction() as session:session['username']=name


def test_inventory_readers_cannot_manage_global_catalog_or_other_domain_photos(client):
    model=create(client)
    role(client,'devices-read',['devices.view'])
    assert client.get('/api/catalog/models').status_code==200
    assert client.get('/api/inventory/device/1/photo').status_code==200
    assert client.get('/api/inventory/asset/1/photo').status_code==403
    assert client.post('/api/inventory/device/1/photo',json={'action':'hide','expectedUpdatedAt':''}).status_code==403
    assert client.post('/api/catalog/models',json={}).status_code==403
    assert client.put(f"/api/catalog/models/{model['id']}",json={}).status_code==403
    assert client.delete(f"/api/catalog/models/{model['id']}",json={}).status_code==403
    assert client.post('/api/catalog/reconcile',json={}).status_code==403


def test_private_override_hash_cannot_be_served_as_catalog_or_another_object(client):
    model=create(client)
    response=client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt=''))
    digest=response.json['hash']
    assert client.get(f"/media/catalog/{model['id']}/{digest}/thumb").status_code==404
    assert client.get(f'/media/inventory/device/2/{digest}/thumb').status_code==404
    assert client.get(response.json['url']+'/invalid').status_code==404
    assert client.get(response.json['url'].replace('/thumb','/original')).status_code==404


def test_uploads_enforce_csrf_origin_rights_and_parser_size(client,monkeypatch):
    monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt='')).status_code==403
    token=client.get('/api/csrf-token').json['csrfToken'];headers={'X-CSRF-Token':token}
    assert client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt=''),headers={**headers,'Origin':'https://evil.example'}).status_code==403
    data=image_data(expectedUpdatedAt='');data['rightsConfirmed']='false'
    assert client.post('/api/inventory/device/1/photo/upload',data=data,headers=headers).status_code==400
    assert client.post('/api/inventory/device/1/photo/upload',data=image_data(expectedUpdatedAt=''),headers=headers).status_code==201
    huge={'image':(BytesIO(b'x'*(8*1024*1024+65536)),'huge.png','image/png'),'expectedUpdatedAt':''}
    assert client.post('/api/inventory/device/2/photo/upload',data=huge,headers=headers).status_code==413


def test_model_versions_rollback_errors_rate_limits_and_reconciliation(client):
    model=create(client)
    data={'manufacturer':'Other','name':'QA Model 456','expectedUpdatedAt':model['updated_at']}
    result=client.put(f"/api/catalog/models/{model['id']}",json=data)
    assert result.status_code==200
    assert client.put(f"/api/catalog/models/{model['id']}",json=data).status_code==409
    assert client.post('/api/catalog/reconcile',json={'after':{'device':[]}}).status_code==400
    assert client.post('/api/catalog/reconcile',json={}).json['processed']==40
    for _ in range(13):response=client.post('/api/inventory/device/1/photo/upload',data={})
    assert response.status_code==429 and response.headers['Retry-After']=='60'
    assert client.get('/api/catalog/models?page=bad').status_code==200
