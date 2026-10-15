from test_inventory_workspace import client


def test_empty_optional_dependency_references_are_null_not_foreign_key_errors(client):
    team=client.post('/api/teams',json={'name':'QA unassigned team','department_id':''})
    assert team.status_code==201
    software=client.post('/api/software',json={'name':'QA unowned software','owner_team_id':''})
    assert software.status_code==201
    installation=client.post('/api/software-installations',json={'software_id':software.json['id'],'device_id':1,'asset_id':''})
    assert installation.status_code==201
    assert client.put('/api/teams/'+str(team.json['id']),json={'name':'QA renamed team','department_id':''}).status_code==200
    assert client.put('/api/software/'+str(software.json['id']),json={'owner_team_id':''}).status_code==200


def test_unknown_or_invalid_dependency_references_fail_before_mutation(client):
    for reference in [True,'bad',999999,-1,10**30]:
        assert client.post('/api/teams',json={'name':'QA invalid team','department_id':reference}).status_code==400
        assert client.post('/api/software',json={'name':'QA invalid software','owner_team_id':reference}).status_code==400
        assert client.post('/api/software-installations',json={'software_id':reference,'device_id':1}).status_code==400
    assert client.get('/api/teams').json==[]
    assert client.get('/api/software').json==[]


def test_delete_dependencies_rejects_in_use_records_without_partial_changes(client):
    department=client.post('/api/departments',json={'name':'QA protected department'}).json['id']
    team=client.post('/api/teams',json={'name':'QA protected team','department_id':department}).json['id']
    software=client.post('/api/software',json={'name':'QA protected software','owner_team_id':team}).json['id']
    installation=client.post('/api/software-installations',json={'software_id':software,'device_id':1}).json['id']
    for path in [f'/api/departments/{department}',f'/api/teams/{team}',f'/api/software/{software}']:
        response=client.delete(path)
        assert response.status_code==409 and 'wird noch verwendet' in response.json['error']
    assert client.get('/api/departments').json[0]['id']==department
    assert client.get('/api/teams').json[0]['id']==team
    assert client.get('/api/software').json[0]['id']==software
    assert client.delete(f'/api/software-installations/{installation}').status_code==200
    assert client.delete(f'/api/software/{software}').status_code==200
    assert client.delete(f'/api/teams/{team}').status_code==200
    assert client.delete(f'/api/departments/{department}').status_code==200
