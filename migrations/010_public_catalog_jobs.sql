ALTER TABLE product_catalog_settings ADD COLUMN external_revision TEXT NOT NULL DEFAULT '';
-- Persistent, deduplicated background lookups. No inventory/customer names stored.
CREATE TABLE IF NOT EXISTS product_lookup_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    identity_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','matched','no_match','no_image','ambiguous','unlicensed','insufficient','error')),
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_token TEXT NOT NULL DEFAULT '',
    lease_until INTEGER NOT NULL DEFAULT 0,
    retry_at INTEGER NOT NULL DEFAULT 0,
    result_json TEXT NOT NULL DEFAULT '{}',
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_product_lookup_jobs_queue ON product_lookup_jobs(status,retry_at,lease_until,id);
CREATE TABLE IF NOT EXISTS product_lookup_targets (
    job_id INTEGER NOT NULL REFERENCES product_lookup_jobs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('device','asset')),
    object_id INTEGER NOT NULL CHECK(object_id>0),
    PRIMARY KEY(job_id,kind,object_id)
);
