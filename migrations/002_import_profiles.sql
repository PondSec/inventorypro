CREATE TABLE IF NOT EXISTS import_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    entity TEXT NOT NULL CHECK (entity IN ('devices', 'assets')),
    mapping_json TEXT NOT NULL DEFAULT '{}',
    matching_key TEXT,
    sheet_name TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_import_profiles_entity ON import_profiles(entity);
