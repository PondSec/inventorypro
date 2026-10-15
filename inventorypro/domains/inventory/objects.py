"""Permission-scoped read model for the shared inventory object panel.

No new business entities: devices and asset entries keep their existing models.
The same predicates used by the ticket routes guard linked ticket information.
"""
import json
import re


def specs_object(value):
    try:
        result = json.loads(value or '{}') if isinstance(value, str) else value
    except (ValueError, TypeError):
        result = {}
    return result if isinstance(result, dict) else {}


def product_identity(specs):
    normalized = {re.sub(r'[\W_]+', '', str(key).casefold()): value for key, value in specs.items()}
    def pick(*names):
        return next((str(normalized[key]) for key in names if normalized.get(key) not in (None, '')), '')
    return {'manufacturer': pick('hersteller', 'manufacturer', 'brand', 'marke'),
            'model': pick('modell', 'model', 'produktmodell'),
            'mpn': pick('mpn', 'herstellernummer', 'herstellerteilenummer', 'partnumber'),
            'asset_tag': pick('assettag', 'inventarnummer', 'inventartag')}


def fallback_icon(name, category='', kind='device'):
    text = f'{category} {name}'.casefold()
    for words, icon in [(['notebook', 'laptop', 'macbook', 'thinkpad', 'elitebook', 'latitude'], 'laptop'),
                        (['smartphone', 'iphone', 'telefon'], 'smartphone'),
                        (['drucker', 'printer', 'laserjet'], 'printer'),
                        (['server', 'nas', 'diskstation', 'rack'], 'server'),
                        (['monitor', 'display', 'ultrasharp'], 'monitor'),
                        (['switch', 'router', 'access point', 'netzwerk'], 'network'),
                        (['ssd', 'festplatte', 'speicher'], 'drive')]:
        if any(word in text for word in words):
            return icon
    return 'component' if kind == 'asset' else 'monitor'


def load_panel(db, kind, object_id, *, can, access, ticket_visible):
    if kind not in {'device', 'asset'}:
        return None
    table, category_table = ('devices', 'categories') if kind == 'device' else ('assets', 'asset_categories')
    row = db.execute(f'''SELECT o.*, c.name AS category FROM {table} o
        LEFT JOIN {category_table} c ON c.id=o.category_id WHERE o.id=?''', (object_id,)).fetchone()
    if row is None:
        return None
    obj = dict(row)
    obj.update(kind=kind, specs=specs_object(obj.get('specs')))
    obj.update(product_identity(obj['specs']))
    obj['icon'] = fallback_icon(obj['name'], obj.get('category') or '', kind)
    obj['detail_url'] = f"/inventory/{'devices' if kind == 'device' else 'assets'}/{object_id}"
    obj['edit_url'] = f"/?view={'devices' if kind == 'device' else 'assets'}&edit_{kind}={object_id}"
    obj['can_edit'] = can('devices.manage' if kind == 'device' else 'assets.manage')
    obj['can_history'] = can('activity.view')
    obj['can_maintenance'] = kind == 'device' and (can('maintenance.view') or can('maintenance.manage'))
    obj['can_tickets'] = can('tickets.view_all') or can('tickets.view_own')
    obj['can_links'] = can('assets.view') or can('assets.manage') if kind == 'device' else can('devices.view') or can('devices.manage')
    obj['can_relations'] = can('assets.view') or can('assets.manage')
    obj['location'] = ''
    if kind == 'device' and obj.get('location_id'):
        site = db.execute('SELECT name FROM locations WHERE id=?', (obj['location_id'],)).fetchone()
        obj['location'] = site['name'] if site else ''
    obj['links'] = []
    if obj['can_links']:
        if kind == 'device':
            obj['links'] = [dict(r) for r in db.execute('''SELECT a.id,a.name,ad.quantity,ad.notes,
                'asset' AS kind FROM asset_devices ad JOIN assets a ON a.id=ad.asset_id
                WHERE ad.device_id=? ORDER BY a.name LIMIT 100''', (object_id,))]
        else:
            obj['links'] = [dict(r) for r in db.execute('''SELECT d.id,d.name,d.serial_number,
                l.name AS location,ad.quantity,ad.notes,'device' AS kind FROM asset_devices ad
                JOIN devices d ON d.id=ad.device_id LEFT JOIN locations l ON l.id=d.location_id
                WHERE ad.asset_id=? ORDER BY d.name LIMIT 100''', (object_id,))]
            obj['location'] = ', '.join(dict.fromkeys(r['location'] for r in obj['links'] if r['location']))
    obj['assignments'] = []
    # Device ownership is represented through its linked sets, not a new direct
    # device-owner field. Keep the source visible instead of inventing assignment.
    assignment_assets = [object_id] if kind == 'asset' else [r['id'] for r in obj['links']]
    if obj['can_relations']:
        for asset_id in assignment_assets:
            assignment = db.execute('''SELECT ah.status,u.username AS assigned_user,t.name AS assigned_team,
                a.name AS asset_name,a.id AS asset_id,ah.due_at FROM asset_assignment_history ah
                JOIN assets a ON a.id=ah.asset_id LEFT JOIN users u ON u.id=ah.assigned_to_user_id
                LEFT JOIN teams t ON t.id=ah.assigned_to_team_id WHERE ah.asset_id=?
                ORDER BY ah.created_at DESC,ah.id DESC LIMIT 1''', (asset_id,)).fetchone()
            if assignment and assignment['status'] in {'assigned', 'checked_out'}:
                obj['assignments'].append(dict(assignment))
    obj['relations'] = []
    if kind == 'asset' and obj['can_relations']:
        obj['relations'] = [dict(r) for r in db.execute('''SELECT
            CASE WHEN ar.asset_id=? THEN a.id ELSE b.id END AS id,
            CASE WHEN ar.asset_id=? THEN a.name ELSE b.name END AS name,rt.name AS relation
            FROM asset_relations ar JOIN assets a ON a.id=ar.related_asset_id
            JOIN assets b ON b.id=ar.asset_id LEFT JOIN asset_relation_types rt ON rt.id=ar.relation_type_id
            WHERE ar.asset_id=? OR ar.related_asset_id=? ORDER BY ar.id DESC LIMIT 100''', (object_id,)*4)]
    obj['tasks'] = [dict(r) for r in db.execute('SELECT id,title,due_date,status FROM maintenance_tasks WHERE device_id=? ORDER BY due_date,id LIMIT 100', (object_id,))] if obj['can_maintenance'] else []
    obj['tickets'] = []
    if obj['can_tickets']:
        predicate = 'ta.asset_id=?' if kind == 'asset' else 'ta.asset_id IN (SELECT asset_id FROM asset_devices WHERE device_id=?)'
        for ticket in db.execute('SELECT DISTINCT t.* FROM tickets t JOIN ticket_assets ta ON ta.ticket_id=t.id WHERE ' + predicate + ' ORDER BY t.updated_at DESC,t.id DESC', (object_id,)):
            ticket = dict(ticket)
            if ticket_visible(ticket, access):
                obj['tickets'].append({key: ticket.get(key) for key in ('id','title','status','priority','due_date')})
            if len(obj['tickets']) == 100:
                break
    obj['history'] = [dict(r) for r in db.execute('SELECT action,username,created_at FROM activity_log WHERE entity_type=? AND entity_id=? ORDER BY id DESC LIMIT 100', (kind, object_id))] if obj['can_history'] else []
    obj['status'] = 'Ausgemustert' if obj.get('retirement_date') else 'Im Bestand'
    obj['status_tone'] = 'neutral' if obj.get('retirement_date') else 'success'
    obj['tabs'] = [('overview', 'Übersicht'), ('details', 'Details')]
    if obj['can_links']:
        obj['tabs'].append(('accessories', f"{'Zubehör' if kind == 'device' else 'Geräte'} ({len(obj['links'])}{'+' if len(obj['links']) == 100 else ''})"))
    if obj['can_tickets']:
        obj['tabs'].append(('tickets', f"Tickets ({len(obj['tickets'])}{'+' if len(obj['tickets']) == 100 else ''})"))
    if obj['can_history']:
        obj['tabs'].append(('history', 'Historie'))
    return obj
