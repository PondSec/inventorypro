"""Catalog validation and transactional model/image management."""
from datetime import datetime, timezone
import re
import sqlite3
from urllib.parse import urlsplit

from .matching import compact, manufacturer_key, part_key, touch_catalog, valid_gtin


class CatalogError(ValueError):
    def __init__(self,message,status=400,fields=None):
        super().__init__(message);self.status=status;self.fields=fields or {}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def text(value,maximum,label,*,required=False):
    if value is None:value=''
    if not isinstance(value,str):raise CatalogError(f'{label}: Bitte Text eingeben.')
    value=re.sub(r'\s+',' ',value).strip()
    if len(value)>maximum or (required and not value):
        raise CatalogError(f'{label}: Bitte einen Wert mit höchstens {maximum} Zeichen eingeben.')
    return value


def source_url(value):
    value=str(value or '').strip()
    if not value:return ''
    if len(value)>2048 or any(ord(char)<32 for char in value):raise CatalogError('Ungültiger Quelllink.')
    try:
        parsed=urlsplit(value)
    except ValueError as error:raise CatalogError('Ungültiger Quelllink.') from error
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise CatalogError('Quelllinks müssen HTTPS verwenden und dürfen keine Zugangsdaten enthalten.')
    return value


def model_values(payload):
    if not isinstance(payload,dict):raise CatalogError('Bitte gültige Modelldaten eingeben.')
    manufacturer=text(payload.get('manufacturer'),120,'Hersteller',required=True)
    name=text(payload.get('name'),240,'Modell',required=True)
    if not manufacturer_key(manufacturer) or not compact(name):raise CatalogError('Hersteller und Modell benötigen eine eindeutige Bezeichnung.')
    aliases=payload.get('aliases',[])
    if not isinstance(aliases,list) or len(aliases)>20 or any(not isinstance(alias,str) for alias in aliases):raise CatalogError('Höchstens 20 Modellbezeichnungen angeben.')
    identifiers=[('name',manufacturer_key(manufacturer),compact(name))]
    for alias in aliases:
        value=compact(text(alias,240,'Modellbezeichnung',required=True))
        if not value:raise CatalogError('Ungültige Modellbezeichnung.')
        identifiers.append(('name',manufacturer_key(manufacturer),value))
    for field,kind in [('mpn','mpn'),('modelIdentifier','model')]:
        value=text(payload.get(field),240,'Modellkennung')
        if value:identifiers.append((kind,manufacturer_key(manufacturer),part_key(value)))
    gtin=text(payload.get('gtin'),32,'GTIN')
    if gtin:
        normalized=valid_gtin(gtin)
        if normalized is None:raise CatalogError('Die GTIN/EAN hat keine gültige Länge oder Prüfziffer.',fields={'gtin':'Bitte eine gültige GTIN/EAN als Text eingeben.'})
        identifiers.append(('gtin','',normalized))
    return {'manufacturer':manufacturer,'manufacturer_key':manufacturer_key(manufacturer),'name':name,'model_key':compact(name),
            'category':text(payload.get('category'),120,'Kategorie'),'source_url':source_url(payload.get('source_url')),
            'identifiers':list(dict.fromkeys(identifiers))}


def get_model(db,model_id):
    row=db.execute('SELECT * FROM product_models WHERE id=?',(model_id,)).fetchone()
    if row is None:raise CatalogError('Produktmodell nicht gefunden.',404)
    model=dict(row)
    model['identifiers']=[dict(item) for item in db.execute('SELECT kind,value,auto_match FROM product_identifiers WHERE product_id=? ORDER BY kind,id',(model_id,))]
    model['images']=[dict(item) for item in db.execute('''SELECT pi.*,mf.width,mf.height,mf.size_bytes FROM product_images pi
        JOIN product_media_files mf ON mf.hash=pi.media_hash WHERE pi.product_id=? ORDER BY pi.position,pi.id''',(model_id,))]
    for image in model['images']:
        image['url']=f"/media/catalog/{model_id}/{image['media_hash']}/thumb"
        image['large_url']=f"/media/catalog/{model_id}/{image['media_hash']}/large"
    return model


def list_models(db,query='',page=1,per_page=24):
    query=str(query or '').strip()[:240]
    page=max(1,int(page));per_page=min(100,max(1,int(per_page)))
    escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    where=" WHERE (manufacturer||' '||name||' '||category) LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM product_identifiers pi WHERE pi.product_id=product_models.id AND pi.value LIKE ? ESCAPE '\\')" if query else ''
    args=['%'+escaped+'%']*2 if query else []
    total=db.execute('SELECT count(*) FROM product_models'+where,args).fetchone()[0]
    pages=max(1,(total+per_page-1)//per_page);page=min(page,pages)
    ids=[row[0] for row in db.execute('SELECT id FROM product_models'+where+' ORDER BY manufacturer,name,id LIMIT ? OFFSET ?',[*args,per_page,(page-1)*per_page])]
    return {'models':[get_model(db,identifier) for identifier in ids],'total':total,'page':page,'pages':pages,'per_page':per_page,'q':query}


def _identifiers(db,model_id,values):
    db.execute('DELETE FROM product_identifiers WHERE product_id=?',(model_id,))
    db.executemany('INSERT INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,?,?,?)',[(model_id,*item) for item in values])


def create_model(db,payload,*,user_id=None,source_kind='manual',source_ref=''):
    values=model_values(payload);now=timestamp()
    try:
        model=db.execute('''INSERT INTO product_models(manufacturer,manufacturer_key,name,model_key,category,
            source_kind,source_ref,source_url,created_by_user_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (values['manufacturer'],values['manufacturer_key'],values['name'],values['model_key'],values['category'],source_kind,source_ref,values['source_url'],user_id,now,now)).lastrowid
    except sqlite3.IntegrityError as error:raise CatalogError('Dieses Hersteller-/Modellpaar ist bereits im Katalog vorhanden.',409) from error
    _identifiers(db,model,values['identifiers']);touch_catalog(db,user_id)
    return get_model(db,model)


def check_version(model,expected):
    if not expected or expected!=model['updated_at']:
        raise CatalogError('Das Produkt wurde inzwischen geändert. Bitte neu laden und die Änderungen prüfen.',409)


def _claim_model_version(db,model_id,expected,user_id):
    changed=db.execute('UPDATE product_models SET updated_at=? WHERE id=? AND updated_at=?',(timestamp(),model_id,expected))
    if changed.rowcount!=1:raise CatalogError('Das Produkt wurde inzwischen geändert. Bitte neu laden.',409)
    touch_catalog(db,user_id)


def update_model(db,model_id,payload,*,user_id=None):
    if not isinstance(payload,dict):raise CatalogError('Bitte gültige Modelldaten eingeben.')
    model=get_model(db,model_id);check_version(model,payload.get('expectedUpdatedAt'))
    values=model_values(payload)
    _claim_model_version(db,model_id,payload['expectedUpdatedAt'],user_id)
    try:
        db.execute('''UPDATE product_models SET manufacturer=?,manufacturer_key=?,name=?,model_key=?,category=?,
            source_url=?,source_kind='manual' WHERE id=?''',(values['manufacturer'],values['manufacturer_key'],values['name'],values['model_key'],values['category'],values['source_url'],model_id))
    except sqlite3.IntegrityError as error:raise CatalogError('Dieses Hersteller-/Modellpaar ist bereits vorhanden.',409) from error
    _identifiers(db,model_id,values['identifiers'])
    return get_model(db,model_id)


def delete_model(db,model_id,expected,*,user_id=None):
    model=get_model(db,model_id);check_version(model,expected)
    deleted=db.execute('DELETE FROM product_models WHERE id=? AND updated_at=?',(model_id,expected))
    if deleted.rowcount!=1:raise CatalogError('Das Produkt wurde inzwischen geändert. Bitte neu laden.',409)
    touch_catalog(db,user_id)


def image_metadata(payload,username):
    if not isinstance(payload,dict):raise CatalogError('Bitte gültige Bilddaten eingeben.')
    confirmed=payload.get('rightsConfirmed')
    if not (confirmed is True or (isinstance(confirmed,str) and confirmed in {'true','1','on'})):
        raise CatalogError('Bitte bestätigen, dass dieses Bild verwendet werden darf.',fields={'rightsConfirmed':'Nutzungsrecht bestätigen.'})
    license_code=text(payload.get('license_code') or 'LicenseRef-UserProvided',80,'Nutzungsrecht',required=True)
    attribution=text(payload.get('attribution') or username,2000,'Attribution',required=True)
    return {'source_kind':'manual','source_ref':'manual-upload','source_url':source_url(payload.get('source_url')),
            'license_code':license_code,'attribution':attribution,'changes':'Sicher neu kodiert und skaliert; Metadaten entfernt.'}


def add_model_image(db,model_id,media,metadata,expected,*,user_id=None):
    model=get_model(db,model_id);check_version(model,expected)
    _claim_model_version(db,model_id,expected,user_id)
    position=len(model['images'])
    db.execute('''INSERT OR IGNORE INTO product_images(product_id,media_hash,position,source_kind,source_ref,source_url,
        license_code,attribution,changes,reviewed_by_user_id,reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (model_id,media['hash'],position,metadata['source_kind'],metadata['source_ref'],metadata['source_url'],metadata['license_code'],metadata['attribution'],metadata['changes'],user_id,timestamp()))
    return get_model(db,model_id)


def update_model_image(db,model_id,image_id,expected,*,remove=False,user_id=None):
    model=get_model(db,model_id);check_version(model,expected)
    if not any(image['id']==image_id for image in model['images']):raise CatalogError('Produktbild nicht gefunden.',404)
    _claim_model_version(db,model_id,expected,user_id)
    if remove:db.execute('DELETE FROM product_images WHERE id=? AND product_id=?',(image_id,model_id))
    else:
        db.execute('UPDATE product_images SET position=position+1 WHERE product_id=?',(model_id,))
        db.execute('UPDATE product_images SET position=0 WHERE id=? AND product_id=?',(image_id,model_id))
    return get_model(db,model_id)
