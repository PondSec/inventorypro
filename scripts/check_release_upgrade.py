#!/usr/bin/env python3
"""Isolated Docker acceptance using real legacy updater code and signed artifacts.

The published 0.0.6 app omits its runtime package. For a functioning legacy fixture
only, mount the restored package/migrations/dependencies; remove those mounts before upgrading.
No customer containers, databases or Compose files are opened or modified.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LEGACY = 'ghcr.io/pondsec/inventorypro@sha256:1e8997ad250b3d07b6dd84853c4734c24595b51188ec517660ff946850931b66'


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, **kwargs).stdout.strip()


def load_module(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_health(url):
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError('Synthetic instance did not become healthy.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-manifest', type=Path, required=True)
    parser.add_argument('--modern-manifest', type=Path, required=True)
    parser.add_argument('--local-baseline', action='store_true', help='Test a locally built installation with immutable local rollback')
    args = parser.parse_args()
    project = 'inventorypro-release-qa-' + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        fixture = Path(temporary)
        runtime = fixture / 'runtime'
        runtime.mkdir()
        archive = fixture / 'baseline.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive),
                        'fde7ccc734578ee6eb49347e68466712ede2b962', 'inventorypro', 'migrations'], cwd=ROOT, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(runtime, filter='data')
        # This package was originally hidden by an overly broad ignore rule.
        shutil.copytree(ROOT / 'inventorypro/domains/backups', runtime / 'inventorypro/domains/backups')
        dependencies = fixture / 'dependencies'
        dependencies.mkdir()
        command(['docker', 'run', '--rm', '--platform', 'linux/amd64', '--entrypoint', 'pip',
                 '-v', f'{dependencies}:/qa-dependencies',
                 LEGACY, 'install', '--disable-pip-version-check', '--target', '/qa-dependencies', 'openpyxl==3.1.5', 'et-xmlfile==2.0.0'])
        baseline_image = LEGACY
        if args.local_baseline:
            baseline_image = project + ':local-baseline'
            (fixture / 'Dockerfile').write_text(f'FROM {LEGACY}\nCOPY runtime/inventorypro /app/inventorypro\nCOPY runtime/migrations /app/migrations\nCOPY dependencies /usr/local/lib/python3.12/site-packages\nLABEL inventorypro.qa="local-baseline"\n')
            command(['docker', 'build', '--platform', 'linux/amd64', '-t', baseline_image, str(fixture)])
        data = fixture / 'data'
        data.mkdir()
        compose_file = fixture / 'compose.json'
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            host_port = listener.getsockname()[1]
        service = {'image': '${INVENTORY_IMAGE}', 'platform': 'linux/amd64',
                   'ports': [f'127.0.0.1:{host_port}:5000'],
                   'environment': {'INVENTORY_ENV': 'production', 'INVENTORY_SCHEDULER_ENABLED': '0',
                                   'PYTHONPATH': '/qa-dependencies', 'APP_SECRET_KEY': secrets.token_urlsafe(48),
                                   'INVENTORY_INITIAL_ADMIN_PASSWORD': secrets.token_urlsafe(32)},
                   'volumes': [f'{data}:/data', f'{runtime / "inventorypro"}:/app/inventorypro:ro',
                               f'{runtime / "migrations"}:/app/migrations:ro', f'{dependencies}:/qa-dependencies:ro']}
        if args.local_baseline:
            service['volumes'] = [f'{data}:/data']
            service['environment'].pop('PYTHONPATH', None)
        compose = {'name': project, 'services': {'app': service}}
        compose_file.write_text(json.dumps(compose))
        compose_file.chmod(0o600)
        old_file = fixture / 'legacy_updater.py'
        old_file.write_text(command(['git', 'show', '121dee5df67574373ab508bbba3ae95a20f1e8b3:updater.py'], cwd=ROOT))
        old = load_module('release_qa_legacy_updater', old_file)
        modern = load_module('release_qa_modern_updater', ROOT / 'updater.py')
        for module in (old, modern):
            module.DATA_PATH = data
            module.STATE_PATH = data / 'instance/update_state.json'
            module.POLICY_PATH = data / 'instance/update_policy.json'
            module.COMPOSE_FILE = compose_file
            module.COMPOSE_PROJECT_DIR = fixture
            module.PUBLIC_KEY_FILE = str(ROOT / 'updater/release-public-key.pem')
            module.PUBLIC_KEY_VALUE = ''
            module.HEALTH_TIMEOUT_SECONDS = 90
            module.HEALTH_POLL_SECONDS = 1
        os.environ['INVENTORY_IMAGE'] = baseline_image
        try:
            command(old.compose_args('up', '-d', '--no-build'))
            port = command(old.compose_args('port', 'app', '5000')).split(':')[-1]
            old.HEALTH_URL = f'http://127.0.0.1:{port}/login'
            wait_health(old.HEALTH_URL)
            with sqlite3.connect(data / 'inventory.db') as db:
                category = db.execute("INSERT INTO categories(name,fields) VALUES ('QA notebooks','{}')").lastrowid
                db.execute('INSERT INTO devices(name,category_id,serial_number,specs) VALUES (?,?,?,?)',
                           ('Synthetic upgrade notebook', category, 'QA-RELEASE-001', '{"RAM":"32 GB"}'))
                db.commit()
                original = db.execute('SELECT name,category_id,serial_number,specs FROM devices').fetchall()
            upload = data / 'uploads/release-qa.txt'
            upload.parent.mkdir(exist_ok=True)
            upload.write_text('Synthetic persisted attachment')
            print('Baseline healthy with restored runtime/dependencies; waiting for signed release artifacts.', flush=True)
            deadline = time.monotonic() + 1800
            while not (args.legacy_manifest.exists() and args.modern_manifest.exists()):
                if time.monotonic() > deadline:
                    raise RuntimeError('Signed artifacts were not prepared within 30 minutes.')
                time.sleep(5)
            legacy_manifest = json.loads(args.legacy_manifest.read_text())
            modern_manifest = json.loads(args.modern_manifest.read_text())
            old.validate_manifest(legacy_manifest)
            modern.validate_manifest(modern_manifest)
            assert legacy_manifest['image'].split('@')[1] == modern_manifest['image'].split('@')[1]
            old.fetch_manifest = lambda _: legacy_manifest
            modern.fetch_manifest = lambda _: modern_manifest
            # The release image must supply its own complete runtime package.
            service['volumes'] = [f'{data}:/data']
            service['environment'].pop('PYTHONPATH', None)
            compose_file.write_text(json.dumps(compose))
            def internal_health(module_source):
                # Use the actual service network, as a real updater sidecar does.
                # Host port forwarding can reset connections during recreation.
                code = ('import importlib.util; '
                        's=importlib.util.spec_from_file_location("qa_updater","/qa/updater.py"); '
                        'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                        'raise SystemExit(0 if m.wait_for_health() else 1)')
                result = subprocess.run(['docker', 'run', '--rm', '--network', project + '_default',
                    '-v', f'{module_source}:/qa/updater.py:ro',
                    '-e', 'INVENTORY_UPDATE_HEALTH_URL=http://app:5000/login',
                    '-e', 'INVENTORY_UPDATE_HEALTH_TIMEOUT_SECONDS=90',
                    '-e', 'INVENTORY_UPDATE_HEALTH_POLL_SECONDS=1',
                    '--entrypoint', 'python', legacy_manifest['image'], '-c', code],
                    capture_output=True, text=True, stdin=subprocess.DEVNULL)
                if result.returncode:
                    print(result.stderr[-1500:], flush=True)
                return result.returncode == 0
            old.wait_for_health = lambda: internal_health(old_file)
            modern.wait_for_health = lambda: internal_health(ROOT / 'updater.py')
            if args.local_baseline:
                healthy = modern.wait_for_health
                checks = []
                def reject_local_upgrade_once():
                    checks.append(True)
                    if len(checks) == 1:
                        return False
                    return healthy()
                modern.wait_for_health = reject_local_upgrade_once
                assert modern.perform_update({'enabled': True}) == 'rolled_back'
                assert modern.active_image_reference().startswith('sha256:')
                print('PASS: locally built installation rolled back to its exact immutable local image.', flush=True)
                modern.wait_for_health = healthy
                # Backup folder names include seconds; avoid collision between immediate acceptance retries.
                time.sleep(1.1)
                assert modern.perform_update({'enabled': True}) == 'updated'
            else:
                assert old.perform_update({'enabled': True}) == 'updated'
            port = command(old.compose_args('port', 'app', '5000')).split(':')[-1]
            modern.HEALTH_URL = f'http://127.0.0.1:{port}/login'
            wait_health(modern.HEALTH_URL)
            with sqlite3.connect(data / 'inventory.db') as db:
                assert db.execute('SELECT name,category_id,serial_number,specs FROM devices').fetchall() == original
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='storage_plans'").fetchone()
            assert upload.read_text() == 'Synthetic persisted attachment'
            state = json.loads(old.STATE_PATH.read_text())
            assert state['currentVersion'] == legacy_manifest['version']
            assert state['lastCheckStatus'] == 'updated'
            assert Path(state['backupPath'], 'inventory.db').exists()
            container = old.active_container_id()
            version = command(['docker', 'exec', container, 'python', '-c', 'import os; print(os.environ["APP_VERSION"])'])
            assert version == legacy_manifest['version']
            print('PASS: ' + ('new updater upgraded local installation' if args.local_baseline else 'real legacy updater installed signed release') + ', migrated schema, retained device fields/uploads and created backup.')
            # A newly installed updater uses GitLab and can restore an earlier GHCR app.
            # Force a post-migration health rejection, then use a real health check for rollback.
            modern.STATE_PATH.unlink()
            actual_health = modern.wait_for_health
            calls = []
            def reject_first_health():
                calls.append(True)
                if len(calls) == 1:
                    with sqlite3.connect(data / 'inventory.db') as db:
                        db.execute('CREATE TABLE qa_failed_migration (id INTEGER)')
                        db.execute("UPDATE devices SET name='Failed deployment mutation'")
                        db.commit()
                    return False
                port = command(modern.compose_args('port', 'app', '5000')).split(':')[-1]
                modern.HEALTH_URL = f'http://127.0.0.1:{port}/login'
                return actual_health()
            modern.wait_for_health = reject_first_health
            assert modern.perform_update({'enabled': True}) == 'rolled_back'
            with sqlite3.connect(data / 'inventory.db') as db:
                assert db.execute('SELECT name,category_id,serial_number,specs FROM devices').fetchall() == original
                assert not db.execute("SELECT name FROM sqlite_master WHERE name='qa_failed_migration'").fetchone()
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            print('PASS: new updater used GitLab image; forced health failure restored prior schema/data and healthy previous image.')
        finally:
            subprocess.run(old.compose_args('down', '--volumes', '--remove-orphans'), capture_output=True)
            if args.local_baseline:
                subprocess.run(['docker', 'image', 'rm', baseline_image], capture_output=True)


if __name__ == '__main__':
    main()
