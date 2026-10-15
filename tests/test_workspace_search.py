import app as inventory_app
from test_inventory_workspace import client
from test_product_catalog_routes import role


def seed():
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        admin=db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        db.execute("INSERT INTO tickets(title,description,created_by,created_by_user_id,status) VALUES ('QA Needle private','QA body','admin',?,'open')",(admin,))
        own=db.execute("INSERT INTO tickets(title,description,created_by,requester_name,status) VALUES ('QA Needle own','QA body','legacy','Reader','open')").lastrowid
        article=db.execute("INSERT INTO knowledge_entries(title,summary,content) VALUES ('QA Needle knowledge','QA summary','QA article')").lastrowid
        roadmap=db.execute("INSERT INTO roadmaps(title,objective,status) VALUES ('QA Needle roadmap','QA objective','planned')").lastrowid
        db.execute("UPDATE devices SET name='QA Needle device' WHERE id=1")
        db.commit();return own,article,roadmap


def test_global_search_matches_real_modules_and_links_to_the_objects(client):
    own,article,roadmap=seed();response=client.get('/search?q=QA%20Needle')
    assert response.status_code==200
    for value in ['QA Needle device','QA Needle private','QA Needle own','QA Needle knowledge','QA Needle roadmap',f'/knowledge?entry_id={article}',f'/roadmap?roadmap_id={roadmap}']:
        assert value.encode() in response.data
    assert b'QA Needle' not in client.get('/search?q=%25').data
    assert b'QA Needle' not in client.get('/search?q=x').data
    assert b'&lt;script&gt;' in client.get('/search?q=%3Cscript%3E').data


def test_global_search_never_exposes_other_domains_or_others_tickets(client):
    own,article,roadmap=seed();role(client,'Reader',['tickets.view_own'])
    response=client.get('/search?q=QA%20Needle')
    assert b'QA Needle own' in response.data
    for forbidden in ['QA Needle private','QA Needle device','QA Needle knowledge','QA Needle roadmap']:
        assert forbidden.encode() not in response.data
    with client.session_transaction() as session:session.clear()
    assert client.get('/search?q=QA%20Needle').status_code==302
