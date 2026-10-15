from playwright.sync_api import expect
from test_enterprise_browser import browser,live_inventory,sign_in


def test_procurement_vendor_contract_order_workflows_and_search(live_inventory,browser):
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,live_inventory);page.goto(live_inventory+'/procurement')
    page.get_by_role('button',name='Lieferant hinzufügen',exact=True).click()
    modal=page.get_by_role('dialog',name='Neuer Lieferant',exact=True)
    modal.get_by_label('Name des Lieferanten',exact=True).fill('QA Supplier Browser')
    modal.get_by_label('E-Mail-Adresse des Lieferanten').fill('qa@example.invalid')
    modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('searchbox',name='Beschaffung durchsuchen').fill('QA Supplier')
    page.get_by_role('button',name='QA Supplier Browser',exact=True).click()
    expect(page.get_by_role('heading',name='QA Supplier Browser',exact=True)).to_be_visible()
    page.get_by_label('Aktionen für QA Supplier Browser',exact=True).click()
    page.locator('[data-row-menu][open]').get_by_role('button',name='Bearbeiten',exact=True).click()
    edit=page.get_by_role('dialog',name='Lieferant bearbeiten',exact=True)
    expect(edit.get_by_label('Name des Lieferanten',exact=True)).to_have_value('QA Supplier Browser')
    edit.get_by_role('button',name='Dialog schließen').click()
    expect(edit).not_to_be_visible()
    page.get_by_role('tab',name='Verträge',exact=True).click()
    page.get_by_role('button',name='Vertrag hinzufügen',exact=True).click()
    modal=page.get_by_role('dialog',name='Neuer Vertrag',exact=True)
    modal.get_by_label('Name des Vertrags',exact=True).fill('QA Contract Browser')
    modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('searchbox',name='Beschaffung durchsuchen').fill('QA Contract')
    expect(page.get_by_role('button',name='QA Contract Browser',exact=True)).to_be_visible()
    page.get_by_role('tab',name='Bestellungen',exact=True).click()
    page.get_by_role('button',name='Bestellung hinzufügen',exact=True).click()
    modal=page.get_by_role('dialog',name='Neue Bestellung',exact=True)
    modal.get_by_label('Bestellnummer',exact=True).fill('QA-PO-BROWSER')
    page.route('**/api/purchase-orders',lambda route:route.fulfill(status=503,json={'error':'QA unavailable'}) if route.request.method=='POST' else route.continue_())
    modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal.get_by_role('alert')).to_contain_text('QA unavailable')
    expect(modal.get_by_label('Bestellnummer',exact=True)).to_have_value('QA-PO-BROWSER')
    page.unroute('**/api/purchase-orders');modal.get_by_role('button',name='Speichern',exact=True).click();expect(modal).not_to_be_visible()
    page.get_by_role('searchbox',name='Beschaffung durchsuchen').fill('QA-PO')
    expect(page.get_by_role('button',name='QA-PO-BROWSER',exact=True)).to_be_visible()
    for width in [1440,1280,390]:
        page.set_viewport_size({'width':width,'height':900})
        for theme in ['light','dark']:
            page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
            page.wait_for_function("document.documentElement.scrollWidth<=innerWidth+1")
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),page.evaluate("[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width && r.right>innerWidth+1 && getComputedStyle(el).position!=='fixed'}).slice(0,12).map(el=>({tag:el.tagName,cls:el.className,width:el.getBoundingClientRect().width,right:el.getBoundingClientRect().right}))")
    assert not errors,errors
    context.close()
