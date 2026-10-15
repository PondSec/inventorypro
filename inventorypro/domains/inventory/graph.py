"""Normalize historical device nodes without rewriting stored dependency links."""
from .assets import scope_predicate


class CanonicalGraph:
    def __init__(self,db,can,access,ticket_visible):
        self.db=db
        predicate,arguments=scope_predicate(can)
        self.assets={row[0] for row in db.execute('SELECT a.id FROM assets a WHERE '+predicate,arguments)}
        self.legacy=dict(db.execute('SELECT device_id,asset_id FROM asset_legacy_devices'))
        self.tickets={row['id'] for row in db.execute('SELECT * FROM tickets') if ticket_visible(dict(row),access)}

    def node(self,kind,identifier):
        if kind=='device':kind='asset';identifier=self.legacy.get(identifier)
        if kind=='asset' and identifier not in self.assets or kind=='ticket' and identifier not in self.tickets:return None
        return kind,identifier

    def edge(self,row):
        source=self.node(row['source_type'],row['source_id']);target=self.node(row['target_type'],row['target_id'])
        if not source or not target:return None
        return {**dict(row),'source_type':source[0],'source_id':source[1],'target_type':target[0],'target_id':target[1]}

    def implicit_edges(self):
        result=[]
        def add(source,target,relation,**extra):
            value=self.edge(dict(source_type=source[0],source_id=source[1],target_type=target[0],target_id=target[1],
                relation=relation,criticality='medium',redundancy_group=None,notes=None,implicit=True,**extra))
            if value:result.append(value)
        for row in self.db.execute('SELECT * FROM asset_components'):
            add(('asset',row['parent_asset_id']),('asset',row['child_asset_id']),'contains',quantity=row['quantity'])
        for row in self.db.execute('SELECT id,location_id FROM assets WHERE location_id IS NOT NULL'):
            add(('asset',row['id']),('location',row['location_id']),'located_at')
        for row in self.db.execute('''SELECT ah.* FROM asset_assignment_history ah WHERE ah.id=(
            SELECT latest.id FROM asset_assignment_history latest WHERE latest.asset_id=ah.asset_id ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1)
            AND ah.status IN ('assigned','checked_out','transferred')'''):
            if row['assigned_to_user_id']:add(('asset',row['asset_id']),('user',row['assigned_to_user_id']),'assigned_to')
            if row['assigned_to_team_id']:add(('asset',row['asset_id']),('team',row['assigned_to_team_id']),'assigned_to')
        return result
