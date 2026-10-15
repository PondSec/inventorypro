-- Explicit schema rollback only: new catalog metadata is removed. Restore a backup
-- to recover it. Inventory business rows and persistent image files are untouched.
DROP TABLE IF EXISTS device_product_media;
DROP TABLE IF EXISTS asset_product_media;
DROP TABLE IF EXISTS product_images;
DROP TABLE IF EXISTS product_identifiers;
DROP TABLE IF EXISTS product_media_files;
DROP TABLE IF EXISTS product_models;
DROP TABLE IF EXISTS product_catalog_settings;
