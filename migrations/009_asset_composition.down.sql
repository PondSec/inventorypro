-- Downgrading a converted installation requires its pre-upgrade backup.
DROP TRIGGER IF EXISTS asset_components_no_cycle_update;
DROP TRIGGER IF EXISTS asset_components_no_cycle_insert;
DROP TABLE IF EXISTS asset_components;
DROP TABLE IF EXISTS asset_legacy_devices;
DROP TABLE IF EXISTS asset_legacy_categories;
DROP INDEX IF EXISTS idx_assets_location;
DROP TABLE IF EXISTS inventory_model_state;
ALTER TABLE assets DROP COLUMN location_id;
ALTER TABLE assets DROP COLUMN serial_number;
