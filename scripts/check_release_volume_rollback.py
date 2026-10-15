#!/usr/bin/env python3
"""Exercise the real SQLite rollback inside Docker's own persistent volume."""
import argparse
from pathlib import Path
import secrets
import subprocess
import time


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    name = 'inventorypro-volume-qa-' + secrets.token_hex(4)
    source = Path(__file__).resolve().parents[1] / 'updater.py'
    run(['docker', 'volume', 'create', name])
    try:
        run(['docker', 'run', '-d', '--name', name, '-v', name + ':/data',
             '-e', 'INVENTORY_ENV=production', '-e', 'INVENTORY_SCHEDULER_ENABLED=0', args.image])
        def healthy():
            for _ in range(90):
                if run(['docker', 'inspect', '--format', '{{.State.Health.Status}}', name]) == 'healthy':
                    return
                time.sleep(1)
            raise RuntimeError('Isolated application did not become healthy.')
        healthy()
        run(['docker', 'stop', name])
        code = '''import sqlite3, sys
sys.path.insert(0, '/qa')
import updater
with sqlite3.connect('/data/inventory.db') as db:
 db.execute("CREATE TABLE qa_preserved (name TEXT)")
 db.execute("INSERT INTO qa_preserved VALUES ('Original')")
 db.commit()
db.close()
backup = updater.backup_database('0.2.0-volume-qa')
with sqlite3.connect('/data/inventory.db') as db:
 db.execute("ALTER TABLE qa_preserved ADD COLUMN failed_migration INTEGER")
 db.execute("UPDATE qa_preserved SET name='Mutated'")
 db.commit()
db.close()
updater.restore_database(backup)
with sqlite3.connect('/data/inventory.db') as db:
 assert db.execute('SELECT * FROM qa_preserved').fetchall() == [('Original',)]
 assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
db.close()
print('PASS: real updater restored original schema/data inside a Docker named volume.')
'''
        print(run(['docker', 'run', '--rm', '-v', name + ':/data', '-v', f'{source}:/qa/updater.py:ro',
                   '--entrypoint', 'python', args.image, '-c', code]), flush=True)
        run(['docker', 'start', name])
        healthy()
        print('PASS: application healthy after database restoration and restart.', flush=True)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        subprocess.run(['docker', 'volume', 'rm', name], capture_output=True)


if __name__ == '__main__':
    main()
