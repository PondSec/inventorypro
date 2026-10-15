"""Server-rendered, bookmarkable inventory lists and object detail pages."""
import json
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session
from .service import list_inventory, workspace_tasks
from .objects import load_panel


def build_inventory_blueprint(*, get_db, user_can, get_access, login_required, load_asset, ticket_visible):
    blueprint = Blueprint('inventory_workspace', __name__)

    @blueprint.app_template_filter('inventory_date')
    def inventory_date(value, include_time=False):
        if not value:
            return ''
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M' if include_time else '%d.%m.%Y')
        except (TypeError, ValueError):
            return str(value)

    def can_read(kind):
        prefix = 'devices' if kind == 'device' else 'assets'
        return user_can(prefix + '.view') or user_can(prefix + '.manage')

    def context():
        access = get_access(get_db())
        return dict(username=session.get('username'), permissions=sorted(access['permissions']), is_superuser=access['is_superuser'])

    @blueprint.get('/api/workspace/tasks')
    @login_required
    def tasks():
        return jsonify({'tasks': workspace_tasks(get_db(), user_can, get_access(get_db()))})

    @blueprint.get('/inventory')
    @login_required
    def inventory():
        if not (can_read('device') or can_read('asset')):
            abort(403)
        maintenance_allowed = user_can('maintenance.view') or user_can('maintenance.manage')
        result = list_inventory(get_db(), request.args, devices_allowed=can_read('device'), assets_allowed=can_read('asset'), maintenance_allowed=maintenance_allowed)
        def link(**changes):
            return '/inventory?' + urlencode({**{key: result[key] for key in ('q','kind','filter','sort','direction','category','location','assigned','page','per_page')}, **changes})
        return render_template('inventory_workspace.html', inventory=result, inventory_link=link,
                               can_devices=can_read('device'), can_assets=can_read('asset'), can_maintenance=maintenance_allowed, **context())

    @blueprint.get('/inventory/new')
    @login_required
    def new_record():
        if not user_can('devices.manage'):
            abort(403)
        return redirect('/?view=devices&create=device')

    @blueprint.get('/api/inventory/<kind>/<int:object_id>/panel')
    @login_required
    def object_panel(kind, object_id):
        if kind not in {'device', 'asset'}:
            abort(404)
        if not can_read(kind):
            abort(403)
        db = get_db()
        obj = load_panel(db, kind, object_id, can=user_can, access=get_access(db), ticket_visible=ticket_visible)
        if obj is None:
            abort(404)
        if request.args.get('format') == 'html':
            return render_template('_object_panel.html', object=obj, **context())
        return jsonify(obj)

    @blueprint.get('/inventory/devices/<int:object_id>')
    @login_required
    def device_detail(object_id):
        if not can_read('device'):
            abort(403)
        db = get_db()
        row = db.execute('''SELECT d.*, c.name AS category_name, l.name AS location_name
            FROM devices d LEFT JOIN categories c ON c.id=d.category_id
            LEFT JOIN locations l ON l.id=d.location_id WHERE d.id=?''', (object_id,)).fetchone()
        if not row:
            abort(404)
        device = dict(row)
        try:
            device['specs'] = json.loads(device.get('specs') or '{}')
        except (ValueError, TypeError):
            device['specs'] = {}
        if not isinstance(device['specs'], dict):
            device['specs'] = {}
        tabs = [('overview', 'Übersicht'), ('hardware', 'Hardware'), ('accessories', 'Zubehör'),
                ('assignment', 'Zuweisung'), ('maintenance', 'Wartung'), ('history', 'Verlauf')]
        tab = request.args.get('tab', 'overview')
        if tab not in dict(tabs):
            abort(404)
        assets = db.execute('''SELECT a.id, a.name, ad.quantity, ad.notes FROM assets a
            JOIN asset_devices ad ON ad.asset_id=a.id WHERE ad.device_id=? ORDER BY a.name''', (object_id,)).fetchall() if can_read('asset') else []
        tasks = db.execute('SELECT * FROM maintenance_tasks WHERE device_id=? ORDER BY due_date, id', (object_id,)).fetchall() if user_can('maintenance.view') or user_can('maintenance.manage') else []
        history = db.execute("SELECT action, username, created_at FROM activity_log WHERE entity_type='device' AND entity_id=? ORDER BY id DESC LIMIT 100", (object_id,)).fetchall() if user_can('activity.view') else []
        notes = db.execute('SELECT * FROM device_notes WHERE device_id=? ORDER BY id DESC LIMIT 100', (object_id,)).fetchall()
        return render_template('device_detail.html', device=device, assets=assets, tasks=tasks, history=history,
                               notes=notes, tabs=tabs, tab=tab, can_edit=user_can('devices.manage'), **context())

    @blueprint.get('/inventory/assets/<int:object_id>')
    @login_required
    def asset_detail(object_id):
        if not can_read('asset'):
            abort(403)
        response = load_asset(object_id)
        if isinstance(response, tuple):
            return response
        if response.status_code != 200:
            return response
        return render_template('asset_detail.html', asset=response.get_json(), can_edit=user_can('assets.manage'), **context())

    return blueprint
