-- Back up first: asset notes and canonical maintenance data are removed by rollback.
DROP TABLE IF EXISTS asset_maintenance_tasks;
DROP TABLE IF EXISTS asset_notes;
DROP TRIGGER IF EXISTS asset_contents_remove;
DROP TRIGGER IF EXISTS asset_contents_change;
DROP TRIGGER IF EXISTS asset_contents_create;
DROP TRIGGER IF EXISTS asset_version_change;
DROP TRIGGER IF EXISTS asset_version_create;
DROP TABLE IF EXISTS asset_edit_versions;
DROP TABLE IF EXISTS asset_permission_scope;
