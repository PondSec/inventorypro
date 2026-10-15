import json
from flask import Blueprint, abort, jsonify, render_template, request, session
from inventorypro.domains.inventory.service import list_inventory
from .service import PlanningError, compute_plan, dimension_suggestions


def build_planning_blueprint(*, get_db, user_can, get_access, login_required, pack, build_layers, enrich_layers, log_activity):
    blueprint=Blueprint('storage_planning',__name__)
    def require_read():
        if not (user_can('assets.view') or user_can('assets.manage')):
            abort(403)
    def preview(payload):
        return compute_plan(get_db(),payload,pack=pack,build_layers=build_layers,enrich_layers=enrich_layers)

    @blueprint.get('/inventory/planning')
    @login_required
    def page():
        require_read()
        access=get_access(get_db())
        return render_template('storage_planning.html',username=session.get('username'),permissions=sorted(access['permissions']),is_superuser=access['is_superuser'])

    @blueprint.get('/api/planning/assets')
    @login_required
    def assets():
        require_read()
        db=get_db()
        result=list_inventory(db,{**request.args.to_dict(),'kind':'asset','per_page':20},devices_allowed=False,assets_allowed=True)
        ids=[row['id'] for row in result['rows']]
        options={}
        if ids:
            placeholders=','.join('?' for _ in ids)
            rows=db.execute(f'''SELECT a.id,a.specs,c.fields FROM assets a LEFT JOIN asset_categories c ON c.id=a.category_id WHERE a.id IN ({placeholders})''',ids)
            options={row['id']:dimension_suggestions(row['specs'],row['fields']) for row in rows}
        return jsonify(items=[{**row,'suggestions':options[row['id']]} for row in result['rows']],page=result['page'],pages=result['pages'],total=result['total'])

    @blueprint.post('/api/planning/preview')
    @login_required
    def calculate():
        require_read()
        try:
            return jsonify(preview(request.get_json(silent=True)))
        except PlanningError as error:
            return jsonify(error=str(error)),400

    @blueprint.get('/api/planning/plans')
    @login_required
    def plans():
        require_read()
        rows=get_db().execute('SELECT id,name,created_at FROM storage_plans ORDER BY id DESC LIMIT 50').fetchall()
        return jsonify(items=[dict(row) for row in rows])

    @blueprint.post('/api/planning/plans')
    @login_required
    def save():
        require_read()
        if not user_can('assets.manage'):
            abort(403)
        payload=request.get_json(silent=True)
        try:
            result=preview(payload)
        except PlanningError as error:
            return jsonify(error=str(error)),400
        name=str(payload.get('name') or '').strip()[:120]
        if not name:
            return jsonify(error='Planname ist erforderlich.'),400
        db=get_db()
        user=get_access(db)['user']
        cursor=db.execute('INSERT INTO storage_plans(name,payload_json,preview_json,created_by_user_id) VALUES (?,?,?,?)',
                          (name,json.dumps(payload,allow_nan=False),json.dumps(result,allow_nan=False),user['id']))
        log_activity(db,"create","storage_plan",cursor.lastrowid,{"name":name})
        db.commit()
        return jsonify(id=cursor.lastrowid,name=name),201

    @blueprint.route('/api/planning/plans/<int:plan_id>',methods=['GET','DELETE'])
    @login_required
    def plan(plan_id):
        require_read()
        row=get_db().execute('SELECT * FROM storage_plans WHERE id=?',(plan_id,)).fetchone()
        if not row:
            abort(404)
        if request.method=='DELETE':
            if not user_can('assets.manage'):
                abort(403)
            db=get_db()
            db.execute('DELETE FROM storage_plans WHERE id=?',(plan_id,))
            log_activity(db,'delete','storage_plan',plan_id,{'name':row['name']})
            db.commit()
            return jsonify(status='deleted')
        return jsonify(id=row['id'],name=row['name'],preview=json.loads(row['preview_json']),payload=json.loads(row['payload_json']))

    return blueprint
