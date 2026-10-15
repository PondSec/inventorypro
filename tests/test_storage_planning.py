import copy
import json
from itertools import combinations

import pytest
import app as inventory_app
from inventorypro.domains.planning.service import dimension_suggestions


@pytest.fixture
def planning(isolated_inventory):
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        category=db.execute("INSERT INTO asset_categories(name,fields) VALUES ('QA dimensions',?)",(json.dumps({'Breite':{'type':'number','unit':'cm'},'Höhe':{'type':'number','unit':'cm'},'Tiefe':{'type':'number','unit':'cm'}}),)).lastrowid
        container=db.execute('INSERT INTO assets(name,category_id,specs) VALUES (?,?,?)',('QA Container',category,json.dumps({'Breite':10,'Höhe':10,'Tiefe':10}))).lastrowid
        item=db.execute('INSERT INTO assets(name,category_id,specs) VALUES (?,?,?)',('QA Box',category,json.dumps({'Breite':2,'Höhe':2,'Tiefe':2}))).lastrowid
        db.commit()
    client=isolated_inventory.test_client()
    with client.session_transaction() as session:
        session.update(logged_in=True,username='admin',mfa_verified=True)
    payload={'name':'QA plan','container_id':container,'container':{'width':100,'height':100,'depth':100},'unit':'mm',
             'items':[{'id':item,'dimensions':{'width':20,'height':20,'depth':20},'quantity':8}], 'clearance':2,'gap':3,'allow_rotation':True}
    return client,payload


def test_automatically_detects_and_converts_dimension_fields():
    result=dimension_suggestions({'Breite':10,'Höhe':2,'Tiefe':30},{'Breite':{'unit':'cm'},'Höhe':{'unit':'m'},'Tiefe':{'unit':'mm'}})
    assert result['dimensions']=={'width':100,'height':2000,'depth':30}
    assert dimension_suggestions({'Width [cm]':10,'Height':2,'Depth':3},{})['dimensions']['width']==100
    assert dimension_suggestions({'Breite':10},{'Breite':{'unit':'kg'}})['warnings']
    assert 'width' not in dimension_suggestions({'Breite':10,'Width':20},{})['dimensions']


def test_preview_respects_walls_gaps_and_has_no_overlapping_boxes(planning):
    client,payload=planning
    response=client.post('/api/planning/preview',json=payload)
    assert response.status_code==200,response.data
    result=response.json
    assert result['placed_count']==8 and result['total_count']==8
    assert 'optimal' in result['message']
    for placement in result['placements']:
        for coord,axis in [('x','width'),('y','depth'),('z','height')]:
            assert placement[coord]>=2
            assert placement[coord]+placement[axis]<=98.0001
    for first,second in combinations(result['placements'],2):
        assert any(first[coord]+first[axis]+3 <= second[coord]+.0001 or second[coord]+second[axis]+3 <= first[coord]+.0001
                   for coord,axis in [('x','width'),('y','depth'),('z','height')])


@pytest.mark.parametrize('change',[
    {'unit':'kg'}, {'unit':[]}, {'container':{'width':0,'height':1,'depth':1}},
    {'container':{'width':'nan','height':1,'depth':1}}, {'container':{'width':'inf','height':1,'depth':1}},
    {'clearance':100}, {'gap':-1}, {'allow_rotation':'yes'}, {'items':[]},
    {'items':[{'id':999999,'dimensions':{'width':1,'height':1,'depth':1}}]},
])
def test_invalid_planning_inputs_are_actionable_and_do_not_mutate_inventory(planning,change):
    client,payload=planning
    response=client.post('/api/planning/preview',json={**payload,**change})
    assert response.status_code==400
    assert response.json['error']
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT count(*) FROM storage_plans').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==2


def test_quantity_limit_self_reference_and_duplicate_ids(planning):
    client,payload=planning
    for quantity in [0,201,1.5,True]:
        data=copy.deepcopy(payload);data['items'][0]['quantity']=quantity
        assert client.post('/api/planning/preview',json=data).status_code==400
    data=copy.deepcopy(payload);data['items'][0]['id']=data['container_id']
    assert client.post('/api/planning/preview',json=data).status_code==400
    data=copy.deepcopy(payload);data['items']*=2
    assert client.post('/api/planning/preview',json=data).status_code==400


def test_packing_reports_unplaced_items_without_claiming_impossibility(planning):
    client,payload=planning
    payload['items'][0]['dimensions']={'width':200,'height':200,'depth':200}
    response=client.post('/api/planning/preview',json=payload)
    assert response.status_code==200
    assert response.json['unplaced_count']==8
    assert response.json['plan_status']=='partial'


def test_plan_save_read_delete_and_no_taxonomy_side_effects(planning):
    client,payload=planning
    created=client.post('/api/planning/plans',json=payload)
    assert created.status_code==201,created.data
    plan_id=created.json['id']
    saved=client.get(f'/api/planning/plans/{plan_id}').json
    assert saved['preview']['placed_count']==8
    assert saved['payload']==payload
    assert len(client.get('/api/planning/plans').json['items'])==1
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT count(*) FROM asset_relations').fetchone()[0]==0
    assert client.delete(f'/api/planning/plans/{plan_id}').status_code==200
    assert client.get(f'/api/planning/plans/{plan_id}').status_code==404


def test_legacy_dimension_resolver_rejects_nonfinite_values():
    dimensions,missing,invalid=inventory_app.resolve_dimension_triplet({'w':'inf','h':'nan','d':4},{'width':'w','height':'h','depth':'d'})
    assert len(invalid)==2 and dimensions=={'depth':4}


def test_readonly_planning_user_cannot_save_or_delete(planning):
    client,payload=planning
    created=client.post('/api/planning/plans',json=payload).json['id']
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        user=db.execute("INSERT INTO users(username,password_hash) VALUES ('planner-reader','unused')").lastrowid
        role=db.execute("INSERT INTO roles(name) VALUES ('Planning read')").lastrowid
        db.execute('INSERT INTO user_roles(user_id,role_id) VALUES (?,?)',(user,role))
        db.execute("INSERT INTO role_permissions(role_id,permission_id) SELECT ?,id FROM permissions WHERE key='assets.view'",(role,))
        db.commit()
    with client.session_transaction() as session:
        session['username']='planner-reader'
    assert client.post('/api/planning/preview',json=payload).status_code==200
    assert client.get(f'/api/planning/plans/{created}').status_code==200
    assert client.post('/api/planning/plans',json=payload).status_code==403
    assert client.delete(f'/api/planning/plans/{created}').status_code==403
    with client.session_transaction() as session:
        session.clear()
    assert client.get('/api/planning/plans').status_code==302


def test_unified_planning_respects_converted_scope_in_search_preview_and_saved_plans(planning):
    from inventorypro.domains.inventory.unification import convert_inventory
    from test_product_catalog_routes import role
    client,payload=planning
    with inventory_app.app.app_context():
        db=inventory_app.get_db();convert_inventory(db)
        hidden=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=1').fetchone()[0];db.commit()
    saved=client.post('/api/planning/plans',json=payload)
    assert saved.status_code==201
    role(client,'planning-original-assets',['assets.view','assets.manage'])
    assert client.get('/api/planning/assets?q=Notebook').json['total']==0
    hidden_payload=copy.deepcopy(payload);hidden_payload['items'][0]['id']=hidden
    assert client.post('/api/planning/preview',json=hidden_payload).status_code==403
    assert client.post('/api/planning/plans',json=hidden_payload).status_code==403
    assert client.get('/api/planning/plans/'+str(saved.json['id'])).status_code==200
    role(client,'planning-converted-only',['devices.view','devices.manage'])
    assert client.get('/inventory/planning').status_code==200
    assert client.get('/api/planning/assets?q=Notebook').json['total']==40
    assert client.get('/api/planning/plans').json['items']==[]
    assert client.get('/api/planning/plans/'+str(saved.json['id'])).status_code==403
