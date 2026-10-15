from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in
from test_workspace_search import seed


def test_topbar_search_and_knowledge_roadmap_deep_links(live_inventory,browser):
    _,article,roadmap=seed()
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.keyboard.press('Control+k')
    search=page.locator('.global-search input');expect(search).to_be_focused();search.fill('QA Needle');search.press('Enter')
    page.wait_for_url('**/search?q=QA+Needle')
    expect(page.get_by_role('heading',name='Wissensbasis',exact=True)).to_be_visible()
    page.get_by_role('link',name='QA Needle knowledge QA summary',exact=True).click()
    expect(page.locator('h3').filter(has_text='QA Needle knowledge')).to_be_visible()
    page.go_back();page.get_by_role('link',name='QA Needle roadmap QA objective',exact=True).click()
    expect(page.locator('[x-text="selectedRoadmap.title"]')).to_have_text('QA Needle roadmap')
    assert not errors,errors
    context.close()
