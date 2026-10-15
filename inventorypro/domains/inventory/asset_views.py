"""Shared panel/detail read model for canonical assets and retained legacy history."""
from . import assets
from .objects import product_identity,fallback_icon


def load_asset_panel(db,identifier,*,can,access,ticket_visible):
    obj=assets.get_asset(db,can,identifier)
    obj.update(kind='asset',unified=True,icon=fallback_icon(obj['name'],obj.get('category') or '','asset'))
    obj.update(product_identity(obj['specs']))
    obj['detail_url']=f'/inventory/assets/{identifier}';obj['edit_url']=obj['detail_url']+'/edit'
    obj['can_history']=can('activity.view');obj['can_maintenance']=can('maintenance.view') or can('maintenance.manage')
    obj['can_tickets']=can('tickets.view_all') or can('tickets.view_own')
    obj['can_links']=True;obj['can_relations']=True
    obj['links']=[{**item,'kind':'asset'} for item in obj['components']]
    obj['assignments']=[]
    row=db.execute('''SELECT ah.status,u.username AS assigned_user,t.name AS assigned_team,a.name AS asset_name,a.id AS asset_id,ah.due_at
        FROM asset_assignment_history ah JOIN assets a ON a.id=ah.asset_id
        LEFT JOIN users u ON u.id=ah.assigned_to_user_id LEFT JOIN teams t ON t.id=ah.assigned_to_team_id
        WHERE ah.asset_id=? ORDER BY ah.created_at DESC,ah.id DESC LIMIT 1''',(identifier,)).fetchone()
    if row and row['status'] in {'assigned','checked_out','transferred'}:obj['assignments']=[dict(row)]
    predicate,args=assets.scope_predicate(can)
    obj['relations']=[dict(row) for row in db.execute(f'''SELECT a.id,a.name,rt.name AS relation FROM asset_relations ar
        JOIN assets a ON a.id=CASE WHEN ar.asset_id=? THEN ar.related_asset_id ELSE ar.asset_id END
        LEFT JOIN asset_relation_types rt ON rt.id=ar.relation_type_id WHERE (ar.asset_id=? OR ar.related_asset_id=?) AND {predicate}
        ORDER BY ar.id DESC LIMIT 100''',[identifier,identifier,identifier,*args])]
    legacy=db.execute('SELECT device_id FROM asset_legacy_devices WHERE asset_id=?',(identifier,)).fetchone()
    device_id=legacy[0] if legacy else None
    obj['tasks']=[];obj['note_entries']=[]
    if obj['can_maintenance']:
        obj['tasks']=[{**dict(row),'key':'asset-'+str(row['id'])} for row in db.execute('SELECT * FROM asset_maintenance_tasks WHERE asset_id=? ORDER BY due_date,id',(identifier,))]
        if device_id:obj['tasks'] += [{**dict(row),'key':'legacy-'+str(row['id'])} for row in db.execute('SELECT * FROM maintenance_tasks WHERE device_id=? ORDER BY due_date,id',(device_id,))]
    obj['note_entries']=[dict(row) for row in db.execute('SELECT note,created_at FROM asset_notes WHERE asset_id=? ORDER BY id DESC LIMIT 100',(identifier,))]
    if device_id:obj['note_entries'] += [dict(row) for row in db.execute('SELECT note,created_at FROM device_notes WHERE device_id=? ORDER BY id DESC LIMIT 100',(device_id,))]
    obj['tickets']=[]
    if obj['can_tickets']:
        for row in db.execute('SELECT DISTINCT t.* FROM tickets t JOIN ticket_assets ta ON ta.ticket_id=t.id WHERE ta.asset_id=? ORDER BY t.updated_at DESC,t.id DESC',(identifier,)):
            ticket=dict(row)
            if ticket_visible(ticket,access):obj['tickets'].append({key:ticket.get(key) for key in ['id','title','status','priority','due_date']})
            if len(obj['tickets'])>=100:break
    obj['history']=[]
    if obj['can_history']:
        obj['history']=[dict(row) for row in db.execute('''SELECT action,username,created_at FROM activity_log
            WHERE (entity_type IN ('asset','asset_entry') AND entity_id=?) OR (entity_type='device' AND entity_id=?)
            ORDER BY id DESC LIMIT 100''',(identifier,device_id))]
    obj['status']='Ausgemustert' if obj.get('retirement_date') else 'Im Bestand';obj['status_tone']='neutral' if obj.get('retirement_date') else 'success'
    obj['tabs']=[('overview','Übersicht'),('details','Details'),('accessories',f"Inhalt ({len(obj['components'])})")]
    if obj['can_tickets']:obj['tabs'].append(('tickets',f"Tickets ({len(obj['tickets'])})"))
    if obj['can_history']:obj['tabs'].append(('history','Historie'))
    return obj
