"""Authenticated catalog and object-photo APIs; files never expose arbitrary hashes."""
from flask import Blueprint, abort, jsonify, request, send_file, session, render_template, current_app
from werkzeug.exceptions import RequestEntityTooLarge
from . import service, jobs
from .matching import sync_inventory
from .media import MediaError, open_media, store_image
from .objects import choices, change, object_row, resolve


def build_catalog_blueprint(*,get_db,get_access,user_can,login_required,get_uploads_dir,rate_limiter,log_activity):
    bp=Blueprint('product_catalog',__name__)
    def readable(kind):
        prefix={'device':'devices','asset':'assets'}.get(kind)
        if prefix is None:abort(404)
        return user_can(prefix+'.view') or user_can(prefix+'.manage')
    def require_catalog(manage=False):
        if not user_can('server_settings.manage') and (manage or not (readable('device') or readable('asset'))):abort(403)
    def require_object(kind,identifier,manage=False):
        if kind=='asset':
            from inventorypro.domains.inventory import assets
            if assets.unified(get_db()):
                try:assets.require(get_db(),user_can,identifier,write=manage)
                except assets.AssetError as error:raise service.CatalogError(str(error),error.status) from error
                return object_row(get_db(),kind,identifier)
        if not readable(kind) or (manage and not user_can(('devices' if kind=='device' else 'assets')+'.manage')):abort(403)
        return object_row(get_db(),kind,identifier)
    def user_id():return get_access(get_db())['user']['id']
    def limited(action,maximum=30):
        if rate_limiter.is_limited(f'catalog:{action}:{user_id()}',window_seconds=60,max_requests=maximum):
            abort(429,description='Zu viele Bildanfragen. Bitte in einer Minute erneut versuchen.')
    def payload():
        value=request.get_json(silent=True)
        if not isinstance(value,dict):raise service.CatalogError('Bitte gültige Daten eingeben.')
        return value
    def upload():
        file=request.files.get('image')
        if file is None:raise service.CatalogError('Bitte eine Bilddatei auswählen.')
        metadata=service.image_metadata(request.form.to_dict(),session.get('username',''))
        media=store_image(get_db(),get_uploads_dir(),file.stream,mime_type=file.mimetype,user_id=user_id())
        return media,metadata
    def commit(action,entity,identifier):
        log_activity(get_db(),action,entity,identifier)
        get_db().commit()
    @bp.errorhandler(service.CatalogError)
    def catalog_error(error):
        get_db().rollback();return jsonify(error=str(error),fields=error.fields),error.status
    @bp.errorhandler(MediaError)
    def media_error(error):
        get_db().rollback();return jsonify(error=str(error)),400
    @bp.errorhandler(RequestEntityTooLarge)
    def too_large(error):return jsonify(error='Bilder dürfen höchstens 8 MB groß sein.'),413
    @bp.errorhandler(429)
    def rate_error(error):
        response=jsonify(error=error.description);response.status_code=429;response.headers['Retry-After']='60';return response
    @bp.after_request
    def private(response):
        response.headers['Cache-Control']='private, no-cache, must-revalidate'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    def context():
        access=get_access(get_db())
        return dict(username=session.get('username'),permissions=sorted(access['permissions']),is_superuser=access['is_superuser'])
    @bp.before_request
    def canonical_photo_alias():
        values=request.view_args or {}
        if values.get('kind')=='device' and 'identifier' in values:
            from inventorypro.domains.inventory.assets import unified
            if unified(get_db()):
                mapped=get_db().execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=?',(values['identifier'],)).fetchone()
                if mapped:values['kind']='asset';values['identifier']=mapped[0]
    @bp.after_app_request
    def resume_public_lookups(response):
        if response.status_code<400 and (request.method in {'POST','PUT','PATCH'} or str(request.endpoint or '').startswith('product_catalog.')):
            jobs.start_worker(current_app._get_current_object(),get_db,get_uploads_dir())
        return response
    @bp.get('/api/catalog/external')
    @login_required
    def external_status():
        require_catalog(True);return jsonify(jobs.status(get_db()))
    @bp.put('/api/catalog/external')
    @login_required
    def external_settings():
        require_catalog(True);limited('write')
        result=jobs.update_settings(get_db(),payload(),user_id=user_id());commit('source_settings','product_catalog',1)
        return jsonify(result)
    @bp.post('/api/catalog/external/queue')
    @login_required
    def external_queue():
        require_catalog(True);limited('public_queue',30);data=payload();after=data.get('after',{})
        if not isinstance(after,dict) or any(kind not in {'device','asset'} or not isinstance(value,int) or isinstance(value,bool) or value<0 for kind,value in after.items()):
            raise service.CatalogError('Ungültiger Fortschrittsstand.')
        result=jobs.enqueue_inventory(get_db(),after=after);get_db().commit();return jsonify(result),202
    @bp.get('/inventory/catalog')
    @login_required
    def catalog_page():
        require_catalog()
        return render_template('product_catalog.html',catalog=service.list_models(get_db(),request.args.get('q',''),request.args.get('page',1,type=int)),can_manage=user_can('server_settings.manage'),external=jobs.status(get_db()) if user_can('server_settings.manage') else None,**context())
    @bp.get('/inventory/catalog/<int:identifier>')
    @login_required
    def catalog_detail(identifier):
        require_catalog()
        return render_template('product_model.html',model=service.get_model(get_db(),identifier),can_manage=user_can('server_settings.manage'),**context())
    @bp.get('/inventory/<kind>/<int:identifier>/photo')
    @login_required
    def object_photo_page(kind,identifier):
        require_object(kind,identifier,True)
        return render_template('object_photo.html',photo=choices(get_db(),get_uploads_dir(),kind,identifier),**context())
    @bp.get('/api/catalog/models')
    @login_required
    def models():
        require_catalog()
        return jsonify(service.list_models(get_db(),request.args.get('q',''),request.args.get('page',1,type=int),request.args.get('per_page',24,type=int)))
    @bp.get('/api/catalog/models/<int:identifier>')
    @login_required
    def model(identifier):
        require_catalog();return jsonify(service.get_model(get_db(),identifier))
    @bp.post('/api/catalog/models')
    @login_required
    def create():
        require_catalog(True);limited('write')
        result=service.create_model(get_db(),payload(),user_id=user_id());commit('create','product_model',result['id'])
        return jsonify(result),201
    @bp.put('/api/catalog/models/<int:identifier>')
    @login_required
    def update(identifier):
        require_catalog(True);limited('write')
        result=service.update_model(get_db(),identifier,payload(),user_id=user_id());commit('update','product_model',identifier)
        return jsonify(result)
    @bp.delete('/api/catalog/models/<int:identifier>')
    @login_required
    def delete(identifier):
        require_catalog(True);limited('write')
        service.delete_model(get_db(),identifier,payload().get('expectedUpdatedAt'),user_id=user_id());commit('delete','product_model',identifier)
        return jsonify(deleted=True)
    @bp.post('/api/catalog/models/<int:identifier>/images')
    @login_required
    def model_upload(identifier):
        require_catalog(True);limited('upload',12)
        service.check_version(service.get_model(get_db(),identifier),request.form.get('expectedUpdatedAt'))
        media,metadata=upload()
        result=service.add_model_image(get_db(),identifier,media,metadata,request.form.get('expectedUpdatedAt'),user_id=user_id())
        commit('image_upload','product_model',identifier);return jsonify(result),201
    @bp.post('/api/catalog/models/<int:identifier>/images/<int:image_id>')
    @login_required
    def model_image(identifier,image_id):
        require_catalog(True);limited('write');data=payload()
        if data.get('action') not in {'primary','remove'}:raise service.CatalogError('Ungültige Bildaktion.')
        result=service.update_model_image(get_db(),identifier,image_id,data.get('expectedUpdatedAt'),remove=data['action']=='remove',user_id=user_id())
        commit('image_'+data['action'],'product_model',identifier);return jsonify(result)
    @bp.post('/api/catalog/reconcile')
    @login_required
    def reconcile():
        require_catalog(True);limited('reconcile',30);data=payload();after=data.get('after',{})
        if not isinstance(after,dict) or any(kind not in {'device','asset'} or not isinstance(value,int) or isinstance(value,bool) or value<0 for kind,value in after.items()):
            raise service.CatalogError('Ungültiger Fortschrittsstand.')
        result=sync_inventory(get_db(),limit=100,after=after);get_db().commit();return jsonify(result)
    @bp.get('/api/inventory/<kind>/<int:identifier>/photo')
    @login_required
    def photo(kind,identifier):
        require_object(kind,identifier);return jsonify(choices(get_db(),get_uploads_dir(),kind,identifier))
    @bp.post('/api/inventory/<kind>/<int:identifier>/photo')
    @login_required
    def photo_change(kind,identifier):
        require_object(kind,identifier,True);limited('object')
        change(get_db(),kind,identifier,payload(),user_id=user_id());commit('image_choice',kind,identifier)
        return jsonify(choices(get_db(),get_uploads_dir(),kind,identifier))
    @bp.post('/api/inventory/<kind>/<int:identifier>/photo/upload')
    @login_required
    def photo_upload(kind,identifier):
        require_object(kind,identifier,True);limited('upload',12)
        # Validate stale versions before spending CPU on image decoding.
        current=resolve(get_db(),get_uploads_dir(),kind,identifier)
        if request.form.get('expectedUpdatedAt')!=current['updated_at']:raise service.CatalogError('Die Bildzuordnung wurde inzwischen geändert. Bitte neu laden.',409)
        media,metadata=upload()
        change(get_db(),kind,identifier,{'action':'upload','expectedUpdatedAt':request.form.get('expectedUpdatedAt')},user_id=user_id(),media=media,metadata=metadata)
        commit('image_upload',kind,identifier);return jsonify(choices(get_db(),get_uploads_dir(),kind,identifier)),201
    def image_file(digest,size):
        try:file=open_media(get_uploads_dir(),digest,size)
        except (MediaError,OSError):abort(404)
        try:
            response=send_file(file,mimetype='image/webp',download_name=digest+'.webp',etag=digest+'-'+size,max_age=0)
            response.make_conditional(request);response.call_on_close(file.close);return response
        except BaseException:file.close();raise
    @bp.get('/media/inventory/<kind>/<int:identifier>/<digest>/<size>')
    @login_required
    def object_image(kind,identifier,digest,size):
        require_object(kind,identifier)
        if resolve(get_db(),get_uploads_dir(),kind,identifier)['hash']!=digest:abort(404)
        return image_file(digest,size)
    @bp.get('/media/catalog/<int:identifier>/<digest>/<size>')
    @login_required
    def catalog_image(identifier,digest,size):
        require_catalog()
        if not get_db().execute('SELECT 1 FROM product_images WHERE product_id=? AND media_hash=?',(identifier,digest)).fetchone():abort(404)
        return image_file(digest,size)
    return bp
