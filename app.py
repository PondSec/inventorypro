from flask import Flask, render_template, jsonify, request, g, redirect, url_for, session, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from functools import wraps
import os
import csv
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO, StringIO
import base64


app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24).hex()

DATABASE = 'inventory.db'
PRO_ENABLED = os.getenv('INVENTORY_PRO_ENABLED', '0') == '1'
PRO_FEATURES = [
    "maintenance_schedule",
    "csv_export",
    "advanced_analytics"
]
FREE_FEATURES = [
    "tags",
    "notes",
    "activity_feed"
]

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        c = db.cursor()

        # Tabellen erstellen (wie zuvor)
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                otp_secret TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT,
                fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                serial_number TEXT,
                specs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS device_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS device_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Default-Kategorien
        default_categories = [
            ("CPU", "cpu", '{"cores":"number","clock":"text","manufacturer":"text"}'),
            ("GPU", "gpu", '{"vram":"text","model":"text","manufacturer":"text"}'),
            ("RAM", "memory", '{"size":"text","type":"text","speed":"text"}')
        ]
        c.executemany('''
            INSERT OR IGNORE INTO categories (name, icon, fields)
            VALUES (?, ?, ?)
        ''', default_categories)

        # Temporären Setup-Admin erstellen (nur wenn noch kein anderer User existiert)
        existing_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if existing_users == 0:
            password_hash = generate_password_hash('admin')
            try:
                c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                         ('admin', password_hash))
                print("\n[!] TEMPORÄRER ADMIN ERSTELLT:")
                print("    Benutzername: admin")
                print("    Passwort:    admin")
                print("    WICHTIG: Diesen Account nach dem Setup löschen!\n")
            except sqlite3.IntegrityError:
                pass

        db.commit()

# Setup-Funktion zum Benutzer erstellen
def create_user(username, password):
    with app.app_context():
        db = get_db()
        password_hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            db.commit()
            print(f"[+] Benutzer '{username}' erstellt.")
        except sqlite3.IntegrityError:
            print(f"[!] Benutzer '{username}' existiert bereits.")

def delete_user(username):
    with app.app_context():
        db = get_db()
        result = db.execute("DELETE FROM users WHERE username = ?", (username,))
        db.commit()
        if result.rowcount > 0:
            print(f"[✓] Benutzer '{username}' gelöscht.")
        else:
            print(f"[!] Benutzer '{username}' nicht gefunden.")


# Login Required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(db, action, entity_type, entity_id=None, details=None):
    username = session.get('username', 'system')
    db.execute('''
        INSERT INTO activity_log (username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, action, entity_type, entity_id, json.dumps(details or {})))

def pro_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not PRO_ENABLED:
            return jsonify({"error": "Pro feature locked"}), 403
        return f(*args, **kwargs)
    return wrapped

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))

        return render_template('login.html', error="Ungültige Anmeldedaten")

    return render_template('login.html')

@app.route('/logout', methods=['POST'])  # Nur POST erlauben
def logout():
    # Sicherstellen, dass der User eingeloggt war
    if not session.get('logged_in'):
        return jsonify({"error": "Not logged in"}), 401
    
    # Session bereinigen
    session.clear()
    
    # Response mit explizitem Cookie-Löschen
    response = jsonify({"message": "Successfully logged out"})
    response.set_cookie(
        'session',  # Ihr Session-Cookie-Name
        '',
        expires=0,
        path='/',
        secure=True if request.is_secure else False,
        httponly=True,
        samesite='Lax'
    )
    return response

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'))

@app.route('/users')
@login_required
def users_page():
    return render_template('users.html', username=session.get('username'))

@app.route('/api/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_category(category_id):
    db = get_db()

    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data['name'].strip()
            icon = data.get('icon', 'default').strip()
            fields = json.dumps(data['fields'])

            result = db.execute('''
                UPDATE categories 
                SET name = ?, icon = ?, fields = ?
                WHERE id = ?
            ''', (name, icon, fields, category_id))

            if result.rowcount == 0:
                return jsonify({"error": "Kategorie nicht gefunden"}), 404

            log_activity(db, "update", "category", category_id, {"name": name})
            db.commit()
            return jsonify({"status": "updated"}), 200

        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Ungültige Daten: {str(e)}"}), 400

    elif request.method == 'DELETE':
        result = db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Kategorie nicht gefunden"}), 404

        log_activity(db, "delete", "category", category_id)
        db.commit()
        return jsonify({"status": "deleted"}), 200

@app.route('/api/categories', methods=['GET', 'POST'])
@login_required
def handle_categories():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        try:
            db.execute('''
                INSERT INTO categories (name, icon, fields)
                VALUES (?, ?, ?)
            ''', (data['name'], data.get('icon', 'cpu'), json.dumps(data['fields'])))
            log_activity(db, "create", "category", details={"name": data['name']})
            db.commit()
            return jsonify({"status": "success"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Kategorie existiert bereits"}), 400
    
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/devices/<int:device_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_device(device_id):
    db = get_db()

    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data['name'].strip()
            serial_number = data.get('serial_number', '').strip()
            specs = json.dumps(data.get('specs', {}))
            category_id = data.get('category_id')

            result = db.execute('''
                UPDATE devices 
                SET name = ?, serial_number = ?, specs = ?, category_id = ?
                WHERE id = ?
            ''', (name, serial_number, specs, category_id, device_id))

            if result.rowcount == 0:
                return jsonify({"error": "Gerät nicht gefunden"}), 404

            log_activity(db, "update", "device", device_id, {"name": name})
            db.commit()
            return jsonify({"status": "updated"}), 200

        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Ungültige Daten: {str(e)}"}), 400

    elif request.method == 'DELETE':
        result = db.execute('DELETE FROM devices WHERE id = ?', (device_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Gerät nicht gefunden"}), 404

        log_activity(db, "delete", "device", device_id)
        db.commit()
        return jsonify({"status": "deleted"}), 200

@app.route('/api/devices', methods=['POST'])
@login_required
def handle_devices():
    db = get_db()
    try:
        data = request.get_json()
        required_fields = ['name', 'category_id']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Fehlende erforderliche Felder"}), 400

        db.execute('''
            INSERT INTO devices (name, category_id, serial_number, specs)
            VALUES (?, ?, ?, ?)
        ''', (
            data['name'].strip(),
            data['category_id'],
            data.get('serial_number', '').strip(),
            json.dumps(data.get('specs', {}))
        ))
        log_activity(db, "create", "device", details={"name": data['name']})
        db.commit()
        return jsonify({"status": "created"}), 201

    except sqlite3.Error as e:
        return jsonify({"error": f"Datenbankfehler: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Serverfehler: {str(e)}"}), 500

@app.route('/api/devices', methods=['GET'])
@login_required
def get_devices():
    db = get_db()
    category_id = request.args.get('category_id')
    search_query = request.args.get('search', '').strip()

    query = '''
        SELECT d.*, c.name as category_name, c.icon as category_icon 
        FROM devices d
        JOIN categories c ON d.category_id = c.id
    '''
    params = []
    
    conditions = []
    if category_id:
        conditions.append('d.category_id = ?')
        params.append(category_id)
    
    if search_query:
        conditions.append('(d.name LIKE ? OR d.serial_number LIKE ?)')
        params.extend([f'%{search_query}%', f'%{search_query}%'])
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' ORDER BY d.created_at DESC'
    
    devices = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in devices])

@app.route('/api/features', methods=['GET'])
@login_required
def feature_flags():
    return jsonify({
        "pro_enabled": PRO_ENABLED,
        "pro_features": PRO_FEATURES,
        "free_features": FREE_FEATURES
    })

@app.route('/api/activity', methods=['GET'])
@login_required
def activity_feed():
    db = get_db()
    limit = int(request.args.get('limit', 8))
    rows = db.execute('''
        SELECT username, action, entity_type, entity_id, details, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    activity = []
    for row in rows:
        entry = dict(row)
        try:
            entry['details'] = json.loads(entry.get('details') or '{}')
        except json.JSONDecodeError:
            entry['details'] = {}
        activity.append(entry)
    return jsonify(activity)

@app.route('/api/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({"error": "Benutzername und Passwort sind erforderlich"}), 400
        password_hash = generate_password_hash(password)
        try:
            db.execute('''
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            ''', (username, password_hash))
            log_activity(db, "create", "user", details={"username": username})
            db.commit()
            return jsonify({"status": "created"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Benutzername existiert bereits"}), 400

    users = db.execute('SELECT id, username, otp_secret FROM users ORDER BY username').fetchall()
    result = []
    for user in users:
        entry = dict(user)
        entry['otp_enabled'] = bool(entry.pop('otp_secret'))
        result.append(entry)
    return jsonify(result)

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def remove_user(user_id):
    db = get_db()
    current = db.execute('SELECT id FROM users WHERE username = ?', (session.get('username'),)).fetchone()
    if current and current['id'] == user_id:
        return jsonify({"error": "Eigenes Konto kann nicht gelöscht werden"}), 400
    result = db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Benutzer nicht gefunden"}), 404
    log_activity(db, "delete", "user", user_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/users/<int:user_id>/password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    db = get_db()
    data = request.get_json()
    password = data.get('password') or ''
    if not password:
        return jsonify({"error": "Passwort ist erforderlich"}), 400
    password_hash = generate_password_hash(password)
    result = db.execute('''
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    ''', (password_hash, user_id))
    if result.rowcount == 0:
        return jsonify({"error": "Benutzer nicht gefunden"}), 404
    log_activity(db, "update", "user_password", user_id)
    db.commit()
    return jsonify({"status": "updated"}), 200

@app.route('/api/devices/<int:device_id>/tags', methods=['GET', 'POST'])
@login_required
def device_tags(device_id):
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        tag = (data.get('tag') or '').strip()
        if not tag:
            return jsonify({"error": "Tag darf nicht leer sein"}), 400
        db.execute('''
            INSERT INTO device_tags (device_id, tag)
            VALUES (?, ?)
        ''', (device_id, tag))
        log_activity(db, "create", "tag", device_id, {"tag": tag})
        db.commit()
        return jsonify({"status": "created"}), 201

    tags = db.execute('''
        SELECT id, tag, created_at
        FROM device_tags
        WHERE device_id = ?
        ORDER BY created_at DESC
    ''', (device_id,)).fetchall()
    return jsonify([dict(row) for row in tags])

@app.route('/api/devices/<int:device_id>/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def delete_device_tag(device_id, tag_id):
    db = get_db()
    result = db.execute('''
        DELETE FROM device_tags
        WHERE id = ? AND device_id = ?
    ''', (tag_id, device_id))
    if result.rowcount == 0:
        return jsonify({"error": "Tag nicht gefunden"}), 404
    log_activity(db, "delete", "tag", device_id, {"tag_id": tag_id})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/devices/<int:device_id>/notes', methods=['GET', 'POST'])
@login_required
def device_notes(device_id):
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        note = (data.get('note') or '').strip()
        if not note:
            return jsonify({"error": "Notiz darf nicht leer sein"}), 400
        db.execute('''
            INSERT INTO device_notes (device_id, note)
            VALUES (?, ?)
        ''', (device_id, note))
        log_activity(db, "create", "note", device_id)
        db.commit()
        return jsonify({"status": "created"}), 201

    notes = db.execute('''
        SELECT id, note, created_at
        FROM device_notes
        WHERE device_id = ?
        ORDER BY created_at DESC
    ''', (device_id,)).fetchall()
    return jsonify([dict(row) for row in notes])

@app.route('/api/devices/<int:device_id>/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_device_note(device_id, note_id):
    db = get_db()
    result = db.execute('''
        DELETE FROM device_notes
        WHERE id = ? AND device_id = ?
    ''', (note_id, device_id))
    if result.rowcount == 0:
        return jsonify({"error": "Notiz nicht gefunden"}), 404
    log_activity(db, "delete", "note", device_id, {"note_id": note_id})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/maintenance', methods=['GET', 'POST'])
@login_required
@pro_required
def maintenance_tasks():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        device_id = data.get('device_id')
        title = (data.get('title') or '').strip()
        due_date = (data.get('due_date') or '').strip()
        if not device_id or not title:
            return jsonify({"error": "Gerät und Titel sind erforderlich"}), 400
        db.execute('''
            INSERT INTO maintenance_tasks (device_id, title, due_date, status)
            VALUES (?, ?, ?, ?)
        ''', (device_id, title, due_date, 'open'))
        log_activity(db, "create", "maintenance", device_id, {"title": title})
        db.commit()
        return jsonify({"status": "created"}), 201

    device_id = request.args.get('device_id')
    params = []
    query = '''
        SELECT m.id, m.device_id, m.title, m.due_date, m.status, m.created_at, d.name as device_name
        FROM maintenance_tasks m
        JOIN devices d ON d.id = m.device_id
    '''
    if device_id:
        query += ' WHERE m.device_id = ?'
        params.append(device_id)
    query += ' ORDER BY m.created_at DESC'
    tasks = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in tasks])

@app.route('/api/maintenance/<int:task_id>', methods=['PATCH'])
@login_required
@pro_required
def update_maintenance(task_id):
    db = get_db()
    data = request.get_json()
    status = (data.get('status') or '').strip().lower()
    if status not in {'open', 'done'}:
        return jsonify({"error": "Ungültiger Status"}), 400
    result = db.execute('''
        UPDATE maintenance_tasks
        SET status = ?
        WHERE id = ?
    ''', (status, task_id))
    if result.rowcount == 0:
        return jsonify({"error": "Wartung nicht gefunden"}), 404
    log_activity(db, "update", "maintenance", task_id, {"status": status})
    db.commit()
    return jsonify({"status": "updated"}), 200

@app.route('/api/maintenance/summary', methods=['GET'])
@login_required
def maintenance_summary():
    if not PRO_ENABLED:
        return jsonify({"pro_locked": True, "open": 0, "overdue": 0})
    db = get_db()
    open_count = db.execute('''
        SELECT COUNT(*) FROM maintenance_tasks WHERE status = 'open'
    ''').fetchone()[0]
    overdue_count = db.execute('''
        SELECT COUNT(*) FROM maintenance_tasks
        WHERE status = 'open' AND due_date != '' AND date(due_date) < date('now')
    ''').fetchone()[0]
    return jsonify({"pro_locked": False, "open": open_count, "overdue": overdue_count})

@app.route('/api/export/devices', methods=['GET'])
@login_required
@pro_required
def export_devices():
    db = get_db()
    devices = db.execute('''
        SELECT d.id, d.name, d.serial_number, d.specs, d.created_at, c.name as category_name
        FROM devices d
        JOIN categories c ON d.category_id = c.id
        ORDER BY d.created_at DESC
    ''').fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Kategorie", "Besitzer", "Spezifikationen", "Erstellt"])
    for device in devices:
        writer.writerow([
            device['id'],
            device['name'],
            device['category_name'],
            device['serial_number'] or '',
            device['specs'] or '',
            device['created_at']
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8'),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=devices.csv'}
    )

@app.route('/stats')
@login_required
def stats():
    db = get_db()
    
    # 1. Grundstatistiken mit Default-Werten
    total_devices = db.execute('SELECT COUNT(*) FROM devices').fetchone()[0] or 0
    total_categories = db.execute('SELECT COUNT(*) FROM categories').fetchone()[0] or 0
    
    # 2. Kategorieverteilung mit sicherer Abfrage
    categories = db.execute('''
        SELECT c.id, c.name, COUNT(d.id) as device_count
        FROM categories c
        LEFT JOIN devices d ON c.id = d.category_id
        GROUP BY c.id
    ''').fetchall()
    categories_data = [dict(c) for c in categories] if categories else []
    
    # 3. Verbesserte Statusverteilung mit Default-Werten
    status_data = {'Verwendet': 0, 'Lager': 0, 'Defekt': 0}
    devices = db.execute('SELECT specs FROM devices').fetchall()
    for device in devices:
        try:
            specs = json.loads(device['specs']) if device['specs'] else {}
            status = specs.get('Status', 'Verwendet')
            # Normalisiere den Status (entferne Leerzeichen, mache erste Buchstabe groß)
            status = status.strip().capitalize()
            # Falls der Status nicht in unserer Liste ist, zählen wir als "Verwendet"
            if status in status_data:
                status_data[status] += 1
            else:
                status_data['Verwendet'] += 1
        except json.JSONDecodeError:
            status_data['Verwendet'] += 1
    
    # 4. Letzte Geräte mit sicherer Abfrage
    recent_devices = db.execute('''
        SELECT d.name, c.name as category_name, d.serial_number, d.created_at
        FROM devices d
        JOIN categories c ON d.category_id = c.id
        ORDER BY d.created_at DESC
        LIMIT 5
    ''').fetchall()
    recent_devices_data = [dict(d) for d in recent_devices] if recent_devices else []
    
    context = {
        'total_devices': total_devices,
        'total_categories': total_categories,
        'categories': categories_data,
        'status_data': status_data,
        'recent_devices': recent_devices_data,
        'username': session.get('username', '')
    }
    
    return render_template('stats.html', **context)

@app.route('/api/otp/setup', methods=['POST'])
@login_required
def setup_otp():
    username = session.get('username')
    db = get_db()

    # 1. Vorher prüfen, ob bereits ein OTP eingerichtet ist
    user = db.execute("SELECT otp_secret FROM users WHERE username = ?", (username,)).fetchone()
    if user and user['otp_secret']:
        # Bereits eingerichtet – nur Status zurückgeben
        return jsonify({'enabled': True}), 200

    # 2. Wenn nicht vorhanden, neues Secret generieren und speichern
    secret = pyotp.random_base32()
    db.execute("UPDATE users SET otp_secret = ? WHERE username = ?", (secret, username))
    db.commit()

    # 3. QR-Code generieren
    issuer_name = "Inventory Pro"
    otp_uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer_name)
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(otp_uri, image_factory=factory)
    stream = BytesIO()
    img.save(stream)
    qr_code = stream.getvalue().decode()
    
    qr_img = qrcode.make(otp_uri)
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    img_str = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

    # 4. Secret + QR zurückgeben
    return jsonify({
        'enabled': False,
        'secret': secret,
        'qr_code': img_str
    })


@app.route('/verify')
@login_required
def verify():
    return render_template('verify_otp.html')

@app.route('/api/otp/verify', methods=['POST'])
@login_required
def verify_otp():
    code = request.json.get('code')
    username = session.get('username')

    db = get_db()
    user = db.execute('SELECT otp_secret FROM users WHERE username = ?', (username,)).fetchone()

    if user and pyotp.TOTP(user['otp_secret']).verify(code):
        return jsonify({"verified": True}), 200
    else:
        return jsonify({"verified": False}), 401

@app.route('/reset', methods=['GET'])
def reset_page():
    return render_template('reset_password.html')

@app.route('/reset', methods=['POST'])
def reset_password():
    username = request.form.get('username')
    otp_code = request.form.get('otp')
    new_password = request.form.get('new_password')

    if not all([username, otp_code, new_password]):
        return render_template('reset_password.html', error="Alle Felder ausfüllen!")

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if not user:
        return render_template('reset_password.html', error="Benutzer existiert nicht.")

    if not user['otp_secret']:
        return render_template('reset_password.html', error="Kein OTP eingerichtet.")

    if not pyotp.TOTP(user['otp_secret']).verify(otp_code):
        return render_template('reset_password.html', error="OTP ungültig.")

    # Neues Passwort setzen
    new_hash = generate_password_hash(new_password)
    db.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, username))
    db.commit()

    #return render_template('reset_password.html', success="Passwort erfolgreich geändert!")
    return redirect(url_for('login'))

@app.route('/api/otp/disable', methods=['POST'])
@login_required
def disable_otp():
    username = session.get('username')
    db = get_db()

    # OTP löschen
    db.execute('UPDATE users SET otp_secret = NULL WHERE username = ?', (username,))
    db.commit()
    return jsonify({'disabled': True}), 200

@app.route('/api/otp/status', methods=['GET'])
@login_required
def otp_status():
    username = session.get('username')
    db = get_db()
    user = db.execute("SELECT otp_secret FROM users WHERE username = ?", (username,)).fetchone()
    return jsonify({'enabled': bool(user and user['otp_secret'])})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
