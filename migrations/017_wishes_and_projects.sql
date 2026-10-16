CREATE TABLE wish_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 240),
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private','team')),
    currency TEXT NOT NULL DEFAULT 'EUR',
    budget_cents INTEGER CHECK(budget_cents >= 0),
    target_date TEXT,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE wishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    project_id INTEGER REFERENCES wish_projects(id) ON DELETE SET NULL,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 240),
    notes TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private','team')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity BETWEEN 1 AND 10000),
    category_id INTEGER REFERENCES asset_categories(id) ON DELETE SET NULL,
    manufacturer TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    unit_price_cents INTEGER CHECK(unit_price_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'EUR',
    url TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('low','normal','high')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE wish_acquisitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wish_id INTEGER NOT NULL REFERENCES wishes(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    asset_name TEXT NOT NULL,
    unit_cost_cents INTEGER CHECK(unit_cost_cents >= 0),
    currency TEXT NOT NULL,
    actor_id INTEGER NOT NULL REFERENCES users(id),
    request_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX wish_acquired_asset ON wish_acquisitions(asset_id) WHERE asset_id IS NOT NULL;
CREATE INDEX wishes_owner_project ON wishes(owner_id,project_id);
CREATE INDEX wishes_project ON wishes(project_id);
CREATE INDEX wish_projects_owner ON wish_projects(owner_id);
CREATE INDEX wish_acquisition_request ON wish_acquisitions(actor_id,request_key);
