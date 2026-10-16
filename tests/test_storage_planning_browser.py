from playwright.sync_api import expect
import app as inventory_app
from test_enterprise_browser import browser, live_inventory, sign_in
from test_unified_assets_browser import unified_live


def setup_plan(page,base):
    headers={'X-CSRF-Token':page.request.get(base+'/api/csrf-token').json()['csrfToken']}
    created=[]
    for name in ['QA shelf','QA box']:
        response=page.request.post(base+'/api/inventory/assets',data={'name':name},headers=headers)
        assert response.status==201;created.append(response.json()['id'])
    payload={'name':'QA saved plan','container_id':created[0],'container':{'width':100,'height':100,'depth':100},'unit':'mm','items':[{'id':created[1],'dimensions':{'width':20,'height':20,'depth':20},'quantity':2}],'allow_rotation':True}
    result=page.request.post(base+'/api/planning/plans',data=payload,headers=headers)
    assert result.status==201
    return created,result.json()['id']


def test_unified_3d_stays_in_planning_camera_keyboard_and_delete_work(unified_live,browser,tmp_path):
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)));sign_in(page,unified_live)
    ids,plan_id=setup_plan(page,unified_live)
    page.goto(unified_live+'/inventory/planning');page.get_by_text('Gespeicherte Pläne (letzte 50)',exact=True).click()
    page.get_by_role('button',name='QA saved plan',exact=True).click()
    expect(page.locator('.planning-result')).to_contain_text('2 von 2 Stück eingeplant.')
    original=page.url;page.get_by_role('button',name='3D-Ansicht öffnen',exact=True).click()
    dialog=page.get_by_role('dialog',name='3D-Ansicht',exact=True)
    expect(dialog).to_be_visible();assert page.url==original
    expect(dialog.locator('polygon[data-binpacking-step]')).to_have_count(6)
    page.get_by_role('button',name='Front',exact=True).click()
    expect(page.get_by_role('button',name='Front',exact=True)).to_have_attribute('aria-pressed','true')
    step=dialog.get_by_role('group',name='Einräumfolge').get_by_role('button').nth(1)
    step.focus();page.keyboard.press('Enter');expect(step).to_have_attribute('aria-pressed','true')
    for theme in ['light','dark']:
        page.evaluate('(t)=>InventoryTheme.set(t)',theme)
        expect(dialog).to_have_css('background-color', 'rgb(17, 24, 32)' if theme == 'dark' else 'rgb(255, 255, 255)')
        svg=dialog.locator('.binpacking-scene__svg')
        assert svg.evaluate('(s)=>s.getBoundingClientRect().height>250')
        assert svg.evaluate('(s)=>[...s.querySelectorAll("polygon[data-binpacking-step]")].every(p=>{const a=p.getBoundingClientRect(), b=s.getBoundingClientRect(); return a.top>=b.top-1 && a.bottom<=b.bottom+1;})')
        page.screenshot(path=str(tmp_path/f'packing-{theme}.png'),animations='disabled')
        assert dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth+1')
    page.set_viewport_size({'width':390,'height':844})
    assert dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth+1')
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button',name='3D-Ansicht öffnen',exact=True)).to_be_focused()
    page.once('dialog',lambda d:d.dismiss());page.get_by_role('button',name='Plan „QA saved plan“ löschen',exact=True).click()
    expect(page.get_by_role('button',name='QA saved plan',exact=True)).to_be_visible()
    page.route('**/api/planning/plans/*',lambda route:route.fulfill(status=503,json={'error':'QA delete unavailable'}) if route.request.method=='DELETE' else route.continue_())
    page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Plan „QA saved plan“ löschen',exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('QA delete unavailable')
    expect(page.get_by_role('button',name='QA saved plan',exact=True)).to_be_visible()
    page.unroute('**/api/planning/plans/*')
    page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Plan „QA saved plan“ löschen',exact=True).click()
    expect(page.get_by_role('button',name='QA saved plan',exact=True)).to_have_count(0)
    for identifier in ids:assert page.request.get(unified_live+f'/api/inventory/assets/{identifier}').status==200
    assert not errors,errors;context.close()
