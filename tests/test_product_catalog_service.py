from io import BytesIO
import pytest
from PIL import Image
import app as inventory_app
from inventorypro.domains.catalog.service import (CatalogError, create_model, update_model, delete_model,
    get_model, list_models, image_metadata, add_model_image, update_model_image)
from inventorypro.domains.catalog.media import store_image


def test_catalog_crud_normalizes_identifiers_checks_versions_and_keeps_inventory(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        before=[tuple(row) for row in db.execute('SELECT * FROM devices')]
        model=create_model(db,{'manufacturer':'Apple Inc.','name':'MacBook Air 13 M4','modelIdentifier':'Mac16,12','gtin':'036000291452','aliases':['MacBook Air 13″ M4']})
        assert len(model['identifiers'])==3
        assert list_models(db,'Mac16,12')['total']==1
        assert list_models(db,'%')['total']==0
        with pytest.raises(CatalogError,match='bereits'):create_model(db,{'manufacturer':'Apple','name':'MacBook Air 13 M4'})
        payload={'manufacturer':'Apple','name':'MacBook Air 13 M4','mpn':'AB-12','expectedUpdatedAt':model['updated_at']}
        changed=update_model(db,model['id'],payload)
        assert changed['updated_at']!=model['updated_at']
        assert any(item['value']=='ab-12' for item in changed['identifiers'])
        with pytest.raises(CatalogError) as error:update_model(db,model['id'],payload)
        assert error.value.status==409
        db.execute("INSERT INTO device_product_media(device_id,product_id,match_method) VALUES (1,?,'manual')",(model['id'],))
        delete_model(db,model['id'],changed['updated_at'])
        assert db.execute('SELECT product_id FROM device_product_media WHERE device_id=1').fetchone()[0] is None
        assert [tuple(row) for row in db.execute('SELECT * FROM devices')]==before


@pytest.mark.parametrize('payload',[None,[],{'manufacturer':[], 'name':'M4'}, {'manufacturer':'Apple','name':'M4','gtin':'036000291451'},
    {'manufacturer':'Apple','name':'M4','source_url':'https://user:secret@example.com/a'}, {'manufacturer':'Apple','name':'M4','source_url':'https://['}])
def test_malformed_catalog_payloads_have_controlled_errors(isolated_inventory,payload):
    with isolated_inventory.app_context():
        with pytest.raises(CatalogError):create_model(inventory_app.get_db(),payload)


@pytest.mark.parametrize('confirmed',[None,False,[],{},1])
def test_image_use_requires_explicit_rights_confirmation(confirmed):
    with pytest.raises(CatalogError):image_metadata({'rightsConfirmed':confirmed},'QA')


def test_reviewed_images_deduplicate_reorder_and_detach_without_deleting_files(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();model=create_model(db,{'manufacturer':'QA','name':'QA Model 123'})
        def add(color,model):
            stream=BytesIO();Image.new('RGB',(100,60),color).save(stream,format='PNG');stream.seek(0)
            media=store_image(db,inventory_app.UPLOADS_DIR,stream,mime_type='image/png')
            meta=image_metadata({'rightsConfirmed':True,'source_url':'https://example.com/source','attribution':'QA Author'},'QA')
            return add_model_image(db,model['id'],media,meta,model['updated_at'])
        model=add('blue',model);model=add('red',model);model=add('blue',model)
        assert len(model['images'])==2
        assert model['images'][0]['attribution']=='QA Author'
        second=model['images'][1]['id']
        model=update_model_image(db,model['id'],second,model['updated_at'])
        assert model['images'][0]['id']==second
        model=update_model_image(db,model['id'],second,model['updated_at'],remove=True)
        assert len(model['images'])==1
        assert db.execute('SELECT count(*) FROM product_media_files').fetchone()[0]==2
        assert len(list(inventory_app.UPLOADS_DIR.rglob('full.webp')))==2
