-- Additive product/media layer. Existing inventory rows and uploads stay unchanged.
CREATE TABLE IF NOT EXISTS product_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer TEXT NOT NULL CHECK(length(trim(manufacturer)) BETWEEN 1 AND 120),
    manufacturer_key TEXT NOT NULL,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 240),
    model_key TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(manufacturer_key, model_key)
);
CREATE TABLE IF NOT EXISTS product_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES product_models(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('mpn','gtin','model','name')),
    manufacturer_key TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL CHECK(length(value) BETWEEN 1 AND 240),
    auto_match INTEGER NOT NULL DEFAULT 1 CHECK(auto_match IN (0,1)),
    UNIQUE(product_id,kind,manufacturer_key,value)
);
CREATE INDEX IF NOT EXISTS idx_product_identifiers_lookup ON product_identifiers(kind,manufacturer_key,value);
CREATE TABLE IF NOT EXISTS product_media_files (
    hash TEXT PRIMARY KEY CHECK(length(hash)=64 AND hash NOT GLOB '*[^0-9a-f]*'),
    width INTEGER NOT NULL CHECK(width BETWEEN 1 AND 1600),
    height INTEGER NOT NULL CHECK(height BETWEEN 1 AND 1600),
    size_bytes INTEGER NOT NULL CHECK(size_bytes BETWEEN 1 AND 8388608),
    mime_type TEXT NOT NULL DEFAULT 'image/webp' CHECK(mime_type='image/webp'),
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES product_models(id) ON DELETE CASCADE,
    media_hash TEXT NOT NULL REFERENCES product_media_files(hash) ON DELETE RESTRICT,
    position INTEGER NOT NULL DEFAULT 0,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    license_code TEXT NOT NULL,
    attribution TEXT NOT NULL DEFAULT '',
    changes TEXT NOT NULL DEFAULT '',
    reviewed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id,media_hash)
);
CREATE INDEX IF NOT EXISTS idx_product_images_primary ON product_images(product_id,position,id);
CREATE TABLE IF NOT EXISTS device_product_media (
    device_id INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES product_models(id) ON DELETE SET NULL,
    override_hash TEXT REFERENCES product_media_files(hash) ON DELETE RESTRICT,
    suppress_image INTEGER NOT NULL DEFAULT 0 CHECK(suppress_image IN (0,1)),
    match_method TEXT NOT NULL DEFAULT 'none' CHECK(match_method IN ('none','manual','gtin','mpn','model','name_exact')),
    fingerprint TEXT NOT NULL DEFAULT '',
    confirmed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_device_product_media_product ON device_product_media(product_id);
CREATE TABLE IF NOT EXISTS asset_product_media (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES product_models(id) ON DELETE SET NULL,
    override_hash TEXT REFERENCES product_media_files(hash) ON DELETE RESTRICT,
    suppress_image INTEGER NOT NULL DEFAULT 0 CHECK(suppress_image IN (0,1)),
    match_method TEXT NOT NULL DEFAULT 'none' CHECK(match_method IN ('none','manual','gtin','mpn','model','name_exact')),
    fingerprint TEXT NOT NULL DEFAULT '',
    confirmed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_asset_product_media_product ON asset_product_media(product_id);
CREATE TABLE IF NOT EXISTS product_catalog_settings (
    id INTEGER PRIMARY KEY CHECK(id=1),
    local_auto_match INTEGER NOT NULL DEFAULT 1 CHECK(local_auto_match IN (0,1)),
    external_enabled INTEGER NOT NULL DEFAULT 0 CHECK(external_enabled IN (0,1)),
    rights_reviewed INTEGER NOT NULL DEFAULT 0 CHECK(rights_reviewed IN (0,1)),
    provider TEXT NOT NULL DEFAULT 'commons' CHECK(provider='commons'),
    updated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO product_catalog_settings(id) VALUES(1);
