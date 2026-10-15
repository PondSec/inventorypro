#!/usr/bin/env python3
"""Inventory real routes/components and capture repeatable synthetic browser views."""
import argparse
from datetime import datetime, timezone
import inspect
import json
import logging
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from visual_fixture import visual_instance, PASSWORD
from playwright.sync_api import sync_playwright

CASES = {'dashboard':'/','inventory':'/inventory','devices':'/inventory?kind=device','sets':'/inventory?kind=asset',
 'legacy-devices':'/?view=devices','legacy-assets':'/?view=assets','templates':'/?view=taxonomy',
 'capture':'/inventory/new','device':'/inventory/devices/1','hardware':'/inventory/devices/1?tab=hardware',
 'accessories':'/inventory/devices/1?tab=accessories','maintenance':'/inventory/devices/1?tab=maintenance',
 'assignment':'/inventory/devices/1?tab=assignment','history':'/inventory/devices/1?tab=history',
 'set-detail':'/inventory/assets/1','planning':'/inventory/planning','locations':'/locations',
 'tickets':'/tickets','ticket-detail':'/tickets/1','ticket-admin':'/admin/tickets',
 'knowledge':'/knowledge','roadmap':'/roadmap','procurement':'/procurement','stats':'/stats',
 'dependencies':'/dependencies','time-machine':'/time-machine','health':'/health','users':'/users',
 'settings':'/settings','design-settings':'/settings?section=customize','terminal':'/settings/terminal',
 'account':'/account/security','otp':'/verify','mfa':'/mfa-enroll','not-found':'/visual-not-found',
 'empty-inventory':'/inventory?q=QA-NO-MATCH'}


def inventory_routes(application):
    result=[]
    for route in sorted(application.app.url_map.iter_rules(),key=lambda r:r.rule):
        if 'GET' not in route.methods:continue
        view=inspect.unwrap(application.app.view_functions[route.endpoint])
        try:source=inspect.getsource(view)
        except (OSError,TypeError):source=''
        templates=re.findall(r'render_template\(\s*[\'"]([^\'"]+)',source)
        result.append({'route':route.rule,'endpoint':route.endpoint,'templates':templates,
                       'kind':'static' if route.endpoint=='static' else 'page' if templates else 'API/redirect/helper'})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',default='before')
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--count',type=int,default=1000)
    args=parser.parse_args()
    output=ROOT/'docs/visual-audit'/args.phase;output.mkdir(parents=True,exist_ok=True)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    results=[]
    with visual_instance(args.count) as (application,base),sync_playwright() as p:
        routes=inventory_routes(application)
        browser=p.chromium.launch()
        sizes=[(1440,900)] if not args.full else [(1920,1080),(1672,941),(1440,900),(1280,800),(390,844)]
        for width,height in sizes:
            context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce')
            page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/login');page.screenshot(path=str(output/f'login-{width}-light.png'))
            page.get_by_label('Benutzername').fill('admin');page.locator('input[name=password]').fill(PASSWORD)
            page.get_by_role('button',name='Anmelden',exact=True).click();page.wait_for_url(lambda url:url in {base+'/',base+'/inventory'})
            for theme in ['light','dark'] if args.full else ['light']:
                for name,url in CASES.items():
                    errors.clear()
                    response=page.goto(base+url)
                    page.wait_for_load_state('networkidle')
                    page.evaluate('(theme)=>window.InventoryTheme?.set(theme)',theme)
                    page.wait_for_timeout(120)
                    filename=f'{name}-{width}-{theme}.png';page.screenshot(path=str(output/filename))
                    metrics=page.evaluate('''()=>({sidebar:document.querySelector('.app-sidebar')?.getBoundingClientRect().width,
                        rows:[...document.querySelectorAll('.data-table tbody tr')].slice(0,12).map(r=>r.getBoundingClientRect().height),
                        overflow:document.documentElement.scrollWidth>innerWidth+1})''')
                    results.append({'name':name,'route':url,'width':width,'theme':theme,'http':response.status,
                                    'actual_url':page.url.replace(base,''),'errors':list(errors),'metrics':metrics,'screenshot':filename})
            context.close()
        browser.close()
    (output/'manifest.json').write_text(json.dumps({'phase':args.phase,'routes':routes,'screenshots':results},indent=2))
    templates=[]
    for f in sorted((ROOT/'templates').glob('*.html')):
        text=f.read_text();base=re.search(r"extends\s+['\"]([^'\"]+)",text)
        templates.append({'file':f.name,'base':base.group(1) if base else 'partial/root',
                          'inline_style_blocks':text.count('<style'),'dialog_markers':len(re.findall('modal|role="dialog"|<dialog',text))})
    (output/'components.json').write_text(json.dumps(templates,indent=2))
    matrix=['# Route- und Komponentenmatrix','',f'Phase: {args.phase}. Synthetische Daten; {args.count} Geräte.','',
            '| GET-Route | Endpoint | Layout/Template | Erfassung |','|---|---|---|---|']
    for r in routes:
        matrix.append(f"| `{r['route']}` | `{r['endpoint']}` | {', '.join(r['templates']) or r['kind']} | registriert |")
    matrix+=['','## Browseransichten','','| Ansicht | Route | HTTP | Browserfehler | Screenshot |','|---|---|---|---|---|']
    for r in results:matrix.append(f"| {r['name']} ({r['width']}, {r['theme']}) | `{r['route']}` | {r['http']} | {len(r['errors'])} | [{r['screenshot']}]({args.phase}/{r['screenshot']}) |")
    (ROOT/'docs/visual-audit/route-matrix.md').write_text('\n'.join(matrix)+'\n')
    print(f"Captured {len(results)} views; inventoried {len(routes)} GET routes and {len(templates)} templates.")
    for r in results:
        if r['errors']:print(r['name'],r['errors'])


if __name__=='__main__':main()
