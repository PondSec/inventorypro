from test_inventory_workspace import client


def test_about_identifies_author_and_license_without_exposing_instance_configuration(client):
    response=client.get('/about');assert response.status_code==200
    body=response.get_data(as_text=True)
    assert 'Joshua Pond' in body and 'Inventory Pro Community License' in body
    assert 'paid hosted service, SaaS product' in body and 'keine OSI' in body
    assert 'APP_SECRET_KEY' not in body and '/opt/' not in body
    assert client.get('/inventory').get_data(as_text=True).count('href="/about"')==1


def test_about_requires_login(client):
    client.get('/logout')
    with client.session_transaction() as session:session.clear()
    response=client.get('/about');assert response.status_code==302 and '/login' in response.location
