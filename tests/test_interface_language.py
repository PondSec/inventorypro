import pytest
import app as inventory_app
from test_unified_asset_routes import unified_client,create
from test_inventory_workspace import client


def test_language_setting_persists_without_restart_or_inventory_changes(unified_client):
    client=unified_client;item=create(client,'Standort');before=client.get('/api/settings/server').json
    saved=client.patch('/api/settings/server',json={'appearance':{'language':'en'}})
    assert saved.status_code==200 and saved.json['settings']['appearance']=={'language':'en'}
    assert saved.json['meta']['pendingRestart']==before['meta']['pendingRestart']
    assert client.get('/api/settings/server').json['settings']['appearance']['language']=='en'
    page=client.get(f"/inventory/assets/{item['id']}").get_data(as_text=True)
    assert '<html lang="en"' in page and 'Standort</h1>' in page
    assert client.get(f"/api/inventory/assets/{item['id']}").json['name']=='Standort'
    second=inventory_app.app.test_client()
    assert '<html lang="en"' in second.get('/login').get_data(as_text=True)


@pytest.mark.parametrize('value',['fr','EN','',None,True,{},['de']])
def test_language_rejects_unsupported_values_without_changing_settings(unified_client,value):
    response=unified_client.patch('/api/settings/server',json={'appearance':{'language':value}})
    assert response.status_code==400
    assert unified_client.get('/api/settings/server').json['settings']['appearance']['language']=='de'


def test_language_change_requires_admin_permission_and_csrf(unified_client,monkeypatch):
    from test_product_catalog_routes import role
    monkeypatch.setitem(inventory_app.app.config,'TESTING',False)
    assert unified_client.patch('/api/settings/server',json={'appearance':{'language':'en'}}).status_code==403
    token=unified_client.get('/api/csrf-token').json['csrfToken']
    role(unified_client,'asset-reader',['assets.view'])
    assert unified_client.patch('/api/settings/server',json={'appearance':{'language':'en'}},headers={'X-CSRF-Token':token}).status_code==403


def test_public_catalog_is_static_cacheable_and_conditional(unified_client):
    client=inventory_app.app.test_client()
    first=client.get('/i18n/en.js');assert first.status_code==200
    assert first.content_type.startswith('application/javascript') and first.headers.get('ETag')
    second=client.get('/i18n/en.js',headers={'If-None-Match':first.headers['ETag']})
    assert second.status_code==304
    assert b'password_hash' not in first.data
