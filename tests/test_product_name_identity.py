import json
import pytest
import app as inventory_app
from inventorypro.domains.catalog.identity import for_object
from inventorypro.domains.catalog.matching import exact_match,sync_object
from inventorypro.domains.catalog import jobs
from test_inventory_workspace import client
from test_product_matching import product
from test_product_lookup_jobs import provider,enable


@pytest.mark.parametrize('name,maker,model', [
    ('Apple AirPods 4 ANC','Apple','AirPods 4 ANC'), ('AirPods 4','Apple','AirPods 4'),
    ('Apple MacBook Air 13″ M4 · 0001','Apple','MacBook Air 13 M4'), ('iPhone 16 Pro 128GB','Apple','iPhone 16 Pro'),
    ('Bosch GSR 12V-15','Bosch','GSR 12V-15'), ('DeWalt DCD796','DeWalt','DCD796'),
    ('Samsung Galaxy S24 Ultra','Samsung','Galaxy S24 Ultra'), ('Dell OptiPlex 7050 Micro','Dell','OptiPlex 7050 Micro')])
def test_bounded_public_models_in_names_are_recognized(name,maker,model):
    assert for_object({},name)['manufacturer']==maker
    assert for_object({},name)['model']==model


@pytest.mark.parametrize('name',['AirPods 4 · PRIVATE-PERSON','Apple AirPods 4 ANC Büro','Laptop von PRIVATE-PERSON',
    'Apple secret-project-123','Dell PRIVATE-SERVER-123','AirPods 4 and AirPods Pro 2'])
def test_free_form_inventory_names_are_never_provider_queries(name):
    assert not for_object({},name)['model']


def test_explicit_product_fields_and_conflicting_brands_are_never_overwritten():
    assert for_object({'manufacturer':'Other'},'AirPods 4')['model']==''
    assert for_object({'manufacturer':'Apple','model':'AirPods Pro 2'},'AirPods 4')['model']=='AirPods Pro 2'


def test_short_full_reviewed_model_names_can_match_locally(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();identifier=product(db,'AirPods 4')
        assert exact_match(db,{},'AirPods 4')['product_id']==identifier
        db.execute("UPDATE devices SET name='Apple AirPods 4',specs='{}' WHERE id=1")
        assert sync_object(db,'device',1)['product_id']==identifier


def test_name_only_lookup_is_queued_and_cached_for_other_clients(client,monkeypatch):
    calls=provider(monkeypatch)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();enable(db)
        db.execute("UPDATE devices SET name='Apple AirPods 4 ANC',specs=? WHERE id=1",(json.dumps({'Owner':'PRIVATE-PERSON','Standort':'PRIVATE-ROOM'}),))
        assert sync_object(db,'device',1)['reason']=='no_match'
        db.commit();assert jobs.process_next(db,inventory_app.UPLOADS_DIR)
        assert calls[0]['model']=='AirPods 4 ANC' and 'PRIVATE' not in json.dumps(calls)
    photo=client.get('/api/inventory/device/1/photo').json
    assert photo['source']=='catalog' and client.get(photo['url']).status_code==200
