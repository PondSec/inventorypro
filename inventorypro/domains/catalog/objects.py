"""Object-bound image resolution and explicit, versioned image choices."""
from .matching import TABLES, identity_from_specs, suggest_models, sync_object
from .media import media_path
from .service import CatalogError, get_model, timestamp


def object_row(db,kind,identifier):
    if kind not in TABLES:raise CatalogError('Inventartyp nicht gefunden.',404)
    table,_,_=TABLES[kind]
    row=db.execute(f'SELECT id,name,specs FROM {table} WHERE id=?',(identifier,)).fetchone()
    if row is None:raise CatalogError('Inventareintrag nicht gefunden.',404)
    return row


def resolution_source(kind):
    _,table,key=TABLES[kind]
    return f'''SELECT o.*,pm.name AS product_name,pm.manufacturer,
        pi.media_hash AS catalog_hash,pi.source_url AS catalog_source_url,pi.license_code AS catalog_license_code,
        pi.attribution AS catalog_attribution,pi.changes AS catalog_changes FROM {table} o
        LEFT JOIN product_models pm ON pm.id=o.product_id
        LEFT JOIN product_images pi ON pi.id=(SELECT id FROM product_images WHERE product_id=o.product_id ORDER BY position,id LIMIT 1)
        '''


def resolve(db,uploads,kind,identifier,*,row=None):
    _,_,key=TABLES[kind]
    if row is None:row=db.execute(resolution_source(kind)+f' WHERE o.{key}=?',(identifier,)).fetchone()
    state=dict(row) if row else {'product_id':None,'updated_at':'','suppress_image':0,'override_hash':None,'match_method':'none'}
    own=bool(state.get('override_hash'))
    digest=None if state['suppress_image'] else state.get('override_hash') or state.get('catalog_hash')
    # Missing media are a normal fallback state, never a broken <img>.
    if digest:
        try:
            if not media_path(uploads,digest,'thumb').is_file():digest=None
        except (OSError,ValueError):digest=None
    prefix='override' if own else 'catalog'
    return {'product_id':state['product_id'],'product_name':state.get('product_name') or '',
            'manufacturer':state.get('manufacturer') or '', 'updated_at':state['updated_at'],
            'match_method':state['match_method'],'suppressed':bool(state['suppress_image']),
            'has_override':own,'hash':digest,'source':'individual' if own and digest else 'catalog' if digest else 'fallback',
            'url':f'/media/inventory/{kind}/{identifier}/{digest}/thumb' if digest else '',
            'large_url':f'/media/inventory/{kind}/{identifier}/{digest}/large' if digest else '',
            'source_url':state.get(prefix+'_source_url') or '', 'license_code':state.get(prefix+'_license_code') or '',
            'attribution':state.get(prefix+'_attribution') or '', 'changes':state.get(prefix+'_changes') or ''}


def resolve_many(db,uploads,rows):
    result={}
    for kind,(_,_,key) in TABLES.items():
        identifiers=[row['id'] for row in rows if row['kind']==kind]
        if not identifiers:continue
        placeholders=','.join('?' for _ in identifiers)
        found={row[key]:row for row in db.execute(resolution_source(kind)+f' WHERE o.{key} IN ({placeholders})',identifiers)}
        for identifier in identifiers:result[(kind,identifier)]=resolve(db,uploads,kind,identifier,row=found.get(identifier,{}))
    return result


def choices(db,uploads,kind,identifier):
    row=object_row(db,kind,identifier)
    state=resolve(db,uploads,kind,identifier)
    return {**state,'kind':kind,'object_id':identifier,'name':row['name'],
            'suggestions':suggest_models(db,identity_from_specs(row['specs']),row['name'])}


def change(db,kind,identifier,payload,*,user_id=None,media=None,metadata=None):
    object_row(db,kind,identifier)
    if not isinstance(payload,dict):raise CatalogError('Bitte gültige Bilddaten eingeben.')
    action=payload.get('action')
    if action not in {'assign','automatic','hide','show','remove_override','upload','unlink'}:raise CatalogError('Ungültige Bildaktion.')
    _,table,key=TABLES[kind]
    previous=db.execute(f'SELECT * FROM {table} WHERE {key}=?',(identifier,)).fetchone()
    expected=payload.get('expectedUpdatedAt')
    if not isinstance(expected,str) or expected!=(previous['updated_at'] if previous else ''):
        raise CatalogError('Die Bildzuordnung wurde inzwischen geändert. Bitte neu laden.',409)
    values={}
    if action=='assign':
        product_id=payload.get('product_id')
        if not isinstance(product_id,int) or isinstance(product_id,bool) or product_id<1:raise CatalogError('Bitte ein Produktmodell auswählen.')
        get_model(db,product_id)
        values.update(product_id=product_id,match_method='manual',confirmed_by_user_id=user_id,suppress_image=0)
    elif action=='unlink':values.update(product_id=None,match_method='manual',confirmed_by_user_id=user_id)
    elif action=='hide':values.update(suppress_image=1)
    elif action=='show':values.update(suppress_image=0)
    elif action=='automatic':values.update(match_method='none',fingerprint='',suppress_image=0,confirmed_by_user_id=None)
    elif action=='remove_override':values.update(override_hash=None,override_source_url='',override_license_code='',override_attribution='',override_reviewed_at=None,override_reviewed_by_user_id=None)
    elif action=='upload':
        if not media or not metadata:raise CatalogError('Bitte eine Bilddatei mit Nutzungsrecht auswählen.')
        values.update(override_hash=media['hash'],override_source_url=metadata['source_url'],override_license_code=metadata['license_code'],
            override_attribution=metadata['attribution'],override_reviewed_at=timestamp(),override_reviewed_by_user_id=user_id,suppress_image=0)
    values['updated_at']=timestamp()
    if previous:
        changed=db.execute(f"UPDATE {table} SET "+','.join(f'{field}=?' for field in values)+f' WHERE {key}=? AND updated_at=?',[*values.values(),identifier,expected]).rowcount
    else:
        changed=db.execute(f"INSERT INTO {table} ({key},"+','.join(values)+') VALUES ('+','.join('?' for _ in range(len(values)+1))+f') ON CONFLICT({key}) DO NOTHING',[identifier,*values.values()]).rowcount
    if changed!=1:raise CatalogError('Die Bildzuordnung wurde inzwischen geändert. Bitte neu laden.',409)
    if action=='automatic':return sync_object(db,kind,identifier,force=True)
    return values
