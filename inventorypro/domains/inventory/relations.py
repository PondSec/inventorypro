"""Explicit asset relations retain direction and each object's access boundary."""
from . import assets


def add_relations(db,can,identifier,payload):
    with assets.mutation(db):
        assets.require(db,can,identifier,write=True)
        assets._check_revision(db,identifier,payload.get('expectedRevision'))
        targets=payload.get('targets')
        if not isinstance(targets,list) or not 1<=len(targets)<=100:raise assets.AssetError('Bitte zwischen 1 und 100 Assets auswählen.')
        if any(isinstance(value,bool) or not isinstance(value,int) or value<=0 or value>9223372036854775807 for value in targets) or len(set(targets))!=len(targets):raise assets.AssetError('Bitte eindeutige gültige Assets auswählen.')
        kind=assets._foreign(db,payload.get('relation_type_id'),'asset_relation_types','Beziehungstyp')
        for target in targets:
            if target==identifier:raise assets.AssetError('Ein Asset kann keine Beziehung zu sich selbst erhalten.')
            assets.require(db,can,target)
        for target in targets:
            if not db.execute('SELECT 1 FROM asset_relations WHERE asset_id=? AND related_asset_id=? AND relation_type_id IS ?',(identifier,target,kind)).fetchone():
                db.execute('INSERT INTO asset_relations(asset_id,related_asset_id,relation_type_id) VALUES (?,?,?)',(identifier,target,kind))
        db.execute('UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id=?',(identifier,))


def remove_relation(db,can,identifier,relation_id,expected):
    with assets.mutation(db):
        assets.require(db,can,identifier,write=True)
        assets._check_revision(db,identifier,expected)
        row=db.execute('SELECT * FROM asset_relations WHERE id=? AND (asset_id=? OR related_asset_id=?)',(relation_id,identifier,identifier)).fetchone()
        if not row:raise assets.AssetError('Die Beziehung existiert nicht mehr.',404)
        assets.require(db,can,row['asset_id'],write=True)
        assets.require(db,can,row['related_asset_id'])
        db.execute('DELETE FROM asset_relations WHERE id=?',(relation_id,))
        db.execute('UPDATE asset_edit_versions SET revision=revision+1 WHERE asset_id IN (?,?)',(identifier,row['asset_id']))
