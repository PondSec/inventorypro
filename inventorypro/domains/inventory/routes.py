"""Server-rendered, bookmarkable inventory lists and object detail pages."""
import json
import csv
import re
import tempfile
from io import TextIOWrapper
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, send_file
from inventorypro.domains.exports.service import protect_spreadsheet_row
from .service import SORTS, inventory_query, list_inventory, workspace_tasks
from .objects import load_panel


def build_inventory_blueprint(*, get_db, user_can, get_access, login_required, load_asset, ticket_visible, get_export_settings):
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
                               can_devices=can_read('device'), can_assets=can_read('asset'), can_maintenance=maintenance_allowed,
                               can_export=user_can('server_settings.manage') and get_export_settings(get_db())['importExport']['exportAllowed'], **context())

    @blueprint.get('/inventory/export')
    @login_required
    def inventory_export():
        db = get_db()
        if not user_can('server_settings.manage') or not get_export_settings(db)['importExport']['exportAllowed']:
            abort(403)
        source,predicate,params,state = inventory_query(request.args,devices_allowed=can_read('device'),
            assets_allowed=can_read('asset'),maintenance_allowed=user_can('maintenance.view') or user_can('maintenance.manage'))
        if not source:
            abort(403)
        selected = request.args.get('selection','')
        if selected:
            entries = selected.split(',')
            if len(entries)>100 or any(not re.fullmatch(r'(device|asset)-[1-9]\d{0,8}', entry) for entry in entries):
                abort(400)
            predicate += ' AND (' + ' OR '.join('(kind=? AND id=?)' for _ in entries) + ')'
            for entry in entries:
                kind,identifier = entry.split('-');params.extend([kind,int(identifier)])
        cursor = db.execute(source + 'SELECT * FROM inventory' + predicate + f" ORDER BY {SORTS[state['sort']]} {state['direction']},kind,id",params)
        # Materialize to a private temporary file while the request's DB is open.
        # The file wrapper streams it afterwards without retaining all rows in RAM.
        output = tempfile.TemporaryFile(mode='w+b')
        try:
            text = TextIOWrapper(output,encoding='utf-8-sig',newline='')
            writer = csv.writer(text,delimiter=';')
            writer.writerow(['Bezeichnung','Art','Vorlage','Identifikation','Standort','Zugewiesen an','Status','Letzte Änderung'])
            for row in cursor:
                writer.writerow(protect_spreadsheet_row([row['name'],'Gerät' if row['kind']=='device' else 'Set / Zubehör',row['category'],
                    row['serial_number'],row['location'],row['assigned_to'],'Ausgemustert' if row['retired'] else 'Im Bestand',row['updated_at']]))
            text.flush();text.detach();output.seek(0)
            response = send_file(output,mimetype='text/csv',as_attachment=True,download_name='inventorypro-bestand.csv',max_age=0)
            response.headers['Cache-Control'] = 'no-store'
            response.call_on_close(output.close)
            return response
        except BaseException:
            output.close()
            raise

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
