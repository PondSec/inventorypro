-- Keep per-object upload rights separate even when identical image bytes deduplicate.
ALTER TABLE device_product_media ADD COLUMN override_source_url TEXT NOT NULL DEFAULT '';
ALTER TABLE device_product_media ADD COLUMN override_license_code TEXT NOT NULL DEFAULT '';
ALTER TABLE device_product_media ADD COLUMN override_attribution TEXT NOT NULL DEFAULT '';
ALTER TABLE device_product_media ADD COLUMN override_reviewed_at TEXT;
ALTER TABLE device_product_media ADD COLUMN override_reviewed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE asset_product_media ADD COLUMN override_source_url TEXT NOT NULL DEFAULT '';
ALTER TABLE asset_product_media ADD COLUMN override_license_code TEXT NOT NULL DEFAULT '';
ALTER TABLE asset_product_media ADD COLUMN override_attribution TEXT NOT NULL DEFAULT '';
ALTER TABLE asset_product_media ADD COLUMN override_reviewed_at TEXT;
ALTER TABLE asset_product_media ADD COLUMN override_reviewed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
