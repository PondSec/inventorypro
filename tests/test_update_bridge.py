import base64
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import updater

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from prepare_update_bridge import prepare_bridge


def test_bridge_is_accepted_by_real_legacy_validator_and_new_validator(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    modern, legacy = prepare_bridge('1.2.3', 'gitlab.pondsec.com/pondsec/inventorypro@sha256:' + 'a'*64,
                                    'ghcr.io/pondsec/inventorypro@sha256:' + 'b'*64, key, public)
    # Execute the exact validator shipped before migration; no publication/network.
    source = subprocess.check_output(['git', 'show', '121dee5df67574373ab508bbba3ae95a20f1e8b3:updater.py'])
    legacy_file = tmp_path / 'legacy_updater.py'
    legacy_file.write_bytes(source)
    spec = importlib.util.spec_from_file_location('legacy_updater', legacy_file)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    encoded = base64.b64encode(public).decode()
    old.PUBLIC_KEY_VALUE = encoded
    monkeypatch.setattr(updater, 'PUBLIC_KEY_VALUE', encoded)
    assert old.validate_manifest(legacy)['version'] == '1.2.3'
    assert updater.validate_manifest(modern)['version'] == '1.2.3'
    with pytest.raises(old.UpdateError):
        old.validate_manifest(modern)
    legacy['version'] = '1.2.4'
    with pytest.raises(old.UpdateError):
        old.validate_manifest(legacy)


def test_bridge_refuses_wrong_signing_key():
    with pytest.raises(ValueError, match='Signierschlüssel passt nicht'):
        prepare_bridge('1.2.3', '', '', Ed25519PrivateKey.generate(), b'unrelated-key')


def test_database_rollback_restores_data_and_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'DATA_PATH', tmp_path)
    with sqlite3.connect(tmp_path / 'inventory.db') as db:
        db.execute('CREATE TABLE inventory (name TEXT)')
        db.execute("INSERT INTO inventory VALUES ('Original')")
    backup = updater.backup_database('1.2.3')
    with sqlite3.connect(tmp_path / 'inventory.db') as db:
        db.execute('ALTER TABLE inventory ADD COLUMN migrated INTEGER')
        db.execute("UPDATE inventory SET name='Changed'")
    updater.restore_database(backup)
    with sqlite3.connect(tmp_path / 'inventory.db') as db:
        assert db.execute('SELECT * FROM inventory').fetchall() == [('Original',)]
        assert len(db.execute('PRAGMA table_info(inventory)').fetchall()) == 1
