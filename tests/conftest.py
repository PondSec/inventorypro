import pytest

import app as inventory_app


@pytest.fixture(scope='session',autouse=True)
def legacy_contract_startup_mode():
    """Set the historical state before unittest setUpClass starts live servers."""
    missing=object();previous=inventory_app.app.config.get('INVENTORY_UNIFIED_ASSETS_ENABLED',missing)
    inventory_app.app.config['INVENTORY_UNIFIED_ASSETS_ENABLED']=False
    yield
    if previous is missing:inventory_app.app.config.pop('INVENTORY_UNIFIED_ASSETS_ENABLED',None)
    else:inventory_app.app.config['INVENTORY_UNIFIED_ASSETS_ENABLED']=previous


@pytest.fixture(autouse=True)
def enable_flask_test_mode(monkeypatch):
    """Keep legacy workflow tests focused on their domain behaviour.

    CSRF enforcement is enabled in production and covered explicitly in the
    security test module with this flag temporarily disabled.
    """
    previous_value = inventory_app.app.config.get("TESTING", False)
    inventory_app.app.config["TESTING"] = True
    # Historical contract suites deliberately exercise the pre-upgrade state.
    # Dedicated startup tests explicitly enable the production default.
    monkeypatch.setitem(inventory_app.app.config,'INVENTORY_UNIFIED_ASSETS_ENABLED',False)
    yield
    inventory_app.app.config["TESTING"] = previous_value


@pytest.fixture
def isolated_inventory(tmp_path, monkeypatch):
    """Synthetic database; never open the developer's existing inventory."""
    for name, value in {
        'DATABASE': str(tmp_path / 'inventory.db'), 'UPLOADS_DIR': tmp_path / 'uploads',
        'APP_INSTANCE_PATH': tmp_path / 'instance', 'RUNTIME_CONFIG_PATH': tmp_path / 'runtime.json',
        'RUNTIME_SETTINGS_CACHE': {'host': '127.0.0.1', 'port': 5000, 'debug': False},
        'INITIAL_ADMIN_CREDENTIALS_PATH': None,
    }.items():
        monkeypatch.setattr(inventory_app, name, value)
    monkeypatch.setitem(inventory_app.app.config,'CATALOG_BACKGROUND_ENABLED',False)
    inventory_app.init_db()
    inventory_app.RATE_LIMIT_CACHE.clear()
    with inventory_app.app.app_context():
        db = inventory_app.get_db()
        # Service unit fixtures start with an empty catalog; starter data has its own tests.
        db.execute('DELETE FROM product_models')
        db.execute('DELETE FROM product_media_files')
        import shutil
        shutil.rmtree(inventory_app.UPLOADS_DIR / 'product-media', ignore_errors=True)
        db.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE username='admin'",
                   (inventory_app.generate_password_hash('Synthetic-Test-Only-42!'),))
        category = db.execute("INSERT INTO categories (name, fields) VALUES ('Notebooks', '{}')").lastrowid
        for index in range(40):
            db.execute('INSERT INTO devices (name, category_id, serial_number, specs) VALUES (?, ?, ?, ?)',
                       (f'Notebook {index:03}', category, f'QA-{index:03}', '{}'))
        db.commit()
    yield inventory_app.app
    inventory_app.RATE_LIMIT_CACHE.clear()
