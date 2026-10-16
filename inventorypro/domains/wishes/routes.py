"""Authenticated planning pages and JSON mutations with normal CSRF protection."""
from decimal import Decimal
from math import ceil
from flask import Blueprint, abort, jsonify, render_template, request, session

from inventorypro.domains.inventory import assets
from . import service


def build_wishes_blueprint(*, get_db, user_can, get_access, login_required, parse_fields, validate_specs, log_activity):
    bp = Blueprint('wishes', __name__)

    def actor():
        return get_access(get_db())['user']['id']

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise service.WishError('Bitte gültige Plandaten eingeben.')
        return value

    def commit(action, kind, identifier):
        log_activity(get_db(), action, kind, identifier)
        get_db().commit()

    @bp.errorhandler(assets.AssetError)
    def invalid(error):
        get_db().rollback()
        if request.path.startswith('/api/'):
            return jsonify(error=str(error), fields=error.fields), error.status
        abort(error.status)

    @bp.app_template_filter('wish_money')
    def money(value, currency='EUR'):
        if value is None:
            return '—'
        from inventorypro.i18n import language
        amount = format(Decimal(value) / 100, ',.2f')
        if language() == 'de':
            amount = amount.translate(str.maketrans({',': '.', '.': ','}))
        return amount + ' ' + currency

    def context():
        db = get_db()
        access = get_access(db)
        return dict(username=session.get('username'), permissions=sorted(access['permissions']), is_superuser=access['is_superuser'],
            can_manage=user_can('wishes.manage'), can_inventory=user_can('assets.manage') or user_can('devices.manage'),
            categories=[dict(r) for r in db.execute('SELECT id,name,fields FROM asset_categories ORDER BY name')],
            locations=[dict(r) for r in db.execute('SELECT id,name FROM locations ORDER BY name')],
            projects=[dict(r) for r in db.execute(f'SELECT id,name,currency FROM wish_projects p WHERE {service.visible("p", True)} AND asset_id IS NULL ORDER BY name LIMIT 500', (actor(),))])

    def project_summary(row):
        db = get_db()
        result = dict(row)
        aggregate = db.execute('''SELECT coalesce(sum(w.quantity),0) AS needed,
            coalesce(sum((SELECT count(*) FROM wish_acquisitions a WHERE a.wish_id=w.id AND a.asset_id IS NOT NULL)),0) AS owned,
            sum(w.quantity*w.unit_price_cents) AS estimate,
            sum(CASE WHEN w.unit_price_cents IS NULL THEN 1 ELSE 0 END) AS unpriced
            FROM wishes w WHERE w.project_id=? AND w.archived=0''', (row['id'],)).fetchone()
        result.update(dict(aggregate))
        result['spent'] = db.execute('''SELECT sum(a.unit_cost_cents) FROM wish_acquisitions a JOIN wishes w ON w.id=a.wish_id
            WHERE w.project_id=? AND w.archived=0''', (row['id'],)).fetchone()[0]
        result['missing'] = max(0, result['needed'] - result['owned'])
        result['progress'] = round(100 * result['owned'] / result['needed']) if result['needed'] else 0
        result['inventory_link'] = bool(result['asset_id'] and assets.can_access(db, user_can, result['asset_id']))
        return result

    def records(parent=None, kind='wishes'):
        db = get_db()
        query = request.args.get('q', '').strip()[:240]
        status = request.args.get('status', '')
        visibility = request.args.get('visibility', '')
        priority = request.args.get('priority', '')
        try:
            per_page = int(request.args.get('per_page', 10))
            page = max(1, int(request.args.get('page', 1)))
        except (ValueError, TypeError):
            per_page, page = 10, 1
        if per_page not in (10, 20, 50):
            per_page = 10
        if kind == 'projects':
            sql = ' FROM wish_projects p WHERE '+service.visible('p', True)
            args = [actor()]
            if query:
                sql += " AND (instr(lower(p.name),lower(?))>0 OR instr(lower(p.description),lower(?))>0)"
                args += [query, query]
            if status == 'owned':
                sql += ' AND p.asset_id IS NOT NULL'
            elif status == 'missing':
                sql += ' AND p.asset_id IS NULL'
            if visibility in {'private', 'team'}:
                sql += ' AND p.visibility=?'; args.append(visibility)
            select, order = 'p.*', 'p.updated_at DESC,p.id DESC'
        else:
            sql = ' FROM wishes w LEFT JOIN wish_projects p ON p.id=w.project_id WHERE '+service.visible()
            args = [actor(), actor()]
            if parent:
                sql += ' AND w.project_id=?'; args.append(parent['id'])
            if query:
                sql += ' AND (instr(lower(w.name),lower(?))>0 OR instr(lower(w.notes),lower(?))>0 OR instr(lower(w.model),lower(?))>0)'
                args += [query, query, query]
            owned = '(SELECT count(*) FROM wish_acquisitions a WHERE a.wish_id=w.id AND a.asset_id IS NOT NULL)'
            sql += ' AND w.archived=?'; args.append(1 if status == 'archived' else 0)
            if status == 'missing':
                sql += ' AND '+owned+'<w.quantity'
            elif status == 'owned':
                sql += ' AND '+owned+'>=w.quantity'
            if priority in {'low', 'normal', 'high'}:
                sql += ' AND w.priority=?'; args.append(priority)
            if visibility in {'private', 'team'}:
                sql += ' AND coalesce(p.visibility,w.visibility)=?'; args.append(visibility)
            select, order = 'w.id', "CASE w.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,w.updated_at DESC,w.id DESC"
        total = db.execute('SELECT count(*)'+sql, args).fetchone()[0]
        pages = max(1, ceil(total / per_page))
        page = min(page, pages)
        rows = db.execute('SELECT '+select+sql+' ORDER BY '+order+' LIMIT ? OFFSET ?', [*args, per_page, (page-1)*per_page]).fetchall()
        items = [project_summary(row) if kind == 'projects' else service.wish(db, user_can, actor(), row['id']) for row in rows]
        def page_url(number):
            from urllib.parse import urlencode
            return request.path+'?'+urlencode({**request.args.to_dict(), 'page': number, 'per_page': per_page})
        return dict(items=items, total=total, page=page, pages=pages, per_page=per_page, q=query, status=status,
                    visibility=visibility, priority=priority, page_url=page_url, page_numbers=range(max(1,page-2), min(pages,page+2)+1))

    @bp.get('/wishes')
    @login_required
    def index():
        service.permission(user_can)
        kind = 'projects' if request.args.get('tab') == 'projects' else 'wishes'
        return render_template('wishes.html', kind=kind, project=None, **records(kind=kind), **context())

    @bp.get('/wishes/projects/<int:identifier>')
    @login_required
    def project_page(identifier):
        row = project_summary(service.project(get_db(), user_can, actor(), identifier))
        return render_template('wishes.html', kind='wishes', project=row, **records(parent=row), **context())

    @bp.route('/api/wishes/projects', methods=['GET', 'POST'])
    @login_required
    def projects():
        if request.method == 'GET':
            service.permission(user_can)
            return jsonify(context()['projects'])
        result = service.save_project(get_db(), user_can, actor(), body())
        commit('create', 'wish_project', result['id'])
        return jsonify(result), 201

    @bp.route('/api/wishes/projects/<int:identifier>', methods=['GET', 'PUT', 'DELETE'])
    @login_required
    def project(identifier):
        if request.method == 'GET':
            return jsonify(project_summary(service.project(get_db(), user_can, actor(), identifier)))
        if request.method == 'DELETE':
            service.remove(get_db(), user_can, actor(), 'projects', identifier, body())
            commit('delete', 'wish_project', identifier)
            return jsonify(deleted=True)
        result = service.save_project(get_db(), user_can, actor(), body(), identifier)
        commit('update', 'wish_project', identifier)
        return jsonify(result)

    @bp.post('/api/wishes')
    @login_required
    def create():
        result = service.save_wish(get_db(), user_can, actor(), body())
        commit('create', 'wish', result['id'])
        return jsonify(result), 201

    @bp.route('/api/wishes/<int:identifier>', methods=['GET', 'PUT', 'DELETE'])
    @login_required
    def detail(identifier):
        if request.method == 'GET':
            return jsonify(service.wish(get_db(), user_can, actor(), identifier))
        if request.method == 'DELETE':
            service.remove(get_db(), user_can, actor(), 'wishes', identifier, body())
            commit('delete', 'wish', identifier)
            return jsonify(deleted=True)
        result = service.save_wish(get_db(), user_can, actor(), body(), identifier)
        commit('update', 'wish', identifier)
        return jsonify(result)

    @bp.post('/api/wishes/<int:identifier>/acquire')
    @login_required
    def acquire(identifier):
        if not assets.unified(get_db()):
            raise service.WishError('Bitte zuerst die einheitliche Asset-Verwaltung aktivieren.', 409)
        result = service.acquire(get_db(), user_can, actor(), identifier, body(), parse_fields=parse_fields, validate_specs=validate_specs)
        commit('acquire', 'wish', identifier)
        return jsonify(result)

    @bp.post('/api/wishes/projects/<int:identifier>/assemble')
    @login_required
    def assemble(identifier):
        if not assets.unified(get_db()):
            raise service.WishError('Bitte zuerst die einheitliche Asset-Verwaltung aktivieren.', 409)
        result = service.assemble(get_db(), user_can, actor(), identifier, body(), parse_fields=parse_fields, validate_specs=validate_specs)
        commit('assemble', 'wish_project', identifier)
        return jsonify(result)

    @bp.delete('/api/wishes/<int:identifier>/acquisitions/<int:acquisition>')
    @login_required
    def release(identifier, acquisition):
        result = service.release(get_db(), user_can, actor(), identifier, acquisition, body())
        commit('release', 'wish', identifier)
        return jsonify(result)

    return bp
