ALTER TABLE server_settings ADD COLUMN ui_language TEXT NOT NULL DEFAULT 'de' CHECK(ui_language IN ('de','en'));
