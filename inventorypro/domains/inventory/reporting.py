"""Read-only report aliases count canonical assets once and retain old report keys.

Each query gets the same explicit, permission-filtered CTEs. Physical legacy
tables remain untouched for integrations, history and rollback.
"""
from .assets import scope_predicate


class ReportingReader:
    def __init__(self,db,can,access):
        self.db=db
        predicate,self.arguments=scope_predicate(can)
        ticket_predicate='1' if can('tickets.view_all') else "(t.created_by_user_id=? OR (t.created_by_user_id IS NULL AND (lower(trim(t.created_by))=lower(trim(?)) OR lower(trim(t.requester_name))=lower(trim(?)))))" if can('tickets.view_own') else '0'
        if ticket_predicate.startswith('('):self.arguments += [access['user']['id'],access['user']['username'],access['user']['username']]
        maintenance='1' if can('maintenance.view') or can('maintenance.manage') else '0'
        activity='1' if can('activity.view') else '0'
        self.prefix=f'''WITH assets AS (SELECT a.* FROM main.assets a WHERE {predicate}),
            devices AS (SELECT * FROM assets),categories AS (SELECT * FROM main.asset_categories),
            device_tags AS (SELECT id,asset_id AS device_id,tag,created_at FROM main.asset_tags WHERE asset_id IN (SELECT id FROM assets)
                UNION ALL SELECT d.id,m.asset_id,d.tag,d.created_at FROM main.device_tags d
                JOIN main.asset_legacy_devices m ON m.device_id=d.device_id WHERE m.asset_id IN (SELECT id FROM assets)),
            device_notes AS (SELECT id,asset_id AS device_id,note,created_at FROM main.asset_notes WHERE asset_id IN (SELECT id FROM assets)
                UNION ALL SELECT d.id,m.asset_id,d.note,d.created_at FROM main.device_notes d
                JOIN main.asset_legacy_devices m ON m.device_id=d.device_id WHERE m.asset_id IN (SELECT id FROM assets)),
            maintenance_tasks AS (SELECT id,asset_id AS device_id,title,due_date,status FROM main.asset_maintenance_tasks WHERE {maintenance} AND asset_id IN (SELECT id FROM assets)
                UNION ALL SELECT d.id,m.asset_id,d.title,d.due_date,CASE WHEN d.status='completed' THEN 'done' ELSE d.status END
                FROM main.maintenance_tasks d JOIN main.asset_legacy_devices m ON m.device_id=d.device_id WHERE {maintenance} AND m.asset_id IN (SELECT id FROM assets)),
            tickets AS (SELECT t.* FROM main.tickets t WHERE {ticket_predicate}),
            ticket_assets AS (SELECT * FROM main.ticket_assets WHERE ticket_id IN (SELECT id FROM tickets) AND asset_id IN (SELECT id FROM assets)),
            ticket_comments AS (SELECT * FROM main.ticket_comments WHERE ticket_id IN (SELECT id FROM tickets)),
            activity_log AS (SELECT * FROM main.activity_log WHERE {activity}) '''

    def execute(self,sql,parameters=()):
        if not sql.lstrip().upper().startswith('SELECT'):raise ValueError('ReportingReader erlaubt ausschließlich SELECT-Abfragen.')
        return self.db.execute(self.prefix+sql,[*self.arguments,*parameters])
