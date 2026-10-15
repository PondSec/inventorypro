-- Canonical assets keep historical access scopes without granting new permissions.
CREATE TABLE IF NOT EXISTS asset_permission_scope (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK(scope IN ('devices','assets'))
);
CREATE TABLE IF NOT EXISTS asset_edit_versions (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0)
);
INSERT OR IGNORE INTO asset_edit_versions(asset_id) SELECT id FROM assets;
CREATE TRIGGER IF NOT EXISTS asset_version_create AFTER INSERT ON assets BEGIN
    INSERT OR IGNORE INTO asset_edit_versions(asset_id) VALUES(NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS asset_version_change AFTER UPDATE ON assets BEGIN
    UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS asset_contents_create AFTER INSERT ON asset_components BEGIN
    UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id=NEW.parent_asset_id;
END;
CREATE TRIGGER IF NOT EXISTS asset_contents_change AFTER UPDATE ON asset_components BEGIN
    UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id IN (OLD.parent_asset_id,NEW.parent_asset_id);
END;
CREATE TRIGGER IF NOT EXISTS asset_contents_remove AFTER DELETE ON asset_components BEGIN
    UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id=OLD.parent_asset_id;
END;
CREATE TABLE IF NOT EXISTS asset_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS asset_maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_asset_maintenance_due ON asset_maintenance_tasks(status,due_date,asset_id);
