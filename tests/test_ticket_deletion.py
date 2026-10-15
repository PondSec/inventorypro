import sqlite3
import pytest
import app as inventory_app
from inventorypro.domains.tickets.deletion import delete_ticket,TicketDeletionError
from test_inventory_workspace import client
from test_product_catalog_routes import role


def linked_ticket(db):
    ticket=db.execute("INSERT INTO tickets(title,description,status,created_by) VALUES ('QA Delete','QA','open','admin')").lastrowid
    other=db.execute("INSERT INTO tickets(title,description,status,created_by) VALUES ('QA Keep','QA','open','admin')").lastrowid
    asset=db.execute("INSERT INTO assets(name,specs) VALUES ('QA Asset','{}')").lastrowid
    db.execute("INSERT INTO ticket_comments(ticket_id,author,body) VALUES (?,'admin','QA comment')",(ticket,))
    db.execute("INSERT INTO ticket_watchers(ticket_id,email) VALUES (?,'qa@example.invalid')",(ticket,))
    db.execute('INSERT INTO ticket_assets(ticket_id,asset_id) VALUES (?,?)',(ticket,asset))
    db.execute("INSERT INTO roadmaps(ticket_id,title) VALUES (?,'QA Roadmap')",(ticket,))
    db.execute("INSERT INTO knowledge_entries(related_ticket_id,title,content) VALUES (?,'QA Knowledge','Keep this')",(ticket,))
    check=db.execute('SELECT id FROM health_check_definitions LIMIT 1').fetchone()[0]
    db.execute("INSERT INTO health_incidents(check_id,status,summary,opened_at,ticket_id) VALUES (?,'open','Keep incident','2026-01-01',?)",(check,ticket))
    db.execute("INSERT INTO attachments(entity_type,entity_id,original_filename,stored_filename) VALUES ('ticket',?,'QA.txt','qa-file.txt')",(ticket,))
    return ticket,other,asset


def test_delete_detaches_health_knowledge_roadmap_and_preserves_independent_data(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();ticket,other,asset=linked_ticket(db);db.commit()
    result=client.delete(f'/api/tickets/{ticket}')
    assert result.status_code==200 and result.json['detached']=={'roadmap':1,'knowledge_entry':1,'health_incident':1}
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT id FROM tickets WHERE id=?',(other,)).fetchone()
        assert db.execute('SELECT id FROM assets WHERE id=?',(asset,)).fetchone()
        for table,column in [('roadmaps','ticket_id'),('knowledge_entries','related_ticket_id'),('health_incidents','ticket_id')]:
            row=db.execute(f'SELECT {column} FROM {table} ORDER BY id DESC LIMIT 1').fetchone();assert row and row[0] is None
        for table in ['ticket_comments','ticket_watchers','ticket_assets']:assert db.execute(f'SELECT count(*) FROM {table} WHERE ticket_id=?',(ticket,)).fetchone()[0]==0
        assert db.execute("SELECT deleted_at FROM attachments WHERE entity_type='ticket' AND entity_id=?",(ticket,)).fetchone()[0]
        assert db.execute("SELECT count(*) FROM activity_log WHERE action='ticket_unlinked'").fetchone()[0]==3
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert client.delete(f'/api/tickets/{ticket}').status_code==404


def test_unexpected_reference_rolls_back_every_detachment_and_owned_row(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();ticket,_,_=linked_ticket(db)
        db.execute('CREATE TABLE qa_ticket_reference(ticket_id INTEGER REFERENCES tickets(id))');db.execute('INSERT INTO qa_ticket_reference VALUES (?)',(ticket,));db.commit()
    result=client.delete(f'/api/tickets/{ticket}')
    assert result.status_code==409 and result.json['code']=='ticket_in_use'
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        assert db.execute('SELECT ticket_id FROM roadmaps').fetchone()[0]==ticket
        assert db.execute('SELECT count(*) FROM ticket_comments WHERE ticket_id=?',(ticket,)).fetchone()[0]==1
        assert db.execute('SELECT deleted_at FROM attachments WHERE entity_id=?',(ticket,)).fetchone()[0] is None


def test_delete_requires_domain_read_and_delete_permissions(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();ticket,_,_=linked_ticket(db);db.commit()
    role(client,'read-no-delete',['tickets.view_all'])
    assert client.delete(f'/api/tickets/{ticket}').status_code==403


def test_review_guard_is_rechecked_inside_the_transaction(client):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();ticket,other,_=linked_ticket(db)
        db.execute('INSERT INTO ticket_review_links(change_ticket_id,review_ticket_id) VALUES (?,?)',(ticket,other));db.commit()
        with pytest.raises(TicketDeletionError,match='Review'):delete_ticket(db,ticket,log_activity=lambda *args:None)
        assert db.execute('SELECT count(*) FROM tickets').fetchone()[0]==2
