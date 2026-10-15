"""A single asset list after conversion, retaining historical permission scopes."""
from .assets import scope_predicate


def filters(legacy_filters):
    result={key:value.replace("kind='device'","kind='asset'") for key,value in legacy_filters.items()}
    for key,condition in [('maintenance',"status='open'"),('overdue_maintenance',"status='open' AND date(due_date)<date('now')"),('due_maintenance',"status='open' AND date(due_date)<=date('now','+30 days')")]:
        result[key]=f'''id IN (SELECT asset_id FROM asset_maintenance_tasks WHERE {condition}
            UNION SELECT m.asset_id FROM asset_legacy_devices m JOIN maintenance_tasks ON maintenance_tasks.device_id=m.device_id WHERE {condition})'''
    result['incomplete']="location_id IS NULL OR trim(coalesce(serial_number,''))='' OR lifecycle_missing=1"
    return result


def source(*,devices_allowed,assets_allowed):
    def can(key):return devices_allowed if key.startswith('devices.') else assets_allowed if key.startswith('assets.') else False
    predicate,args=scope_predicate(can)
    # The values are fixed internal permission domain names, not request input.
    for scope in args:predicate=predicate.replace('?',"'"+scope+"'",1)
    return f'''WITH inventory AS (SELECT a.id,'asset' AS kind,a.name,c.name AS category,a.category_id,
        a.serial_number,a.location_id,l.name AS location,a.created_at,
        CASE WHEN trim(coalesce(a.retirement_date,''))<>'' THEN 1 ELSE 0 END AS retired,
        CASE WHEN trim(coalesce(a.acquisition_date,''))='' AND trim(coalesce(a.commissioning_date,''))=''
          AND trim(coalesce(a.warranty_end,''))='' THEN 1 ELSE 0 END AS lifecycle_missing,
        coalesce((SELECT max(created_at) FROM activity_log WHERE entity_type IN ('asset','asset_entry') AND entity_id=a.id),a.created_at) AS updated_at,
        coalesce((SELECT coalesce(u.username,t.name,'') FROM asset_assignment_history ah
            LEFT JOIN users u ON u.id=ah.assigned_to_user_id LEFT JOIN teams t ON t.id=ah.assigned_to_team_id
            WHERE ah.asset_id=a.id AND ah.id=(SELECT latest.id FROM asset_assignment_history latest WHERE latest.asset_id=a.id
                ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1) AND ah.status IN ('assigned','checked_out','transferred')),'') AS assigned_to
        FROM assets a LEFT JOIN asset_categories c ON c.id=a.category_id LEFT JOIN locations l ON l.id=a.location_id
        WHERE {predicate}) '''
