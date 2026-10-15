"""One asset taxonomy with safe reassignment and existing field definitions."""
import json
import sqlite3
from flask import Blueprint,abort,jsonify,render_template,request,session
from . import assets
from inventorypro.domains.categories.service import remove_category,CategoryRemovalError


def scopes(db,identifier):
    values=set()
    explicit=db.execute('SELECT scope FROM asset_category_scope WHERE category_id=?',(identifier,)).fetchone()
    if explicit:values.add(explicit[0])
    if db.execute('SELECT 1 FROM asset_legacy_categories WHERE asset_category_id=?',(identifier,)).fetchone():values.add('devices')
    for row in db.execute('''SELECT DISTINCT coalesce(s.scope,CASE WHEN m.device_id IS NOT NULL THEN 'devices' ELSE 'assets' END)
        FROM assets a LEFT JOIN asset_permission_scope s ON s.asset_id=a.id LEFT JOIN asset_legacy_devices m ON m.asset_id=a.id WHERE a.category_id=?''',(identifier,)):
        values.add(row[0])
    return values or {'assets'}


def can_manage(db,can,identifier):
    return all(can('categories.manage' if scope=='devices' else 'asset_categories.manage') for scope in scopes(db,identifier))


def build_category_blueprint(*,get_db,user_can,get_access,login_required,parse_fields,normalize_fields,log_activity):
    bp=Blueprint('asset_taxonomy',__name__)
    def active():
        if not assets.unified(get_db()):abort(404)
    def read():
        if not any(user_can(key) for key in ['assets.view','assets.manage','devices.view','devices.manage','asset_categories.view','asset_categories.manage','categories.view','categories.manage']):abort(403)
    def categories():
        db=get_db();predicate,args=assets.scope_predicate(user_can)
        result=[]
        for row in db.execute('SELECT c.*,v.revision FROM asset_categories c JOIN asset_category_versions v ON v.category_id=c.id ORDER BY c.name'):
            item=dict(row);item['fields']=parse_fields(item['fields']);item['can_edit']=can_manage(db,user_can,item['id'])
            item['count']=db.execute('SELECT count(*) FROM assets a WHERE a.category_id=? AND '+predicate,[item['id'],*args]).fetchone()[0];result.append(item)
        return result
    def payload():
        value=request.get_json(silent=True)
        if not isinstance(value,dict):raise assets.AssetError('Bitte gültige Kategoriedaten eingeben.')
        return value
    def revision(identifier,expected):
        row=get_db().execute('SELECT revision FROM asset_category_versions WHERE category_id=?',(identifier,)).fetchone()
        if not row:raise assets.AssetError('Asset-Kategorie nicht gefunden.',404)
        if isinstance(expected,bool) or not isinstance(expected,int) or row[0]!=expected:raise assets.AssetError('Die Kategorie wurde inzwischen geändert. Bitte neu laden.',409)
    @bp.errorhandler(assets.AssetError)
    def error(problem):get_db().rollback();return jsonify(error=str(problem),fields=problem.fields),problem.status
    @bp.errorhandler(CategoryRemovalError)
    def category_error(problem):get_db().rollback();return jsonify(problem.payload),problem.status
    @bp.get('/inventory/categories')
    @login_required
    def taxonomy_page():
        active();read();access=get_access(get_db())
        return render_template('asset_categories.html',categories=categories(),can_create=user_can('categories.manage') or user_can('asset_categories.manage'),username=session.get('username'),permissions=sorted(access['permissions']),is_superuser=access['is_superuser'])
    @bp.route('/api/inventory/categories',methods=['GET','POST'])
    @bp.route('/api/inventory/categories/<int:identifier>',methods=['PUT','DELETE'])
    @login_required
    def taxonomy_api(identifier=None):
        active();read()
        if request.method=='GET':return jsonify(categories=categories())
        db=get_db();data=payload()
        with assets.mutation(db):
            if identifier is None:
                if not (user_can('categories.manage') or user_can('asset_categories.manage')):abort(403)
            else:
                if not can_manage(db,user_can,identifier):abort(403)
                revision(identifier,data.get('expectedRevision'))
            if request.method=='DELETE':
                target=data.get('target_category_id')
                if isinstance(target,int) and not isinstance(target,bool):
                    if not can_manage(db,user_can,target):abort(403)
                    if db.execute('SELECT 1 FROM assets WHERE category_id=?',(identifier,)).fetchone() and not all(user_can(scope+'.manage') for scope in scopes(db,identifier)):abort(403)
                result=remove_category(db,'asset',identifier,data.get('target_category_id'));log_activity(db,'delete','asset_category',identifier,result)
            else:
                name=assets._text(data.get('name'),'Kategoriename',120)
                if not name:raise assets.AssetError('Bitte einen Kategorienamen eingeben.')
                raw=data.get('fields',{})
                if not isinstance(raw,dict) or len(raw)>100:raise assets.AssetError('Bitte höchstens 100 gültige Felder angeben.')
                fields=normalize_fields(raw)
                if len(fields)!=len(raw):raise assets.AssetError('Bitte gültige eindeutige Feldnamen angeben.')
                values=(name,assets._text(data.get('description'),'Beschreibung',4000),assets._text(data.get('icon') or 'package','Symbol',50),json.dumps(fields,ensure_ascii=False))
                try:
                    if identifier is None:
                        identifier=db.execute('INSERT INTO asset_categories(name,description,icon,fields) VALUES (?,?,?,?)',values).lastrowid
                        scope='assets' if user_can('asset_categories.manage') else 'devices'
                        db.execute('INSERT INTO asset_category_scope(category_id,scope) VALUES (?,?)',(identifier,scope))
                    else:db.execute('UPDATE asset_categories SET name=?,description=?,icon=?,fields=? WHERE id=?',[*values,identifier])
                except sqlite3.IntegrityError as problem:raise assets.AssetError('Eine Asset-Kategorie mit diesem Namen existiert bereits.',409) from problem
                log_activity(db,'update' if request.method=='PUT' else 'create','asset_category',identifier)
                result={'id':identifier}
        db.commit();return jsonify(result),201 if request.method=='POST' else 200
    return bp
