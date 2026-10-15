from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from test_ticket_deletion import linked_ticket


def test_linked_ticket_bulk_delete_preserves_roadmap_knowledge_and_incident(live_inventory,browser):
    with inventory_app.app.app_context():
        db=inventory_app.get_db();ticket,other,_=linked_ticket(db);db.commit()
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/tickets?queue=all-open')
    page.get_by_role('checkbox',name=f'Ticket {ticket} auswählen',exact=True).check()
    page.get_by_role('checkbox',name=f'Ticket {other} auswählen',exact=True).check()
    page.once('dialog',lambda dialog:dialog.accept())
    with page.expect_response(lambda response:response.url.endswith(f'/api/tickets/{other}') and response.request.method=='DELETE') as deleted:
        page.get_by_role('button',name='Löschen',exact=True).click()
    assert deleted.value.status==200
    expect(page.get_by_role('checkbox',name=f'Ticket {ticket} auswählen',exact=True)).to_have_count(0)
    expect(page.get_by_role('checkbox',name=f'Ticket {other} auswählen',exact=True)).to_have_count(0)
    with inventory_app.app.app_context():
        db=inventory_app.get_db();assert db.execute('SELECT ticket_id FROM roadmaps').fetchone()[0] is None
        assert db.execute('SELECT related_ticket_id FROM knowledge_entries ORDER BY id DESC LIMIT 1').fetchone()[0] is None
        assert db.execute('SELECT ticket_id FROM health_incidents').fetchone()[0] is None
    assert not errors,errors
    context.close()
