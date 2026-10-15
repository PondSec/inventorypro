import json
import pytest
import app as inventory_app
from inventorypro.domains.catalog.matching import compact, exact_match, identity_from_specs, part_key, sync_object, sync_inventory, suggest_models, touch_catalog, valid_gtin


def product(db,name='MacBook Air 13″ M4',manufacturer='Apple',identifier=None):
    key=compact(manufacturer)
    identifier=identifier or compact(name)
    result=db.execute('INSERT INTO product_models(manufacturer,manufacturer_key,name,model_key) VALUES (?,?,?,?)',(manufacturer,key,name,compact(name))).lastrowid
    db.execute("INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'name',?,?)",(result,key,identifier))
    return result


@pytest.mark.parametrize('code',['4006381333931','96385074','036000291452','00012345600012'])
def test_gtin_preserves_leading_zeroes_and_validates_check_digits(code):
    assert valid_gtin(code)==code
    assert valid_gtin(code[:-1]+str((int(code[-1])+1)%10)) is None
    assert valid_gtin('SERIAL-'+code) is None


def test_manufacturer_and_exact_identifiers_match_but_punctuation_and_conflicts_do_not(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();first=product(db)
        db.execute("INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'mpn','apple','ab-12')",(first,))
        db.execute("INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'gtin','','4006381333931')",(first,))
        assert exact_match(db,{'manufacturer':'Apple Inc.','mpn':' AB-12 '})['product_id']==first
        assert exact_match(db,{'manufacturer':'Apple','mpn':'AB12'})['product_id'] is None
        assert exact_match(db,{'mpn':'AB-12'})['product_id'] is None
        assert exact_match(db,{'gtin':'4006381333931'})['product_id']==first
        assert exact_match(db,{'manufacturer':'Lenovo','gtin':'4006381333931'})['reason']=='conflict'
        second=product(db,'QA Other Model','Apple')
        db.execute("INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'mpn','apple','other')",(second,))
        assert exact_match(db,{'manufacturer':'Apple','gtin':'4006381333931','mpn':'other'})['reason']=='conflict'


def test_full_reviewed_model_name_is_exact_but_similar_names_require_confirmation(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();model=product(db)
        for name in ('MacBook Air 13" M4','MacBook Air 13″ M4 · 0001','MacBook Air 13 M4 | QA-0001'):
            assert exact_match(db,{},name)['product_id']==model
        for name in ('MacBook Air','MacBook Air 15 M4','MacBook Air 13 M3','MacBook Pro 13 M4','MacBook Air 13 M4 · Marc'):
            assert exact_match(db,{},name)['product_id'] is None
        assert suggest_models(db,{'manufacturer':'Apple','model':'MacBook Air 13 M3'})[0]['id']==model
        assert exact_match(db,{'manufacturer':'Lenovo'},'MacBook Air 13 M4')['product_id'] is None
        assert exact_match(db,{'manufacturer':'Apple','model':'MacBook Air 15 M4'},'MacBook Air 13 M4')['product_id'] is None
        assert exact_match(db,{'model_code':'Unrecognized model'},'MacBook Air 13 M4')['product_id'] is None
        assert exact_match(db,{'model':'MacBook Air 13 M4'})['product_id']==model


def test_ambiguous_catalog_identifiers_never_assign_automatically(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();first=product(db);product(db,'MacBook Air 13 M4 Variant',identifier=compact('MacBook Air 13 M4'))
        assert exact_match(db,{'manufacturer':'Apple','model':'MacBook Air 13 M4'})['reason']=='conflict'


def test_sensitive_inventory_attributes_are_not_product_identifiers():
    identity=identity_from_specs({'Hersteller':'Apple','Modell':'MacBook Air 13 M4','Modellkennung':'Mac16,12','MPN':'AB-12','EAN':'4006381333931',
        'Seriennummer':'SECRET-SERIAL','Besitzer':'Private Person','Standort':'Secret Room','Asset-Tag':'SECRET-TAG','Barcode':'SECRET-BARCODE'})
    assert identity=={'manufacturer':'Apple','model':'MacBook Air 13 M4','model_code':'Mac16,12','mpn':'AB-12','gtin':'4006381333931'}
    assert 'SECRET' not in json.dumps(identity)
    assert part_key(' AB - 12 ')=='ab-12'


def test_cached_matching_tracks_model_changes_and_keeps_manual_choices(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();model=product(db)
        db.execute('UPDATE devices SET specs=? WHERE id=1',(json.dumps({'Hersteller':'Apple','Modell':'MacBook Air 13 M4'}),))
        assert sync_object(db,'device',1)['product_id']==model
        assert sync_object(db,'device',1)['reason']=='cached'
        db.execute('UPDATE devices SET specs=? WHERE id=1',('{"Hersteller":"Apple","Modell":"MacBook Air 15 M4"}',))
        assert sync_object(db,'device',1)['product_id'] is None
        db.execute("UPDATE device_product_media SET product_id=?,match_method='manual' WHERE device_id=1",(model,))
        assert sync_object(db,'device',1,force=True)['reason']=='manual'
        assert db.execute('SELECT product_id FROM device_product_media WHERE device_id=1').fetchone()[0]==model
        db.execute("UPDATE device_product_media SET match_method='none',suppress_image=1 WHERE device_id=1")
        assert sync_object(db,'device',1,force=True)['reason']=='manual'


def test_catalog_revision_rechecks_misses_and_bulk_reconciliation_is_offline_and_bounded(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        db.execute('UPDATE devices SET specs=? WHERE id=1',('{"Hersteller":"Apple","Modell":"MacBook Air 13 M4"}',))
        assert sync_object(db,'device',1)['product_id'] is None
        model=product(db);touch_catalog(db)
        assert sync_object(db,'device',1)['product_id']==model
        before=[tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]
        result=sync_inventory(db,limit=10)
        assert result['processed']==10 and result['last']['device']==10
        assert sync_inventory(db,limit=10,after=result['last'])['last']['device']==20
        assert [tuple(row) for row in db.execute('SELECT * FROM devices ORDER BY id')]==before
        for index in range(3):db.execute("INSERT INTO assets(name,specs) VALUES (?, '{}')",(f'QA Set {index}',))
        after={'device':40,'asset':0}
        result=sync_inventory(db,limit=2,after=after)
        assert result['processed']==2 and result['last']['device']==40
        result=sync_inventory(db,limit=2,after=result['last'])
        assert result['processed']==1 and result['last']['device']==40
        assert sync_inventory(db,limit=2,after=result['last'])['processed']==0
