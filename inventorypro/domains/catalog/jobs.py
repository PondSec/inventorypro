"""Persistent opt-in lookups, leased across workers; no network in list requests."""
from hashlib import sha256
from io import BytesIO
import json
import sqlite3
import threading
import time
import uuid

from . import commons, service
from .matching import TABLES, identity_from_specs, sync_object, compact, manufacturer_key
from .media import store_image, MAX_UPLOAD_BYTES
from .network import fetch, IMAGE_HOSTS, ProviderError

_WORKERS=set()
_WORKER_LOCK=threading.Lock()


def settings(db):
    return dict(db.execute('SELECT external_enabled,rights_reviewed,provider,external_revision AS updated_at FROM product_catalog_settings WHERE id=1').fetchone())


def enabled(db):
    policy=settings(db)
    return bool(policy['external_enabled'] and policy['rights_reviewed'])


def update_settings(db,payload,*,user_id=None):
    policy=settings(db)
    if payload.get('expectedUpdatedAt')!=policy['updated_at']:raise service.CatalogError('Die Bildquellen-Einstellung wurde inzwischen geändert. Bitte neu laden.',409)
    value=payload.get('enabled');reviewed=payload.get('rightsReviewed')
    if not isinstance(value,bool) or not isinstance(reviewed,bool):raise service.CatalogError('Bitte eine gültige Bildquellen-Einstellung angeben.')
    if value and not reviewed:raise service.CatalogError('Bitte die Übertragung öffentlicher Produktdaten und die Bildlizenzen bestätigen.')
    db.execute('UPDATE product_catalog_settings SET external_enabled=?,rights_reviewed=?,updated_by_user_id=?,external_revision=?,updated_at=? WHERE id=1',
        (int(value),int(reviewed),user_id,service.timestamp(),service.timestamp()))
    return settings(db)


def identity_key(identity):
    return sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def enqueue(db,kind,object_id,identity):
    if not enabled(db):return None
    identity=commons.public_identity(identity)
    if not identity:return None
    fingerprint=identity_key(identity);now=int(time.time())
    db.execute('''INSERT INTO product_lookup_jobs(fingerprint,identity_json) VALUES (?,?)
        ON CONFLICT(fingerprint) DO UPDATE SET status='queued',message='',updated_at=CURRENT_TIMESTAMP
        WHERE product_lookup_jobs.status NOT IN ('queued','running') AND product_lookup_jobs.retry_at<=?''',
        (fingerprint,json.dumps(identity,ensure_ascii=False),now))
    job=db.execute('SELECT id FROM product_lookup_jobs WHERE fingerprint=?',(fingerprint,)).fetchone()[0]
    db.execute('INSERT OR IGNORE INTO product_lookup_targets(job_id,kind,object_id) VALUES (?,?,?)',(job,kind,object_id))
    return job


def enqueue_inventory(db,*,after=None,limit=100):
    if not enabled(db):raise service.CatalogError('Die öffentliche Bildquelle ist deaktiviert.',409)
    result={'processed':0,'queued':0,'last':dict(after or {})}
    from inventorypro.domains.inventory.assets import unified
    is_unified=unified(db)
    for kind,(table,links,key) in TABLES.items():
        if is_unified and kind=='device':continue
        rows=db.execute(f'''SELECT a.id,a.specs FROM {table} a LEFT JOIN {links} p ON p.{key}=a.id
            WHERE a.id>? AND coalesce(p.suppress_image,0)=0 AND p.override_hash IS NULL
            AND coalesce(p.match_method,'none')<>'manual' AND NOT EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id=p.product_id) ORDER BY a.id LIMIT ?''',((after or {}).get(kind,0),min(250,max(1,limit)))).fetchall()
        for row in rows:
            result['processed']+=1;result['last'][kind]=row['id']
            result['queued']+=bool(enqueue(db,kind,row['id'],identity_from_specs(row['specs'])))
    return result


def status(db):
    counts={row['status']:row['total'] for row in db.execute('SELECT status,count(*) total FROM product_lookup_jobs GROUP BY status')}
    recent=[dict(row) for row in db.execute('SELECT id,identity_json,status,message,result_json,updated_at FROM product_lookup_jobs ORDER BY id DESC LIMIT 12')]
    for job in recent:
        job['identity']=json.loads(job.pop('identity_json'));job['result']=json.loads(job.pop('result_json'))
    return {'settings':settings(db),'counts':counts,'recent':recent}


def claim(db):
    """A short write transaction; caller never holds it over external I/O."""
    if db.in_transaction:raise RuntimeError('Lookup workers require a committed connection.')
    db.execute('BEGIN IMMEDIATE')
    try:
        if not enabled(db):db.rollback();return None
        now=int(time.time())
        row=db.execute('''SELECT * FROM product_lookup_jobs WHERE (status='queued' AND retry_at<=?)
            OR (status='running' AND lease_until<?) ORDER BY id LIMIT 1''',(now,now)).fetchone()
        if not row:db.rollback();return None
        token=uuid.uuid4().hex
        db.execute("UPDATE product_lookup_jobs SET status='running',lease_token=?,lease_until=?,attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(token,now+300,row['id']))
        revision=settings(db)['updated_at'];db.commit()
        return {**dict(row),'lease_token':token,'policy_revision':revision}
    except BaseException:db.rollback();raise


def _current(db,job):
    policy=settings(db)
    row=db.execute('SELECT lease_token FROM product_lookup_jobs WHERE id=?',(job['id'],)).fetchone()
    return bool(row and row[0]==job['lease_token'] and policy['external_enabled'] and policy['rights_reviewed'] and policy['updated_at']==job['policy_revision'])


def _finish(db,job,state,*,result=None,message='',retry_delay=7*86400):
    db.execute('''UPDATE product_lookup_jobs SET status=?,lease_token='',lease_until=0,retry_at=?,result_json=?,message=?,updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND lease_token=?''',(state,int(time.time())+retry_delay,json.dumps(result or {},ensure_ascii=False),str(message)[:500],job['id'],job['lease_token']))


def _import(db,uploads_dir,job,result,data,mime):
    identity=result['identity']
    existing=db.execute('SELECT id FROM product_models WHERE manufacturer_key=? AND model_key=?',
        (manufacturer_key(identity['manufacturer']),compact(identity['model'] or result['entity']['name']))).fetchone()
    model=service.get_model(db,existing[0]) if existing else service.create_model(db,{'manufacturer':identity['manufacturer'],
        'name':identity['model'] or result['entity']['name'],'gtin':result['entity'].get('verified_gtin',''),
        'source_url':result['entity']['source_url']},source_kind='wikidata',source_ref=result['entity']['source_ref'])
    verified_gtin=result['entity'].get('verified_gtin')
    if verified_gtin and verified_gtin==identity.get('gtin') and not any(item['kind']=='gtin' and item['value']==verified_gtin for item in model['identifiers']):
        db.execute("INSERT OR IGNORE INTO product_identifiers(product_id,kind,manufacturer_key,value) VALUES (?,'gtin','',?)",(model['id'],verified_gtin))
    if not model['images']:
        media=store_image(db,uploads_dir,BytesIO(data),mime_type=mime)
        model=service.add_model_image(db,model['id'],media,result['image'],model['updated_at'])
    for target in db.execute('SELECT kind,object_id FROM product_lookup_targets WHERE job_id=?',(job['id'],)).fetchall():
        table,_,_=TABLES[target['kind']]
        row=db.execute(f'SELECT specs FROM {table} WHERE id=?',(target['object_id'],)).fetchone()
        # Never attach an answer to an object edited/deleted during the lookup.
        if row and commons.public_identity(identity_from_specs(row['specs']))==identity:
            sync_object(db,target['kind'],target['object_id'],force=True,external=False)
    return model['id']


def process_next(db,uploads_dir):
    job=claim(db)
    if not job:return False
    try:
        result=commons.lookup(json.loads(job['identity_json']))
        data=mime=None
        if result['status']=='matched' and _current(db,job):
            data,mime=fetch(result['image']['image_url'],allowed=IMAGE_HOSTS,maximum=MAX_UPLOAD_BYTES)
        db.execute('BEGIN IMMEDIATE')
        if not _current(db,job):
            _finish(db,job,'queued',retry_delay=0);db.commit();return True
        if result['status']=='matched':
            if data is None:raise ProviderError('Die Bildquelle wurde während des Abrufs geändert. Bitte erneut versuchen.')
            model_id=_import(db,uploads_dir,job,result,data,mime)
            _finish(db,job,'matched',result={'product_id':model_id,'source':result['entity']['source_url']},retry_delay=30*86400)
        else:_finish(db,job,result['status'],result={'candidates':result.get('candidates',[])})
        db.commit()
    except Exception as error:
        db.rollback()
        # Safe user-facing errors only; no exception/URL payload from providers.
        message=str(error) if isinstance(error,(ProviderError,service.CatalogError)) else 'Das Produktbild konnte nicht übernommen werden. Bitte später erneut versuchen.'
        _finish(db,job,'error',message=message,retry_delay=1800);db.commit()
    return True


def start_worker(app,get_db,uploads_dir):
    """A bounded daemon; leases survive process exit and are reclaimed on use."""
    if app.config.get('TESTING') or not app.config.get('CATALOG_BACKGROUND_ENABLED',True):return
    db=get_db()
    if not enabled(db):return
    database=db.execute('PRAGMA database_list').fetchone()[2]
    with _WORKER_LOCK:
        if database in _WORKERS:return
        _WORKERS.add(database)
    def work():
        try:
            with app.app_context():
                connection=get_db()
                for _ in range(50):
                    if not process_next(connection,uploads_dir):break
        except (sqlite3.Error,OSError):app.logger.warning('Produktbild-Abgleich wird beim nächsten Zugriff fortgesetzt.')
        finally:
            with _WORKER_LOCK:_WORKERS.discard(database)
    thread=threading.Thread(target=work,name='product-image-lookup',daemon=True)
    try:thread.start()
    except BaseException:
        with _WORKER_LOCK:_WORKERS.discard(database)
        raise
