"""One inventory workspace over distinct, unchanged domain models."""
from __future__ import annotations

SORTS = {'name': 'name COLLATE NOCASE', 'kind': 'kind', 'category': 'category COLLATE NOCASE',
         'serial_number': 'serial_number COLLATE NOCASE', 'created_at': 'created_at'}
FILTERS = {
    'missing_identity': "kind='device' AND (location_id IS NULL OR trim(coalesce(serial_number,''))='')",
    'missing_location': "kind='device' AND location_id IS NULL",
    'missing_serial': "kind='device' AND trim(coalesce(serial_number,''))=''",
    'maintenance': "kind='device' AND id IN (SELECT device_id FROM maintenance_tasks WHERE status='open')",
    'overdue_maintenance': "kind='device' AND id IN (SELECT device_id FROM maintenance_tasks WHERE status='open' AND date(due_date)<date('now'))",
    'missing_lifecycle': "kind='asset' AND lifecycle_missing=1",
    'uncategorized': "category_id IS NULL",
}


def integer(value, default, minimum=1, maximum=1000000):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def list_inventory(db, arguments, *, devices_allowed, assets_allowed):
    branches = []
    if devices_allowed:
        branches.append("""SELECT d.id, 'device' AS kind, d.name, c.name AS category, d.category_id,
            d.serial_number, d.location_id, l.name AS location, d.created_at, 0 AS retired, 0 AS lifecycle_missing
            FROM devices d LEFT JOIN categories c ON c.id=d.category_id LEFT JOIN locations l ON l.id=d.location_id""")
    if assets_allowed:
        branches.append("""SELECT a.id, 'asset' AS kind, a.name, ac.name AS category, a.category_id,
            '' AS serial_number, NULL AS location_id,
            (SELECT group_concat(DISTINCT l.name) FROM asset_devices ad JOIN devices d ON d.id=ad.device_id
             JOIN locations l ON l.id=d.location_id WHERE ad.asset_id=a.id) AS location,
            a.created_at, CASE WHEN trim(coalesce(a.retirement_date,''))<>'' THEN 1 ELSE 0 END AS retired,
            CASE WHEN trim(coalesce(a.acquisition_date,''))='' AND trim(coalesce(a.commissioning_date,''))=''
              AND trim(coalesce(a.warranty_end,''))='' THEN 1 ELSE 0 END AS lifecycle_missing
            FROM assets a LEFT JOIN asset_categories ac ON ac.id=a.category_id""")
    search = str(arguments.get('q', '')).strip()[:256]
    kind = arguments.get('kind', '')
    status = arguments.get('filter', '')
    sort = arguments.get('sort', 'name')
    sort = sort if sort in SORTS else 'name'
    direction = 'desc' if arguments.get('direction') == 'desc' else 'asc'
    per_page = integer(arguments.get('per_page'), 25, maximum=100)
    state = {'q': search, 'kind': kind if kind in {'device', 'asset'} else '',
             'filter': status if status in FILTERS else '', 'sort': sort, 'direction': direction,
             'per_page': per_page, 'page': integer(arguments.get('page'), 1)}
    if not branches:
        return {'rows': [], 'total': 0, 'pages': 1, **state}
    where, parameters = ['1=1'], []
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        where.append("(coalesce(name,'') || ' ' || coalesce(category,'') || ' ' || coalesce(serial_number,'') || ' ' || coalesce(location,'')) LIKE ? ESCAPE '\\'")
        parameters.append('%' + escaped + '%')
    if state['kind']:
        where.append('kind=?')
        parameters.append(state['kind'])
    if state['filter']:
        where.append(FILTERS[state['filter']])
    source = 'WITH inventory AS (' + ' UNION ALL '.join(branches) + ') '
    predicate = ' WHERE ' + ' AND '.join(where)
    total = db.execute(source + 'SELECT COUNT(*) FROM inventory' + predicate, parameters).fetchone()[0]
    pages = max(1, (total + per_page - 1) // per_page)
    state['page'] = min(state['page'], pages)
    rows = db.execute(source + 'SELECT * FROM inventory' + predicate +
                      f' ORDER BY {SORTS[sort]} {direction}, kind, id LIMIT ? OFFSET ?',
                      [*parameters, per_page, (state['page'] - 1)*per_page]).fetchall()
    return {'rows': [dict(row) for row in rows], 'total': total, 'pages': pages, **state}
