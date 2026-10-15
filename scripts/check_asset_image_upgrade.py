#!/usr/bin/env python3
"""Upgrade/rollback real app images in a disposable Docker volume with synthetic data."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile


def run(arguments):
    result=subprocess.run(arguments,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr[-3000:])
    return result.stdout.strip()


SEED='''import app,json
from pathlib import Path
with app.app.app_context():
 db=app.get_db()
 db.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE username='admin'",(app.generate_password_hash('Synthetic-Upgrade-Only-42!'),))
 category=db.execute("INSERT INTO categories(name,fields) VALUES ('QA Upgrade Laptops',?)",(json.dumps({'Hersteller':'text','Modell':'text','Unknown':'text'}),)).lastrowid
 location=db.execute("INSERT INTO locations(name) VALUES ('QA Upgrade Room')").lastrowid
 devices=[]
 for index in range(20):
  devices.append(db.execute('INSERT INTO devices(name,category_id,serial_number,location_id,specs) VALUES (?,?,?,?,?)',('MacBook Air 13″ M4' if index==0 else 'QA Upgrade Device '+str(index),category,'QA-UPGRADE-'+str(index),location,json.dumps({'Hersteller':'Apple','Modell':'MacBook Air 13″ M4','Unknown':'Retained'}) if index==0 else '{}')).lastrowid)
 asset_category=db.execute("SELECT id FROM asset_categories WHERE name='Assets'").fetchone()[0]
 parents=[]
 for index in range(2):
  parent=db.execute('INSERT INTO assets(name,category_id,notes,specs) VALUES (?,?,?,?)',('QA Upgrade Set '+str(index),asset_category,'QA retained description','{"Unknown":"Retained"}')).lastrowid;parents.append(parent)
  db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity,notes) VALUES (?,?,2,?)',(parent,devices[index],'QA retained contents'))
 ticket=db.execute("INSERT INTO tickets(title,description,status,created_by,created_by_user_id) VALUES ('QA Upgrade Ticket','QA synthetic','open','admin',?)",(db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0],)).lastrowid
 db.execute('INSERT INTO ticket_assets(ticket_id,asset_id) VALUES (?,?)',(ticket,parents[0]))
 db.execute("INSERT INTO roadmaps(title,ticket_id) VALUES ('QA linked roadmap',?)",(ticket,))
 db.execute('UPDATE server_settings SET update_policy_json=?',(json.dumps({'autoUpdateEnabled':False,'maintenanceWindow':'04:15','channel':'stable','checkIntervalMinutes':90}),))
 db.commit()
 tables=['devices','assets','asset_devices','users','user_roles','role_permissions','tickets','roadmaps']
 snapshot={table:[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')] for table in tables}
 snapshot['policy']=db.execute('SELECT update_policy_json FROM server_settings').fetchone()[0]
 snapshot['secret']=Path('/data/instance/application-secret.key').read_text()
 Path('/data/uploads').mkdir(exist_ok=True);Path('/data/uploads/qa-retained.txt').write_text('QA persistent upload')
 print(json.dumps(snapshot))
'''

VERIFY='''import app,json,sys,sqlite3
from pathlib import Path
expected=json.loads(sys.argv[1])
with app.app.app_context():
 db=app.get_db()
 assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 assert not db.execute('PRAGMA foreign_key_check').fetchall()
 for table in ['devices','asset_devices','users','user_roles','role_permissions','tickets','roadmaps']:
  actual=[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')]
  assert len(actual)==len(expected[table]),table+' row count'
  for old,new in zip(expected[table],actual):assert all(new[key]==value for key,value in old.items()),table+': '+str([key for key,value in old.items() if new[key]!=value])
 for old in expected['assets']:
  actual=dict(db.execute('SELECT * FROM assets WHERE id=?',(old['id'],)).fetchone())
  assert all(actual[key]==value for key,value in old.items()),'old asset data'
 assert db.execute('SELECT update_policy_json FROM server_settings').fetchone()[0]==expected['policy']
 assert db.execute('SELECT unified_assets FROM inventory_model_state').fetchone()[0]==1
 assert db.execute('SELECT count(*) FROM assets').fetchone()[0]==22
 assert db.execute('SELECT count(*) FROM asset_components').fetchone()[0]==2
 assert db.execute('SELECT quantity FROM asset_components LIMIT 1').fetchone()[0]==2
 identifier=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=?',(expected['devices'][0]['id'],)).fetchone()[0]
 from inventorypro.domains.catalog.objects import resolve
 photo=resolve(db,Path('/data/uploads'),'asset',identifier)
 assert photo['source']=='catalog' and photo['url']
 assert Path('/data/instance/application-secret.key').read_text()==expected['secret']
 assert Path('/data/uploads/qa-retained.txt').read_text()=='QA persistent upload'
 backups=list(Path('/data/backups/pre-asset-conversion').glob('*.sqlite3'))
 assert len(backups)==1
 with sqlite3.connect(backups[0]) as backup:assert backup.execute('SELECT count(*) FROM assets').fetchone()[0]==2
print('PASS: 20 devices become 20 scoped assets; 2 existing sets, quantities, roles, tickets, uploads, policy and secret retained; starter product photo resolves.')
'''

HTTP='''import json,urllib.request,urllib.parse,http.cookiejar,sys
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
root='http://127.0.0.1:5000'
token=json.load(opener.open(root+'/api/csrf-token'))['csrfToken']
request=urllib.request.Request(root+'/login',data=urllib.parse.urlencode({'username':'admin','password':'Synthetic-Upgrade-Only-42!'}).encode(),headers={'X-CSRF-Token':token})
assert opener.open(request).url.endswith('/inventory')
items=json.load(opener.open(root+'/api/inventory/assets'))
assert items['total']==22
photo=json.load(opener.open(root+'/api/inventory/asset/'+str(items['rows'][0]['id'])+'/photo'))
# The MacBook may sort after the two sets; search its real canonical identity.
mac=json.load(opener.open(root+'/api/inventory/assets?q=MacBook'))['rows'][0]
photo=json.load(opener.open(root+'/api/inventory/asset/'+str(mac['id'])+'/photo'))
assert photo['source']=='catalog' and opener.open(root+photo['url']).headers.get_content_type()=='image/webp'
# Historical roadmap foreign keys caused the reported ticket-delete 503.
token=json.load(opener.open(root+'/api/csrf-token'))['csrfToken']
request=urllib.request.Request(root+'/api/tickets/'+str(json.loads(sys.argv[1])['tickets'][0]['id']),method='DELETE',headers={'X-CSRF-Token':token})
assert opener.open(request).status==200
print('PASS: migrated login, paginated asset API and product photo work over HTTP; linked ticket deletion succeeds.')
'''

RESTORE='''from pathlib import Path
import sqlite3
source=next(Path('/data/backups/pre-asset-conversion').glob('*.sqlite3'))
with sqlite3.connect(source) as original,sqlite3.connect('/data/inventory.db') as target:original.backup(target)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-image',required=True);parser.add_argument('--to-image',required=True)
    args=parser.parse_args();project='inventorypro-asset-upgrade-qa-'+secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix=project) as directory:
        path=Path(directory)/'compose.json'
        configuration={'name':project,'services':{'app':{'image':args.from_image,'environment':{'INVENTORY_ENV':'production','INVENTORY_SCHEDULER_ENABLED':'0'},'volumes':['qa-data:/data']}},'volumes':{'qa-data':{}}}
        def select(image):configuration['services']['app']['image']=image;path.write_text(json.dumps(configuration))
        select(args.from_image);base=['docker','compose','-f',str(path)]
        def up():run(base+['up','-d','--wait','--wait-timeout','180'])
        def python(code,*values):return run(base+['exec','-T','app','python','-c',code,*values])
        try:
            up();snapshot=python(SEED)
            select(args.to_image);up();print(python(VERIFY,snapshot))
            run(base+['restart','app']);up();print(python(VERIFY,snapshot));print(python(HTTP,snapshot))
            run(base+['stop','app'])
            run(base+['run','--rm','--no-deps','--entrypoint','python','app','-c',RESTORE])
            select(args.from_image);up()
            restored=json.loads(python("import app,json\nwith app.app.app_context():\n db=app.get_db();print(json.dumps({table:[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')] for table in ['devices','assets','asset_devices','users','user_roles','role_permissions','tickets','roadmaps']}))"))
            expected=json.loads(snapshot)
            for table,rows in restored.items():assert rows==expected[table],table
            print('PASS: previous image starts with pre-conversion database; all original business rows restored after forced rollback.')
        finally:subprocess.run(base+['down','--volumes','--remove-orphans'],capture_output=True)


if __name__=='__main__':main()
