"""Canonical asset APIs and focused editor; old routes remain compatibility paths."""
import json
import re
from datetime import date
from flask import Blueprint,abort,jsonify,render_template,request,session,redirect
from . import assets
from .service import list_inventory
from inventorypro.domains.catalog.objects import resolve,resolve_many


def editor_options(db,user_can,parse_fields):
    return dict(categories=[{**dict(row),'fields':parse_fields(row['fields'])} for row in db.execute('SELECT id,name,fields FROM asset_categories ORDER BY name')],
        locations=[dict(row) for row in db.execute('SELECT id,name FROM locations ORDER BY name')],
        vendors=[dict(row) for row in db.execute('SELECT id,name FROM vendors ORDER BY name')] if user_can('procurement.view') or user_can('procurement.manage') else [],
        orders=[dict(row) for row in db.execute('SELECT id,po_number AS name FROM purchase_orders ORDER BY id DESC LIMIT 500')] if user_can('procurement.view') or user_can('procurement.manage') else [])

def build_assets_blueprint(*,get_db,user_can,get_access,login_required,parse_fields,validate_specs,log_activity,get_uploads_dir):
    bp=Blueprint('unified_assets',__name__)
    def active():
        if not assets.unified(get_db()):abort(404)
    def context():
        access=get_access(get_db())
        return dict(username=session.get('username'),permissions=sorted(access['permissions']),is_superuser=access['is_superuser'])
    def data():
        value=request.get_json(silent=True)
        if not isinstance(value,dict):raise assets.AssetError('Bitte gültige Assetdaten eingeben.')
        return value
    def write(action,identifier):log_activity(get_db(),action,'asset',identifier);get_db().commit()
    @bp.before_app_request
    def legacy_access_guard():
        if not session.get('logged_in') or not (request.path.startswith('/api/asset-entries/') or request.path.startswith('/assets/') or request.endpoint=='handle_device' and request.method=='DELETE'):
            return None
        db=get_db()
        if not assets.unified(db):return None
        try:
            if request.endpoint=='handle_device' and request.method=='DELETE':
                legacy_id=(request.view_args or {}).get('device_id')
                mapped=db.execute('SELECT asset_id FROM asset_legacy_devices WHERE device_id=?',(legacy_id,)).fetchone()
                if mapped:
                    assets.delete_asset(db,user_can,mapped[0],assets.version(db,mapped[0]));write('delete',mapped[0]);return jsonify(status='deleted')
            identifier=(request.view_args or {}).get('asset_id')
            if identifier is not None:assets.require(db,user_can,identifier)
            if request.endpoint=='asset_entry_detail' and request.method=='DELETE':
                assets.delete_asset(db,user_can,identifier,assets.version(db,identifier));write('delete',identifier)
                return jsonify(status='deleted')
        except assets.AssetError as problem:
            db.rollback();return jsonify(error=str(problem)),problem.status
        return None
    @bp.app_context_processor
    def inventory_mode():return {'unified_inventory':assets.unified(get_db())}
    @bp.errorhandler(assets.AssetError)
    def asset_error(error):get_db().rollback();return jsonify(error=str(error),fields=error.fields),error.status
    @bp.get('/api/inventory/assets')
    @login_required
    def asset_list():
        active()
        if not any(user_can(key) for key in ['assets.view','assets.manage','devices.view','devices.manage']):abort(403)
        result=list_inventory(get_db(),request.args,devices_allowed=user_can('devices.view') or user_can('devices.manage'),assets_allowed=user_can('assets.view') or user_can('assets.manage'),maintenance_allowed=user_can('maintenance.view') or user_can('maintenance.manage'))
        pictures=resolve_many(get_db(),get_uploads_dir(),result['rows'])
        for row in result['rows']:row['image_url']=pictures[('asset',row['id'])]['url']
        return jsonify(result)
    @bp.post('/api/inventory/assets')
    @login_required
    def asset_create():
        active();result=assets.create_asset(get_db(),user_can,data(),parse_fields=parse_fields,validate_specs=validate_specs)
        write('create',result['id']);return jsonify(result),201
    @bp.route('/api/inventory/assets/<int:identifier>',methods=['GET','PUT','DELETE'])
    @login_required
    def asset_detail(identifier):
        active()
        if request.method=='GET':return jsonify(assets.get_asset(get_db(),user_can,identifier))
        payload=data()
        if request.method=='DELETE':
            assets.delete_asset(get_db(),user_can,identifier,payload.get('expectedRevision'));write('delete',identifier);return jsonify(deleted=True)
        result=assets.update_asset(get_db(),user_can,identifier,payload,parse_fields=parse_fields,validate_specs=validate_specs)
        write('update',identifier);return jsonify(result)
    @bp.put('/api/inventory/assets/<int:identifier>/components')
    @login_required
    def asset_components(identifier):
        active();payload=data();items=payload.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=100:raise assets.AssetError('Bitte zwischen 1 und 100 Assets auswählen.')
        ids=set()
        with assets.mutation(get_db()):
            assets.require(get_db(),user_can,identifier,write=True);assets._check_revision(get_db(),identifier,payload.get('expectedRevision'))
            for item in items:
                if not isinstance(item,dict) or isinstance(item.get('id'),bool) or not isinstance(item.get('id'),int) or item['id']<=0 or item['id'] in ids:raise assets.AssetError('Bitte eindeutige gültige Assets auswählen.')
                ids.add(item['id'])
                assets.set_component(get_db(),user_can,identifier,item['id'],item.get('quantity',1),item.get('notes',''),assets.version(get_db(),identifier))
            result=assets.get_asset(get_db(),user_can,identifier)
        write('contents_update',identifier);return jsonify(result)
    @bp.delete('/api/inventory/assets/<int:identifier>/components/<int:child>')
    @login_required
    def asset_component_remove(identifier,child):
        active();result=assets.remove_component(get_db(),user_can,identifier,child,data().get('expectedRevision'))
        write('contents_remove',identifier);return jsonify(result)
    @bp.get('/api/inventory/relation-types')
    @login_required
    def relation_types():
        active()
        if not any(user_can(key) for key in ['assets.view','assets.manage','devices.view','devices.manage']):abort(403)
        return jsonify([dict(row) for row in get_db().execute('SELECT id,name,description FROM asset_relation_types ORDER BY name')])
    @bp.post('/api/inventory/assets/<int:identifier>/relations')
    @login_required
    def asset_relations_add(identifier):
        from .relations import add_relations
        active();add_relations(get_db(),user_can,identifier,data());write('relations_add',identifier)
        return jsonify(saved=True),201
    @bp.delete('/api/inventory/assets/<int:identifier>/relations/<int:relation_id>')
    @login_required
    def asset_relation_remove(identifier,relation_id):
        from .relations import remove_relation
        active();remove_relation(get_db(),user_can,identifier,relation_id,data().get('expectedRevision'));write('relation_remove',identifier)
        return jsonify(deleted=True)
    @bp.post('/api/inventory/assets/<int:identifier>/notes')
    @login_required
    def asset_note(identifier):
        active();assets.require(get_db(),user_can,identifier,write=True)
        note=assets._text(data().get('note'),'Notiz',20000)
        if not note:raise assets.AssetError('Bitte eine Notiz eingeben.')
        get_db().execute('INSERT INTO asset_notes(asset_id,note,created_by_user_id) VALUES (?,?,?)',(identifier,note,get_access(get_db())['user']['id']))
        write('note_add',identifier);return jsonify(saved=True),201
    @bp.post('/api/inventory/assets/<int:identifier>/tags')
    @login_required
    def asset_tag(identifier):
        active();assets.require(get_db(),user_can,identifier,write=True)
        tag=assets._text(data().get('tag'),'Tag',120)
        if not tag:raise assets.AssetError('Bitte einen Tag eingeben.')
        get_db().execute('INSERT INTO asset_tags(asset_id,tag) VALUES (?,?)',(identifier,tag))
        write('tag_add',identifier);return jsonify(saved=True),201
    @bp.delete('/api/inventory/assets/<int:identifier>/extras/<kind>/<key>')
    @login_required
    def asset_extra_remove(identifier,kind,key):
        active();assets.require(get_db(),user_can,identifier,write=True)
        match=re.fullmatch(r'(legacy|asset)-([1-9]\d*)',key)
        if not match or kind not in {'tag','note'}:raise assets.AssetError('Ungültiger Eintrag.')
        table=('asset_tags' if kind=='tag' else 'asset_notes') if match[1]=='asset' else ('device_tags' if kind=='tag' else 'device_notes')
        if match[1]=='asset':result=get_db().execute(f'DELETE FROM {table} WHERE id=? AND asset_id=?',(int(match[2]),identifier))
        else:result=get_db().execute(f'DELETE FROM {table} WHERE id=? AND device_id IN (SELECT device_id FROM asset_legacy_devices WHERE asset_id=?)',(int(match[2]),identifier))
        if not result.rowcount:raise assets.AssetError('Der Eintrag existiert nicht mehr.',404)
        write(kind+'_remove',identifier);return jsonify(deleted=True)
    @bp.post('/api/inventory/assets/<int:identifier>/maintenance')
    @login_required
    def asset_maintenance(identifier):
        active();assets.require(get_db(),user_can,identifier)
        if not user_can('maintenance.manage'):abort(403)
        payload=data();title=assets._text(payload.get('title'),'Aufgabe')
        if not title:raise assets.AssetError('Bitte eine Aufgabe eingeben.')
        due=payload.get('due_date') or None
        if due:
            try:due=date.fromisoformat(due).isoformat()
            except (ValueError,TypeError):raise assets.AssetError('Bitte ein gültiges Datum eingeben.')
        get_db().execute('INSERT INTO asset_maintenance_tasks(asset_id,title,due_date) VALUES (?,?,?)',(identifier,title,due))
        write('maintenance_add',identifier);return jsonify(saved=True),201
    @bp.put('/api/inventory/assets/<int:identifier>/maintenance/<key>')
    @login_required
    def asset_maintenance_status(identifier,key):
        active();assets.require(get_db(),user_can,identifier)
        if not user_can('maintenance.manage'):abort(403)
        match=re.fullmatch(r'(legacy|asset)-([1-9]\d*)',key);status=data().get('status')
        if not match or status not in {'open','done'}:raise assets.AssetError('Ungültige Wartungsaufgabe.')
        if match[1]=='asset':result=get_db().execute('UPDATE asset_maintenance_tasks SET status=? WHERE id=? AND asset_id=?',(status,int(match[2]),identifier))
        else:result=get_db().execute('''UPDATE maintenance_tasks SET status=? WHERE id=? AND device_id IN
            (SELECT device_id FROM asset_legacy_devices WHERE asset_id=?)''',('completed' if status=='done' else status,int(match[2]),identifier))
        if not result.rowcount:raise assets.AssetError('Wartungsaufgabe nicht gefunden.',404)
        write('maintenance_status',identifier);return jsonify(saved=True)
    @bp.get('/inventory/assets/new')
    @bp.get('/inventory/assets/<int:identifier>/edit')
    @login_required
    def asset_editor(identifier=None):
        active()
        if identifier is None:
            if not (user_can('assets.manage') or user_can('devices.manage')):abort(403)
            asset={'id':None,'name':'','specs':{},'revision':None}
        else:
            assets.require(get_db(),user_can,identifier,write=True)
            return redirect(f'/inventory/assets/{identifier}?edit=1')
        return render_template('asset_editor.html',asset=asset,options=editor_options(get_db(),user_can,parse_fields),**context())
    return bp
