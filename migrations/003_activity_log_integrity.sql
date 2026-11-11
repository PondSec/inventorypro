ALTER TABLE activity_log ADD COLUMN request_id TEXT;

ALTER TABLE activity_log ADD COLUMN outcome TEXT NOT NULL DEFAULT 'success'
CHECK (outcome IN ('success', 'failure', 'denied'));

CREATE INDEX IF NOT EXISTS idx_activity_log_request_id
ON activity_log(request_id);

CREATE TRIGGER IF NOT EXISTS activity_log_prevent_update
BEFORE UPDATE ON activity_log
BEGIN
    SELECT RAISE(ABORT, 'activity_log entries are immutable');
END;

CREATE TRIGGER IF NOT EXISTS activity_log_prevent_delete
BEFORE DELETE ON activity_log
BEGIN
    SELECT RAISE(ABORT, 'activity_log entries are immutable');
END;
