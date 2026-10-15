import json
import pytest
import app as inventory_app
from inventorypro.domains.inventory import assets
from inventorypro.domains.inventory.unification import convert_inventory


def all_permissions(key):return True


def callbacks():return {'parse_fields':inventory_app.parse_field_definitions,'validate_specs':inventory_app.validate_dynamic_specs}


def create(db,name,**extra):return assets.create_asset(db,all_permissions,{'name':name,**extra},**callbacks())


def test_nested_assets_quantities_and_reverse_use_preserve_independent_children(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        workstation=create(db,'Arbeitsplatz');pc=create(db,'Mini PC XY');cpu=create(db,'CPU XY');ram=create(db,'RAM XY')
        pc=assets.set_component(db,all_permissions,pc['id'],cpu['id'],1,'Sockel',pc['revision'])
        pc=assets.set_component(db,all_permissions,pc['id'],ram['id'],2,'DIMM',pc['revision'])
        workstation=assets.set_component(db,all_permissions,workstation['id'],pc['id'],1,'',workstation['revision'])
        assert [(item['name'],item['quantity']) for item in pc['components']]==[('CPU XY',1),('RAM XY',2)]
        assert assets.get_asset(db,all_permissions,pc['id'])['used_in'][0]['id']==workstation['id']
        assert assets.get_asset(db,all_permissions,cpu['id'])['used_in'][0]['id']==pc['id']
        with pytest.raises(assets.AssetError,match='Kreis'):
            assets.set_component(db,all_permissions,cpu['id'],workstation['id'],1,'',cpu['revision'])
        assert db.execute('SELECT count(*) FROM asset_components').fetchone()[0]==3
        assets.delete_asset(db,all_permissions,workstation['id'],workstation['revision'])
        assert assets.get_asset(db,all_permissions,pc['id'])['used_in']==[]
        assert assets.get_asset(db,all_permissions,pc['id'])['components']==pc['components']
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_concurrent_edit_and_composition_cannot_overwrite_revision(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db);parent=create(db,'PC');child=create(db,'RAM')
        updated=assets.update_asset(db,all_permissions,parent['id'],{'name':'PC renamed','expectedRevision':parent['revision']},**callbacks())
        with pytest.raises(assets.AssetError,match='inzwischen'):
            assets.set_component(db,all_permissions,parent['id'],child['id'],1,'',parent['revision'])
        assert not updated['components']
        linked=assets.set_component(db,all_permissions,parent['id'],child['id'],1,'',updated['revision'])
        with pytest.raises(assets.AssetError):assets.update_asset(db,all_permissions,parent['id'],{'name':'Stale','expectedRevision':updated['revision']},**callbacks())
        assert assets.get_asset(db,all_permissions,parent['id'])['name']=='PC renamed'
        assert linked['revision']>updated['revision']


def test_imported_device_permissions_do_not_expose_old_assets_or_hidden_components(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();secret=create(db,'Private original asset');convert_inventory(db)
        mapped=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0]
        assets.set_component(db,all_permissions,mapped,secret['id'],1,'Hidden',assets.version(db,mapped))
        device_only=lambda key:key in {'devices.view','devices.manage'}
        assert assets.get_asset(db,device_only,mapped)['components']==[]
        with pytest.raises(assets.AssetError) as error:assets.get_asset(db,device_only,secret['id'])
        assert error.value.status==403
        own=assets.create_asset(db,device_only,{'name':'Scoped new asset'},**callbacks())
        assert assets.permission_scope(db,own['id'])=='devices'
        asset_only=lambda key:key in {'assets.view','assets.manage'}
        with pytest.raises(assets.AssetError):assets.get_asset(db,asset_only,mapped)
        assert assets.get_asset(db,asset_only,secret['id'])['name']=='Private original asset'
        predicate,params=assets.scope_predicate(device_only)
        ids={row[0] for row in db.execute('SELECT a.id FROM assets a WHERE '+predicate,params)}
        assert own['id'] in ids and mapped in ids and secret['id'] not in ids


def test_partial_edits_keep_extra_specs_procurement_and_duplicate_physical_names(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        category=db.execute("INSERT INTO asset_categories(name,fields) VALUES ('Memory',?)",(json.dumps({'Kapazität':{'type':'number','unit':'GB'}}),)).lastrowid
        original=create(db,'RAM XY',category_id=category,specs={'Kapazität':16,'Privates Feld':'Erhalten'},purchase_cost=125,currency='EUR',invoice_number='QA-INV')
        same=create(db,'RAM XY',category_id=category)
        assert original['id']!=same['id']
        changed=assets.update_asset(db,all_permissions,original['id'],{'specs':{'Kapazität':32},'expectedRevision':original['revision']},**callbacks())
        assert changed['specs']=={'Kapazität':32,'Privates Feld':'Erhalten'}
        assert changed['purchase_cost']==125 and changed['invoice_number']=='QA-INV'
        with pytest.raises(assets.AssetError):assets.update_asset(db,all_permissions,original['id'],{'specs':{'Kapazität':'invalid'},'expectedRevision':changed['revision']},**callbacks())
        assert assets.get_asset(db,all_permissions,original['id'])['specs']==changed['specs']


@pytest.mark.parametrize('quantity',[0,-1,1.5,True,1000001,'2'])
def test_composition_rejects_bad_quantities_without_partial_change(isolated_inventory,quantity):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db);parent=create(db,'PC');child=create(db,'RAM')
        with pytest.raises(assets.AssetError):assets.set_component(db,all_permissions,parent['id'],child['id'],quantity,'',parent['revision'])
        assert assets.version(db,parent['id'])==parent['revision']
        assert not assets.get_asset(db,all_permissions,parent['id'])['components']


def test_used_child_and_independent_ticket_references_block_unsafe_delete(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db();convert_inventory(db);parent=create(db,'PC');child=create(db,'RAM')
        parent=assets.set_component(db,all_permissions,parent['id'],child['id'],1,'',parent['revision'])
        with pytest.raises(assets.AssetError,match='verwendet'):assets.delete_asset(db,all_permissions,child['id'],child['revision'])
        parent=assets.remove_component(db,all_permissions,parent['id'],child['id'],parent['revision'])
        ticket=db.execute("INSERT INTO tickets(title,description,status,created_by) VALUES ('QA linked ticket','Synthetic','open','admin')").lastrowid
        db.execute('INSERT INTO ticket_assets(ticket_id,asset_id) VALUES (?,?)',(ticket,child['id']))
        with pytest.raises(assets.AssetError,match='Vorgängen'):assets.delete_asset(db,all_permissions,child['id'],child['revision'])
        assert db.execute('SELECT 1 FROM tickets WHERE id=?',(ticket,)).fetchone()
        assert assets.get_asset(db,all_permissions,child['id'])['name']=='RAM'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
