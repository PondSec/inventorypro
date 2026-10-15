-- Additive preparation for one asset domain. Conversion is activated separately.
CREATE TABLE IF NOT EXISTS inventory_model_state (
    id INTEGER PRIMARY KEY CHECK(id=1),
    unified_assets INTEGER NOT NULL DEFAULT 0 CHECK(unified_assets IN (0,1)),
    converted_at TEXT
);
INSERT OR IGNORE INTO inventory_model_state(id) VALUES(1);
ALTER TABLE assets ADD COLUMN serial_number TEXT NOT NULL DEFAULT '';
ALTER TABLE assets ADD COLUMN location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location_id);
CREATE TABLE IF NOT EXISTS asset_legacy_categories (
    category_id INTEGER PRIMARY KEY REFERENCES categories(id) ON DELETE RESTRICT,
    asset_category_id INTEGER NOT NULL UNIQUE REFERENCES asset_categories(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS asset_legacy_devices (
    device_id INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE RESTRICT,
    asset_id INTEGER NOT NULL UNIQUE REFERENCES assets(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS asset_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    child_asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity BETWEEN 1 AND 1000000),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_asset_id,child_asset_id),
    CHECK(parent_asset_id<>child_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_asset_components_child ON asset_components(child_asset_id,parent_asset_id);
CREATE TRIGGER IF NOT EXISTS asset_components_no_cycle_insert
BEFORE INSERT ON asset_components
WHEN EXISTS (
    WITH RECURSIVE descendants(id) AS (
        SELECT child_asset_id FROM asset_components WHERE parent_asset_id=NEW.child_asset_id
        UNION
        SELECT ac.child_asset_id FROM asset_components ac JOIN descendants d ON ac.parent_asset_id=d.id
    ) SELECT 1 FROM descendants WHERE id=NEW.parent_asset_id
)
BEGIN
    SELECT RAISE(ABORT,'asset_composition_cycle');
END;
CREATE TRIGGER IF NOT EXISTS asset_components_no_cycle_update
BEFORE UPDATE OF parent_asset_id,child_asset_id ON asset_components
WHEN EXISTS (
    WITH RECURSIVE descendants(id) AS (
        SELECT child_asset_id FROM asset_components WHERE parent_asset_id=NEW.child_asset_id AND id<>OLD.id
        UNION
        SELECT ac.child_asset_id FROM asset_components ac JOIN descendants d ON ac.parent_asset_id=d.id WHERE ac.id<>OLD.id
    ) SELECT 1 FROM descendants WHERE id=NEW.parent_asset_id
)
BEGIN
    SELECT RAISE(ABORT,'asset_composition_cycle');
END;
