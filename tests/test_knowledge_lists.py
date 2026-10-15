import app as inventory_app


def test_knowledge_pagination_filters_and_legacy_response(isolated_inventory):
    client = isolated_inventory.test_client()
    with client.session_transaction() as session:
        session.update(logged_in=True, username='admin', mfa_verified=True)
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        for index in range(70):
            db.execute('INSERT INTO knowledge_entries(title,content,summary) VALUES (?,?,?)',
                       (f'QA article {index:03}', 'Synthetic content', 'Synthetic summary'))
        db.commit()
    legacy = client.get('/api/knowledge/entries?search=QA+article').json
    assert isinstance(legacy, list) and len(legacy) == 70
    first = client.get('/api/knowledge/entries?paginated=1&search=QA+article').json
    second = client.get('/api/knowledge/entries?paginated=1&search=QA+article&page=2').json
    assert first['total'] == 70 and first['pages'] == 3 and len(first['items']) == 25
    assert {row['id'] for row in first['items']}.isdisjoint({row['id'] for row in second['items']})
    assert client.get('/api/knowledge/entries?paginated=1&search=QA+article&page=999').json['page'] == 3
    assert client.get('/api/knowledge/entries?paginated=1&page=invalid').status_code == 200
    result = client.get('/api/knowledge/entries?paginated=1&search=QA+article+069').json
    assert result['total'] == 1 and result['items'][0]['title'] == 'QA article 069'
