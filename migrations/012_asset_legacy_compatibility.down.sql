-- Alias mappings may now intentionally share a destination. Retain that safe
-- relation on rollback; the original UNIQUE constraint would discard merges.
DROP TRIGGER IF EXISTS compat_contents_delete;
DROP TRIGGER IF EXISTS compat_contents_update;
DROP TRIGGER IF EXISTS compat_contents_insert;
DROP TRIGGER IF EXISTS compat_legacy_contents_delete;
DROP TRIGGER IF EXISTS compat_legacy_contents_update;
DROP TRIGGER IF EXISTS compat_legacy_contents_insert;
DROP TRIGGER IF EXISTS compat_asset_change;
DROP TRIGGER IF EXISTS compat_device_change;
DROP TRIGGER IF EXISTS compat_device_create;
DROP TRIGGER IF EXISTS compat_category_create;
DROP TABLE inventory_compat_sync;
