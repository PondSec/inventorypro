-- Photo bytes and object/model references remain; restore a backup to recover
-- per-object rights metadata after an explicit schema rollback.
ALTER TABLE device_product_media DROP COLUMN override_source_url;
ALTER TABLE device_product_media DROP COLUMN override_license_code;
ALTER TABLE device_product_media DROP COLUMN override_attribution;
ALTER TABLE device_product_media DROP COLUMN override_reviewed_at;
ALTER TABLE device_product_media DROP COLUMN override_reviewed_by_user_id;
ALTER TABLE asset_product_media DROP COLUMN override_source_url;
ALTER TABLE asset_product_media DROP COLUMN override_license_code;
ALTER TABLE asset_product_media DROP COLUMN override_attribution;
ALTER TABLE asset_product_media DROP COLUMN override_reviewed_at;
ALTER TABLE asset_product_media DROP COLUMN override_reviewed_by_user_id;
