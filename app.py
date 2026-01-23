from flask import Flask, render_template, jsonify, request, g, redirect, url_for, session, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from datetime import datetime
from functools import wraps
import os
import csv
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO, StringIO
import base64
import secrets
from ldap3 import Server, Connection, BASE, ALL
from ldap3.utils.conv import escape_filter_chars
from email.message import EmailMessage
import smtplib


app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24).hex()

DATABASE = 'inventory.db'
PRO_ENABLED = True
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

DEFAULT_ROLE_NAME = "Mitarbeiter"
PERMISSIONS = [
    {
        "key": "categories.view",
        "label": "Kategorien anzeigen",
        "description": "Kategorien und Inventarübersicht einsehen.",
        "group": "Inventar"
    },
    {
        "key": "categories.manage",
        "label": "Kategorien verwalten",
        "description": "Kategorien erstellen, bearbeiten und löschen.",
        "group": "Inventar"
    },
    {
        "key": "devices.view",
        "label": "Geräte anzeigen",
        "description": "Geräteübersicht einsehen.",
        "group": "Inventar"
    },
    {
        "key": "devices.manage",
        "label": "Geräte verwalten",
        "description": "Geräte erstellen, bearbeiten und löschen.",
        "group": "Inventar"
    },
    {
        "key": "assets.view",
        "label": "Assets anzeigen",
        "description": "Assets und Zuweisungen einsehen.",
        "group": "Inventar"
    },
    {
        "key": "assets.manage",
        "label": "Assets verwalten",
        "description": "Assets erstellen, bearbeiten und löschen.",
        "group": "Inventar"
    },
    {
        "key": "locations.view",
        "label": "Standorte anzeigen",
        "description": "Standorte und Details einsehen.",
        "group": "Inventar"
    },
    {
        "key": "locations.manage",
        "label": "Standorte verwalten",
        "description": "Standorte erstellen, bearbeiten und löschen.",
        "group": "Inventar"
    },
    {
        "key": "maintenance.view",
        "label": "Wartungen anzeigen",
        "description": "Wartungsaufgaben und Status einsehen.",
        "group": "Inventar"
    },
    {
        "key": "maintenance.manage",
        "label": "Wartungen verwalten",
        "description": "Wartungsaufgaben erstellen und aktualisieren.",
        "group": "Inventar"
    },
    {
        "key": "tickets.view_all",
        "label": "Alle Tickets anzeigen",
        "description": "Zugriff auf alle Tickets im System.",
        "group": "Tickets"
    },
    {
        "key": "tickets.view_own",
        "label": "Eigene Tickets anzeigen",
        "description": "Nur eigene Tickets einsehen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.create",
        "label": "Tickets erstellen",
        "description": "Tickets anlegen und einreichen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.update",
        "label": "Tickets bearbeiten",
        "description": "Tickets bearbeiten und Status ändern.",
        "group": "Tickets"
    },
    {
        "key": "tickets.update_own",
        "label": "Eigene Tickets bearbeiten",
        "description": "Eigene Tickets bearbeiten.",
        "group": "Tickets"
    },
    {
        "key": "tickets.delete",
        "label": "Tickets löschen",
        "description": "Tickets löschen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.delete_own",
        "label": "Eigene Tickets löschen",
        "description": "Eigene Tickets löschen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.comment",
        "label": "Kommentare schreiben",
        "description": "Kommentare zu allen Tickets hinzufügen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.comment_own",
        "label": "Eigene Tickets kommentieren",
        "description": "Kommentare auf eigene Tickets schreiben.",
        "group": "Tickets"
    },
    {
        "key": "tickets.comment_internal",
        "label": "Interne Kommentare",
        "description": "Interne Ticket-Kommentare verfassen.",
        "group": "Tickets"
    },
    {
        "key": "tickets.watch",
        "label": "Watcher verwalten",
        "description": "Watcher für alle Tickets verwalten.",
        "group": "Tickets"
    },
    {
        "key": "tickets.watch_own",
        "label": "Eigene Watcher",
        "description": "Watcher für eigene Tickets verwalten.",
        "group": "Tickets"
    },
    {
        "key": "ticket_categories.manage",
        "label": "Ticket-Kategorien verwalten",
        "description": "Ticket-Kategorien erstellen und bearbeiten.",
        "group": "Tickets"
    },
    {
        "key": "ticket_alerts.manage",
        "label": "Ticket-Alerts verwalten",
        "description": "Alert-Regeln konfigurieren.",
        "group": "Tickets"
    },
    {
        "key": "notifications.manage",
        "label": "Benachrichtigungen verwalten",
        "description": "E-Mail-Benachrichtigungen konfigurieren.",
        "group": "Tickets"
    },
    {
        "key": "users.manage",
        "label": "Benutzer verwalten",
        "description": "Benutzer anlegen, löschen und Passwörter zurücksetzen.",
        "group": "Administration"
    },
    {
        "key": "roles.manage",
        "label": "Rollen verwalten",
        "description": "Rollen erstellen, bearbeiten und löschen.",
        "group": "Administration"
    },
    {
        "key": "roles.assign",
        "label": "Rollen zuweisen",
        "description": "Rollen Benutzern zuweisen.",
        "group": "Administration"
    },
    {
        "key": "stats.view",
        "label": "Statistiken anzeigen",
        "description": "Dashboards und Statistiken einsehen.",
        "group": "Reporting"
    },
    {
        "key": "activity.view",
        "label": "Aktivitätslog anzeigen",
        "description": "Aktivitätslog einsehen.",
        "group": "Reporting"
    }
]

DEFAULT_ROLES = [
    {
        "name": "Admin",
        "description": "Voller Zugriff auf alle Funktionen.",
        "is_system": 1,
        "is_superuser": 1,
        "permissions": "ALL"
    },
    {
        "name": "Mitarbeiter",
        "description": "Interne Mitarbeitende mit Zugriff auf Inventar und Tickets.",
        "is_system": 1,
        "is_superuser": 0,
        "permissions": [
            "categories.view",
            "categories.manage",
            "devices.view",
            "devices.manage",
            "assets.view",
            "assets.manage",
            "locations.view",
            "locations.manage",
            "maintenance.view",
            "maintenance.manage",
            "tickets.view_all",
            "tickets.create",
            "tickets.update",
            "tickets.delete",
            "tickets.comment",
            "tickets.comment_internal",
            "tickets.watch",
            "ticket_categories.manage",
            "ticket_alerts.manage",
            "notifications.manage",
            "stats.view",
            "activity.view"
        ]
    },
    {
        "name": "Kunde",
        "description": "Externe Kunden mit Zugriff auf eigene Tickets.",
        "is_system": 1,
        "is_superuser": 0,
        "permissions": [
            "tickets.view_own",
            "tickets.create",
            "tickets.comment_own",
            "tickets.watch_own"
        ]
    }
]

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def seed_permissions(db):
    for perm in PERMISSIONS:
        db.execute('''
            INSERT OR IGNORE INTO permissions (key, label, description, group_name)
            VALUES (?, ?, ?, ?)
        ''', (perm["key"], perm["label"], perm["description"], perm["group"]))
        db.execute('''
            UPDATE permissions
            SET label = ?, description = ?, group_name = ?
            WHERE key = ?
        ''', (perm["label"], perm["description"], perm["group"], perm["key"]))

def seed_roles(db):
    for role in DEFAULT_ROLES:
        db.execute('''
            INSERT OR IGNORE INTO roles (name, description, is_system, is_superuser)
            VALUES (?, ?, ?, ?)
        ''', (role["name"], role["description"], role["is_system"], role["is_superuser"]))
        db.execute('''
            UPDATE roles
            SET description = ?, is_system = ?, is_superuser = ?
            WHERE name = ?
        ''', (role["description"], role["is_system"], role["is_superuser"], role["name"]))

    role_rows = db.execute('SELECT id, name, is_superuser FROM roles').fetchall()
    role_map = {row["name"]: row for row in role_rows}
    permission_rows = db.execute('SELECT id, key FROM permissions').fetchall()
    permission_map = {row["key"]: row["id"] for row in permission_rows}

    for role in DEFAULT_ROLES:
        role_row = role_map.get(role["name"])
        if not role_row:
            continue
        role_id = role_row["id"]
        if role.get("permissions") == "ALL":
            permission_ids = list(permission_map.values())
        else:
            permission_ids = [permission_map[key] for key in role.get("permissions", []) if key in permission_map]
        for permission_id in permission_ids:
            db.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role_id, permission_id))

def assign_user_role(db, user_id, role_name):
    role = db.execute('SELECT id FROM roles WHERE name = ?', (role_name,)).fetchone()
    if not role:
        return
    db.execute('''
        INSERT OR IGNORE INTO user_roles (user_id, role_id)
        VALUES (?, ?)
    ''', (user_id, role["id"]))

def ensure_default_roles(db):
    default_role = db.execute('SELECT id FROM roles WHERE name = ?', (DEFAULT_ROLE_NAME,)).fetchone()
    if not default_role:
        return
    users_without_role = db.execute('''
        SELECT u.id FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        WHERE ur.user_id IS NULL
    ''').fetchall()
    for user in users_without_role:
        db.execute('''
            INSERT INTO user_roles (user_id, role_id)
            VALUES (?, ?)
        ''', (user["id"], default_role["id"]))

def ensure_admin_user(db):
    admin_exists = db.execute('''
        SELECT 1
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.is_superuser = 1
        LIMIT 1
    ''').fetchone()
    if admin_exists:
        return

    username = "admin"
    while db.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
        username = f"admin-{secrets.token_hex(3)}"

    password = secrets.token_urlsafe(12)
    password_hash = generate_password_hash(password)
    cursor = db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
    assign_user_role(db, cursor.lastrowid, "Admin")

    print("\n[!] ADMIN-KONTO ERSTELLT (kein Admin vorhanden):")
    print(f"    Benutzername: {username}")
    print(f"    Passwort:    {password}")
    print("    WICHTIG: Passwort nach dem ersten Login ändern!\n")

def get_user_access(db):
    if hasattr(g, 'user_access'):
        return g.user_access
    username = session.get('username')
    if not username:
        g.user_access = {
            "user": None,
            "roles": [],
            "permissions": set(),
            "is_superuser": False
        }
        return g.user_access
    user = db.execute('SELECT id, username FROM users WHERE username = ?', (username,)).fetchone()
    if not user:
        g.user_access = {
            "user": None,
            "roles": [],
            "permissions": set(),
            "is_superuser": False
        }
        return g.user_access
    roles = db.execute('''
        SELECT r.id, r.name, r.is_superuser
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        ORDER BY r.name
    ''', (user["id"],)).fetchall()
    is_superuser = any(role["is_superuser"] for role in roles)
    if is_superuser:
        permission_rows = db.execute('SELECT key FROM permissions').fetchall()
        permissions = {row["key"] for row in permission_rows}
    else:
        permission_rows = db.execute('''
            SELECT DISTINCT p.key
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            JOIN user_roles ur ON ur.role_id = rp.role_id
            WHERE ur.user_id = ?
        ''', (user["id"],)).fetchall()
        permissions = {row["key"] for row in permission_rows}
    g.user_access = {
        "user": dict(user),
        "roles": [dict(role) for role in roles],
        "permissions": permissions,
        "is_superuser": is_superuser
    }
    return g.user_access

def user_can(permission_key):
    access = get_user_access(get_db())
    return access["is_superuser"] or permission_key in access["permissions"]

def require_permissions(*permission_keys):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            access = get_user_access(get_db())
            if access["is_superuser"]:
                return f(*args, **kwargs)
            if not any(key in access["permissions"] for key in permission_keys):
                return jsonify({"error": "Keine Berechtigung"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

def require_permission(permission_key):
    return require_permissions(permission_key)

def get_post_login_redirect(access):
    if access["is_superuser"]:
        return url_for('index')
    landing_targets = [
        (("categories.view", "categories.manage"), "index"),
        (("tickets.view_all", "tickets.view_own", "tickets.create"), "tickets_page"),
        (("stats.view",), "stats"),
        (("users.manage",), "users_page"),
        (("locations.view", "locations.manage"), "locations_page")
    ]
    for permissions, endpoint in landing_targets:
        if any(permission in access["permissions"] for permission in permissions):
            return url_for(endpoint)
    return url_for('index')

def ensure_ticket_access(ticket, access, require_owner_permission=False):
    if access["is_superuser"]:
        return True
    if "tickets.view_all" in access["permissions"]:
        return True
    if "tickets.view_own" in access["permissions"]:
        return ticket and ticket.get("created_by") == session.get('username')
    if require_owner_permission:
        return ticket and ticket.get("created_by") == session.get('username')
    return False

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
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_system INTEGER DEFAULT 0,
                is_superuser INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                description TEXT,
                group_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                UNIQUE(role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id),
                FOREIGN KEY (permission_id) REFERENCES permissions(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                UNIQUE(user_id, role_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (role_id) REFERENCES roles(id)
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
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                serial_number TEXT,
                location_id INTEGER,
                specs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (location_id) REFERENCES locations(id)
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
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT,
                specs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        try:
            c.execute('ALTER TABLE assets ADD COLUMN notes TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE assets ADD COLUMN specs TEXT')
        except sqlite3.OperationalError:
            pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                device_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id),
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

        c.execute('''
            CREATE TABLE IF NOT EXISTS ticket_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#2563eb',
                sla_hours INTEGER DEFAULT 72,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category_id INTEGER,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'open',
                requester_name TEXT,
                requester_email TEXT,
                created_by TEXT,
                assignee TEXT,
                assignee_email TEXT,
                due_date TEXT,
                tags TEXT,
                custom_fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES ticket_categories(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ticket_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                author TEXT,
                body TEXT NOT NULL,
                is_internal INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ticket_watchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ticket_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status_match TEXT,
                priority_match TEXT,
                category_id INTEGER,
                recipient_emails TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES ticket_categories(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                smtp_host TEXT,
                smtp_port INTEGER DEFAULT 587,
                smtp_username TEXT,
                smtp_password TEXT,
                smtp_from TEXT,
                use_tls INTEGER DEFAULT 1,
                default_recipients TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('INSERT OR IGNORE INTO notification_settings (id) VALUES (1)')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ad_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                server_url TEXT,
                base_dn TEXT,
                bind_dn TEXT,
                bind_password TEXT,
                user_attribute TEXT DEFAULT 'sAMAccountName',
                domain TEXT,
                use_ssl INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('INSERT OR IGNORE INTO ad_settings (id) VALUES (1)')

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

        default_locations = [
            ("Lager", "Zentrales Lager"),
            ("Büro", "Arbeitsplätze und Office-Equipment")
        ]
        c.executemany('''
            INSERT OR IGNORE INTO locations (name, description)
            VALUES (?, ?)
        ''', default_locations)

        default_ticket_categories = [
            ("Allgemein", "Allgemeine Anfragen und Rückfragen", "#2563eb", 72, 1),
            ("Incident", "Störungen und dringende Ausfälle", "#dc2626", 24, 0),
            ("Service Request", "Bestellungen und Service-Anfragen", "#0f766e", 120, 0),
            ("Change", "Geplante Änderungen und Wartungen", "#7c3aed", 168, 0)
        ]
        c.executemany('''
            INSERT OR IGNORE INTO ticket_categories (name, description, color, sla_hours, is_default)
            VALUES (?, ?, ?, ?, ?)
        ''', default_ticket_categories)

        try:
            c.execute('ALTER TABLE devices ADD COLUMN location_id INTEGER')
        except sqlite3.OperationalError:
            pass

        seed_permissions(db)
        seed_roles(db)
        ensure_default_roles(db)
        ensure_admin_user(db)

        db.commit()

# Setup-Funktion zum Benutzer erstellen
def create_user(username, password):
    with app.app_context():
        db = get_db()
        password_hash = generate_password_hash(password)
        try:
            cursor = db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            assign_user_role(db, cursor.lastrowid, DEFAULT_ROLE_NAME)
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
        return f(*args, **kwargs)
    return wrapped

def parse_email_list(value):
    if not value:
        return []
    if isinstance(value, list):
        emails = value
    else:
        emails = value.split(',')
    return [email.strip() for email in emails if email and email.strip()]

def get_notification_settings(db):
    settings = db.execute('SELECT * FROM notification_settings WHERE id = 1').fetchone()
    if not settings:
        db.execute('INSERT INTO notification_settings (id) VALUES (1)')
        db.commit()
        settings = db.execute('SELECT * FROM notification_settings WHERE id = 1').fetchone()
    return settings

def serialize_notification_settings(settings):
    if not settings:
        return {
            "enabled": False,
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_from": "",
            "use_tls": True,
            "default_recipients": "",
            "has_password": False
        }
    return {
        "enabled": bool(settings["enabled"]),
        "smtp_host": settings["smtp_host"] or "",
        "smtp_port": settings["smtp_port"] or 587,
        "smtp_username": settings["smtp_username"] or "",
        "smtp_from": settings["smtp_from"] or "",
        "use_tls": bool(settings["use_tls"]),
        "default_recipients": settings["default_recipients"] or "",
        "has_password": bool(settings["smtp_password"])
    }

def send_notification_email(settings, recipients, subject, body):
    if not settings or not settings["enabled"]:
        return False
    recipients = parse_email_list(recipients)
    if not recipients:
        return False
    smtp_host = settings["smtp_host"]
    smtp_port = settings["smtp_port"] or 587
    smtp_from = settings["smtp_from"] or settings["smtp_username"]
    if not smtp_host or not smtp_from:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if settings["use_tls"]:
                server.starttls()
            if settings["smtp_username"] and settings["smtp_password"]:
                server.login(settings["smtp_username"], settings["smtp_password"])
            server.send_message(message)
        return True
    except Exception:
        return False

def format_ticket_subject(ticket, prefix):
    return f"{prefix} #{ticket['id']} - {ticket['title']}"

def build_ticket_email_body(ticket, header, comment=None):
    lines = [
        header,
        "",
        f"Ticket: #{ticket['id']} - {ticket['title']}",
        f"Status: {ticket.get('status')}",
        f"Priorität: {ticket.get('priority')}",
        f"Kategorie: {ticket.get('category_name') or 'Unbekannt'}",
        f"Zuständig: {ticket.get('assignee') or '-'}",
        f"Fällig: {ticket.get('due_date') or '-'}",
        "",
        "Beschreibung:",
        ticket.get('description') or "-"
    ]
    if comment:
        lines.extend(["", "Neuer Kommentar:", comment])
    return "\n".join(lines)

def trigger_ticket_notifications(db, event_type, ticket, comment=None):
    settings = get_notification_settings(db)
    if not settings or not settings["enabled"]:
        return

    recipients = []
    recipients.extend(parse_email_list(settings["default_recipients"]))
    recipients.extend(parse_email_list(ticket.get("requester_email")))
    recipients.extend(parse_email_list(ticket.get("assignee_email")))

    watcher_rows = db.execute('SELECT email FROM ticket_watchers WHERE ticket_id = ?', (ticket["id"],)).fetchall()
    recipients.extend([row["email"] for row in watcher_rows])

    alerts = db.execute('''
        SELECT * FROM ticket_alerts
        WHERE is_enabled = 1 AND event_type = ?
    ''', (event_type,)).fetchall()

    for alert in alerts:
        if alert["status_match"] and alert["status_match"] != ticket.get("status"):
            continue
        if alert["priority_match"] and alert["priority_match"] != ticket.get("priority"):
            continue
        if alert["category_id"] and alert["category_id"] != ticket.get("category_id"):
            continue
        recipients.extend(parse_email_list(alert["recipient_emails"]))

    unique_recipients = list(dict.fromkeys([email for email in recipients if email]))
    if not unique_recipients:
        return

    subject = format_ticket_subject(ticket, "Ticket Update")
    header = f"Es gibt ein Update zum Ticket {ticket['id']}."
    if event_type == "created":
        header = f"Ein neues Ticket wurde erstellt."
        subject = format_ticket_subject(ticket, "Neues Ticket")
    elif event_type == "commented":
        header = "Es gibt einen neuen Kommentar."
        subject = format_ticket_subject(ticket, "Kommentar erhalten")
    elif event_type == "status_changed":
        header = f"Der Status wurde auf '{ticket.get('status')}' geändert."
        subject = format_ticket_subject(ticket, "Status geändert")

    body = build_ticket_email_body(ticket, header, comment=comment)
    send_notification_email(settings, unique_recipients, subject, body)

def fetch_ticket(db, ticket_id):
    ticket = db.execute('''
        SELECT t.*, c.name as category_name, c.color as category_color
        FROM tickets t
        LEFT JOIN ticket_categories c ON t.category_id = c.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()
    return dict(ticket) if ticket else None

def normalize_ticket_row(row):
    ticket = dict(row)
    try:
        ticket['tags'] = json.loads(ticket.get('tags') or '[]')
    except json.JSONDecodeError:
        ticket['tags'] = []
    try:
        ticket['custom_fields'] = json.loads(ticket.get('custom_fields') or '[]')
    except json.JSONDecodeError:
        ticket['custom_fields'] = []
    return ticket

def get_ad_settings(db):
    settings = db.execute('SELECT * FROM ad_settings WHERE id = 1').fetchone()
    if not settings:
        db.execute('INSERT INTO ad_settings (id) VALUES (1)')
        db.commit()
        settings = db.execute('SELECT * FROM ad_settings WHERE id = 1').fetchone()
    return settings

def serialize_ad_settings(settings):
    if not settings:
        return {
            "enabled": False,
            "server_url": "",
            "base_dn": "",
            "bind_dn": "",
            "user_attribute": "sAMAccountName",
            "domain": "",
            "use_ssl": False,
            "has_bind_password": False
        }
    return {
        "enabled": bool(settings["enabled"]),
        "server_url": settings["server_url"] or "",
        "base_dn": settings["base_dn"] or "",
        "bind_dn": settings["bind_dn"] or "",
        "user_attribute": settings["user_attribute"] or "sAMAccountName",
        "domain": settings["domain"] or "",
        "use_ssl": bool(settings["use_ssl"]),
        "has_bind_password": bool(settings["bind_password"])
    }

def domain_to_base_dn(domain):
    parts = [part for part in (domain or "").split('.') if part]
    if not parts:
        return ""
    return ",".join(f"DC={part}" for part in parts)

def discover_base_dn(server, connection, domain):
    base_dn = ""
    try:
        naming_contexts = (
            server.info.other.get("defaultNamingContext")
            or server.info.other.get("defaultNamingContexts")
            or []
        )
        if naming_contexts:
            base_dn = naming_contexts[0]
    except Exception:
        base_dn = ""
    if not base_dn:
        try:
            connection.search("", "(objectClass=*)", search_scope=BASE, attributes=["defaultNamingContext"])
            if connection.entries:
                base_dn = connection.entries[0].defaultNamingContext.value
        except Exception:
            base_dn = ""
    if not base_dn:
        base_dn = domain_to_base_dn(domain)
    return base_dn

def build_ad_principals(username, domain):
    principals = []
    if not username:
        return principals
    username = username.strip()
    if not username:
        return principals

    principals.append(username)

    if "\\" in username:
        if domain:
            account_name = username.split("\\", 1)[1]
            principals.append(f"{account_name}@{domain}")
        return list(dict.fromkeys(principals))

    if "@" in username:
        if domain:
            account_name = username.split("@", 1)[0]
            principals.append(f"{domain}\\{account_name}")
        return list(dict.fromkeys(principals))

    if domain:
        principals.append(f"{username}@{domain}")
        principals.append(f"{domain}\\{username}")

    return list(dict.fromkeys(principals))

def authenticate_ad_user(username, password, settings):
    if not settings or not settings["enabled"]:
        return False
    server_url = settings["server_url"] or ""
    base_dn = settings["base_dn"] or ""
    if not server_url or not base_dn:
        return False
    if not password:
        return False

    server = Server(server_url, use_ssl=bool(settings["use_ssl"]))
    bind_dn = settings["bind_dn"] or ""
    bind_password = settings["bind_password"] or ""
    user_attribute = settings["user_attribute"] or "sAMAccountName"
    domain = settings["domain"] or ""

    if bind_dn:
        try:
            admin_conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        except Exception:
            return False
        safe_username = escape_filter_chars(username)
        search_filter = f"({user_attribute}={safe_username})"
        admin_conn.search(base_dn, search_filter, attributes=["distinguishedName"])
        if not admin_conn.entries:
            admin_conn.unbind()
            return False
        user_dn = admin_conn.entries[0].entry_dn
        admin_conn.unbind()
        try:
            user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
            user_conn.unbind()
            return True
        except Exception:
            return False

    for user_principal in build_ad_principals(username, domain):
        try:
            user_conn = Connection(server, user=user_principal, password=password, auto_bind=True)
            user_conn.unbind()
            return True
        except Exception:
            continue
    return False

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
            access = get_user_access(db)
            log_activity(db, "login", "user", user['id'], {"username": username})
            db.commit()
            return redirect(get_post_login_redirect(access))

        ad_settings = get_ad_settings(db)
        if authenticate_ad_user(username, password, ad_settings):
            existing_user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if not existing_user:
                placeholder_password = generate_password_hash(os.urandom(24).hex())
                cursor = db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, placeholder_password))
                assign_user_role(db, cursor.lastrowid, DEFAULT_ROLE_NAME)
                existing_user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            session['logged_in'] = True
            session['username'] = username
            access = get_user_access(db)
            log_activity(db, "login", "user", existing_user['id'], {"username": username, "source": "ad"})
            db.commit()
            return redirect(get_post_login_redirect(access))

        log_activity(db, "login_failed", "user", details={"username": username})
        db.commit()
        return render_template('login.html', error="Ungültige Anmeldedaten")

    return render_template('login.html')

@app.route('/logout', methods=['POST'])  # Nur POST erlauben
def logout():
    # Sicherstellen, dass der User eingeloggt war
    if not session.get('logged_in'):
        return jsonify({"error": "Not logged in"}), 401

    db = get_db()
    log_activity(db, "logout", "user", details={"username": session.get('username')})
    db.commit()
    
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
@require_permissions('categories.view', 'categories.manage')
def index():
    access = get_user_access(get_db())
    return render_template('index.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/users')
@login_required
@require_permission('users.manage')
def users_page():
    access = get_user_access(get_db())
    return render_template('users.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/locations')
@login_required
@require_permissions('locations.view', 'locations.manage')
def locations_page():
    access = get_user_access(get_db())
    return render_template('locations.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/tickets')
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own', 'tickets.create')
def tickets_page():
    access = get_user_access(get_db())
    return render_template('tickets.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/api/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_category(category_id):
    db = get_db()
    if not user_can('categories.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403

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
        device_rows = db.execute('SELECT id FROM devices WHERE category_id = ?', (category_id,)).fetchall()
        device_ids = [row['id'] for row in device_rows]

        for device_id in device_ids:
            db.execute('DELETE FROM device_tags WHERE device_id = ?', (device_id,))
            db.execute('DELETE FROM device_notes WHERE device_id = ?', (device_id,))
            db.execute('DELETE FROM maintenance_tasks WHERE device_id = ?', (device_id,))

        if device_ids:
            db.execute('DELETE FROM devices WHERE category_id = ?', (category_id,))

        result = db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Kategorie nicht gefunden"}), 404

        log_activity(db, "delete", "category", category_id, {"deleted_devices": len(device_ids)})
        db.commit()
        return jsonify({"status": "deleted"}), 200

@app.route('/api/categories', methods=['GET', 'POST'])
@login_required
def handle_categories():
    db = get_db()
    if request.method == 'POST':
        if not user_can('categories.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
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
    
    if not (user_can('categories.view') or user_can('categories.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/devices/<int:device_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_device(device_id):
    db = get_db()
    if not user_can('devices.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data['name'].strip()
            serial_number = data.get('serial_number', '').strip()
            specs = json.dumps(data.get('specs', {}))
            category_id = data.get('category_id')
            location_id = data.get('location_id')

            result = db.execute('''
                UPDATE devices 
                SET name = ?, serial_number = ?, specs = ?, category_id = ?, location_id = ?
                WHERE id = ?
            ''', (name, serial_number, specs, category_id, location_id, device_id))

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
    if not user_can('devices.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    try:
        data = request.get_json()
        required_fields = ['name', 'category_id']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Fehlende erforderliche Felder"}), 400

        db.execute('''
            INSERT INTO devices (name, category_id, serial_number, location_id, specs)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'].strip(),
            data['category_id'],
            data.get('serial_number', '').strip(),
            data.get('location_id'),
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
    if not (user_can('devices.view') or user_can('devices.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    category_id = request.args.get('category_id')
    search_query = request.args.get('search', '').strip()

    query = '''
        SELECT d.*, c.name as category_name, c.icon as category_icon, l.name as location_name
        FROM devices d
        JOIN categories c ON d.category_id = c.id
        LEFT JOIN locations l ON d.location_id = l.id
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

@app.route('/api/assets', methods=['GET', 'POST'])
@login_required
def manage_assets():
    db = get_db()
    if request.method == 'POST':
        if not user_can('assets.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json()
        name = (data.get('name') or '').strip()
        notes = (data.get('notes') or '').strip()
        specs = json.dumps(data.get('specs', {}))
        device_ids = data.get('device_ids') or []
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO assets (name, notes, specs)
                VALUES (?, ?, ?)
            ''', (name, notes, specs))
            asset_id = cursor.lastrowid
            for device_id in device_ids:
                db.execute('''
                    INSERT INTO asset_devices (asset_id, device_id)
                    VALUES (?, ?)
                ''', (asset_id, device_id))
            log_activity(db, "create", "asset", asset_id, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": asset_id}), 201
        except sqlite3.Error as e:
            return jsonify({"error": f"Datenbankfehler: {str(e)}"}), 500

    if not (user_can('assets.view') or user_can('assets.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    assets = db.execute('''
        SELECT a.*, COUNT(ad.device_id) as device_count
        FROM assets a
        LEFT JOIN asset_devices ad ON a.id = ad.asset_id
        GROUP BY a.id
        ORDER BY a.created_at DESC
    ''').fetchall()
    result = []
    for row in assets:
        asset = dict(row)
        try:
            asset['specs'] = json.loads(asset.get('specs') or '{}')
        except json.JSONDecodeError:
            asset['specs'] = {}
        result.append(asset)
    return jsonify(result)

@app.route('/api/assets/<int:asset_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def asset_detail(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT * FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404

    if request.method == 'GET':
        if not (user_can('assets.view') or user_can('assets.manage')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        device_rows = db.execute('''
            SELECT d.*, c.name as category_name, c.icon as category_icon, l.name as location_name
            FROM devices d
            JOIN asset_devices ad ON ad.device_id = d.id
            JOIN categories c ON d.category_id = c.id
            LEFT JOIN locations l ON d.location_id = l.id
            WHERE ad.asset_id = ?
            ORDER BY d.created_at DESC
        ''', (asset_id,)).fetchall()
        asset = dict(asset_row)
        try:
            asset['specs'] = json.loads(asset.get('specs') or '{}')
        except json.JSONDecodeError:
            asset['specs'] = {}
        asset['devices'] = [dict(row) for row in device_rows]
        return jsonify(asset)

    if request.method == 'PUT':
        if not user_can('assets.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json()
        name = (data.get('name') or '').strip()
        notes = (data.get('notes') or '').strip()
        specs = json.dumps(data.get('specs', {}))
        device_ids = data.get('device_ids') or []
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        db.execute('''
            UPDATE assets
            SET name = ?, notes = ?, specs = ?
            WHERE id = ?
        ''', (name, notes, specs, asset_id))
        db.execute('DELETE FROM asset_devices WHERE asset_id = ?', (asset_id,))
        for device_id in device_ids:
            db.execute('''
                INSERT INTO asset_devices (asset_id, device_id)
                VALUES (?, ?)
            ''', (asset_id, device_id))
        log_activity(db, "update", "asset", asset_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('assets.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    db.execute('DELETE FROM asset_devices WHERE asset_id = ?', (asset_id,))
    db.execute('DELETE FROM assets WHERE id = ?', (asset_id,))
    log_activity(db, "delete", "asset", asset_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/locations', methods=['GET', 'POST'])
@login_required
def manage_locations():
    db = get_db()
    if request.method == 'POST':
        if not user_can('locations.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json()
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            db.execute('''
                INSERT INTO locations (name, description)
                VALUES (?, ?)
            ''', (name, description))
            log_activity(db, "create", "location", details={"name": name})
            db.commit()
            return jsonify({"status": "created"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Standort existiert bereits"}), 400

    if not (user_can('locations.view') or user_can('locations.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    locations = db.execute('SELECT * FROM locations ORDER BY name').fetchall()
    return jsonify([dict(row) for row in locations])

@app.route('/api/locations/<int:location_id>', methods=['PUT', 'DELETE'])
@login_required
def update_location(location_id):
    db = get_db()
    if request.method == 'PUT':
        if not user_can('locations.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json()
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        result = db.execute('''
            UPDATE locations
            SET name = ?, description = ?
            WHERE id = ?
        ''', (name, description, location_id))
        if result.rowcount == 0:
            return jsonify({"error": "Standort nicht gefunden"}), 404
        log_activity(db, "update", "location", location_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('locations.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    result = db.execute('DELETE FROM locations WHERE id = ?', (location_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Standort nicht gefunden"}), 404
    log_activity(db, "delete", "location", location_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/ticket-categories', methods=['GET', 'POST'])
@login_required
def ticket_categories():
    db = get_db()
    if request.method == 'POST':
        if not user_can('ticket_categories.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        color = (data.get('color') or '#2563eb').strip()
        sla_hours = int(data.get('sla_hours') or 72)
        is_default = 1 if data.get('is_default') else 0
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            db.execute('''
                INSERT INTO ticket_categories (name, description, color, sla_hours, is_default)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, color, sla_hours, is_default))
            log_activity(db, "create", "ticket_category", details={"name": name})
            db.commit()
            return jsonify({"status": "created"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Kategorie existiert bereits"}), 400

    if not (user_can('tickets.view_all') or user_can('tickets.view_own') or user_can('tickets.create')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    categories = db.execute('SELECT * FROM ticket_categories ORDER BY name').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/ticket-categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def ticket_category_detail(category_id):
    db = get_db()
    if request.method == 'PUT':
        if not user_can('ticket_categories.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        color = (data.get('color') or '#2563eb').strip()
        sla_hours = int(data.get('sla_hours') or 72)
        is_default = 1 if data.get('is_default') else 0
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        result = db.execute('''
            UPDATE ticket_categories
            SET name = ?, description = ?, color = ?, sla_hours = ?, is_default = ?
            WHERE id = ?
        ''', (name, description, color, sla_hours, is_default, category_id))
        if result.rowcount == 0:
            return jsonify({"error": "Kategorie nicht gefunden"}), 404
        log_activity(db, "update", "ticket_category", category_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('ticket_categories.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    result = db.execute('DELETE FROM ticket_categories WHERE id = ?', (category_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Kategorie nicht gefunden"}), 404
    log_activity(db, "delete", "ticket_category", category_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/tickets', methods=['GET', 'POST'])
@login_required
def tickets():
    db = get_db()
    access = get_user_access(db)
    if request.method == 'POST':
        if not user_can('tickets.create'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        category_id = data.get('category_id')
        priority = (data.get('priority') or 'normal').strip()
        status = (data.get('status') or 'open').strip()
        requester_name = (data.get('requester_name') or session.get('username') or '').strip()
        requester_email = (data.get('requester_email') or '').strip()
        assignee = (data.get('assignee') or '').strip()
        assignee_email = (data.get('assignee_email') or '').strip()
        due_date = (data.get('due_date') or '').strip()
        if not user_can('tickets.update'):
            status = 'open'
            assignee = ''
            assignee_email = ''
            due_date = ''
        tags = json.dumps(data.get('tags') or [])
        custom_fields = json.dumps(data.get('custom_fields') or [])
        if not title or not description:
            return jsonify({"error": "Titel und Beschreibung sind erforderlich"}), 400
        cursor = db.execute('''
            INSERT INTO tickets (
                title, description, category_id, priority, status, requester_name,
                requester_email, created_by, assignee, assignee_email, due_date, tags, custom_fields
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, description, category_id, priority, status, requester_name, requester_email,
            session.get('username'), assignee, assignee_email, due_date, tags, custom_fields
        ))
        ticket_id = cursor.lastrowid
        log_activity(db, "create", "ticket", ticket_id, {"title": title})
        db.commit()
        ticket = fetch_ticket(db, ticket_id)
        if ticket:
            ticket = normalize_ticket_row(ticket)
            trigger_ticket_notifications(db, "created", ticket)
        return jsonify({"status": "created", "id": ticket_id}), 201

    if not (user_can('tickets.view_all') or user_can('tickets.view_own')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    filters = []
    params = []
    status = request.args.get('status')
    priority = request.args.get('priority')
    category_id = request.args.get('category_id')
    assignee = request.args.get('assignee')
    mine = request.args.get('mine')
    search = (request.args.get('search') or '').strip()

    if status:
        filters.append('t.status = ?')
        params.append(status)
    if priority:
        filters.append('t.priority = ?')
        params.append(priority)
    if category_id:
        filters.append('t.category_id = ?')
        params.append(category_id)
    if assignee:
        filters.append('t.assignee = ?')
        params.append(assignee)
    if mine:
        filters.append('t.created_by = ?')
        params.append(session.get('username'))
    if not access["is_superuser"] and 'tickets.view_all' not in access["permissions"]:
        filters.append('t.created_by = ?')
        params.append(session.get('username'))
    if search:
        filters.append('(t.title LIKE ? OR t.description LIKE ? OR t.requester_name LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    query = '''
        SELECT t.*, c.name as category_name, c.color as category_color
        FROM tickets t
        LEFT JOIN ticket_categories c ON t.category_id = c.id
    '''
    if filters:
        query += ' WHERE ' + ' AND '.join(filters)
    query += ' ORDER BY t.updated_at DESC, t.created_at DESC'

    rows = db.execute(query, params).fetchall()
    tickets = [normalize_ticket_row(row) for row in rows]
    return jsonify(tickets)

@app.route('/api/tickets/<int:ticket_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def ticket_detail(ticket_id):
    db = get_db()
    ticket = fetch_ticket(db, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket nicht gefunden"}), 404
    access = get_user_access(db)
    if not ensure_ticket_access(ticket, access):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'GET':
        ticket = normalize_ticket_row(ticket)
        comments = db.execute('''
            SELECT id, author, body, is_internal, created_at
            FROM ticket_comments
            WHERE ticket_id = ?
            ORDER BY created_at ASC
        ''', (ticket_id,)).fetchall()
        watchers = db.execute('''
            SELECT id, email
            FROM ticket_watchers
            WHERE ticket_id = ?
            ORDER BY created_at DESC
        ''', (ticket_id,)).fetchall()
        ticket['comments'] = [dict(row) for row in comments]
        ticket['watchers'] = [dict(row) for row in watchers]
        return jsonify(ticket)

    if request.method == 'PUT':
        can_update = user_can('tickets.update')
        can_update_own = user_can('tickets.update_own')
        if not can_update and not (can_update_own and ticket.get('created_by') == session.get('username')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        title = (data.get('title') or ticket['title']).strip()
        description = (data.get('description') or ticket['description']).strip()
        category_id = data.get('category_id')
        priority = (data.get('priority') or ticket['priority']).strip()
        status = (data.get('status') or ticket['status']).strip()
        requester_name = (data.get('requester_name') or ticket.get('requester_name') or '').strip()
        requester_email = (data.get('requester_email') or ticket.get('requester_email') or '').strip()
        assignee = (data.get('assignee') or ticket.get('assignee') or '').strip()
        assignee_email = (data.get('assignee_email') or ticket.get('assignee_email') or '').strip()
        due_date = (data.get('due_date') or ticket.get('due_date') or '').strip()
        tags = json.dumps(data.get('tags') or json.loads(ticket.get('tags') or '[]'))
        custom_fields = json.dumps(data.get('custom_fields') or json.loads(ticket.get('custom_fields') or '[]'))
        status_changed = status != ticket.get('status')

        db.execute('''
            UPDATE tickets
            SET title = ?, description = ?, category_id = ?, priority = ?, status = ?,
                requester_name = ?, requester_email = ?, assignee = ?, assignee_email = ?,
                due_date = ?, tags = ?, custom_fields = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            title, description, category_id, priority, status, requester_name, requester_email,
            assignee, assignee_email, due_date, tags, custom_fields, ticket_id
        ))
        log_activity(db, "update", "ticket", ticket_id, {"title": title})
        db.commit()
        updated_ticket = fetch_ticket(db, ticket_id)
        if updated_ticket:
            normalized = normalize_ticket_row(updated_ticket)
            trigger_ticket_notifications(db, "updated", normalized)
            if status_changed:
                trigger_ticket_notifications(db, "status_changed", normalized)
        return jsonify({"status": "updated"}), 200

    can_delete = user_can('tickets.delete')
    can_delete_own = user_can('tickets.delete_own')
    if not can_delete and not (can_delete_own and ticket.get('created_by') == session.get('username')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    db.execute('DELETE FROM ticket_comments WHERE ticket_id = ?', (ticket_id,))
    db.execute('DELETE FROM ticket_watchers WHERE ticket_id = ?', (ticket_id,))
    db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
    log_activity(db, "delete", "ticket", ticket_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/tickets/<int:ticket_id>/comments', methods=['GET', 'POST'])
@login_required
def ticket_comments(ticket_id):
    db = get_db()
    ticket = fetch_ticket(db, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket nicht gefunden"}), 404
    access = get_user_access(db)
    if not ensure_ticket_access(ticket, access):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'POST':
        can_comment = user_can('tickets.comment')
        can_comment_own = user_can('tickets.comment_own')
        if not can_comment and not (can_comment_own and ticket.get('created_by') == session.get('username')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        allow_internal = user_can('tickets.comment_internal')
        is_internal = 1 if allow_internal and data.get('is_internal') else 0
        if not body:
            return jsonify({"error": "Kommentar darf nicht leer sein"}), 400
        db.execute('''
            INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
            VALUES (?, ?, ?, ?)
        ''', (ticket_id, session.get('username'), body, is_internal))
        db.execute('UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (ticket_id,))
        log_activity(db, "comment", "ticket", ticket_id)
        db.commit()
        ticket = fetch_ticket(db, ticket_id)
        if ticket:
            ticket = normalize_ticket_row(ticket)
            trigger_ticket_notifications(db, "commented", ticket, comment=body)
        return jsonify({"status": "created"}), 201

    comments = db.execute('''
        SELECT id, author, body, is_internal, created_at
        FROM ticket_comments
        WHERE ticket_id = ?
        ORDER BY created_at ASC
    ''', (ticket_id,)).fetchall()
    return jsonify([dict(row) for row in comments])

@app.route('/api/tickets/<int:ticket_id>/watchers', methods=['GET', 'POST'])
@login_required
def ticket_watchers(ticket_id):
    db = get_db()
    ticket = fetch_ticket(db, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket nicht gefunden"}), 404
    access = get_user_access(db)
    if not ensure_ticket_access(ticket, access):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'POST':
        can_watch = user_can('tickets.watch')
        can_watch_own = user_can('tickets.watch_own')
        if not can_watch and not (can_watch_own and ticket.get('created_by') == session.get('username')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        email = (data.get('email') or '').strip()
        if not email:
            return jsonify({"error": "E-Mail ist erforderlich"}), 400
        db.execute('''
            INSERT INTO ticket_watchers (ticket_id, email)
            VALUES (?, ?)
        ''', (ticket_id, email))
        log_activity(db, "watch", "ticket", ticket_id, {"email": email})
        db.commit()
        return jsonify({"status": "created"}), 201

    watchers = db.execute('''
        SELECT id, email, created_at
        FROM ticket_watchers
        WHERE ticket_id = ?
        ORDER BY created_at DESC
    ''', (ticket_id,)).fetchall()
    return jsonify([dict(row) for row in watchers])

@app.route('/api/tickets/<int:ticket_id>/watchers/<int:watcher_id>', methods=['DELETE'])
@login_required
def delete_ticket_watcher(ticket_id, watcher_id):
    db = get_db()
    ticket = fetch_ticket(db, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket nicht gefunden"}), 404
    access = get_user_access(db)
    if not ensure_ticket_access(ticket, access):
        return jsonify({"error": "Keine Berechtigung"}), 403
    can_watch = user_can('tickets.watch')
    can_watch_own = user_can('tickets.watch_own')
    if not can_watch and not (can_watch_own and ticket.get('created_by') == session.get('username')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    result = db.execute('''
        DELETE FROM ticket_watchers
        WHERE id = ? AND ticket_id = ?
    ''', (watcher_id, ticket_id))
    if result.rowcount == 0:
        return jsonify({"error": "Watcher nicht gefunden"}), 404
    log_activity(db, "unwatch", "ticket", ticket_id, {"watcher_id": watcher_id})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/ticket-alerts', methods=['GET', 'POST'])
@login_required
def ticket_alerts():
    db = get_db()
    if request.method == 'POST':
        if not user_can('ticket_alerts.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        event_type = (data.get('event_type') or '').strip()
        status_match = (data.get('status_match') or '').strip() or None
        priority_match = (data.get('priority_match') or '').strip() or None
        category_id = data.get('category_id') or None
        recipient_emails = (data.get('recipient_emails') or '').strip()
        is_enabled = 1 if data.get('is_enabled', True) else 0
        if not name or not event_type or not recipient_emails:
            return jsonify({"error": "Name, Event und Empfänger sind erforderlich"}), 400
        db.execute('''
            INSERT INTO ticket_alerts (name, event_type, status_match, priority_match, category_id, recipient_emails, is_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, event_type, status_match, priority_match, category_id, recipient_emails, is_enabled))
        log_activity(db, "create", "ticket_alert", details={"name": name})
        db.commit()
        return jsonify({"status": "created"}), 201

    if not user_can('ticket_alerts.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    alerts = db.execute('SELECT * FROM ticket_alerts ORDER BY created_at DESC').fetchall()
    return jsonify([dict(row) for row in alerts])

@app.route('/api/ticket-alerts/<int:alert_id>', methods=['PUT', 'DELETE'])
@login_required
def ticket_alert_detail(alert_id):
    db = get_db()
    if request.method == 'PUT':
        if not user_can('ticket_alerts.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        event_type = (data.get('event_type') or '').strip()
        status_match = (data.get('status_match') or '').strip() or None
        priority_match = (data.get('priority_match') or '').strip() or None
        category_id = data.get('category_id') or None
        recipient_emails = (data.get('recipient_emails') or '').strip()
        is_enabled = 1 if data.get('is_enabled', True) else 0
        if not name or not event_type or not recipient_emails:
            return jsonify({"error": "Name, Event und Empfänger sind erforderlich"}), 400
        result = db.execute('''
            UPDATE ticket_alerts
            SET name = ?, event_type = ?, status_match = ?, priority_match = ?, category_id = ?, recipient_emails = ?, is_enabled = ?
            WHERE id = ?
        ''', (name, event_type, status_match, priority_match, category_id, recipient_emails, is_enabled, alert_id))
        if result.rowcount == 0:
            return jsonify({"error": "Alert nicht gefunden"}), 404
        log_activity(db, "update", "ticket_alert", alert_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('ticket_alerts.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    result = db.execute('DELETE FROM ticket_alerts WHERE id = ?', (alert_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Alert nicht gefunden"}), 404
    log_activity(db, "delete", "ticket_alert", alert_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/notifications/settings', methods=['GET', 'POST'])
@login_required
def notification_settings():
    db = get_db()
    if not user_can('notifications.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'POST':
        data = request.get_json() or {}
        enabled = 1 if data.get('enabled') else 0
        smtp_host = (data.get('smtp_host') or '').strip()
        smtp_port = int(data.get('smtp_port') or 587)
        smtp_username = (data.get('smtp_username') or '').strip()
        smtp_password = data.get('smtp_password') or ''
        smtp_from = (data.get('smtp_from') or '').strip()
        use_tls = 1 if data.get('use_tls', True) else 0
        default_recipients = (data.get('default_recipients') or '').strip()

        existing = get_notification_settings(db)
        if existing and not smtp_password:
            smtp_password = existing["smtp_password"] or ''

        db.execute('''
            UPDATE notification_settings
            SET enabled = ?, smtp_host = ?, smtp_port = ?, smtp_username = ?, smtp_password = ?,
                smtp_from = ?, use_tls = ?, default_recipients = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (
            enabled, smtp_host, smtp_port, smtp_username, smtp_password, smtp_from,
            use_tls, default_recipients
        ))
        log_activity(db, "update", "notification_settings", details={"enabled": bool(enabled)})
        db.commit()
        settings = get_notification_settings(db)
        return jsonify(serialize_notification_settings(settings))

    settings = get_notification_settings(db)
    return jsonify(serialize_notification_settings(settings))

@app.route('/api/notifications/test', methods=['POST'])
@login_required
def notification_test():
    db = get_db()
    if not user_can('notifications.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    data = request.get_json() or {}
    recipients = data.get('recipients')
    settings = get_notification_settings(db)
    if not settings or not settings["enabled"]:
        return jsonify({"error": "Benachrichtigungen sind deaktiviert"}), 400
    if not recipients:
        return jsonify({"error": "Empfänger fehlt"}), 400
    subject = "Inventory Pro Ticket-System Test"
    body = "Dies ist eine Test-E-Mail aus dem Inventory Pro Helpdesk."
    success = send_notification_email(settings, recipients, subject, body)
    if not success:
        return jsonify({"error": "E-Mail konnte nicht versendet werden"}), 400
    return jsonify({"status": "sent"}), 200

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
    if not user_can('activity.view'):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
@require_permission('users.manage')
def manage_users():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        role_ids = data.get('role_ids') or []
        if not username or not password:
            return jsonify({"error": "Benutzername und Passwort sind erforderlich"}), 400
        if role_ids and not user_can('roles.assign'):
            return jsonify({"error": "Keine Berechtigung für Rollen"}), 403
        password_hash = generate_password_hash(password)
        try:
            cursor = db.execute('''
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            ''', (username, password_hash))
            user_id = cursor.lastrowid
            if role_ids:
                db.execute('DELETE FROM user_roles WHERE user_id = ?', (user_id,))
                for role_id in role_ids:
                    db.execute('''
                        INSERT OR IGNORE INTO user_roles (user_id, role_id)
                        VALUES (?, ?)
                    ''', (user_id, role_id))
            else:
                assign_user_role(db, user_id, DEFAULT_ROLE_NAME)
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
        roles = db.execute('''
            SELECT r.id, r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            ORDER BY r.name
        ''', (entry["id"],)).fetchall()
        entry['roles'] = [dict(role) for role in roles]
        result.append(entry)
    return jsonify(result)

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@require_permission('users.manage')
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
@require_permission('users.manage')
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

@app.route('/api/permissions', methods=['GET'])
@login_required
@require_permission('roles.manage')
def list_permissions():
    db = get_db()
    rows = db.execute('''
        SELECT id, key, label, description, group_name
        FROM permissions
        ORDER BY group_name, label
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/roles', methods=['GET', 'POST'])
@login_required
def manage_roles():
    db = get_db()
    if request.method == 'POST':
        if not user_can('roles.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        permission_ids = data.get('permission_ids') or []
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO roles (name, description, is_system, is_superuser)
                VALUES (?, ?, 0, 0)
            ''', (name, description))
            role_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error": "Rolle existiert bereits"}), 400
        for permission_id in permission_ids:
            db.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role_id, permission_id))
        log_activity(db, "create", "role", role_id, {"name": name})
        db.commit()
        return jsonify({"status": "created", "id": role_id}), 201

    if not (user_can('roles.manage') or user_can('roles.assign')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    roles = db.execute('SELECT id, name, description, is_system, is_superuser FROM roles ORDER BY name').fetchall()
    results = []
    for role in roles:
        permissions = db.execute('''
            SELECT p.id, p.key, p.label
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            WHERE rp.role_id = ?
            ORDER BY p.label
        ''', (role["id"],)).fetchall()
        entry = dict(role)
        entry["permissions"] = [dict(row) for row in permissions]
        results.append(entry)
    return jsonify(results)

@app.route('/api/roles/<int:role_id>', methods=['PUT', 'DELETE'])
@login_required
@require_permission('roles.manage')
def role_detail(role_id):
    db = get_db()
    role = db.execute('SELECT id, name, is_system FROM roles WHERE id = ?', (role_id,)).fetchone()
    if not role:
        return jsonify({"error": "Rolle nicht gefunden"}), 404
    if request.method == 'DELETE':
        if role["is_system"]:
            return jsonify({"error": "Systemrollen können nicht gelöscht werden"}), 400
        db.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
        db.execute('DELETE FROM user_roles WHERE role_id = ?', (role_id,))
        db.execute('DELETE FROM roles WHERE id = ?', (role_id,))
        log_activity(db, "delete", "role", role_id, {"name": role["name"]})
        db.commit()
        return jsonify({"status": "deleted"}), 200

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    permission_ids = data.get('permission_ids') or []
    if not name:
        return jsonify({"error": "Name ist erforderlich"}), 400
    db.execute('''
        UPDATE roles
        SET name = ?, description = ?
        WHERE id = ?
    ''', (name, description, role_id))
    db.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
    for permission_id in permission_ids:
        db.execute('''
            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
            VALUES (?, ?)
        ''', (role_id, permission_id))
    log_activity(db, "update", "role", role_id, {"name": name})
    db.commit()
    return jsonify({"status": "updated"}), 200

@app.route('/api/me', methods=['GET'])
@login_required
def current_user_info():
    db = get_db()
    access = get_user_access(db)
    if not access["user"]:
        return jsonify({"error": "Benutzer nicht gefunden"}), 404
    return jsonify({
        "id": access["user"]["id"],
        "username": access["user"]["username"],
        "roles": access["roles"],
        "permissions": sorted(access["permissions"]),
        "is_superuser": access["is_superuser"]
    })

@app.route('/api/users/<int:user_id>/roles', methods=['PUT'])
@login_required
@require_permission('roles.assign')
def update_user_roles(user_id):
    db = get_db()
    data = request.get_json() or {}
    role_ids = data.get('role_ids') or []
    if not isinstance(role_ids, list):
        return jsonify({"error": "Rollenliste ungültig"}), 400
    existing_user = db.execute('SELECT id, username FROM users WHERE id = ?', (user_id,)).fetchone()
    if not existing_user:
        return jsonify({"error": "Benutzer nicht gefunden"}), 404
    db.execute('DELETE FROM user_roles WHERE user_id = ?', (user_id,))
    for role_id in role_ids:
        db.execute('''
            INSERT OR IGNORE INTO user_roles (user_id, role_id)
            VALUES (?, ?)
        ''', (user_id, role_id))
    log_activity(db, "update", "user_roles", user_id, {"roles": role_ids})
    db.commit()
    roles = db.execute('''
        SELECT r.id, r.name
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        ORDER BY r.name
    ''', (user_id,)).fetchall()
    return jsonify({"status": "updated", "roles": [dict(role) for role in roles]}), 200

@app.route('/api/ad/settings', methods=['GET'])
@login_required
def ad_settings():
    db = get_db()
    if not user_can('users.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    settings = get_ad_settings(db)
    return jsonify(serialize_ad_settings(settings))

@app.route('/api/ad/quick-connect', methods=['POST'])
@login_required
def quick_connect_ad():
    db = get_db()
    if not user_can('users.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    data = request.get_json() or {}
    server_url = (data.get('server_url') or '').strip()
    domain = (data.get('domain') or '').strip()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    use_ssl = bool(data.get('use_ssl'))

    if not server_url:
        return jsonify({"error": "Server-URL ist erforderlich"}), 400
    if not username or not password:
        return jsonify({"error": "AD-Benutzername und Passwort sind erforderlich"}), 400

    user_principal = f"{username}@{domain}" if domain else username
    server = Server(server_url, use_ssl=use_ssl, get_info=ALL)
    try:
        user_conn = Connection(server, user=user_principal, password=password, auto_bind=True)
    except Exception:
        return jsonify({"error": "Anmeldung am Active Directory fehlgeschlagen"}), 400

    base_dn = discover_base_dn(server, user_conn, domain)
    user_conn.unbind()
    if not base_dn:
        return jsonify({"error": "Base DN konnte nicht ermittelt werden. Bitte im Expertenmodus eintragen."}), 400

    db.execute('''
        UPDATE ad_settings
        SET enabled = 1,
            server_url = ?,
            base_dn = ?,
            bind_dn = '',
            bind_password = '',
            user_attribute = 'sAMAccountName',
            domain = ?,
            use_ssl = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    ''', (
        server_url,
        base_dn,
        domain,
        1 if use_ssl else 0
    ))
    log_activity(db, "update", "ad_settings", details={"enabled": True, "server_url": server_url, "mode": "quick"})
    db.commit()
    settings = get_ad_settings(db)
    return jsonify(serialize_ad_settings(settings))

@app.route('/api/ad/connect', methods=['POST'])
@login_required
def connect_ad():
    db = get_db()
    if not user_can('users.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    data = request.get_json() or {}
    server_url = (data.get('server_url') or '').strip()
    base_dn = (data.get('base_dn') or '').strip()
    bind_dn = (data.get('bind_dn') or '').strip()
    bind_password = data.get('bind_password') or ''
    user_attribute = (data.get('user_attribute') or 'sAMAccountName').strip()
    domain = (data.get('domain') or '').strip()
    use_ssl = bool(data.get('use_ssl'))

    if not server_url or not base_dn:
        return jsonify({"error": "Server-URL und Base DN sind erforderlich"}), 400

    existing = get_ad_settings(db)
    if not bind_password and existing:
        bind_password = existing["bind_password"] or ''

    server = Server(server_url, use_ssl=use_ssl)
    if bind_dn:
        try:
            test_conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
            test_conn.unbind()
        except Exception:
            return jsonify({"error": "Bind zum Active Directory fehlgeschlagen"}), 400

    db.execute('''
        UPDATE ad_settings
        SET enabled = 1,
            server_url = ?,
            base_dn = ?,
            bind_dn = ?,
            bind_password = ?,
            user_attribute = ?,
            domain = ?,
            use_ssl = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    ''', (
        server_url,
        base_dn,
        bind_dn,
        bind_password,
        user_attribute,
        domain,
        1 if use_ssl else 0
    ))
    log_activity(db, "update", "ad_settings", details={"enabled": True, "server_url": server_url})
    db.commit()
    settings = get_ad_settings(db)
    return jsonify(serialize_ad_settings(settings))

@app.route('/api/ad/disconnect', methods=['POST'])
@login_required
def disconnect_ad():
    db = get_db()
    if not user_can('users.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    db.execute('''
        UPDATE ad_settings
        SET enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    ''')
    log_activity(db, "update", "ad_settings", details={"enabled": False})
    db.commit()
    settings = get_ad_settings(db)
    return jsonify(serialize_ad_settings(settings))

@app.route('/api/devices/<int:device_id>/tags', methods=['GET', 'POST'])
@login_required
def device_tags(device_id):
    db = get_db()
    if not (user_can('devices.manage') or user_can('devices.view')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'POST':
        if not user_can('devices.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
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
    if not user_can('devices.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
    if not (user_can('devices.manage') or user_can('devices.view')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'POST':
        if not user_can('devices.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
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
    if not user_can('devices.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
        if not user_can('maintenance.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
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

    if not (user_can('maintenance.view') or user_can('maintenance.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
    if not user_can('maintenance.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
    db = get_db()
    if not (user_can('maintenance.view') or user_can('maintenance.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
    if not (user_can('devices.view') or user_can('devices.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
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
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=devices.csv'}
    )

@app.route('/stats')
@login_required
@require_permission('stats.view')
def stats():
    db = get_db()
    access = get_user_access(db)
    
    # 1. Grundstatistiken mit Default-Werten
    total_devices = db.execute('SELECT COUNT(*) FROM devices').fetchone()[0] or 0
    total_categories = db.execute('SELECT COUNT(*) FROM categories').fetchone()[0] or 0
    total_locations = db.execute('SELECT COUNT(*) FROM locations').fetchone()[0] or 0
    total_tags = db.execute('SELECT COUNT(*) FROM device_tags').fetchone()[0] or 0
    total_notes = db.execute('SELECT COUNT(*) FROM device_notes').fetchone()[0] or 0
    total_maintenance = db.execute('SELECT COUNT(*) FROM maintenance_tasks').fetchone()[0] or 0
    open_maintenance = db.execute(
        "SELECT COUNT(*) FROM maintenance_tasks WHERE status = 'open'"
    ).fetchone()[0] or 0
    done_maintenance = db.execute(
        "SELECT COUNT(*) FROM maintenance_tasks WHERE status = 'done'"
    ).fetchone()[0] or 0
    overdue_maintenance = db.execute('''
        SELECT COUNT(*) FROM maintenance_tasks
        WHERE status = 'open' AND due_date != '' AND date(due_date) < date('now')
    ''').fetchone()[0] or 0
    due_soon_maintenance = db.execute('''
        SELECT COUNT(*) FROM maintenance_tasks
        WHERE status = 'open' AND due_date != ''
        AND date(due_date) >= date('now') AND date(due_date) <= date('now', '+7 days')
    ''').fetchone()[0] or 0
    devices_recent_7 = db.execute('''
        SELECT COUNT(*) FROM devices WHERE date(created_at) >= date('now', '-7 days')
    ''').fetchone()[0] or 0
    devices_recent_30 = db.execute('''
        SELECT COUNT(*) FROM devices WHERE date(created_at) >= date('now', '-30 days')
    ''').fetchone()[0] or 0
    
    # 2. Kategorieverteilung mit sicherer Abfrage
    categories = db.execute('''
        SELECT c.id, c.name, COUNT(d.id) as device_count
        FROM categories c
        LEFT JOIN devices d ON c.id = d.category_id
        GROUP BY c.id
    ''').fetchall()
    categories_data = [dict(c) for c in categories] if categories else []
    
    # 3. Verbesserte Statusverteilung mit Default-Werten
    status_data = {'Verwendet': 0, 'Lager': 0, 'Defekt': 0, 'Unbekannt': 0}
    devices = db.execute('SELECT specs FROM devices').fetchall()
    for device in devices:
        try:
            specs = json.loads(device['specs']) if device['specs'] else {}
            status = specs.get('Status') or specs.get('status') or 'Verwendet'
            # Normalisiere den Status (entferne Leerzeichen, mache erste Buchstabe groß)
            status = status.strip().capitalize()
            # Falls der Status nicht in unserer Liste ist, zählen wir als "Verwendet"
            if status in status_data:
                status_data[status] += 1
            else:
                status_data['Unbekannt'] += 1
        except json.JSONDecodeError:
            status_data['Unbekannt'] += 1

    # 3b. Standortverteilung
    locations = db.execute('''
        SELECT l.id, l.name, COUNT(d.id) as device_count
        FROM locations l
        LEFT JOIN devices d ON l.id = d.location_id
        GROUP BY l.id
    ''').fetchall()
    locations_data = [dict(l) for l in locations] if locations else []
    unknown_location_count = db.execute('''
        SELECT COUNT(*) FROM devices WHERE location_id IS NULL
    ''').fetchone()[0] or 0

    # 3c. Gerätezugang letzte 6 Monate
    monthly_rows = db.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as device_count
        FROM devices
        WHERE date(created_at) >= date('now', '-5 months', 'start of month')
        GROUP BY month
        ORDER BY month
    ''').fetchall()
    monthly_counts = {row['month']: row['device_count'] for row in monthly_rows}
    now = datetime.utcnow()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for offset in range(-5, 1):
        year = current_month_start.year + (current_month_start.month - 1 + offset) // 12
        month = (current_month_start.month - 1 + offset) % 12 + 1
        label = f"{year:04d}-{month:02d}"
        months.append({'month': label, 'count': monthly_counts.get(label, 0)})

    # 3d. Gerätealter-Buckets
    age_buckets = {
        '0-30 Tage': 0,
        '31-90 Tage': 0,
        '91-180 Tage': 0,
        '181-365 Tage': 0,
        '365+ Tage': 0
    }
    device_dates = db.execute('SELECT created_at FROM devices').fetchall()
    for row in device_dates:
        if not row['created_at']:
            continue
        try:
            created_at = datetime.fromisoformat(row['created_at'])
        except ValueError:
            continue
        age_days = (now - created_at).days
        if age_days <= 30:
            age_buckets['0-30 Tage'] += 1
        elif age_days <= 90:
            age_buckets['31-90 Tage'] += 1
        elif age_days <= 180:
            age_buckets['91-180 Tage'] += 1
        elif age_days <= 365:
            age_buckets['181-365 Tage'] += 1
        else:
            age_buckets['365+ Tage'] += 1

    # 3e. Zusatz-KPIs
    devices_with_tags = db.execute('SELECT COUNT(DISTINCT device_id) FROM device_tags').fetchone()[0] or 0
    devices_with_notes = db.execute('SELECT COUNT(DISTINCT device_id) FROM device_notes').fetchone()[0] or 0
    tag_coverage = round((devices_with_tags / total_devices) * 100) if total_devices else 0
    note_coverage = round((devices_with_notes / total_devices) * 100) if total_devices else 0
    activity_summary = db.execute('''
        SELECT action, COUNT(*) as total
        FROM activity_log
        WHERE date(created_at) >= date('now', '-7 days')
        GROUP BY action
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    activity_summary_data = [dict(row) for row in activity_summary] if activity_summary else []
    top_categories = sorted(categories_data, key=lambda x: x['device_count'], reverse=True)[:5]
    
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
        'total_locations': total_locations,
        'total_tags': total_tags,
        'total_notes': total_notes,
        'total_maintenance': total_maintenance,
        'open_maintenance': open_maintenance,
        'done_maintenance': done_maintenance,
        'overdue_maintenance': overdue_maintenance,
        'due_soon_maintenance': due_soon_maintenance,
        'devices_recent_7': devices_recent_7,
        'devices_recent_30': devices_recent_30,
        'categories': categories_data,
        'status_data': status_data,
        'locations': locations_data,
        'unknown_location_count': unknown_location_count,
        'devices_by_month': months,
        'age_buckets': age_buckets,
        'devices_with_tags': devices_with_tags,
        'devices_with_notes': devices_with_notes,
        'tag_coverage': tag_coverage,
        'note_coverage': note_coverage,
        'activity_summary': activity_summary_data,
        'top_categories': top_categories,
        'recent_devices': recent_devices_data,
        'username': session.get('username', ''),
        'permissions': sorted(access["permissions"]),
        'is_superuser': access["is_superuser"]
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
    log_activity(db, "otp_setup", "user", details={"username": username})
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
        log_activity(db, "otp_verify", "user", details={"username": username})
        db.commit()
        return jsonify({"verified": True}), 200
    else:
        log_activity(db, "otp_failed", "user", details={"username": username})
        db.commit()
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
    log_activity(db, "password_reset", "user", details={"username": username})
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
    log_activity(db, "otp_disabled", "user", details={"username": username})
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
