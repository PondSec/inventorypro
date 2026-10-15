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
