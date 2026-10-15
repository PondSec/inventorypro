"""Scoped historical aggregates over the canonical inventory, without duplicate devices."""
from .assets import scope_predicate


class TimelineReader:
    def __init__(self,db,can,access,graph):
        self.db=db
        predicate,self.arguments=scope_predicate(can)
        ticket_predicate='1' if can('tickets.view_all') else "(t.created_by_user_id=? OR (t.created_by_user_id IS NULL AND (lower(trim(t.created_by))=lower(trim(?)) OR lower(trim(t.requester_name))=lower(trim(?)))))" if can('tickets.view_own') else '0'
        if ticket_predicate.startswith('('):self.arguments += [access['user']['id'],access['user']['username'],access['user']['username']]
        roadmap='1' if can('roadmap.view') or can('roadmap.manage') else '0'
        graph_ids=[row['id'] for row in db.execute('SELECT * FROM dependency_links') if can('dependencies.view') and graph.edge(row)]
        links=','.join('?' for _ in graph_ids) or 'NULL'
        self.arguments += graph_ids
        # Full inventory readers also retain events for deleted objects. Scoped
        # readers cannot recover private names through the historical log.
        full_inventory=all(can(scope+'.view') or can(scope+'.manage') for scope in ['assets','devices'])
        asset_activity='1' if full_inventory else 'l.entity_id IN (SELECT id FROM assets)'
        device_activity='1' if full_inventory else 'l.entity_id IN (SELECT device_id FROM main.asset_legacy_devices WHERE asset_id IN (SELECT id FROM assets))'
        other_types=[]
        for kinds,permissions in [(['asset_category','category'],['asset_categories.view','asset_categories.manage','categories.view','categories.manage']),
            (['software'],['software.view','software.manage']),(['team'],['teams.view','teams.manage']),(['department'],['departments.view','departments.manage']),
            (['location'],['locations.view','locations.manage']),(['user'],['users.view','users.manage'])]:
            if any(can(permission) for permission in permissions):other_types.extend(kinds)
        permitted_other=','.join("'"+kind+"'" for kind in other_types) or 'NULL'
        historical='1' if can('activity.view') else '0'
        self.prefix=f'''WITH assets AS (SELECT a.* FROM main.assets a WHERE {predicate}),
            devices AS (SELECT * FROM main.devices WHERE 0),
            tickets AS (SELECT t.* FROM main.tickets t WHERE {ticket_predicate}),
            roadmaps AS (SELECT * FROM main.roadmaps WHERE {roadmap}),
            roadmap_steps AS (SELECT * FROM main.roadmap_steps WHERE roadmap_id IN (SELECT id FROM roadmaps)),
            dependency_links AS (SELECT * FROM main.dependency_links WHERE id IN ({links})),
            activity_log AS (SELECT l.* FROM main.activity_log l WHERE {historical} AND (
                (l.entity_type IN ('asset','asset_entry') AND {asset_activity}) OR
                (l.entity_type='device' AND {device_activity}) OR
                (l.entity_type='ticket' AND l.entity_id IN (SELECT id FROM tickets)) OR
                (l.entity_type='roadmap' AND l.entity_id IN (SELECT id FROM roadmaps)) OR
                (l.entity_type='roadmap_step' AND l.entity_id IN (SELECT id FROM roadmap_steps)) OR
                (l.entity_type='dependency_link' AND l.entity_id IN (SELECT id FROM dependency_links)) OR
                l.entity_type IN ({permitted_other}) OR
                (l.entity_type NOT IN ('asset','asset_entry','device','ticket','roadmap','roadmap_step','dependency_link','asset_category','category','software','team','department','location','user') AND l.username=?)
            )) '''
        self.arguments.append(access['user']['username'])

    def execute(self,sql,parameters=()):
        if not sql.lstrip().upper().startswith('SELECT'):raise ValueError('TimelineReader erlaubt ausschließlich SELECT-Abfragen.')
        return self.db.execute(self.prefix+sql,[*self.arguments,*parameters])
