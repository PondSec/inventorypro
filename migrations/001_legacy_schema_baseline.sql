-- The legacy schema is created by the compatibility bootstrap in app.py.
-- This immutable marker establishes a verified versioning ledger for upgrades.
CREATE INDEX IF NOT EXISTS idx_inventory_links_user_id ON inventory_links(user_id);
