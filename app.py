from flask import Flask, render_template, jsonify, request, g, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from functools import wraps
import os
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO


app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24).hex()

DATABASE = 'inventory.db'

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

        # Benutzer-Tabelle
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                otp_secret TEXT
            )
        ''')

        # Kategorien-Tabelle
        c.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT,
                fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Geräte-Tabelle
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

            db.commit()
            return jsonify({"status": "updated"}), 200

        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Ungültige Daten: {str(e)}"}), 400

    elif request.method == 'DELETE':
        result = db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Kategorie nicht gefunden"}), 404

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

            db.commit()
            return jsonify({"status": "updated"}), 200

        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Ungültige Daten: {str(e)}"}), 400

    elif request.method == 'DELETE':
        result = db.execute('DELETE FROM devices WHERE id = ?', (device_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Gerät nicht gefunden"}), 404

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
    # 1. Neues Secret generieren
    secret = pyotp.random_base32()

    # 2. Username aus Session holen
    username = session.get('username')

    # 3. In der DB speichern
    db = get_db()
    db.execute("UPDATE users SET otp_secret = ? WHERE username = ?", (secret, username))
    db.commit()

    # 4. QR-Code generieren
    issuer_name = "DeinSystemname"
    otp_uri = pyotp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name=issuer_name
    )
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(otp_uri, image_factory=factory)
    stream = BytesIO()
    img.save(stream)
    qr_code = stream.getvalue().decode()

    # 5. Secret + QR zurückgeben
    return jsonify({
        'secret': secret,
        'qr_code': qr_code
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


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)