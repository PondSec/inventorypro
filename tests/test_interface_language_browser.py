import pytest
from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser,live_inventory,sign_in
from test_unified_assets_browser import unified_live


def set_language(page,language):
    result=page.evaluate('''async language=>{const response=await fetch('/api/settings/server',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({appearance:{language}})});return response.status}''',language)
    assert result==200


def test_english_modules_dynamic_feedback_and_business_values(unified_live,browser):
    live_inventory=unified_live
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(error.stack));page.on('console',lambda message:errors.append(message.text) if message.type=='error' and 'Alpine' in message.text else None);sign_in(page,live_inventory)
    set_language(page,'en')
    for route in ['/inventory','/tickets','/admin/tickets/categories','/settings','/procurement','/health','/stats','/dependencies','/time-machine','/knowledge','/roadmap','/locations','/users','/account/security']:
        response=page.goto(live_inventory+route);assert response.status==200,route
        page.wait_for_load_state('networkidle')
        expect(page.locator('html')).to_have_attribute('lang','en')
        expect(page.get_by_role('button',name='Toggle navigation',exact=True)).to_be_visible()
        expect(page.locator('.app-sidebar')).to_contain_text('Settings')
        expect(page.locator('.app-sidebar')).to_contain_text('Knowledge base')
        assert not errors,(route,errors)
    page.goto(live_inventory+'/inventory/assets/new')
    page.get_by_label('Name *',exact=True).fill('Standort');page.get_by_role('button',name='Save',exact=True).click()
    expect(page.locator('.object-header h1')).to_have_text('Standort')
    page.get_by_role('button',name='Edit',exact=True).click()
    expect(page.get_by_label('Name *',exact=True)).to_have_value('Standort')
    page.get_by_role('button',name='Cancel',exact=True).click()
    page.get_by_role('link',name='Contained assets',exact=True).click();page.get_by_role('button',name='Add assets',exact=True).click()
    expect(page.get_by_role('dialog',name='Select contained assets')).to_be_visible()
    expect(page.get_by_text('No assets selected yet.',exact=True)).to_be_visible()
    page.get_by_role('button',name='Cancel',exact=True).click()
    set_language(page,'de');page.reload();expect(page.get_by_role('button',name='Bearbeiten',exact=True)).to_be_visible()
    assert not errors,errors
    context.close()
