"""Pixel baselines for the planning workspace; synthetic data only."""
import os
import platform
from pathlib import Path
import pytest
from PIL import Image, ImageChops
from test_enterprise_browser import browser, live_inventory, sign_in
from test_wishes_browser import wishes_live
import app as inventory_app


@pytest.mark.parametrize('width,theme', [(1440,'light'),(1440,'dark'),(390,'light'),(390,'dark')])
def test_planning_visual_regression(wishes_live,browser,tmp_path,width,theme):
    with inventory_app.app.app_context():
        db=inventory_app.get_db()
        owner=db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        project=db.execute("INSERT INTO wish_projects(owner_id,name,description,budget_cents,visibility) VALUES (?,'Garden workshop','A place for tools and creative work',35000,'team')",(owner,)).lastrowid
        for index,name in enumerate(['Workbench','Hand tools','Shelving','Task light','Garden chair','Storage boxes','Paint','Protective gloves','Tool cabinet','Ladder','Watering can','Plant pots']):
            db.execute('INSERT INTO wishes(owner_id,project_id,name,quantity,unit_price_cents,priority) VALUES (?,?,?,?,?,?)',(owner,project,name,2 if index==5 else 1,(index+1)*1250,'high' if index==0 else 'normal'))
        db.commit()
    page=browser.new_page(viewport={'width':width,'height':1000 if width>1000 else 844},reduced_motion='reduce')
    sign_in(page,wishes_live)
    page.evaluate('(theme)=>InventoryTheme.set(theme)',theme)
    page.goto(f'{wishes_live}/wishes/projects/{project}')
    page.wait_for_load_state('networkidle')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    name=f'wishes-{browser.browser_type.name}-{width}-{theme}.png'
    actual=tmp_path/name
    page.screenshot(path=str(actual),full_page=True,animations='disabled')
    baseline=Path(__file__).parent/'visual-baselines'/platform.system().lower()/name
    if os.environ.get('UPDATE_WISH_VISUALS')=='1':
        baseline.parent.mkdir(parents=True,exist_ok=True)
        baseline.write_bytes(actual.read_bytes())
    if not baseline.exists():
        pytest.skip('No reviewed wish baseline for this operating system.')
    with Image.open(actual).convert('RGB') as image,Image.open(baseline).convert('RGB') as approved:
        assert image.size==approved.size
        difference=ImageChops.difference(image,approved)
        pixels=zip(*(iter(difference.tobytes()),)*3)
        changed=sum(max(pixel)>24 for pixel in pixels)/(image.width*image.height)
        if changed>0.002:
            difference.save(tmp_path/('diff-'+name))
        assert changed<=0.002,f'{changed:.2%} changed pixels; see {actual}'
    page.close()
