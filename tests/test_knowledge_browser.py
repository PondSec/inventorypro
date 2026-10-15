from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in


def test_knowledge_editor_error_retry_history_and_unsaved_input(live_inventory,browser):
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/knowledge')
    page.get_by_test_id('open-entry-modal').click();modal=page.get_by_test_id('entry-modal')
    modal.get_by_label('Titel',exact=True).fill('QA Knowledge Created')
    modal.get_by_label('Inhalt / Lösung').fill('Synthetic article body')
    page.once('dialog',lambda dialog:dialog.dismiss());modal.get_by_role('button',name='Abbrechen',exact=True).click()
    expect(modal).to_be_visible();expect(modal.get_by_label('Titel',exact=True)).to_have_value('QA Knowledge Created')
    page.route('**/api/knowledge/entries',lambda route:route.fulfill(status=503,json={'error':'QA temporary failure'}))
    modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal.get_by_role('alert')).to_contain_text('QA temporary failure')
    expect(modal.get_by_label('Inhalt / Lösung')).to_have_value('Synthetic article body')
    page.unroute('**/api/knowledge/entries');modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('button').filter(has=page.locator('strong',has_text='QA Knowledge Created')).click()
    expect(page.get_by_role('heading',name='QA Knowledge Created',exact=True)).to_be_visible()
    assert 'entry_id=' in page.url
    page.go_back();expect(page.get_by_role('heading',name='Artikel',exact=True)).to_be_visible()
    page.go_forward();expect(page.get_by_role('heading',name='QA Knowledge Created',exact=True)).to_be_visible()
    page.get_by_role('button',name='Bearbeiten',exact=True).click();expect(modal.get_by_label('Titel',exact=True)).to_have_value('QA Knowledge Created')
    modal.get_by_label('Titel',exact=True).fill('QA Knowledge Updated');modal.get_by_role('button',name='Speichern',exact=True).click()
    expect(page.get_by_role('heading',name='QA Knowledge Updated',exact=True)).to_be_visible()
    assert not errors,errors
    context.close()
