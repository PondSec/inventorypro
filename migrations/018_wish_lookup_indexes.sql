CREATE INDEX wish_acquisitions_wish ON wish_acquisitions(wish_id,asset_id);
CREATE INDEX wish_projects_visibility ON wish_projects(visibility,owner_id);
CREATE INDEX wishes_archive_priority ON wishes(archived,priority,updated_at,id);
