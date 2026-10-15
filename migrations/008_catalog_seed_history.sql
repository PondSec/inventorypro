-- Remember intentional built-in model/image deletion; never resurrect it on restart.
CREATE TABLE IF NOT EXISTS product_catalog_seed_history (
    seed_key TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
