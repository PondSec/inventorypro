#!/usr/bin/env python3
"""Verify an image in an isolated fresh Compose project, then remove it."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import urllib.request


def run(args):
    result = subprocess.run(args, text=True, capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--version',help='Expected APP_VERSION, including explicit QA versions.')
    args = parser.parse_args()
    project = 'inventorypro-install-qa-' + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix=project) as directory:
        compose = Path(directory) / 'compose.json'
        compose.write_text(json.dumps({'name': project, 'services': {'app': {
            'image': args.image, 'ports': ['127.0.0.1::5000'],
            'environment': {'INVENTORY_ENV': 'production', 'INVENTORY_SCHEDULER_ENABLED': '0'},
            'volumes': ['qa-data:/data']}}, 'volumes': {'qa-data': {}}}))
        base = ['docker', 'compose', '--file', str(compose)]
        try:
            run(base + ['up', '-d', '--wait', '--wait-timeout', '180'])
            code = '''import os, sqlite3, hashlib, sys
from pathlib import Path
import app, openpyxl
from inventorypro.domains.backups import service
from inventorypro.domains.inventory import upgrade, graph
from inventorypro.domains.catalog import commons, jobs, media
assert 'Joshua Pond' in Path('/app/NOTICE').read_text()
assert 'Inventory Pro Community License' in Path('/app/LICENSE').read_text()
assert os.environ['APP_VERSION']
if sys.argv[1]: assert 'Joshua Pond' in Path('/app/NOTICE').read_text()
assert 'Inventory Pro Community License' in Path('/app/LICENSE').read_text()
assert os.environ['APP_VERSION'] == sys.argv[1]
secret = Path('/data/instance/application-secret.key')
credentials = Path('/data/instance/initial_admin_credentials.txt')
assert secret.stat().st_mode & 0o777 == 0o600
assert credentials.stat().st_mode & 0o777 == 0o600
assert len(secret.read_text().strip()) >= 48
with sqlite3.connect('/data/inventory.db') as db:
 assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
 assert db.execute('SELECT must_change_password FROM users WHERE username="admin"').fetchone()[0] == 1
 assert db.execute("SELECT name FROM sqlite_master WHERE name='storage_plans'").fetchone()
 assert db.execute('SELECT unified_assets FROM inventory_model_state WHERE id=1').fetchone()[0] == 1
 assert db.execute('SELECT count(*) FROM product_images').fetchone()[0] >= 1
print(hashlib.sha256(secret.read_bytes()).hexdigest())
'''
            before = run(base + ['exec', '-T', 'app', 'python', '-c', code,args.version or ''])
            run(base + ['restart', 'app'])
            run(base + ['up', '-d', '--wait', '--wait-timeout', '180'])
            after = run(base + ['exec', '-T', 'app', 'python', '-c', code,args.version or ''])
            assert before == after, 'Persistent secret changed after restart.'
            port = run(base + ['port', 'app', '5000']).split(':')[-1]
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/login', timeout=10) as response:
                assert response.status == 200
            login_code='''from pathlib import Path
import json,urllib.request,urllib.parse,http.cookiejar
values=dict(line.split(': ',1) for line in Path('/data/instance/initial_admin_credentials.txt').read_text().splitlines() if ': ' in line)
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
token=json.load(opener.open('http://127.0.0.1:5000/api/csrf-token'))['csrfToken']
request=urllib.request.Request('http://127.0.0.1:5000/login',data=urllib.parse.urlencode({'username':values['Benutzername'],'password':values['Passwort']}).encode(),headers={'X-CSRF-Token':token})
response=opener.open(request)
assert response.status==200 and response.url.endswith('/force-password-change')
print('PASS: generated first-run credentials authenticate over HTTP and require a password change.')
'''
            print(run(base+['exec','-T','app','python','-c',login_code]))
            print('PASS: fresh image install/restart, HTTP login, private persistent secret, canonical inventory, starter photos, complete runtime and migrations.')
        finally:
            subprocess.run(base + ['down', '--volumes', '--remove-orphans'], capture_output=True)


if __name__ == '__main__':
    main()
