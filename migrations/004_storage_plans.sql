CREATE TABLE IF NOT EXISTS storage_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    preview_json TEXT NOT NULL,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
