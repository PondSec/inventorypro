from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path
import socket

import pytest
from inventorypro.config import ConfigurationError, resolve_application_secret

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory_setup', ROOT / 'scripts/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_production_secret_is_private_persistent_and_concurrent(tmp_path):
    environment = {'INVENTORY_ENV': 'production', 'INVENTORY_INSTANCE_PATH': str(tmp_path)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(lambda _: resolve_application_secret(environment).value, range(16)))
    assert len(set(keys)) == 1
    assert len(keys[0]) >= 48
    assert (tmp_path / 'application-secret.key').stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob('.application-secret-*'))


def test_legacy_known_compose_secret_is_automatically_replaced(tmp_path):
    env = {'INVENTORY_ENV': 'production', 'INVENTORY_INSTANCE_PATH': str(tmp_path),
           'APP_SECRET_KEY': 'inventorypro-compose-change-me-persistently-before-production'}
    key = resolve_application_secret(env).value
    assert key != env['APP_SECRET_KEY']
    assert resolve_application_secret(env).value == key


def test_existing_real_secret_remains_unchanged(tmp_path):
    assert resolve_application_secret({'INVENTORY_ENV': 'production', 'INVENTORY_INSTANCE_PATH': str(tmp_path),
                                       'APP_SECRET_KEY': 'existing-customer-secret'}).value == 'existing-customer-secret'
    assert not list(tmp_path.iterdir())


def test_secret_refuses_symlink_and_public_file(tmp_path):
    target = tmp_path / 'application-secret.key'
    real = tmp_path / 'real'
    real.write_text('a' * 64)
    target.symlink_to(real)
    with pytest.raises(ConfigurationError):
        resolve_application_secret({'INVENTORY_ENV': 'production', 'INVENTORY_INSTANCE_PATH': str(tmp_path)})
    target.unlink()
    target.write_text('b' * 64)
    target.chmod(0o644)
    with pytest.raises(ConfigurationError):
        resolve_application_secret({'INVENTORY_ENV': 'production', 'INVENTORY_INSTANCE_PATH': str(tmp_path)})


def test_setup_does_not_overwrite_existing_configuration(tmp_path):
    assert setup.prepare_environment(tmp_path, 5055)
    before = (tmp_path / '.env').read_bytes()
    assert not setup.prepare_environment(tmp_path, 5000)
    assert (tmp_path / '.env').read_bytes() == before
    assert b'change-me' not in before
    assert b'PASSWORD=' not in before
    assert b'INVENTORY_PORT=5055' in before
    assert (tmp_path / '.env').stat().st_mode & 0o777 == 0o600


def test_port_conflict_is_explained():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        with pytest.raises(ValueError, match='ist belegt'):
            setup.check_port(occupied.getsockname()[1])


def test_setup_rejects_invalid_port_and_symlink(tmp_path):
    with pytest.raises(ValueError):
        setup.prepare_environment(tmp_path, 70000)
    (tmp_path / '.env').symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError):
        setup.prepare_environment(tmp_path)
