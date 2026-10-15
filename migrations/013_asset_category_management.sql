CREATE TABLE asset_category_scope (
    category_id INTEGER PRIMARY KEY REFERENCES asset_categories(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK(scope IN ('devices','assets'))
);
INSERT INTO asset_category_scope(category_id,scope) SELECT id,
    CASE WHEN EXISTS(SELECT 1 FROM asset_legacy_categories m WHERE m.asset_category_id=asset_categories.id)
    THEN 'devices' ELSE 'assets' END FROM asset_categories;
CREATE TABLE asset_category_versions (
    category_id INTEGER PRIMARY KEY REFERENCES asset_categories(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 1
);
INSERT INTO asset_category_versions(category_id) SELECT id FROM asset_categories;
CREATE TRIGGER asset_category_version_create AFTER INSERT ON asset_categories BEGIN
    INSERT OR IGNORE INTO asset_category_versions(category_id) VALUES(NEW.id);
END;
CREATE TRIGGER asset_category_version_change AFTER UPDATE ON asset_categories BEGIN
    UPDATE asset_category_versions SET revision=revision+1 WHERE category_id=NEW.id;
END;
