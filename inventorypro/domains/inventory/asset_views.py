"""Shared panel/detail read model for canonical assets and retained legacy history."""
from . import assets
from .objects import product_identity,fallback_icon


def load_asset_panel(db,identifier,*,can,access,ticket_visible):
    obj=assets.get_asset(db,can,identifier)
    obj.update(kind='asset',unified=True,icon=fallback_icon(obj['name'],obj.get('category') or '','asset'))
    obj.update(product_identity(obj['specs']))
    obj['detail_url']=f'/inventory/assets/{identifier}';obj['edit_url']=obj['detail_url']+'/edit'
    obj['can_history']=can('activity.view') or can('asset.view_history');obj['can_maintenance']=can('maintenance.view') or can('maintenance.manage')
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
    if not obj['assignments']:
        inherited=db.execute(f'''WITH RECURSIVE parents(id) AS (
            SELECT parent_asset_id FROM asset_components WHERE child_asset_id=?
            UNION SELECT c.parent_asset_id FROM asset_components c JOIN parents p ON c.child_asset_id=p.id)
            SELECT ah.status,u.username AS assigned_user,t.name AS assigned_team,a.name AS asset_name,a.id AS asset_id,ah.due_at
            FROM parents p JOIN assets a ON a.id=p.id JOIN asset_assignment_history ah ON ah.asset_id=a.id
            LEFT JOIN users u ON u.id=ah.assigned_to_user_id LEFT JOIN teams t ON t.id=ah.assigned_to_team_id
            WHERE ah.id=(SELECT latest.id FROM asset_assignment_history latest WHERE latest.asset_id=a.id ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1)
            AND ah.status IN ('assigned','checked_out','transferred') AND {predicate} ORDER BY a.name LIMIT 100''',[identifier,*args])
        obj['assignments']=[dict(row) for row in inherited]
    if not obj['location']:
        from .unified_list import source
        sql=source(devices_allowed=can('devices.view') or can('devices.manage'),assets_allowed=can('assets.view') or can('assets.manage'))
        location=db.execute(sql+'SELECT location FROM inventory WHERE id=?',(identifier,)).fetchone()
        if location:obj['location']=location[0]
    obj['relations']=[dict(row) for row in db.execute(f'''SELECT a.id,a.name,rt.name AS relation FROM asset_relations ar
        JOIN assets a ON a.id=CASE WHEN ar.asset_id=? THEN ar.related_asset_id ELSE ar.asset_id END
        LEFT JOIN asset_relation_types rt ON rt.id=ar.relation_type_id WHERE (ar.asset_id=? OR ar.related_asset_id=?) AND {predicate}
        ORDER BY ar.id DESC LIMIT 100''',[identifier,identifier,identifier,*args])]
    legacy=db.execute('SELECT device_id FROM asset_legacy_devices WHERE asset_id=?',(identifier,)).fetchone()
    device_id=legacy[0] if legacy else None
    obj['tasks']=[];obj['note_entries']=[];obj['tags']=[];obj['software']=[]
    if obj['can_maintenance']:
        obj['tasks']=[{**dict(row),'key':'asset-'+str(row['id'])} for row in db.execute('SELECT * FROM asset_maintenance_tasks WHERE asset_id=? ORDER BY due_date,id',(identifier,))]
        if device_id:obj['tasks'] += [{**dict(row),'key':'legacy-'+str(row['id'])} for row in db.execute('SELECT * FROM maintenance_tasks WHERE device_id=? ORDER BY due_date,id',(device_id,))]
    obj['note_entries']=[{**dict(row),'key':'asset-'+str(row['id'])} for row in db.execute('SELECT id,note,created_at FROM asset_notes WHERE asset_id=? ORDER BY id DESC LIMIT 100',(identifier,))]
    if device_id:obj['note_entries'] += [{**dict(row),'key':'legacy-'+str(row['id'])} for row in db.execute('SELECT id,note,created_at FROM device_notes WHERE device_id=? ORDER BY id DESC LIMIT 100',(device_id,))]
    obj['tags']=[{**dict(row),'key':'asset-'+str(row['id'])} for row in db.execute('SELECT * FROM asset_tags WHERE asset_id=? ORDER BY id DESC',(identifier,))]
    if device_id:obj['tags'] += [{**dict(row),'key':'legacy-'+str(row['id'])} for row in db.execute('SELECT * FROM device_tags WHERE device_id=? ORDER BY id DESC',(device_id,))]
    if can('software.view') or can('software.manage'):
        obj['software']=[dict(row) for row in db.execute('''SELECT si.*,s.name FROM software_installations si JOIN software s ON s.id=si.software_id
            WHERE si.asset_id=? OR si.device_id=? ORDER BY s.name,si.id''',(identifier,device_id))]
    obj['tickets']=[]
    if obj['can_tickets']:
        for row in db.execute('SELECT DISTINCT t.* FROM tickets t JOIN ticket_assets ta ON ta.ticket_id=t.id WHERE ta.asset_id=? ORDER BY t.updated_at DESC,t.id DESC',(identifier,)):
            ticket=dict(row)
            if ticket_visible(ticket,access):obj['tickets'].append({key:ticket.get(key) for key in ['id','title','status','priority','due_date']})
            if len(obj['tickets'])>=100:break
    obj['history']=[]
    obj['assignment_history']=[]
    if can('asset.view_history'):
        obj['assignment_history']=[dict(row) for row in db.execute('''SELECT ah.status,ah.note,ah.due_at,ah.created_at,u.username AS assigned_user,t.name AS assigned_team
            FROM asset_assignment_history ah LEFT JOIN users u ON u.id=ah.assigned_to_user_id
            LEFT JOIN teams t ON t.id=ah.assigned_to_team_id WHERE ah.asset_id=? ORDER BY ah.created_at DESC,ah.id DESC LIMIT 100''',(identifier,))]
    if can('activity.view'):
        obj['history']=[dict(row) for row in db.execute('''SELECT action,username,created_at FROM activity_log
            WHERE (entity_type IN ('asset','asset_entry') AND entity_id=?) OR (entity_type='device' AND entity_id=?)
            ORDER BY id DESC LIMIT 100''',(identifier,device_id))]
    obj['status']='Ausgemustert' if obj.get('retirement_date') else 'Im Bestand';obj['status_tone']='neutral' if obj.get('retirement_date') else 'success'
    obj['tabs']=[('overview','Übersicht'),('details','Details'),('accessories',f"Inhalt ({len(obj['components'])})")]
    if obj['can_tickets']:obj['tabs'].append(('tickets',f"Tickets ({len(obj['tickets'])})"))
    if obj['can_history']:obj['tabs'].append(('history','Historie'))
    return obj
