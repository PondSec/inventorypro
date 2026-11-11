DROP TRIGGER IF EXISTS activity_log_prevent_delete;
DROP TRIGGER IF EXISTS activity_log_prevent_update;
DROP INDEX IF EXISTS idx_activity_log_request_id;

ALTER TABLE activity_log DROP COLUMN outcome;
ALTER TABLE activity_log DROP COLUMN request_id;
