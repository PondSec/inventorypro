"""Automatic one-time inventory upgrade with a private pre-conversion snapshot."""
from datetime import datetime,timezone
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote
from uuid import uuid4


def backup_before_conversion(database):
    if database==':memory:':return None
    path=Path(database).resolve()
    if not path.is_file() or path.stat().st_size==0:return None
    source=sqlite3.connect('file:'+quote(str(path),safe='/')+'?mode=ro',uri=True,timeout=30)
    try:
        tables={row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'devices','assets'}.intersection(tables):return None
        if 'inventory_model_state' in tables:
            state=source.execute('SELECT unified_assets FROM inventory_model_state WHERE id=1').fetchone()
            if state and state[0]:return None
        if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Datenbankintegrität vor der Asset-Übernahme fehlgeschlagen. Die Originaldaten wurden nicht verändert.')
        directory=path.parent/'backups'/'pre-asset-conversion';directory.mkdir(parents=True,exist_ok=True,mode=0o700);directory.chmod(0o700)
        filename=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:12]+'.sqlite3'
        destination=directory/filename
        descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
        try:
            with sqlite3.connect(destination) as backup:
                source.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Die Sicherung konnte nicht geprüft werden.')
        except BaseException:
            destination.unlink(missing_ok=True);raise
        return destination
    finally:source.close()
