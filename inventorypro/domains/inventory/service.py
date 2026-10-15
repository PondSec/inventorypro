"""One inventory workspace over distinct, unchanged domain models."""
from __future__ import annotations

import re
from .objects import fallback_icon
from .assets import unified
from . import unified_list

SORTS = {'name': 'name COLLATE NOCASE', 'kind': 'kind', 'category': 'category COLLATE NOCASE',
         'serial_number': 'serial_number COLLATE NOCASE', 'created_at': 'created_at',
         'updated_at': 'updated_at', 'assigned_to': 'assigned_to COLLATE NOCASE', 'location':'location COLLATE NOCASE'}
FILTERS = {
    'missing_identity': "kind='device' AND (location_id IS NULL OR trim(coalesce(serial_number,''))='')",
    'missing_location': "kind='device' AND location_id IS NULL",
    'missing_serial': "kind='device' AND trim(coalesce(serial_number,''))=''",
    'maintenance': "kind='device' AND id IN (SELECT device_id FROM maintenance_tasks WHERE status='open')",
    'overdue_maintenance': "kind='device' AND id IN (SELECT device_id FROM maintenance_tasks WHERE status='open' AND date(due_date)<date('now'))",
    'due_maintenance': "kind='device' AND id IN (SELECT device_id FROM maintenance_tasks WHERE status='open' AND date(due_date)<=date('now','+30 days'))",
    'missing_lifecycle': "kind='asset' AND lifecycle_missing=1",
    'incomplete': "(kind='device' AND (location_id IS NULL OR trim(coalesce(serial_number,''))='')) OR (kind='asset' AND lifecycle_missing=1)",
    'uncategorized': "category_id IS NULL",
    'active': 'retired=0', 'retired': 'retired=1',
}


def integer(value, default, minimum=1, maximum=1000000):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def inventory_source(*, devices_allowed, assets_allowed):
    branches = []
    assignment = """SELECT coalesce(u.username,t.name,'') FROM asset_assignment_history ah
        LEFT JOIN users u ON u.id=ah.assigned_to_user_id LEFT JOIN teams t ON t.id=ah.assigned_to_team_id
        WHERE ah.id=(SELECT latest.id FROM asset_assignment_history latest WHERE latest.asset_id=a.id
                     ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1)
        AND ah.status IN ('assigned','checked_out')"""
    if devices_allowed:
        owner = f"(SELECT group_concat(DISTINCT NULLIF(owner,'')) FROM (SELECT ({assignment}) AS owner FROM assets a JOIN asset_devices ad ON ad.asset_id=a.id WHERE ad.device_id=d.id))" if assets_allowed else "''"
        branches.append(f"""SELECT d.id, 'device' AS kind, d.name, c.name AS category, d.category_id,
            d.serial_number, d.location_id, l.name AS location, d.created_at, 0 AS retired, 0 AS lifecycle_missing,
            coalesce((SELECT max(created_at) FROM activity_log WHERE entity_type='device' AND entity_id=d.id),d.created_at) AS updated_at,
            coalesce({owner},'') AS assigned_to
            FROM devices d LEFT JOIN categories c ON c.id=d.category_id LEFT JOIN locations l ON l.id=d.location_id""")
    if assets_allowed:
        branches.append(f"""SELECT a.id, 'asset' AS kind, a.name, ac.name AS category, a.category_id,
            '' AS serial_number, NULL AS location_id,
            (SELECT group_concat(DISTINCT l.name) FROM asset_devices ad JOIN devices d ON d.id=ad.device_id
             JOIN locations l ON l.id=d.location_id WHERE ad.asset_id=a.id) AS location,
            a.created_at, CASE WHEN trim(coalesce(a.retirement_date,''))<>'' THEN 1 ELSE 0 END AS retired,
            CASE WHEN trim(coalesce(a.acquisition_date,''))='' AND trim(coalesce(a.commissioning_date,''))=''
              AND trim(coalesce(a.warranty_end,''))='' THEN 1 ELSE 0 END AS lifecycle_missing,
            coalesce((SELECT max(created_at) FROM activity_log WHERE entity_type='asset' AND entity_id=a.id),a.created_at) AS updated_at,
            coalesce(({assignment}),'') AS assigned_to
            FROM assets a LEFT JOIN asset_categories ac ON ac.id=a.category_id""")
    return 'WITH inventory AS (' + ' UNION ALL '.join(branches) + ') ' if branches else ''


def inventory_query(arguments, *, devices_allowed, assets_allowed, maintenance_allowed=False,db=None):
    is_unified=db is not None and unified(db)
    source = unified_list.source(devices_allowed=devices_allowed,assets_allowed=assets_allowed) if is_unified and (devices_allowed or assets_allowed) else inventory_source(devices_allowed=devices_allowed, assets_allowed=assets_allowed)
    available_filters=unified_list.filters(FILTERS) if is_unified else FILTERS
    if is_unified:
        arguments=dict(arguments)
        arguments['kind']=''
        if str(arguments.get('category','')).startswith('device:'):
            old=str(arguments['category']).split(':',1)[1]
            mapped=db.execute('SELECT asset_category_id FROM asset_legacy_categories WHERE category_id=?',(old,)).fetchone()
            arguments['category']='asset:'+str(mapped[0]) if mapped else ''
    kind, status, sort = (arguments.get(key, '') for key in ('kind','filter','sort'))
    category = str(arguments.get('category', ''))
    match = re.fullmatch(r'(device|asset):([1-9]\d{0,8})', category)
    location = str(arguments.get('location', ''))
    state = {'q': str(arguments.get('q', '')).strip()[:256],
             'kind': kind if kind in {'device','asset'} else '',
             'filter': status if status in available_filters and (maintenance_allowed or 'maintenance' not in status) else '',
             'sort': sort if sort in SORTS else 'name',
             'direction': 'desc' if arguments.get('direction') == 'desc' else 'asc',
             'category': category if match else '',
             'location': int(location) if re.fullmatch(r'[1-9]\d{0,8}', location) else 0,
             'assigned': arguments.get('assigned') if arguments.get('assigned') in {'yes','no'} else '',
             'per_page': integer(arguments.get('per_page'), 10, maximum=100),
             'page': integer(arguments.get('page'), 1)}
    where, params = ['1=1'], []
    if state['q']:
        escaped = state['q'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        where.append("(coalesce(name,'') || ' ' || coalesce(category,'') || ' ' || coalesce(serial_number,'') || ' ' || coalesce(location,'') || ' ' || assigned_to) LIKE ? ESCAPE '\\'")
        params.append('%' + escaped + '%')
    if state['kind']:
        where.append('kind=?'); params.append(state['kind'])
    if state['filter']:
        where.append('(' + available_filters[state['filter']] + ')')
    if match:
        where.append('kind=? AND category_id=?'); params.extend([match[1],int(match[2])])
    if state['location']:
        if is_unified:
            where.append("instr(location_ids,','||?||',')>0");params.append(state['location'])
        else:
            where.append("(location_id=? OR (kind='asset' AND id IN (SELECT ad.asset_id FROM asset_devices ad JOIN devices d ON d.id=ad.device_id WHERE d.location_id=?)))")
            params.extend([state['location'],state['location']])
    if state['assigned']:
        where.append("trim(assigned_to)" + ("<>''" if state['assigned']=='yes' else "=''"))
    return source, ' WHERE ' + ' AND '.join(where), params, state


def list_inventory(db, arguments, *, devices_allowed, assets_allowed, maintenance_allowed=False):
    source, predicate, parameters, state = inventory_query(arguments, devices_allowed=devices_allowed,
        assets_allowed=assets_allowed, maintenance_allowed=maintenance_allowed,db=db)
    is_unified=unified(db)
    available_filters=unified_list.filters(FILTERS) if is_unified else FILTERS
    summary = {'total':0,'assigned':0,'maintenance':0,'incomplete':0}
    if not source:
        return {'rows':[], 'total':0, 'pages':1, 'page_numbers':[1], 'summary':summary, 'categories':[], 'locations':[], **state}
    summary = dict(db.execute(source + f'''SELECT count(*) AS total,
        count(CASE WHEN trim(assigned_to)<>'' THEN 1 END) AS assigned,
        count(CASE WHEN {available_filters['due_maintenance'] if maintenance_allowed else '0'} THEN 1 END) AS maintenance,
        count(CASE WHEN {available_filters['incomplete']} THEN 1 END) AS incomplete FROM inventory''').fetchone())
    categories = [dict(r) for r in db.execute(source + 'SELECT DISTINCT kind,category_id AS id,category AS name FROM inventory WHERE category_id IS NOT NULL' + (' AND kind=?' if state['kind'] else '') + ' ORDER BY category COLLATE NOCASE,kind', [state['kind']] if state['kind'] else [])]
    locations = [dict(r) for r in db.execute(source+"SELECT DISTINCT l.id,l.name FROM locations l WHERE EXISTS(SELECT 1 FROM inventory WHERE instr(location_ids,','||l.id||',')>0) ORDER BY l.name COLLATE NOCASE")] if is_unified else [dict(r) for r in db.execute(source + '''SELECT DISTINCT l.id,l.name FROM locations l WHERE
        l.id IN (SELECT location_id FROM inventory WHERE kind='device') OR
        l.id IN (SELECT d.location_id FROM devices d JOIN asset_devices ad ON ad.device_id=d.id
                 WHERE ad.asset_id IN (SELECT id FROM inventory WHERE kind='asset')) ORDER BY l.name COLLATE NOCASE''')]
    total = db.execute(source + 'SELECT COUNT(*) FROM inventory' + predicate, parameters).fetchone()[0]
    pages = max(1, (total + state['per_page'] - 1) // state['per_page'])
    state['page'] = min(state['page'], pages)
    page_numbers = sorted({1,pages,*range(max(1,state['page']-1),min(pages,state['page']+1)+1),*(range(1,min(5,pages)+1) if state['page']<=3 else [])})
    rows = db.execute(source + 'SELECT * FROM inventory' + predicate +
                      f" ORDER BY {SORTS[state['sort']]} {state['direction']},kind,id LIMIT ? OFFSET ?",
                      [*parameters,state['per_page'],(state['page']-1)*state['per_page']]).fetchall()
    rows = [dict(row) for row in rows]
    for row in rows:
        row['icon'] = fallback_icon(row['name'],row['category'] or '',row['kind'])
    return {'rows':rows,'total':total,'pages':pages,'page_numbers':page_numbers,'summary':summary,'categories':categories,'locations':locations,'unified':is_unified,**state}

def workspace_tasks(db, can, access):
    """Return exact actionable counts, scoped like the corresponding work lists."""
    tasks = []
    def add(key, label, sql, url, description, params=(), severity='attention'):
        count = db.execute(sql, params).fetchone()[0]
        tasks.append(dict(key=key, label=label, count=count, url=url, description=description, severity=severity))
    if unified(db):
        devices_allowed=can('devices.view') or can('devices.manage');assets_allowed=can('assets.view') or can('assets.manage')
        if devices_allowed or assets_allowed:
            source=unified_list.source(devices_allowed=devices_allowed,assets_allowed=assets_allowed)
            criteria=unified_list.filters(FILTERS)
            for key,label,criterion,description in [('identity','Inventardaten vervollständigen','missing_identity','Assets ohne Standort oder Identifikationsnummer'),('lifecycle','Beschaffungsdaten ergänzen','missing_lifecycle','Assets ohne Lifecycle-Daten')]:
                add(key,label,source+'SELECT count(*) FROM inventory WHERE '+criteria[criterion],'/inventory?filter='+criterion,description)
            if can('maintenance.view') or can('maintenance.manage'):
                add('maintenance','Überfällige Wartung',source+'SELECT count(*) FROM inventory WHERE '+criteria['overdue_maintenance'],'/inventory?filter=overdue_maintenance','Sichtbare Assets mit offenen, überfälligen Aufgaben',severity='critical')
    else:
        if can('devices.view') or can('devices.manage'):
            add('identity', 'Inventardaten vervollständigen',
                "SELECT count(*) FROM devices WHERE location_id IS NULL OR trim(coalesce(serial_number,''))=''",
                '/inventory?kind=device&filter=missing_identity', 'Geräte ohne Standort oder Identifikationsnummer')
        if can('assets.view') or can('assets.manage'):
            add('lifecycle', 'Beschaffungsdaten ergänzen',
                "SELECT count(*) FROM assets WHERE trim(coalesce(acquisition_date,''))='' AND trim(coalesce(commissioning_date,''))='' AND trim(coalesce(warranty_end,''))=''",
                '/inventory?kind=asset&filter=missing_lifecycle', 'Komponenten und Sets ohne Lifecycle-Daten')
        if can('maintenance.view') or can('maintenance.manage'):
            add('maintenance', 'Überfällige Wartung',
                "SELECT count(DISTINCT device_id) FROM maintenance_tasks WHERE status='open' AND date(due_date)<date('now')",
                '/inventory?kind=device&filter=overdue_maintenance', 'Betroffene Geräte mit offenen, überfälligen Aufgaben', severity='critical')
    if can('tickets.view_all') or can('tickets.view_own'):
        scope, params = '', []
        if not access['is_superuser'] and not can('tickets.view_all'):
            scope = ' AND (created_by_user_id=? OR (created_by_user_id IS NULL AND created_by=?))'
            params = [access['user']['id'], access['user']['username']]
        add('tickets', 'Offene Tickets', "SELECT count(*) FROM tickets WHERE status NOT IN ('closed','resolved')" + scope,
            '/tickets?queue=all-open', 'Offene Anfragen im eigenen Berechtigungsbereich', params)
        add('overdue_tickets', 'Überfällige Tickets', "SELECT count(*) FROM tickets WHERE status NOT IN ('closed','resolved') AND date(due_date)<date('now')" + scope,
            '/tickets?queue=overdue', 'Fällige Anfragen zuerst bearbeiten', params, 'critical')
    return tasks
