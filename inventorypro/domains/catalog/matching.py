"""Conservative offline model matching; fuzzy names are suggestions only."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import unicodedata

from inventorypro.domains.inventory.objects import specs_object

TABLES = {'device':('devices','device_product_media','device_id'),
          'asset':('assets','asset_product_media','asset_id')}


def compact(value):
    return ''.join(character for character in unicodedata.normalize('NFKC',str(value or '')).casefold() if character.isalnum())


def manufacturer_key(value):
    key = compact(value)
    return {'appleinc':'apple','dellinc':'dell','hpinc':'hp','hewlettpackard':'hp','raspberrypifoundation':'raspberrypi'}.get(key,key)


def part_key(value):
    # Punctuation is significant in part numbers: AB-12 must not become AB12.
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value or '')).casefold())[:240]


def valid_gtin(value):
    code = re.sub(r'[\s-]','',str(value or ''))
    if not code.isascii() or not code.isdigit() or len(code) not in {8,12,13,14}:
        return None
    total = sum(int(digit)*(3 if index%2==0 else 1) for index,digit in enumerate(reversed(code[:-1])))
    return code if (10-total%10)%10==int(code[-1]) else None


def identity_from_specs(specs):
    source = {compact(key):value for key,value in specs_object(specs).items()}
    def pick(*keys):
        return next((str(source[key]).strip()[:240] for key in keys if isinstance(source.get(key),(str,int,float)) and not isinstance(source.get(key),bool) and str(source[key]).strip()),'')
    # Never infer product identifiers from serial, asset tag, owner or location.
    return {'manufacturer':pick('hersteller','manufacturer','brand','marke'),
            'model':pick('modell','model','produktmodell'),
            'model_code':pick('modellkennung','modelidentifier','modelid','modellnummer','modelnumber'),
            'mpn':pick('mpn','herstellernummer','herstellerteilenummer','partnumber'),
            'gtin':pick('gtin','ean','ean13')}


def _name_without_inventory_suffix(name):
    value = str(name or '').strip()[:500]
    parts = re.split(r'\s*[·|]\s*',value,maxsplit=1)
    if len(parts)==2 and re.fullmatch(r'(?:[A-Za-z]{0,8}-?)?\d{1,10}',parts[1]):
        return parts[0]
    return value


def exact_match(db,identity,name=''):
    maker = manufacturer_key(identity.get('manufacturer'))
    hits = {}
    conflict = False
    def collect(kind,value,scope,method):
        nonlocal conflict
        if not value:return
        for row in db.execute('''SELECT pi.product_id,pm.manufacturer_key FROM product_identifiers pi
                JOIN product_models pm ON pm.id=pi.product_id
                WHERE pi.kind=? AND pi.manufacturer_key=? AND pi.value=? AND pi.auto_match=1''',(kind,scope,value)):
            if maker and row['manufacturer_key']!=maker:
                conflict = True
            else:
                hits.setdefault(row['product_id'],method)
    collect('gtin',valid_gtin(identity.get('gtin')),'','gtin')
    if maker:
        collect('mpn',part_key(identity.get('mpn')),maker,'mpn')
        collect('model',part_key(identity.get('model_code')),maker,'model')
        collect('name',compact(identity.get('model')),maker,'model')
    # A complete reviewed model name may identify the model offline. Partial
    # names, owner suffixes and generic names never get an automatic photo.
    candidate_name = compact(identity.get('model') or ('' if identity.get('model_code') else _name_without_inventory_suffix(name)))
    if len(candidate_name)>=12 and any(character.isdigit() for character in candidate_name):
        for row in db.execute('''SELECT pi.product_id,pm.manufacturer_key FROM product_identifiers pi
            JOIN product_models pm ON pm.id=pi.product_id
            WHERE pi.kind='name' AND pi.value=? AND pi.auto_match=1''',(candidate_name,)):
            if maker and maker!=row['manufacturer_key']:
                conflict = True
            else:
                hits.setdefault(row['product_id'],'model' if identity.get('model') else 'name_exact')
    if conflict or len(hits)>1:
        return {'product_id':None,'method':'none','reason':'conflict','candidates':sorted(hits)}
    if hits:
        product,method = next(iter(hits.items()))
        return {'product_id':product,'method':method,'reason':'exact','candidates':[product]}
    return {'product_id':None,'method':'none','reason':'no_match','candidates':[]}


def suggest_models(db,identity,name='',limit=8):
    maker = manufacturer_key(identity.get('manufacturer'))
    query = compact(identity.get('model') or _name_without_inventory_suffix(name))
    if len(query)<4:return []
    prefix = query[:min(10,len(query))]
    sql = 'SELECT id,manufacturer,name,category FROM product_models WHERE model_key LIKE ?'
    args = [prefix+'%']
    if maker:sql+=' AND manufacturer_key=?';args.append(maker)
    return [dict(row) for row in db.execute(sql+' ORDER BY manufacturer,name LIMIT ?',[*args,min(20,max(1,limit))])]


def revision(db):
    return db.execute('SELECT updated_at FROM product_catalog_settings WHERE id=1').fetchone()[0]


def touch_catalog(db,user_id=None):
    db.execute('UPDATE product_catalog_settings SET updated_at=?,updated_by_user_id=? WHERE id=1',
               (datetime.now(timezone.utc).isoformat(timespec='microseconds'),user_id))


def sync_object(db,kind,object_id,*,force=False,catalog_revision=None,row=None):
    if kind not in TABLES:raise ValueError('Ungültiger Inventartyp.')
    table,links,key = TABLES[kind]
    source = row if row is not None else db.execute(f'SELECT id,name,specs FROM {table} WHERE id=?',(object_id,)).fetchone()
    if source is None:return {'product_id':None,'method':'none','reason':'missing','changed':False}
    previous = db.execute(f'SELECT * FROM {links} WHERE {key}=?',(object_id,)).fetchone()
    if previous and (previous['match_method']=='manual' or previous['suppress_image']):
        return {'product_id':previous['product_id'],'method':previous['match_method'],'reason':'manual','changed':False}
    if not force and not db.execute('SELECT local_auto_match FROM product_catalog_settings WHERE id=1').fetchone()[0]:
        return {'product_id':previous['product_id'] if previous else None,'method':'none','reason':'disabled','changed':False}
    identity = identity_from_specs(source['specs'])
    fingerprint = sha256(json.dumps([catalog_revision or revision(db),identity,source['name']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if previous and previous['fingerprint']==fingerprint and not force:
        return {'product_id':previous['product_id'],'method':previous['match_method'],'reason':'cached','changed':False}
    match = exact_match(db,identity,source['name'])
    db.execute(f'''INSERT INTO {links}({key},product_id,match_method,fingerprint) VALUES (?,?,?,?)
        ON CONFLICT({key}) DO UPDATE SET product_id=excluded.product_id,match_method=excluded.match_method,
        fingerprint=excluded.fingerprint,updated_at=CURRENT_TIMESTAMP''',(object_id,match['product_id'],match['method'],fingerprint))
    return {**match,'changed':True}


def sync_inventory(db,*,limit=None,after=None):
    """Local-only reconciliation; caller owns transaction/progress and permissions."""
    version = revision(db);result={'processed':0,'matched':0,'changed':0,'last':dict(after or {})}
    for kind,(table,_,_) in TABLES.items():
        sql = f'SELECT id,name,specs FROM {table} WHERE id>? ORDER BY id'
        arguments = [(after or {}).get(kind,0)]
        if limit is not None:sql+=' LIMIT ?';arguments.append(min(250,max(1,int(limit))))
        for row in db.execute(sql,arguments):
            match = sync_object(db,kind,row['id'],catalog_revision=version,row=row)
            result['processed']+=1;result['matched']+=bool(match['product_id']);result['changed']+=match['changed']
            result['last'][kind] = row['id']
    return result
