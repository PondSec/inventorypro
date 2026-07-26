from flask import Flask, render_template, jsonify, request, g, redirect, url_for, session, Response, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from functools import wraps
import os
import csv
import re
import ipaddress
import tempfile
import zipfile
import shutil
import time
import subprocess
import socket
import stat
import http.cookiejar
import urllib.request
import urllib.error
import urllib.parse
import ssl
import threading
import html
from itertools import permutations
from pathlib import Path, PurePosixPath
from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO, StringIO
import base64
import secrets
import uuid
from ldap3 import Server, Connection, BASE, ALL
from ldap3.utils.conv import escape_filter_chars
from email.message import EmailMessage
import smtplib

from inventorypro.config import resolve_application_secret
from inventorypro.cache import BoundedTTLCache, SlidingWindowRateLimiter
from inventorypro.csrf import CSRF_HEADER_NAME, get_csrf_token, validate_csrf_token
from inventorypro.domains.backups.routes import build_backups_blueprint
from inventorypro.domains.locations.routes import build_locations_blueprint
from inventorypro.domains.tickets.routes import build_ticket_pages_blueprint
from inventorypro.migrations import MigrationError, apply_migrations
from inventorypro import backup_restore as backup_restore_service
from inventorypro.secrets import (
    EncryptionKeyring,
    SecretConfigurationError,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_plaintext_secret,
    migrate_plaintext_secret,
)

INVENTORY_INSTANCE_PATH = os.environ.get("INVENTORY_INSTANCE_PATH") or None
app = Flask(__name__, instance_path=INVENTORY_INSTANCE_PATH) if INVENTORY_INSTANCE_PATH else Flask(__name__)
APPLICATION_SECRET = resolve_application_secret()
app.secret_key = APPLICATION_SECRET.value
if APPLICATION_SECRET.generated_for_development:
    app.logger.warning(
        "APP_SECRET_KEY fehlt; ein nicht persistenter Schlüssel wurde nur für %s erzeugt.",
        APPLICATION_SECRET.environment,
    )
ALLOWED_CORS_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in (os.environ.get("INVENTORY_ALLOWED_ORIGINS") or "").split(",")
    if origin.strip()
)
if ALLOWED_CORS_ORIGINS:
    CORS(
        app,
        resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}},
        supports_credentials=True,
    )
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("INVENTORY_SECURE_COOKIES", "0").strip().lower()
        in {"1", "true", "yes", "on"}
    ),
    INVENTORY_CSRF_ENABLED=(
        os.environ.get("INVENTORY_CSRF_ENABLED", "1").strip().lower()
        not in {"0", "false", "no", "off"}
    ),
)

DATABASE = os.environ.get("INVENTORY_DATABASE_PATH") or "inventory.db"
SETTINGS_SCHEMA_VERSION = 1
APP_INSTANCE_PATH = Path(app.instance_path)
RUNTIME_CONFIG_PATH = APP_INSTANCE_PATH / "runtime_config.json"
UPLOADS_DIR = Path(os.environ.get("INVENTORY_UPLOADS_DIR") or "uploads")
INITIAL_ADMIN_CREDENTIALS_PATH = os.environ.get("INVENTORY_INITIAL_ADMIN_CREDENTIALS_PATH")
MAX_IMPORT_BYTES = int(os.environ.get("INVENTORY_MAX_IMPORT_BYTES", 50 * 1024 * 1024))
MAX_IMPORT_EXPANDED_BYTES = int(
    os.environ.get("INVENTORY_MAX_IMPORT_EXPANDED_BYTES", MAX_IMPORT_BYTES * 4)
)
MAX_UPLOAD_BYTES = int(os.environ.get("INVENTORY_MAX_UPLOAD_BYTES", MAX_IMPORT_BYTES))
MAX_RESTORE_BYTES = int(os.environ.get("INVENTORY_MAX_RESTORE_BYTES", 5 * 1024 * 1024 * 1024))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
BLOCKED_ATTACHMENT_EXTENSIONS = {".exe", ".js", ".html", ".htm", ".bat", ".sh", ".ps1"}
BINPACKING_DIMENSIONS = ("width", "height", "depth")
BINPACKING_DEFAULT_RELATION_TYPES = ("enthält", "gelagert in")
BINPACKING_SORT_STRATEGIES = (
    ("volume_desc", "Volumenpriorität"),
    ("footprint_desc", "Stellfläche zuerst"),
    ("height_desc", "Höhenpriorität"),
    ("longest_edge_desc", "Längste Kante zuerst"),
)
BINPACKING_PREVIEW_COLORS = (
    "#2563eb",
    "#0f766e",
    "#7c3aed",
    "#ea580c",
    "#0891b2",
    "#be123c",
    "#4f46e5",
    "#15803d",
)
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 10
INVENTORY_LINK_PROXY_TIMEOUT_SECONDS = int(os.environ.get("INVENTORY_LINK_PROXY_TIMEOUT_SECONDS", 20))
INVENTORY_LINK_PROXY_RATE_LIMIT_WINDOW_SECONDS = 60
INVENTORY_LINK_PROXY_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("INVENTORY_LINK_PROXY_RATE_LIMIT_MAX_REQUESTS", 120))
INVENTORY_LINK_PROXY_TEXT_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "application/javascript",
    "text/javascript",
    "application/x-javascript",
    "text/css",
)
INVENTORY_LINK_PROXY_REWRITE_PATH_PREFIXES = (
    "api",
    "static",
    "login",
    "logout",
    "reset",
    "force-password-change",
    "locations",
    "tickets",
    "knowledge",
    "roadmap",
    "procurement",
    "stats",
    "dependencies",
    "time-machine",
    "health",
    "users",
    "settings",
    "inventory-links",
)
INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS_DEFAULT = os.environ.get("INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS", "0").lower() in {"1", "true", "yes"}
INVENTORY_LINK_LOGIN_TTL_SECONDS = int(os.environ.get("INVENTORY_LINK_LOGIN_TTL_SECONDS", 30 * 60))
TRUSTED_PROXY_NETWORKS = tuple(
    entry.strip()
    for entry in (os.environ.get("INVENTORY_TRUSTED_PROXY_NETWORKS") or "").split(",")
    if entry.strip()
)
PUBLIC_ORIGIN = (os.environ.get("INVENTORY_PUBLIC_ORIGIN") or "").strip().rstrip("/")
SCHEDULER_ENABLED = os.environ.get(
    "INVENTORY_SCHEDULER_ENABLED",
    "0" if APPLICATION_SECRET.environment == "production" else "1",
).strip().lower() in {"1", "true", "yes", "on"}
PRO_ENABLED = True
APP_START_TIME = time.time()
TERMINAL_RATE_LIMIT_WINDOW_SECONDS = 60
TERMINAL_RATE_LIMIT_MAX_REQUESTS = 12
TERMINAL_MAX_OUTPUT_BYTES = 200 * 1024
TERMINAL_SESSION_TTL_SECONDS = 15 * 60
TERMINAL_DEFAULT_TIMEOUT_SECONDS = 8
TERMINAL_LOG_MAX_LINES = 200
TERMINAL_LOG_MAX_BYTES = 150 * 1024
TERMINAL_DB_MAX_ROWS = 100
TERMINAL_DB_MAX_BYTES = 150 * 1024
TERMINAL_REAUTH_WINDOW_SECONDS = 10 * 60
CACHE_MAX_ENTRIES = int(os.environ.get("INVENTORY_CACHE_MAX_ENTRIES", "10000"))
TERMINAL_RATE_LIMIT_CACHE = SlidingWindowRateLimiter(CACHE_MAX_ENTRIES)
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

RUNTIME_SETTINGS_CACHE = None
BACKUP_SCHEDULER = BackgroundScheduler()
HEALTH_SCHEDULER = BackgroundScheduler()
RATE_LIMIT_CACHE = SlidingWindowRateLimiter(CACHE_MAX_ENTRIES)
INVENTORY_LINK_PROXY_RATE_LIMIT_CACHE = SlidingWindowRateLimiter(CACHE_MAX_ENTRIES)
INVENTORY_LINK_LOGIN_SESSION_CACHE = BoundedTTLCache(CACHE_MAX_ENTRIES)

HEALTH_STATUS_ORDER = {
    "OK": 0,
    "WARN": 1,
    "CRIT": 2,
    "UNKNOWN": 3
}
HEALTH_DEFAULT_RETENTION_DAYS = 14
HEALTH_INCIDENT_OPEN_MINUTES = 5
HEALTH_INCIDENT_CLOSE_MINUTES = 5
HEALTH_REDACT_KEYS = {
    "password", "secret", "token", "api_key", "apikey", "key", "authorization", "bearer", "dsn"
}
HEALTH_CHECK_REGISTRY = {}

DEFAULT_ROLE_NAME = "Mitarbeiter"
DEFAULT_SERVER_SETTINGS = {
    "schemaVersion": SETTINGS_SCHEMA_VERSION,
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False
    },
    "proFeaturesEnabled": False,
    "backup": {
        "enabled": False,
        "compress": False,
        "schedule": "daily",
        "time": "02:00",
        "retentionDays": 14,
        "directory": "backups/",
        "notifyEmail": "",
        "encrypt": False
    },
    "updates": {
        "autoUpdateEnabled": False,
        "channel": "stable",
        "checkIntervalMinutes": 360,
        "maintenanceWindow": "03:30"
    },
    "importExport": {
        "exportAllowed": True,
        "importAllowed": False,
        "exportFormat": "sqlite",
        "importMode": "merge",
        "includeUploads": True
    },
    "security": {
        "forceHttps": False,
        "requireMfa": False,
        "sessionTimeoutMinutes": 60,
        "maxFailedAttempts": 5,
        "lockoutMinutes": 15,
        "ipWhitelist": [],
        "minPasswordLength": 10
    },
    "terminal": {
        "enabled": False,
        "requireReauth": True,
        "ipAllowlist": [],
        "allowDbWrite": False,
        "allowServiceRestart": False,
        "breakGlassMode": False
    }
}
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
        "key": "asset_categories.view",
        "label": "Asset-Kategorien anzeigen",
        "description": "Asset-Kategorien und Zuordnungen einsehen.",
        "group": "Inventar"
    },
    {
        "key": "asset_categories.manage",
        "label": "Asset-Kategorien verwalten",
        "description": "Asset-Kategorien erstellen, bearbeiten und löschen.",
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
        "key": "asset.assign",
        "label": "Assets zuweisen",
        "description": "Assets Personen oder Teams zuweisen.",
        "group": "Inventar"
    },
    {
        "key": "asset.checkout",
        "label": "Assets ausgeben",
        "description": "Assets ausgeben und Rückgabedaten pflegen.",
        "group": "Inventar"
    },
    {
        "key": "asset.checkin",
        "label": "Assets einchecken",
        "description": "Assets zurücknehmen und Status aktualisieren.",
        "group": "Inventar"
    },
    {
        "key": "asset.view_history",
        "label": "Asset-Historie anzeigen",
        "description": "Zuweisungsverlauf und Check-out/Check-in Historie einsehen.",
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
        "key": "attachment.upload",
        "label": "Anhänge hochladen",
        "description": "Dateien an Assets, Tickets und Wartungen anhängen.",
        "group": "Dokumente"
    },
    {
        "key": "attachment.download",
        "label": "Anhänge herunterladen",
        "description": "Anhänge aus Assets, Tickets und Wartungen herunterladen.",
        "group": "Dokumente"
    },
    {
        "key": "attachment.delete",
        "label": "Anhänge löschen",
        "description": "Anhänge aus Assets, Tickets und Wartungen löschen.",
        "group": "Dokumente"
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
        "key": "knowledge.view",
        "label": "Wissensbasis anzeigen",
        "description": "Wissensdatenbank durchsuchen und lesen.",
        "group": "Wissensbasis"
    },
    {
        "key": "knowledge.manage",
        "label": "Wissensbasis verwalten",
        "description": "Wissensartikel und Kategorien erstellen und pflegen.",
        "group": "Wissensbasis"
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
        "key": "server_settings.manage",
        "label": "Einstellungen verwalten",
        "description": "Serverkonfigurationen und UI-Anpassungen verwalten.",
        "group": "Administration"
    },
    {
        "key": "terminal.view",
        "label": "Terminal anzeigen",
        "description": "Maintenance Console in den Einstellungen öffnen.",
        "group": "Administration"
    },
    {
        "key": "terminal.use",
        "label": "Terminal nutzen",
        "description": "Diagnose- und Service-Recipes ausführen.",
        "group": "Administration"
    },
    {
        "key": "terminal.db_write",
        "label": "DB-Console Write-Modus",
        "description": "Schreibende Datenbankaktionen in der Terminal-Console ausführen.",
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
    },
    {
        "key": "roadmap.view",
        "label": "Roadmaps anzeigen",
        "description": "Roadmaps und Pläne einsehen.",
        "group": "Roadmap"
    },
    {
        "key": "roadmap.manage",
        "label": "Roadmaps verwalten",
        "description": "Roadmaps erstellen, bearbeiten und löschen.",
        "group": "Roadmap"
    },
    {
        "key": "dependencies.view",
        "label": "Abhängigkeits-Graph anzeigen",
        "description": "Dependency- und Impact-Graph einsehen.",
        "group": "Abhängigkeiten"
    },
    {
        "key": "dependencies.manage",
        "label": "Abhängigkeits-Graph verwalten",
        "description": "Abhängigkeiten modellieren und Impact-Regeln pflegen.",
        "group": "Abhängigkeiten"
    },
    {
        "key": "timemachine.view",
        "label": "Zeitmaschine anzeigen",
        "description": "Zeitachsen, Zustände und Simulationen einsehen.",
        "group": "Zeitmaschine"
    },
    {
        "key": "health.view",
        "label": "Health Dashboard anzeigen",
        "description": "Server- und Service-Health überwachen.",
        "group": "Health"
    },
    {
        "key": "health.manage",
        "label": "Health Checks verwalten",
        "description": "Health-Checks konfigurieren und verwalten.",
        "group": "Health"
    },
    {
        "key": "health.run",
        "label": "Health Checks ausführen",
        "description": "Checks manuell starten und Aktionen ausführen.",
        "group": "Health"
    },
    {
        "key": "health.export",
        "label": "Health Daten exportieren",
        "description": "Health-Reports und Exporte erstellen.",
        "group": "Health"
    },
    {
        "key": "software.view",
        "label": "Software-Inventar anzeigen",
        "description": "Software-Inventar und Installationen einsehen.",
        "group": "Software"
    },
    {
        "key": "software.manage",
        "label": "Software-Inventar verwalten",
        "description": "Software, Installationen und Eigentümer verwalten.",
        "group": "Software"
    },
    {
        "key": "procurement.view",
        "label": "Beschaffung anzeigen",
        "description": "Lieferanten, Verträge und Bestellungen einsehen.",
        "group": "Beschaffung"
    },
    {
        "key": "procurement.manage",
        "label": "Beschaffung verwalten",
        "description": "Lieferanten, Verträge und Bestellungen pflegen.",
        "group": "Beschaffung"
    },
    {
        "key": "teams.view",
        "label": "Teams anzeigen",
        "description": "Teams und Verantwortlichkeiten einsehen.",
        "group": "Organisation"
    },
    {
        "key": "teams.manage",
        "label": "Teams verwalten",
        "description": "Teams und Zuordnungen pflegen.",
        "group": "Organisation"
    },
    {
        "key": "departments.view",
        "label": "Abteilungen anzeigen",
        "description": "Abteilungen und Strukturen einsehen.",
        "group": "Organisation"
    },
    {
        "key": "departments.manage",
        "label": "Abteilungen verwalten",
        "description": "Abteilungen erstellen und pflegen.",
        "group": "Organisation"
    }
]

DEFAULT_CUSTOMIZATION = {
    "schemaVersion": 1,
    "branding": {
        "name": "Inventory Pro",
        "tagline": "Inventarisierung",
        "logoDataUrl": "",
    },
    "baseTokens": {
        "colors": {
            "primary": "#2563eb",
            "secondary": "#6366f1",
            "accent": "#14b8a6",
            "neutral": "#64748b",
            "background": "#f6f7fb",
            "surface": "#ffffff",
            "text": "#0f172a",
            "textMuted": "#6b7280",
            "border": "#e5e7eb",
            "shadow": "rgba(15, 23, 42, 0.12)",
            "focus": "rgba(37, 99, 235, 0.35)",
            "success": "#16a34a",
            "warning": "#f59e0b",
            "danger": "#dc2626",
            "info": "#0ea5e9",
        },
        "typography": {
            "fontFamily": "\"Inter\", \"Segoe UI\", system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            "fontSizes": {
                "xs": "12px",
                "sm": "14px",
                "base": "15px",
                "lg": "18px",
                "xl": "22px",
            },
            "fontWeights": {
                "normal": 400,
                "medium": 500,
                "semibold": 600,
                "bold": 700,
            },
            "lineHeights": {
                "tight": 1.2,
                "normal": 1.6,
                "relaxed": 1.75,
            },
            "letterSpacing": {
                "tight": "-0.01em",
                "normal": "0",
                "wide": "0.05em",
            },
        },
        "spacing": {
            "radius": {
                "sm": 8,
                "md": 12,
                "lg": 18,
                "pill": 999,
            },
            "paddingScale": [4, 8, 12, 16, 20, 24, 32, 40, 48, 64],
            "gapScale": [4, 8, 12, 16, 20, 24, 32, 40],
        },
        "layout": {
            "containerWidth": 1200,
            "sidebarWidth": 280,
            "tableDensity": "normal",
        },
        "states": {
            "hover": 0.92,
            "active": 0.86,
            "disabled": 0.6,
        },
    },
    "componentOverrides": {
        "button": {
            "primary": {
                "radius": 12,
                "background": "#2563eb",
                "text": "#ffffff",
                "border": "transparent",
                "shadow": "0 6px 16px rgba(15, 23, 42, 0.08)",
                "hoverBg": "#1d4ed8",
                "activeBg": "#1e40af",
                "disabledBg": "#e5e7eb",
                "disabledText": "#94a3b8",
            },
            "secondary": {
                "radius": 12,
                "background": "#ffffff",
                "text": "#1f2937",
                "border": "#e2e8f0",
                "shadow": "none",
                "hoverBg": "#f8fafc",
                "activeBg": "#e2e8f0",
                "disabledBg": "#f1f5f9",
                "disabledText": "#94a3b8",
            },
        },
        "input": {
            "radius": 12,
            "background": "#ffffff",
            "text": "#0f172a",
            "border": "#e2e8f0",
            "focusRing": "rgba(37, 99, 235, 0.35)",
            "shadow": "0 1px 2px rgba(15, 23, 42, 0.06)",
            "placeholder": "#94a3b8",
        },
        "card": {
            "radius": 18,
            "background": "#ffffff",
            "border": "#e5e7eb",
            "shadow": "0 12px 30px rgba(15, 23, 42, 0.12)",
        },
        "table": {
            "radius": 16,
            "headerBg": "#f8fafc",
            "rowBg": "#ffffff",
            "zebraBg": "#f8fafc",
            "border": "#e2e8f0",
        },
        "modal": {
            "radius": 20,
            "background": "#ffffff",
            "shadow": "0 20px 50px rgba(15, 23, 42, 0.16)",
        },
        "toast": {
            "radius": 16,
            "background": "#0f172a",
            "text": "#ffffff",
            "shadow": "0 12px 30px rgba(15, 23, 42, 0.2)",
        },
        "badge": {
            "radius": 999,
            "background": "#eef2ff",
            "text": "#4338ca",
        },
        "navbar": {
            "background": "#ffffff",
            "border": "#e5e7eb",
            "text": "#0f172a",
        },
        "sidebar": {
            "background": "#ffffff",
            "border": "#e5e7eb",
            "text": "#0f172a",
        },
    },
    "layoutPrefs": {
        "density": 1,
        "containerWidth": 1200,
        "sidebarWidth": 280,
        "tableDensity": "normal",
        "rowHeight": 44,
        "zebraStriping": True,
        "formSpacing": 16,
    },
    "featurePrefs": {
        "iconSet": "feather",
        "tableDefaults": {
            "defaultSort": "updated_at:desc",
            "defaultColumns": ["name", "status", "owner", "updated_at"],
        },
        "compactSidebar": False,
    },
}

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
            "asset_categories.view",
            "asset_categories.manage",
            "devices.view",
            "devices.manage",
            "assets.view",
            "assets.manage",
            "asset.assign",
            "asset.checkout",
            "asset.checkin",
            "asset.view_history",
            "locations.view",
            "locations.manage",
            "maintenance.view",
            "maintenance.manage",
            "attachment.upload",
            "attachment.download",
            "attachment.delete",
            "tickets.view_all",
            "tickets.create",
            "tickets.update",
            "tickets.delete",
            "tickets.comment",
            "tickets.comment_internal",
            "tickets.watch",
            "knowledge.view",
            "knowledge.manage",
            "ticket_categories.manage",
            "ticket_alerts.manage",
            "notifications.manage",
            "stats.view",
            "activity.view",
            "roadmap.view",
            "roadmap.manage",
            "dependencies.view",
            "dependencies.manage",
            "timemachine.view",
            "health.view",
            "health.run",
            "software.view",
            "software.manage",
            "procurement.view",
            "procurement.manage",
            "teams.view",
            "teams.manage",
            "departments.view",
            "departments.manage"
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
            "tickets.watch_own",
            "roadmap.view"
        ]
    }
]
def ensure_instance_path():
    APP_INSTANCE_PATH.mkdir(parents=True, exist_ok=True)

def ensure_runtime_directories():
    ensure_instance_path()
    Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        ensure_runtime_directories()
        db = g._database = sqlite3.connect(DATABASE, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = NORMAL")
    return db

def parse_bool_env(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None

def apply_runtime_env_overrides(runtime):
    resolved = dict(runtime)
    env_host = (os.environ.get("INVENTORY_HOST") or "").strip()
    env_port = (os.environ.get("INVENTORY_PORT") or os.environ.get("PORT") or "").strip()
    env_debug = parse_bool_env(os.environ.get("INVENTORY_DEBUG"))
    if env_host:
        resolved["host"] = env_host
    if env_port:
        try:
            resolved["port"] = int(env_port)
        except ValueError:
            pass
    if env_debug is not None:
        resolved["debug"] = env_debug
    return resolved

def load_runtime_settings():
    global RUNTIME_SETTINGS_CACHE
    if RUNTIME_SETTINGS_CACHE is not None:
        return apply_runtime_env_overrides(RUNTIME_SETTINGS_CACHE)
    runtime = None
    if RUNTIME_CONFIG_PATH.exists():
        try:
            runtime = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            runtime = None
    if not runtime:
        runtime = {
            "host": DEFAULT_SERVER_SETTINGS["server"]["host"],
            "port": DEFAULT_SERVER_SETTINGS["server"]["port"],
            "debug": DEFAULT_SERVER_SETTINGS["server"]["debug"]
        }
    runtime = apply_runtime_env_overrides(runtime)
    RUNTIME_SETTINGS_CACHE = runtime
    return runtime

def store_runtime_settings(runtime_settings):
    ensure_instance_path()
    payload = {
        "host": runtime_settings["host"],
        "port": runtime_settings["port"],
        "debug": runtime_settings["debug"]
    }
    RUNTIME_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def store_update_policy(update_settings):
    """Atomically publish the non-sensitive updater policy for the optional sidecar."""
    ensure_instance_path()
    policy_path = APP_INSTANCE_PATH / "update_policy.json"
    policy = {
        "schemaVersion": 1,
        "autoUpdateEnabled": bool(update_settings.get("autoUpdateEnabled")),
        "channel": update_settings.get("channel") or "stable",
        "checkIntervalMinutes": int(update_settings.get("checkIntervalMinutes") or 360),
        "maintenanceWindow": update_settings.get("maintenanceWindow") or "03:30",
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=policy_path.parent,
            prefix=".update-policy-",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(policy, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary_path, policy_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

def parse_ip_whitelist(value):
    if value is None:
        return [], []
    if isinstance(value, list):
        candidates = value
    else:
        candidates = [entry.strip() for entry in str(value).split(',')]
    entries = []
    errors = []
    for entry in candidates:
        if not entry:
            continue
        try:
            if '/' in entry:
                ipaddress.ip_network(entry, strict=False)
            else:
                ipaddress.ip_address(entry)
            entries.append(entry)
        except ValueError:
            errors.append(entry)
    return entries, errors

def merge_settings(base, updates):
    merged = json.loads(json.dumps(base))
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_settings(merged[key], value)
        else:
            merged[key] = value
    return merged

def compute_pending_restart(settings):
    runtime = load_runtime_settings()
    server = settings["server"]
    return any([
        server["host"] != runtime.get("host"),
        server["port"] != runtime.get("port"),
        bool(server["debug"]) != bool(runtime.get("debug"))
    ])

def serialize_server_settings(settings_row):
    if not settings_row:
        settings = json.loads(json.dumps(DEFAULT_SERVER_SETTINGS))
    else:
        ip_whitelist, _ = parse_ip_whitelist(settings_row["allowed_ip_ranges"] or "")
        terminal_allowlist, _ = parse_ip_whitelist(settings_row["terminal_ip_allowlist"] or "")
        update_policy = merge_settings(
            DEFAULT_SERVER_SETTINGS["updates"],
            safe_json_load(settings_row["update_policy_json"], {}),
        )
        settings = {
            "schemaVersion": settings_row["schema_version"] or SETTINGS_SCHEMA_VERSION,
            "server": {
                "host": settings_row["host"] or DEFAULT_SERVER_SETTINGS["server"]["host"],
                "port": settings_row["port"] or DEFAULT_SERVER_SETTINGS["server"]["port"],
                "debug": bool(settings_row["debug_mode"])
            },
            "proFeaturesEnabled": bool(settings_row["pro_enabled"]),
            "backup": {
                "enabled": bool(settings_row["backup_enabled"]),
                "compress": bool(settings_row["backup_compress"]),
                "schedule": settings_row["backup_schedule"] or DEFAULT_SERVER_SETTINGS["backup"]["schedule"],
                "time": settings_row["backup_time"] or DEFAULT_SERVER_SETTINGS["backup"]["time"],
                "retentionDays": settings_row["backup_retention_days"] or DEFAULT_SERVER_SETTINGS["backup"]["retentionDays"],
                "directory": settings_row["backup_location"] or DEFAULT_SERVER_SETTINGS["backup"]["directory"],
                "notifyEmail": settings_row["backup_notify_email"] or "",
                "encrypt": bool(settings_row["backup_encrypt"])
            },
            "updates": update_policy,
            "importExport": {
                "exportAllowed": bool(settings_row["allow_db_export"] if settings_row["allow_db_export"] is not None else DEFAULT_SERVER_SETTINGS["importExport"]["exportAllowed"]),
                "importAllowed": bool(settings_row["allow_db_import"]),
                "exportFormat": settings_row["export_format"] or DEFAULT_SERVER_SETTINGS["importExport"]["exportFormat"],
                "importMode": settings_row["import_mode"] or DEFAULT_SERVER_SETTINGS["importExport"]["importMode"],
                "includeUploads": bool(settings_row["include_uploads"] if settings_row["include_uploads"] is not None else DEFAULT_SERVER_SETTINGS["importExport"]["includeUploads"])
            },
            "security": {
                "forceHttps": bool(settings_row["require_https"]),
                "requireMfa": bool(settings_row["enforce_mfa"]),
                "sessionTimeoutMinutes": settings_row["session_timeout_minutes"] or DEFAULT_SERVER_SETTINGS["security"]["sessionTimeoutMinutes"],
                "maxFailedAttempts": settings_row["max_failed_logins"] or DEFAULT_SERVER_SETTINGS["security"]["maxFailedAttempts"],
                "lockoutMinutes": settings_row["lockout_minutes"] or DEFAULT_SERVER_SETTINGS["security"]["lockoutMinutes"],
                "ipWhitelist": ip_whitelist,
                "minPasswordLength": settings_row["password_min_length"] or DEFAULT_SERVER_SETTINGS["security"]["minPasswordLength"]
            },
            "terminal": {
                "enabled": bool(settings_row["terminal_enabled"]),
                "requireReauth": bool(settings_row["terminal_require_reauth"]),
                "ipAllowlist": terminal_allowlist,
                "allowDbWrite": bool(settings_row["terminal_allow_db_write"]),
                "allowServiceRestart": bool(settings_row["terminal_allow_service_restart"]),
                "breakGlassMode": bool(settings_row["terminal_break_glass"])
            }
        }
    settings["schemaVersion"] = SETTINGS_SCHEMA_VERSION
    pending_restart = compute_pending_restart(settings)
    meta = {
        "schemaVersion": SETTINGS_SCHEMA_VERSION,
        "pendingRestart": pending_restart,
        "requiresRestartFields": ["server.host", "server.port", "server.debug"],
        "updatedAt": settings_row["updated_at"] if settings_row else None,
        "updatedBy": settings_row["updated_by"] if settings_row else None,
        "enforcedCapabilities": {
            "forceHttps": {"enforced": bool(settings["security"]["forceHttps"]), "infraRequired": True},
            "requireMfa": {"enforced": bool(settings["security"]["requireMfa"]), "infraRequired": False},
            "backupScheduler": {"enforced": bool(settings["backup"]["enabled"]), "infraRequired": False},
            "autoUpdates": {"enforced": bool(settings["updates"]["autoUpdateEnabled"]), "infraRequired": True},
            "ipWhitelist": {"enforced": bool(settings["security"]["ipWhitelist"]), "infraRequired": False}
        },
        "warnings": []
    }
    if settings["backup"]["encrypt"] and not os.environ.get("BACKUP_ENCRYPTION_KEY"):
        meta["warnings"].append("BACKUP_ENCRYPTION_KEY fehlt. Verschlüsselung ist nicht verfügbar.")
    if settings["terminal"]["enabled"]:
        meta["warnings"].append("Terminal ist aktiviert. Zugriff nur für Admins und freigegebene IPs erlauben.")
    if settings["updates"]["autoUpdateEnabled"] and not parse_bool_env(os.environ.get("INVENTORY_UPDATER_ENABLED")):
        meta["warnings"].append("Automatische Updates sind aktiviert, aber der abgesicherte Updater-Dienst wurde noch nicht bereitgestellt.")
    return settings, meta

def validate_settings_payload(payload, partial=False):
    errors = {}
    if not isinstance(payload, dict):
        return None, {"settings": "Payload muss ein Objekt sein."}
    merged = merge_settings(DEFAULT_SERVER_SETTINGS, payload) if not partial else merge_settings(DEFAULT_SERVER_SETTINGS, payload)
    server = merged.get("server", {})
    host = (server.get("host") or "").strip()
    if not host:
        errors["server.host"] = "Host darf nicht leer sein."
    try:
        port = int(server.get("port"))
    except (TypeError, ValueError):
        errors["server.port"] = "Port muss eine Zahl sein."
        port = None
    if port is not None and (port < 1 or port > 65535):
        errors["server.port"] = "Port muss zwischen 1 und 65535 liegen."
    debug = bool(server.get("debug"))

    backup = merged.get("backup", {})
    schedule = (backup.get("schedule") or "").lower()
    if schedule not in {"daily", "custom"}:
        errors["backup.schedule"] = "Backup-Rhythmus muss daily oder custom sein."
    time_value = (backup.get("time") or "").strip()
    if time_value and not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', time_value):
        errors["backup.time"] = "Backup-Zeit muss im Format HH:MM sein."
    retention = backup.get("retentionDays")
    try:
        retention = int(retention)
    except (TypeError, ValueError):
        errors["backup.retentionDays"] = "Retention muss eine Zahl sein."
    else:
        if retention < 1:
            errors["backup.retentionDays"] = "Retention muss mindestens 1 sein."
    notify_email = (backup.get("notifyEmail") or "").strip()
    if notify_email and not re.match(r'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$', notify_email):
        errors["backup.notifyEmail"] = "E-Mail-Adresse ist ungültig."
    if backup.get("encrypt") and not os.environ.get("BACKUP_ENCRYPTION_KEY"):
        errors["backup.encrypt"] = "BACKUP_ENCRYPTION_KEY fehlt. Verschlüsselung kann nicht aktiviert werden."

    updates = merged.get("updates", {})
    update_channel = (updates.get("channel") or "").strip().lower()
    if update_channel != "stable":
        errors["updates.channel"] = "Nur der signierte Stable-Kanal ist zulässig."
    update_interval = updates.get("checkIntervalMinutes")
    try:
        update_interval = int(update_interval)
    except (TypeError, ValueError):
        errors["updates.checkIntervalMinutes"] = "Prüfintervall muss eine Zahl sein."
    else:
        if update_interval < 15 or update_interval > 1440:
            errors["updates.checkIntervalMinutes"] = "Prüfintervall muss zwischen 15 und 1440 Minuten liegen."
    update_window = (updates.get("maintenanceWindow") or "").strip()
    if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', update_window):
        errors["updates.maintenanceWindow"] = "Wartungsfenster muss im Format HH:MM sein."

    import_export = merged.get("importExport", {})
    export_format = (import_export.get("exportFormat") or "").lower()
    if export_format not in {"sqlite", "csv", "json"}:
        errors["importExport.exportFormat"] = "Export-Format ist ungültig."
    import_mode = (import_export.get("importMode") or "").lower()
    if import_mode not in {"merge", "replace", "append"}:
        errors["importExport.importMode"] = "Import-Modus ist ungültig."

    security = merged.get("security", {})
    session_timeout = security.get("sessionTimeoutMinutes")
    try:
        session_timeout = int(session_timeout)
    except (TypeError, ValueError):
        errors["security.sessionTimeoutMinutes"] = "Session-Timeout muss eine Zahl sein."
    else:
        if session_timeout < 5 or session_timeout > 1440:
            errors["security.sessionTimeoutMinutes"] = "Session-Timeout muss zwischen 5 und 1440 liegen."
    max_failed = security.get("maxFailedAttempts")
    try:
        max_failed = int(max_failed)
    except (TypeError, ValueError):
        errors["security.maxFailedAttempts"] = "Max. Fehlversuche muss eine Zahl sein."
    else:
        if max_failed < 1 or max_failed > 20:
            errors["security.maxFailedAttempts"] = "Max. Fehlversuche muss zwischen 1 und 20 liegen."
    lockout = security.get("lockoutMinutes")
    try:
        lockout = int(lockout)
    except (TypeError, ValueError):
        errors["security.lockoutMinutes"] = "Sperrdauer muss eine Zahl sein."
    else:
        if lockout < 1 or lockout > 240:
            errors["security.lockoutMinutes"] = "Sperrdauer muss zwischen 1 und 240 liegen."
    min_password = security.get("minPasswordLength")
    try:
        min_password = int(min_password)
    except (TypeError, ValueError):
        errors["security.minPasswordLength"] = "Passwortlänge muss eine Zahl sein."
    else:
        if min_password < 6 or min_password > 64:
            errors["security.minPasswordLength"] = "Passwortlänge muss zwischen 6 und 64 liegen."
    ip_whitelist, ip_errors = parse_ip_whitelist(security.get("ipWhitelist", []))
    if ip_errors:
        errors["security.ipWhitelist"] = f"Ungültige IP/CIDR: {', '.join(ip_errors)}"

    terminal = merged.get("terminal", {})
    terminal_allowlist, terminal_errors = parse_ip_whitelist(terminal.get("ipAllowlist", []))
    if terminal_errors:
        errors["terminal.ipAllowlist"] = f"Ungültige IP/CIDR: {', '.join(terminal_errors)}"

    if errors:
        return None, errors

    merged["server"]["host"] = host
    merged["server"]["port"] = port
    merged["server"]["debug"] = debug
    merged["backup"]["schedule"] = schedule
    merged["backup"]["time"] = time_value
    merged["backup"]["retentionDays"] = retention
    merged["backup"]["notifyEmail"] = notify_email
    merged["updates"]["autoUpdateEnabled"] = bool(updates.get("autoUpdateEnabled"))
    merged["updates"]["channel"] = update_channel
    merged["updates"]["checkIntervalMinutes"] = update_interval
    merged["updates"]["maintenanceWindow"] = update_window
    merged["importExport"]["exportFormat"] = export_format
    merged["importExport"]["importMode"] = import_mode
    merged["security"]["sessionTimeoutMinutes"] = session_timeout
    merged["security"]["maxFailedAttempts"] = max_failed
    merged["security"]["lockoutMinutes"] = lockout
    merged["security"]["minPasswordLength"] = min_password
    merged["security"]["ipWhitelist"] = ip_whitelist
    merged["terminal"]["enabled"] = bool(terminal.get("enabled"))
    merged["terminal"]["requireReauth"] = bool(terminal.get("requireReauth"))
    merged["terminal"]["ipAllowlist"] = terminal_allowlist
    merged["terminal"]["allowDbWrite"] = bool(terminal.get("allowDbWrite"))
    merged["terminal"]["allowServiceRestart"] = bool(terminal.get("allowServiceRestart"))
    merged["terminal"]["breakGlassMode"] = bool(terminal.get("breakGlassMode"))
    merged["schemaVersion"] = SETTINGS_SCHEMA_VERSION
    return merged, None

def persist_server_settings(db, settings, updated_by):
    db.execute(
        '''
        UPDATE server_settings
        SET host = ?,
            port = ?,
            debug_mode = ?,
            pro_enabled = ?,
            backup_enabled = ?,
            backup_schedule = ?,
            backup_time = ?,
            backup_retention_days = ?,
            backup_location = ?,
            backup_compress = ?,
            backup_encrypt = ?,
            backup_notify_email = ?,
            allow_db_import = ?,
            allow_db_export = ?,
            export_format = ?,
            import_mode = ?,
            include_uploads = ?,
            require_https = ?,
            session_timeout_minutes = ?,
            max_failed_logins = ?,
            lockout_minutes = ?,
            allowed_ip_ranges = ?,
            password_min_length = ?,
            enforce_mfa = ?,
            terminal_enabled = ?,
            terminal_require_reauth = ?,
            terminal_ip_allowlist = ?,
            terminal_allow_db_write = ?,
            terminal_allow_service_restart = ?,
            terminal_break_glass = ?,
            update_policy_json = ?,
            schema_version = ?,
            updated_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        ''',
        (
            settings["server"]["host"],
            settings["server"]["port"],
            1 if settings["server"]["debug"] else 0,
            1 if settings["proFeaturesEnabled"] else 0,
            1 if settings["backup"]["enabled"] else 0,
            settings["backup"]["schedule"],
            settings["backup"]["time"],
            settings["backup"]["retentionDays"],
            settings["backup"]["directory"],
            1 if settings["backup"]["compress"] else 0,
            1 if settings["backup"]["encrypt"] else 0,
            settings["backup"]["notifyEmail"],
            1 if settings["importExport"]["importAllowed"] else 0,
            1 if settings["importExport"]["exportAllowed"] else 0,
            settings["importExport"]["exportFormat"],
            settings["importExport"]["importMode"],
            1 if settings["importExport"]["includeUploads"] else 0,
            1 if settings["security"]["forceHttps"] else 0,
            settings["security"]["sessionTimeoutMinutes"],
            settings["security"]["maxFailedAttempts"],
            settings["security"]["lockoutMinutes"],
            ",".join(settings["security"]["ipWhitelist"]),
            settings["security"]["minPasswordLength"],
            1 if settings["security"]["requireMfa"] else 0,
            1 if settings["terminal"]["enabled"] else 0,
            1 if settings["terminal"]["requireReauth"] else 0,
            ",".join(settings["terminal"]["ipAllowlist"]),
            1 if settings["terminal"]["allowDbWrite"] else 0,
            1 if settings["terminal"]["allowServiceRestart"] else 0,
            1 if settings["terminal"]["breakGlassMode"] else 0,
            json.dumps(settings["updates"], sort_keys=True, separators=(",", ":")),
            SETTINGS_SCHEMA_VERSION,
            updated_by
        )
    )
    db.execute(
        '''
        INSERT INTO server_settings_revisions (settings_json, created_by)
        VALUES (?, ?)
        ''',
        (json.dumps(settings), updated_by)
    )
    store_runtime_settings(settings["server"])

def get_password_min_length(db):
    settings_row = get_server_settings(db)
    if not settings_row:
        return DEFAULT_SERVER_SETTINGS["security"]["minPasswordLength"]
    return settings_row["password_min_length"] or DEFAULT_SERVER_SETTINGS["security"]["minPasswordLength"]

def should_rate_limit(key):
    return RATE_LIMIT_CACHE.is_limited(
        key,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
    )

def should_rate_limit_terminal(user_id):
    key = f"terminal:{user_id}"
    return TERMINAL_RATE_LIMIT_CACHE.is_limited(
        key,
        window_seconds=TERMINAL_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=TERMINAL_RATE_LIMIT_MAX_REQUESTS,
    )

def should_rate_limit_inventory_proxy(user_id):
    key = f"inventory_links_proxy:{user_id}"
    return INVENTORY_LINK_PROXY_RATE_LIMIT_CACHE.is_limited(
        key,
        window_seconds=INVENTORY_LINK_PROXY_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=INVENTORY_LINK_PROXY_RATE_LIMIT_MAX_REQUESTS,
    )

def get_remote_ip():
    return get_client_ip()

def is_ip_allowed(remote_ip, allowlist):
    if not allowlist:
        return True
    for entry in allowlist:
        try:
            if "/" in entry:
                if ipaddress.ip_address(remote_ip) in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if remote_ip == entry:
                    return True
        except ValueError:
            continue
    return False

def normalize_inventory_link_base_url(base_url):
    if not base_url:
        raise ValueError("Base URL fehlt.")
    candidate = base_url.strip()
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Base URL muss mit http oder https beginnen.")
    if not parsed.netloc:
        raise ValueError("Base URL benötigt einen Host.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL darf keine Zugangsdaten enthalten.")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL darf keine Query oder Fragmente enthalten.")
    path = (parsed.path or "").rstrip("/")
    if path == "/":
        path = ""
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))

def resolve_inventory_link_ips(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []
    ips = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            ips.append(sockaddr[0])
    return list(dict.fromkeys(ips))

def inventory_links_allow_loopback():
    return os.environ.get("INVENTORY_LINKS_ALLOW_LOOPBACK", "0").lower() in {"1", "true", "yes"}

def is_inventory_link_ip_blocked(ip_str, allow_private_network):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip_obj.is_loopback and not inventory_links_allow_loopback():
        return True
    if ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified or ip_obj.is_reserved:
        return True
    if str(ip_obj) == "169.254.169.254":
        return True
    if ip_obj.is_private and not allow_private_network:
        return True
    return False

def validate_inventory_link_target(base_url, allow_private_network):
    normalized = normalize_inventory_link_base_url(base_url)
    parsed = urllib.parse.urlsplit(normalized)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Base URL Host konnte nicht gelesen werden.")
    resolved_ips = resolve_inventory_link_ips(hostname)
    if not resolved_ips:
        raise ValueError("Host konnte nicht aufgelöst werden.")
    for ip_str in resolved_ips:
        if is_inventory_link_ip_blocked(ip_str, allow_private_network):
            raise ValueError("Zieladresse ist nicht erlaubt.")
    return parsed

def is_inventory_link_private_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip_obj.is_loopback:
        return inventory_links_allow_loopback()
    return (
        ip_obj.is_private
        and not ip_obj.is_link_local
        and not ip_obj.is_multicast
        and not ip_obj.is_unspecified
        and not ip_obj.is_reserved
    )

def normalize_inventory_link_connection_scope(scope):
    normalized = (scope or "internet").strip().lower()
    if normalized not in {"internet", "local"}:
        raise ValueError("Verbindungsart muss Internet oder lokales Netzwerk sein.")
    return normalized

def validate_inventory_link_configuration(base_url, connection_scope, verify_tls, allow_private_network):
    """Validate an inventory connection as a safe Internet or LAN-only route.

    Keeping the two paths explicit avoids ambiguous settings such as a public URL
    with private-network access enabled. Resolution is repeated for every proxy
    request to reduce DNS rebinding exposure.
    """
    normalized = normalize_inventory_link_base_url(base_url)
    scope = normalize_inventory_link_connection_scope(connection_scope)
    parsed = urllib.parse.urlsplit(normalized)

    if scope == "internet":
        if parsed.scheme != "https":
            raise ValueError("Internet-Verbindungen benötigen HTTPS.")
        if not verify_tls:
            raise ValueError("Internet-Verbindungen müssen das TLS-Zertifikat prüfen.")
        if allow_private_network:
            raise ValueError("Internet-Verbindungen dürfen keine privaten Netzwerkziele zulassen.")
        validate_inventory_link_target(normalized, False)
        return normalized, scope, True, False

    if not allow_private_network:
        raise ValueError("Lokale Verbindungen benötigen die Freigabe für private Netzwerkziele.")
    validate_inventory_link_target(normalized, True)
    resolved_ips = resolve_inventory_link_ips(parsed.hostname)
    if not resolved_ips or any(not is_inventory_link_private_ip(ip_str) for ip_str in resolved_ips):
        raise ValueError("Lokale Verbindungen dürfen nur auf private LAN-Adressen zeigen.")
    return normalized, scope, bool(verify_tls), True

def can_manage_local_inventory_links(access):
    return bool(access.get("is_superuser") or "server_settings.manage" in access.get("permissions", set()))

def enforce_inventory_link_scope_access(access, connection_scope):
    if connection_scope == "local" and not can_manage_local_inventory_links(access):
        return "Lokale Inventory-Link-Verbindungen benötigen Administratorrechte."
    return None

def parse_inventory_link_login_secret(secret):
    if not secret or ":" not in secret:
        raise ValueError("Login-Secret muss im Format Benutzername:Passwort vorliegen.")
    username, password = secret.split(":", 1)
    username = username.strip()
    if not username or not password:
        raise ValueError("Login-Secret muss Benutzername und Passwort enthalten.")
    return username, password

def extract_inventory_link_cookie_header(cookie_jar):
    cookies = []
    expiry_candidates = []
    for cookie in cookie_jar:
        cookies.append(f"{cookie.name}={cookie.value}")
        if cookie.expires:
            expiry_candidates.append(cookie.expires)
    if not cookies:
        return None, None
    expires_at = min(expiry_candidates) if expiry_candidates else None
    return "; ".join(cookies), expires_at

class InventoryLinkConnectionError(RuntimeError):
    pass

def get_cached_inventory_link_cookie(link, user_id):
    cache_key = f"{user_id}:{link['id']}"
    cached = INVENTORY_LINK_LOGIN_SESSION_CACHE.get(cache_key)
    if not cached:
        return None
    if cached["expires_at"] is None or cached["expires_at"] > time.time():
        return cached["cookie"]
    INVENTORY_LINK_LOGIN_SESSION_CACHE.pop(cache_key, None)
    return None

def login_inventory_link_session(base_url, verify_tls, secret):
    username, password = parse_inventory_link_login_secret(secret)
    login_url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", "login")
    payload = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html",
        "User-Agent": "InventoryPro-Link/1.0"
    }
    cookie_jar = http.cookiejar.CookieJar()
    handlers = [
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(cookie_jar)
    ]
    context = None
    if base_url.startswith("https://"):
        context = build_inventory_link_ssl_context(verify_tls)
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(login_url, data=payload, headers=headers, method="POST")
    try:
        opener.open(req, timeout=INVENTORY_LINK_PROXY_TIMEOUT_SECONDS).read(1024)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ValueError("Login fehlgeschlagen. Prüfe Benutzername/Passwort.") from exc
        raise InventoryLinkConnectionError(f"Login fehlgeschlagen (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        reason = getattr(exc, "reason", exc)
        raise InventoryLinkConnectionError(f"Login-Verbindung fehlgeschlagen: {reason}") from exc
    cookie_header, expires_at = extract_inventory_link_cookie_header(cookie_jar)
    return cookie_header, expires_at

def get_inventory_link_login_cookie(link, secret, user_id):
    cached_cookie = get_cached_inventory_link_cookie(link, user_id)
    if cached_cookie:
        return cached_cookie
    cache_key = f"{user_id}:{link['id']}"
    cookie_header, expires_at = login_inventory_link_session(
        link["base_url"],
        bool(link["verify_tls"]),
        secret
    )
    if not cookie_header:
        raise ValueError("Login fehlgeschlagen. Prüfe Benutzername/Passwort.")
    INVENTORY_LINK_LOGIN_SESSION_CACHE.set(cache_key, {
        "cookie": cookie_header,
        "expires_at": expires_at or (time.time() + INVENTORY_LINK_LOGIN_TTL_SECONDS)
    }, INVENTORY_LINK_LOGIN_TTL_SECONDS)
    return cookie_header

def serialize_inventory_link(row):
    return {
        "id": row["id"],
        "displayName": row["display_name"],
        "baseUrl": row["base_url"],
        "verifyTls": bool(row["verify_tls"]),
        "authMode": row["auth_mode"],
        "allowPrivateNetwork": bool(row["allow_private_network"]),
        "connectionScope": row["connection_scope"] or "internet",
        "healthStatus": row["health_status"],
        "lastCheckedAt": row["health_last_checked_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }

def list_inventory_links(db, user_id):
    rows = db.execute(
        '''
        SELECT id, display_name, base_url, verify_tls, auth_mode, allow_private_network, connection_scope,
               health_status, health_last_checked_at, created_at, updated_at
        FROM inventory_links
        WHERE user_id = ?
        ORDER BY display_name
        ''',
        (user_id,)
    ).fetchall()
    return [serialize_inventory_link(row) for row in rows]

def get_inventory_link(db, user_id, link_id):
    return db.execute(
        '''
        SELECT *
        FROM inventory_links
        WHERE id = ? AND user_id = ?
        ''',
        (link_id, user_id)
    ).fetchone()

def update_inventory_link_health(db, link_id, status):
    db.execute(
        '''
        UPDATE inventory_links
        SET health_status = ?, health_last_checked_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (status, datetime.utcnow().isoformat(), link_id)
    )

def build_inventory_link_target_url(base_url, subpath, query_string):
    base = base_url.rstrip("/")
    if subpath:
        target = f"{base}/{subpath}"
    else:
        target = f"{base}/"
    if query_string:
        query = query_string.decode("utf-8") if isinstance(query_string, (bytes, bytearray)) else str(query_string)
        target = f"{target}?{query}"
    return target

def build_inventory_link_request_headers(auth_mode, secret, link=None, user_id=None):
    headers = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in {
            "host", "origin", "referer", "cookie", "authorization", "proxy-authorization",
            "content-length", "accept-encoding"
        }:
            continue
        headers[key] = value
    if auth_mode == "apiKey":
        headers["X-API-Key"] = secret
    elif auth_mode == "bearerToken":
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_mode == "basic":
        encoded = base64.b64encode(secret.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded}"
    elif auth_mode == "login" and link and user_id:
        if secret:
            cookie_header = get_inventory_link_login_cookie(link, secret, user_id)
        else:
            cookie_header = get_cached_inventory_link_cookie(link, user_id)
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers

def rewrite_inventory_link_location(location, link_id, base_url):
    if not location:
        return None
    rewritten = rewrite_inventory_link_url_reference(location, link_id, base_url)
    if rewritten == location:
        return None
    return rewritten

def get_inventory_link_proxy_prefix(link_id):
    return f"/api/inventory-links/{link_id}/proxy"

def rewrite_inventory_link_url_reference(url, link_id, base_url):
    if not url:
        return url
    proxy_prefix = get_inventory_link_proxy_prefix(link_id)
    if url.startswith(proxy_prefix):
        return url
    if url.startswith(("data:", "blob:", "javascript:", "mailto:", "tel:", "#", "//")):
        return url
    if url.startswith("/"):
        return f"{proxy_prefix}{url}"
    joined = urllib.parse.urlsplit(urllib.parse.urljoin(f"{base_url.rstrip('/')}/", url))
    base_parsed = urllib.parse.urlsplit(base_url)
    if joined.scheme and joined.netloc:
        if joined.scheme != base_parsed.scheme or joined.netloc != base_parsed.netloc:
            return url
    path = joined.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    query = f"?{joined.query}" if joined.query else ""
    fragment = f"#{joined.fragment}" if joined.fragment else ""
    return f"{proxy_prefix}{path}{query}{fragment}"

def get_inventory_link_response_charset(content_type):
    if not content_type:
        return "utf-8"
    match = re.search(r"charset=([^\s;]+)", content_type, re.IGNORECASE)
    if not match:
        return "utf-8"
    return match.group(1).strip("\"'")

def should_rewrite_inventory_link_response(content_type):
    if not content_type:
        return False
    lowered = content_type.lower()
    return any(token in lowered for token in INVENTORY_LINK_PROXY_TEXT_CONTENT_TYPES)

def build_inventory_link_runtime_injection(link_id, base_url):
    proxy_prefix = get_inventory_link_proxy_prefix(link_id)
    remote_origin = f"{urllib.parse.urlsplit(base_url).scheme}://{urllib.parse.urlsplit(base_url).netloc}"
    proxy_prefix_json = json.dumps(proxy_prefix)
    remote_origin_json = json.dumps(remote_origin)
    return f"""
<base href="{proxy_prefix.rstrip('/')}/">
<script>
(function () {{
    const PROXY_PREFIX = {proxy_prefix_json};
    const REMOTE_ORIGIN = {remote_origin_json};
    const URL_ATTRIBUTES = ['href', 'src', 'action', 'poster'];
    const IGNORE_PATTERN = /^(?:data:|blob:|javascript:|mailto:|tel:|#)/i;

    function proxify(url) {{
        if (!url || typeof url !== 'string') {{
            return url;
        }}
        if (url.startsWith(PROXY_PREFIX) || IGNORE_PATTERN.test(url) || url.startsWith('//')) {{
            return url;
        }}
        if (url.startsWith('/')) {{
            return PROXY_PREFIX + url;
        }}
        try {{
            const parsed = new URL(url, window.location.href);
            const path = (parsed.pathname || '/') + (parsed.search || '') + (parsed.hash || '');
            if (parsed.origin === window.location.origin) {{
                if (path.startsWith(PROXY_PREFIX)) {{
                    return path;
                }}
                return PROXY_PREFIX + (path.startsWith('/') ? path : '/' + path);
            }}
            if (parsed.origin === REMOTE_ORIGIN) {{
                return PROXY_PREFIX + (path.startsWith('/') ? path : '/' + path);
            }}
        }} catch (error) {{
            return url;
        }}
        return url;
    }}

    function rewriteSrcset(value) {{
        if (!value) {{
            return value;
        }}
        return value.split(',').map((entry) => {{
            const trimmed = entry.trim();
            if (!trimmed) {{
                return trimmed;
            }}
            const parts = trimmed.split(/\\s+/);
            parts[0] = proxify(parts[0]);
            return parts.join(' ');
        }}).join(', ');
    }}

    function rewriteElement(node) {{
        if (!(node instanceof Element)) {{
            return;
        }}
        URL_ATTRIBUTES.forEach((attribute) => {{
            if (!node.hasAttribute(attribute)) {{
                return;
            }}
            const current = node.getAttribute(attribute);
            const rewritten = proxify(current);
            if (rewritten !== current) {{
                node.setAttribute(attribute, rewritten);
            }}
        }});
        if (node.hasAttribute('srcset')) {{
            const currentSrcset = node.getAttribute('srcset');
            const rewrittenSrcset = rewriteSrcset(currentSrcset);
            if (rewrittenSrcset !== currentSrcset) {{
                node.setAttribute('srcset', rewrittenSrcset);
            }}
        }}
    }}

    function rewriteTree(root) {{
        if (!root) {{
            return;
        }}
        if (root instanceof Element) {{
            rewriteElement(root);
        }}
        if (root.querySelectorAll) {{
            root.querySelectorAll('[href],[src],[action],[poster],[srcset]').forEach(rewriteElement);
        }}
    }}

    if (window.fetch) {{
        const originalFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {{
            if (typeof input === 'string') {{
                return originalFetch(proxify(input), init);
            }}
            if (input instanceof URL) {{
                return originalFetch(proxify(input.toString()), init);
            }}
            if (window.Request && input instanceof Request) {{
                return originalFetch(new Request(proxify(input.url), input), init);
            }}
            return originalFetch(input, init);
        }};
    }}

    const originalXhrOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {{
        if (typeof url === 'string') {{
            arguments[1] = proxify(url);
        }}
        return originalXhrOpen.apply(this, arguments);
    }};

    const originalPushState = history.pushState.bind(history);
    history.pushState = function (state, title, url) {{
        if (typeof url === 'string') {{
            url = proxify(url);
        }}
        return originalPushState(state, title, url);
    }};

    const originalReplaceState = history.replaceState.bind(history);
    history.replaceState = function (state, title, url) {{
        if (typeof url === 'string') {{
            url = proxify(url);
        }}
        return originalReplaceState(state, title, url);
    }};

    const originalSubmit = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function () {{
        if (this.hasAttribute('action')) {{
            const action = this.getAttribute('action');
            const rewritten = proxify(action);
            if (rewritten !== action) {{
                this.setAttribute('action', rewritten);
            }}
        }}
        return originalSubmit.call(this);
    }};

    document.addEventListener('click', (event) => {{
        const link = event.target.closest('a[href]');
        if (!link) {{
            return;
        }}
        const href = link.getAttribute('href');
        const rewritten = proxify(href);
        if (rewritten !== href) {{
            link.setAttribute('href', rewritten);
        }}
    }}, true);

    document.addEventListener('submit', (event) => {{
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('action')) {{
            return;
        }}
        const action = form.getAttribute('action');
        const rewritten = proxify(action);
        if (rewritten !== action) {{
            form.setAttribute('action', rewritten);
        }}
    }}, true);

    const observer = new MutationObserver((mutations) => {{
        mutations.forEach((mutation) => {{
            if (mutation.type === 'attributes' && mutation.target instanceof Element) {{
                rewriteElement(mutation.target);
            }}
            mutation.addedNodes.forEach((node) => rewriteTree(node));
        }});
    }});

    if (document.documentElement) {{
        observer.observe(document.documentElement, {{
            subtree: true,
            childList: true,
            attributes: true,
            attributeFilter: URL_ATTRIBUTES.concat(['srcset'])
        }});
    }}

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', () => rewriteTree(document));
    }} else {{
        rewriteTree(document);
    }}

    window.__inventoryLinkProxify = proxify;
}})();
</script>
"""

def rewrite_inventory_link_text_content(payload, content_type, link_id, base_url):
    charset = get_inventory_link_response_charset(content_type)
    route_prefix_pattern = "|".join(re.escape(item) for item in INVENTORY_LINK_PROXY_REWRITE_PATH_PREFIXES)
    text = payload.decode(charset, errors="replace")

    def replace_attr(match):
        prefix, quote, url = match.groups()
        rewritten = rewrite_inventory_link_url_reference(url, link_id, base_url)
        return f"{prefix}{quote}{rewritten}{quote}"

    def replace_css_url(match):
        prefix, quote, url, suffix = match.groups()
        rewritten = rewrite_inventory_link_url_reference(url, link_id, base_url)
        return f"{prefix}{quote}{rewritten}{quote}{suffix}"

    def replace_srcset(match):
        prefix, quote, urls = match.groups()
        candidates = []
        for candidate in urls.split(","):
            entry = candidate.strip()
            if not entry:
                continue
            parts = entry.split()
            parts[0] = rewrite_inventory_link_url_reference(parts[0], link_id, base_url)
            candidates.append(" ".join(parts))
        return f"{prefix}{quote}{', '.join(candidates)}{quote}"

    def replace_refresh(match):
        prefix, quote, refresh_prefix, url = match.groups()
        rewritten = rewrite_inventory_link_url_reference(url, link_id, base_url)
        return f"{prefix}{quote}{refresh_prefix}{rewritten}{quote}"

    def replace_js_paths(match):
        quote, url = match.groups()
        rewritten = rewrite_inventory_link_url_reference(url, link_id, base_url)
        return f"{quote}{rewritten}{quote}"

    text = re.sub(
        r'(\b(?:href|src|action|poster)\s*=\s*)(["\'])([^"\']+)\2',
        replace_attr,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'(\bsrcset\s*=\s*)(["\'])([^"\']*)\2',
        replace_srcset,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'(\bcontent\s*=\s*)(["\'])([^"\']*url=)([^"\']+)\2',
        replace_refresh,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'(url\(\s*)(["\']?)(/[^)"\']+)\2(\s*\))',
        replace_css_url,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        rf'(["\'`])((?:/(?:{route_prefix_pattern})(?:[^"\'`<\\]*)?)|/(?:[?#][^"\'`<\\]*)?|/)\1',
        replace_js_paths,
        text
    )

    lowered = (content_type or "").lower()
    if "text/html" in lowered or "application/xhtml+xml" in lowered:
        text = re.sub(
            r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>\s*',
            '',
            text,
            flags=re.IGNORECASE
        )
        injection = build_inventory_link_runtime_injection(link_id, base_url)
        if re.search(r"<head\b[^>]*>", text, flags=re.IGNORECASE):
            text = re.sub(
                r'(<head\b[^>]*>)',
                lambda match: match.group(1) + injection,
                text,
                count=1,
                flags=re.IGNORECASE
            )
        else:
            text = injection + text

    return text.encode(charset, errors="replace")

def filter_inventory_link_response_headers(headers, link_id, base_url):
    filtered = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in {
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade", "content-length",
            "set-cookie", "content-encoding", "x-frame-options",
            "content-security-policy", "content-security-policy-report-only"
        }:
            continue
        if lower == "location":
            rewritten = rewrite_inventory_link_location(value, link_id, base_url)
            if rewritten is None:
                continue
            filtered[key] = rewritten
            continue
        filtered[key] = value
    return filtered

def build_inventory_link_ssl_context(verify_tls):
    if verify_tls:
        return ssl.create_default_context()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

def stream_inventory_link_response(resp):
    def generate():
        try:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()
    return generate()

def build_inventory_link_static_headers(auth_mode, secret, base_url=None, verify_tls=True):
    headers = {"Accept": "application/json"}
    if auth_mode == "apiKey":
        headers["X-API-Key"] = secret
    elif auth_mode == "bearerToken":
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_mode == "basic":
        encoded = base64.b64encode(secret.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded}"
    elif auth_mode == "login" and base_url and secret:
        cookie_header, _ = login_inventory_link_session(base_url, verify_tls, secret)
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers

def perform_inventory_link_test(config):
    base_url = config.get("base_url") or ""
    auth_mode = config.get("auth_mode") or "apiKey"
    secret = config.get("secret") or ""
    verify_tls = bool(config.get("verify_tls", True))
    allow_private_network = bool(config.get("allow_private_network", INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS_DEFAULT))
    connection_scope = config.get("connection_scope") or "internet"
    try:
        validate_inventory_link_configuration(
            base_url, connection_scope, verify_tls, allow_private_network
        )
    except ValueError as exc:
        return {"status": "down", "error": str(exc)}

    try:
        headers = build_inventory_link_static_headers(auth_mode, secret, base_url=base_url, verify_tls=verify_tls)
    except ValueError as exc:
        return {"status": "unauthorized", "error": str(exc)}
    except InventoryLinkConnectionError as exc:
        return {"status": "down", "error": str(exc)}
    paths = ["/api/health/summary", "/"]
    last_error = None
    for path in paths:
        target_url = f"{base_url.rstrip('/')}{path}"
        req = urllib.request.Request(target_url, headers=headers, method="GET")
        context = None
        if base_url.startswith("https://"):
            context = build_inventory_link_ssl_context(verify_tls)
        handlers = [urllib.request.ProxyHandler({}), InventoryLinkNoRedirect()]
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        opener = urllib.request.build_opener(*handlers)
        try:
            resp = opener.open(req, timeout=INVENTORY_LINK_PROXY_TIMEOUT_SECONDS)
            status_code = resp.getcode()
            payload = resp.read(4096)
            info = {"statusCode": status_code}
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    info.update(json.loads(payload.decode("utf-8")))
                except json.JSONDecodeError:
                    pass
            return {"status": "ok", "message": "Verbindung erfolgreich.", "info": info}
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                return {"status": "unauthorized", "error": "Nicht autorisiert."}
            last_error = f"HTTP {exc.code}"
        except ssl.SSLError as exc:
            return {"status": "down", "error": f"TLS-Fehler: {str(exc)}"}
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
    return {"status": "down", "error": last_error or "Verbindung fehlgeschlagen."}

REDACT_PATTERNS = [
    re.compile(r"(?i)(password|passphrase|token|secret|api_key|apikey|authorization|bearer|private_key|dsn|connection string)\\s*[:=]\\s*([^\\s,;]+)"),
    re.compile(r"(?i)(aws_access_key_id|aws_secret_access_key|client_secret)\\s*[:=]\\s*([^\\s,;]+)"),
    re.compile(r"(?i)(jdbc:[^\\s]+)"),
]

def redact_text(value):
    if value is None:
        return ""
    text = str(value)
    for pattern in REDACT_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text

def redact_data(value):
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            if str(key).lower() in HEALTH_REDACT_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_data(val)
        return redacted
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value

def truncate_output(text, max_bytes=TERMINAL_MAX_OUTPUT_BYTES):
    if text is None:
        return ""
    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return f"{truncated}\n...output truncated..."

def log_terminal_audit(db, user_id, session_id, action_type, params, status, duration_ms, output_preview=""):
    sanitized_params = redact_data(params or {})
    preview = truncate_output(redact_text(output_preview), max_bytes=2000)
    db.execute(
        '''
        INSERT INTO terminal_audit_logs (user_id, session_id, action_type, params_json, status, duration_ms, output_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            session_id,
            action_type,
            json.dumps(sanitized_params),
            status,
            duration_ms,
            preview
        )
    )
    db.commit()

def validate_hostname(value):
    candidate = (value or "").strip()
    if not candidate or len(candidate) > 255:
        return None
    if re.match(r"^[a-zA-Z0-9.-]+$", candidate) is None:
        return None
    if ".." in candidate:
        return None
    return candidate

def validate_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port < 1 or port > 65535:
        return None
    return port

def safe_subprocess(command, timeout=TERMINAL_DEFAULT_TIMEOUT_SECONDS):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "Zeitüberschreitung."}
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    return {"status": "ok" if result.returncode == 0 else "error", "output": output.strip()}

TERMINAL_SERVICE_ALLOWLIST = [
    "inventorypro",
    "nginx",
    "postgresql",
    "redis",
    "celery"
]

TERMINAL_LOG_SOURCES = {
    "app": str(APP_INSTANCE_PATH / "inventorypro.log"),
    "nginx_access": "/var/log/nginx/access.log",
    "nginx_error": "/var/log/nginx/error.log",
    "system": "/var/log/syslog"
}

def tail_file_lines(path, max_lines=TERMINAL_LOG_MAX_LINES, max_bytes=TERMINAL_LOG_MAX_BYTES):
    if not Path(path).exists():
        return {"status": "error", "output": "Logdatei nicht gefunden."}
    data = []
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        buffer = b""
        while position > 0 and len(data) < max_lines and len(buffer) < max_bytes:
            read_size = min(1024, position)
            position -= read_size
            handle.seek(position)
            buffer = handle.read(read_size) + buffer
            lines = buffer.splitlines()
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
            data = lines
    output = b"\n".join(data).decode("utf-8", errors="ignore")
    return {"status": "ok", "output": output}

def filter_log_lines(lines_text, keyword):
    if not keyword:
        return lines_text
    try:
        regex = re.compile(keyword, re.IGNORECASE)
        filtered = [line for line in lines_text.splitlines() if regex.search(line)]
    except re.error:
        filtered = [line for line in lines_text.splitlines() if keyword.lower() in line.lower()]
    return "\n".join(filtered)

def db_is_postgres():
    database_url = os.environ.get("DATABASE_URL") or ""
    return database_url.startswith("postgres")

def normalize_sql_query(query):
    cleaned = (query or "").strip()
    cleaned = cleaned.rstrip(";")
    statements = [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]
    if len(statements) != 1:
        return None
    return statements[0]

def is_safe_readonly_query(query):
    if not query:
        return False
    normalized = normalize_sql_query(query)
    if not normalized:
        return False
    token = normalized.split()[0].lower()
    if token not in {"select", "with", "explain"}:
        return False
    if re.search(r"\\b(drop|truncate|alter|grant|revoke|create|attach|detach|pragma)\\b", normalized, re.IGNORECASE):
        return False
    return True

def is_dangerous_query(query):
    if not query:
        return True
    normalized = normalize_sql_query(query)
    if not normalized:
        return True
    return bool(re.search(r"\\b(drop|truncate|alter|grant|revoke|create|attach|detach|pragma|vacuum)\\b", normalized, re.IGNORECASE))

def run_ping(params):
    host = validate_hostname(params.get("host"))
    try:
        count = int(params.get("count", 4))
    except (TypeError, ValueError):
        count = 4
    count = min(max(count, 1), 4)
    if not host:
        return {"status": "error", "output": "Ungültiger Host."}
    if not shutil.which("ping"):
        return {"status": "error", "output": "ping ist nicht verfügbar."}
    return safe_subprocess(["ping", "-c", str(count), "-W", "2", host], timeout=TERMINAL_DEFAULT_TIMEOUT_SECONDS)

def run_dns_lookup(params):
    domain = validate_hostname(params.get("domain"))
    if not domain:
        return {"status": "error", "output": "Ungültige Domain."}
    try:
        infos = socket.getaddrinfo(domain, None)
    except socket.gaierror:
        return {"status": "error", "output": "DNS-Auflösung fehlgeschlagen."}
    addresses = sorted({info[4][0] for info in infos})
    return {"status": "ok", "output": "\n".join(addresses) if addresses else "Keine Einträge gefunden."}

def run_tcp_check(params):
    host = validate_hostname(params.get("host"))
    port = validate_port(params.get("port"))
    if not host or not port:
        return {"status": "error", "output": "Host oder Port ist ungültig."}
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=3):
            latency = (time.time() - start) * 1000
            return {"status": "ok", "output": f"Port offen. Latenz: {latency:.0f} ms"}
    except (socket.timeout, ConnectionError, OSError) as exc:
        return {"status": "error", "output": f"Verbindung fehlgeschlagen: {exc}"}

def run_http_check(params):
    url = (params.get("url") or "").strip()
    method = (params.get("method") or "GET").upper()
    if method not in {"GET", "HEAD"}:
        return {"status": "error", "output": "Nur GET oder HEAD erlaubt."}
    if not url.startswith(("http://", "https://")):
        return {"status": "error", "output": "URL muss mit http:// oder https:// beginnen."}
    start = time.time()
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=TERMINAL_DEFAULT_TIMEOUT_SECONDS) as response:
            latency = (time.time() - start) * 1000
            return {
                "status": "ok",
                "output": f"HTTP {response.status} in {latency:.0f} ms"
            }
    except urllib.error.URLError as exc:
        return {"status": "error", "output": f"HTTP-Check fehlgeschlagen: {exc}"}

def run_service_list(_params):
    return {"status": "ok", "output": "\n".join(TERMINAL_SERVICE_ALLOWLIST)}

def run_service_status(params):
    service = (params.get("service") or "").strip()
    if service not in TERMINAL_SERVICE_ALLOWLIST:
        return {"status": "error", "output": "Service nicht erlaubt."}
    if not shutil.which("systemctl"):
        return {"status": "error", "output": "systemctl nicht verfügbar."}
    return safe_subprocess(["systemctl", "is-active", service], timeout=5)

def run_service_restart(params, settings):
    service = (params.get("service") or "").strip()
    confirm = bool(params.get("confirm"))
    if not settings["terminal"]["allowServiceRestart"]:
        return {"status": "error", "output": "Service-Restarts sind deaktiviert."}
    if not confirm:
        return {"status": "error", "output": "Bestätigung erforderlich."}
    if service not in TERMINAL_SERVICE_ALLOWLIST:
        return {"status": "error", "output": "Service nicht erlaubt."}
    if not shutil.which("systemctl"):
        return {"status": "error", "output": "systemctl nicht verfügbar."}
    return safe_subprocess(["systemctl", "restart", service], timeout=TERMINAL_DEFAULT_TIMEOUT_SECONDS)

def run_logs_tail(params):
    source = (params.get("source") or "").strip()
    lines = min(max(int(params.get("lines", 50)), 1), TERMINAL_LOG_MAX_LINES)
    path = TERMINAL_LOG_SOURCES.get(source)
    if not path:
        return {"status": "error", "output": "Logquelle nicht erlaubt."}
    return tail_file_lines(path, max_lines=lines)

def run_logs_search(params):
    source = (params.get("source") or "").strip()
    keyword = (params.get("keyword") or "").strip()
    lines = min(max(int(params.get("lines", 100)), 1), TERMINAL_LOG_MAX_LINES)
    path = TERMINAL_LOG_SOURCES.get(source)
    if not path:
        return {"status": "error", "output": "Logquelle nicht erlaubt."}
    result = tail_file_lines(path, max_lines=lines)
    if result["status"] != "ok":
        return result
    filtered = filter_log_lines(result["output"], keyword)
    return {"status": "ok", "output": filtered or "Keine Treffer."}

def run_environment_snapshot(_params):
    db = get_db()
    start = time.time()
    db_status = "OK"
    latency_ms = None
    try:
        db.execute("SELECT 1").fetchone()
        latency_ms = int((time.time() - start) * 1000)
    except Exception:
        db_status = "ERROR"
    disk = shutil.disk_usage(str(APP_INSTANCE_PATH if APP_INSTANCE_PATH.exists() else Path(".")))
    uptime_seconds = int(time.time() - APP_START_TIME)
    payload = {
        "app_version": os.environ.get("APP_VERSION", "unbekannt"),
        "environment": os.environ.get("FLASK_ENV", "production"),
        "uptime_seconds": uptime_seconds,
        "db_status": db_status,
        "db_latency_ms": latency_ms,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2)
    }
    formatted = "\n".join(f"{key}: {value}" for key, value in payload.items())
    return {"status": "ok", "output": formatted, "meta": payload}

TERMINAL_RECIPES = {
    "ping": {
        "name": "Ping Host",
        "category": "diagnostics",
        "handler": run_ping
    },
    "dns_lookup": {
        "name": "DNS Resolve",
        "category": "diagnostics",
        "handler": run_dns_lookup
    },
    "tcp_check": {
        "name": "TCP Port Check",
        "category": "diagnostics",
        "handler": run_tcp_check
    },
    "http_check": {
        "name": "HTTP Check",
        "category": "diagnostics",
        "handler": run_http_check
    },
    "services_list": {
        "name": "Services",
        "category": "services",
        "handler": run_service_list
    },
    "service_status": {
        "name": "Service Status",
        "category": "services",
        "handler": run_service_status
    },
    "service_restart": {
        "name": "Service Restart",
        "category": "services",
        "handler": run_service_restart
    },
    "logs_tail": {
        "name": "Tail Logs",
        "category": "logs",
        "handler": run_logs_tail
    },
    "logs_search": {
        "name": "Search Logs",
        "category": "logs",
        "handler": run_logs_search
    },
    "environment_snapshot": {
        "name": "Environment Snapshot",
        "category": "environment",
        "handler": run_environment_snapshot
    }
}

def get_terminal_session(db, session_id, user_id):
    if not session_id:
        return None
    row = db.execute(
        '''
        SELECT * FROM terminal_sessions
        WHERE id = ? AND user_id = ? AND active = 1
        ''',
        (session_id, user_id)
    ).fetchone()
    if not row:
        return None
    expires_at = row["expires_at"]
    if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
        db.execute('UPDATE terminal_sessions SET active = 0 WHERE id = ?', (session_id,))
        db.commit()
        return None
    return row

def create_terminal_session(db, user_id, mode, ip, user_agent):
    expires_at = datetime.utcnow() + timedelta(seconds=TERMINAL_SESSION_TTL_SECONDS)
    db.execute(
        '''
        INSERT INTO terminal_sessions (user_id, expires_at, mode, ip, user_agent)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, expires_at.isoformat(), mode, ip, user_agent)
    )
    session_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    return session_id, expires_at

def touch_terminal_session(db, session_id):
    db.execute(
        '''
        UPDATE terminal_sessions
        SET last_activity = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (session_id,)
    )
    db.commit()

def terminate_terminal_session(db, session_id):
    db.execute('UPDATE terminal_sessions SET active = 0 WHERE id = ?', (session_id,))
    db.commit()

def ensure_backup_directory(path_value):
    backup_dir = Path(path_value or DEFAULT_SERVER_SETTINGS["backup"]["directory"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def get_backup_encryption():
    key = os.environ.get("BACKUP_ENCRYPTION_KEY")
    if not key:
        return None
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        return None

def get_inventory_links_encryption():
    try:
        return EncryptionKeyring.from_environ()
    except SecretConfigurationError:
        return None

def encrypt_inventory_link_secret(secret):
    try:
        return encrypt_secret(secret)
    except SecretConfigurationError as error:
        raise ValueError(str(error)) from error

def decrypt_inventory_link_secret(secret_encrypted):
    try:
        return decrypt_secret(secret_encrypted)
    except (SecretConfigurationError, SecretDecryptionError) as error:
        raise ValueError(str(error)) from error

def migrate_inventory_link_secrets(db, reencrypt_all=False):
    """Encrypt legacy values and re-encrypt values after a key rotation.

    Callers must run this as an explicit maintenance action with a valid primary
    key. Values are never included in the result, logs or raised messages.
    """
    try:
        keyring = EncryptionKeyring.from_environ()
    except SecretConfigurationError as error:
        raise ValueError(str(error)) from error

    rows = db.execute(
        "SELECT id, secret_encrypted FROM inventory_links WHERE secret_encrypted IS NOT NULL AND secret_encrypted != ''"
    ).fetchall()
    migrated = 0
    skipped = 0
    for row in rows:
        stored_value = row["secret_encrypted"]
        try:
            if is_plaintext_secret(stored_value):
                encrypted_value = migrate_plaintext_secret(stored_value)
            elif reencrypt_all or not stored_value.startswith("fernet:v1:"):
                encrypted_value = keyring.encrypt(keyring.decrypt(stored_value))
            else:
                continue
        except (SecretConfigurationError, SecretDecryptionError):
            skipped += 1
            continue
        db.execute(
            "UPDATE inventory_links SET secret_encrypted = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (encrypted_value, row["id"]),
        )
        migrated += 1
    db.commit()
    return {"migrated": migrated, "skipped": skipped}

def run_sqlite_backup(target_path):
    with sqlite3.connect(DATABASE) as source:
        with sqlite3.connect(target_path) as dest:
            source.backup(dest)

def run_postgres_backup(target_path):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL fehlt.")
    result = subprocess.run(
        ["pg_dump", database_url, "-f", str(target_path)],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pg_dump fehlgeschlagen.")

def cleanup_old_backups(backup_dir, retention_days):
    cutoff = time.time() - retention_days * 86400
    for path in backup_dir.glob("*"):
        if not path.is_file():
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)

def record_backup_run(db, status, backup_path=None, message=None):
    backup_size = None
    if backup_path and Path(backup_path).exists():
        backup_size = Path(backup_path).stat().st_size
    db.execute(
        '''
        INSERT INTO backup_runs (status, backup_path, backup_size_bytes, message)
        VALUES (?, ?, ?, ?)
        ''',
        (status, backup_path, backup_size, message)
    )
    db.commit()

def send_backup_notification(db, settings, subject, body):
    recipients = parse_email_list(settings["backup"]["notifyEmail"])
    if not recipients:
        return False
    notification_settings = get_notification_settings(db)
    success = send_notification_email(notification_settings, recipients, subject, body)
    return success

def run_backup_job(db, settings, force=False):
    if not settings["backup"]["enabled"] and not force:
        return {"status": "skipped", "message": "Backups sind deaktiviert."}
    backup_dir = ensure_backup_directory(settings["backup"]["directory"])
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_base = backup_dir / f"inventory_backup_{timestamp}"
    db_type = os.environ.get("DATABASE_URL")
    backup_path = None
    try:
        if db_type and db_type.startswith("postgres"):
            backup_path = f"{backup_base}.sql"
            run_postgres_backup(backup_path)
        else:
            backup_path = f"{backup_base}.db"
            run_sqlite_backup(backup_path)

        final_path = Path(backup_path)
        if settings["backup"]["compress"]:
            compressed_path = f"{backup_path}.zip"
            with zipfile.ZipFile(compressed_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(backup_path, arcname=Path(backup_path).name)
            final_path = Path(compressed_path)
            Path(backup_path).unlink(missing_ok=True)

        if settings["backup"]["encrypt"]:
            fernet = get_backup_encryption()
            if not fernet:
                raise RuntimeError("BACKUP_ENCRYPTION_KEY fehlt oder ist ungültig.")
            encrypted_path = f"{final_path}.enc"
            data = final_path.read_bytes()
            encrypted = fernet.encrypt(data)
            Path(encrypted_path).write_bytes(encrypted)
            final_path.unlink(missing_ok=True)
            final_path = Path(encrypted_path)

        write_backup_manifest(final_path)
        cleanup_old_backups(backup_dir, settings["backup"]["retentionDays"])
        record_backup_run(db, "success", str(final_path))
        send_backup_notification(db, settings, "Backup erfolgreich", f"Backup erstellt: {final_path.name}")
        return {"status": "success", "path": str(final_path)}
    except Exception as exc:
        record_backup_run(db, "failed", backup_path, str(exc))
        send_backup_notification(db, settings, "Backup fehlgeschlagen", f"Backup fehlgeschlagen: {exc}")
        return {"status": "failed", "message": str(exc)}

def load_backup_settings(db):
    settings, _ = serialize_server_settings(get_server_settings(db))
    return settings

def backup_manifest_path(backup_path):
    return backup_restore_service.backup_manifest_path(backup_path)

def file_sha256(path):
    return backup_restore_service.file_sha256(path)

def write_backup_manifest(backup_path):
    return backup_restore_service.write_backup_manifest(
        backup_path,
        os.environ.get("APP_VERSION", "dev"),
    )

def verify_backup_manifest(backup_path):
    return backup_restore_service.verify_backup_manifest(backup_path)

def _copy_restore_source(source, destination):
    copied = 0
    with source, destination.open("wb") as output:
        while chunk := source.read(1024 * 1024):
            copied += len(chunk)
            if copied > MAX_RESTORE_BYTES:
                raise ValueError("Backup überschreitet die konfigurierte Restore-Größe.")
            output.write(chunk)

def materialize_sqlite_backup(backup_path, staging_directory):
    backup_path = Path(backup_path).resolve(strict=True)
    verify_backup_manifest(backup_path)
    staging_directory = Path(staging_directory)
    staging_directory.mkdir(parents=True, exist_ok=True)
    raw_path = backup_path
    temporary_paths = []
    try:
        if backup_path.suffix == ".enc":
            fernet = get_backup_encryption()
            if not fernet:
                raise ValueError("BACKUP_ENCRYPTION_KEY fehlt oder ist ungültig.")
            encrypted_data = backup_path.read_bytes()
            if len(encrypted_data) > MAX_RESTORE_BYTES:
                raise ValueError("Verschlüsseltes Backup überschreitet die konfigurierte Restore-Größe.")
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
            except Exception as error:
                raise ValueError("Backup kann mit dem konfigurierten Schlüssel nicht entschlüsselt werden.") from error
            if len(decrypted_data) > MAX_RESTORE_BYTES:
                raise ValueError("Entschlüsseltes Backup überschreitet die konfigurierte Restore-Größe.")
            raw_path = staging_directory / f"decrypted-backup{Path(backup_path.stem).suffix}"
            raw_path.write_bytes(decrypted_data)
            os.chmod(raw_path, stat.S_IRUSR | stat.S_IWUSR)
            temporary_paths.append(raw_path)

        restore_source = staging_directory / "restore-source.db"
        if raw_path.suffix == ".zip" or backup_path.name.endswith(".zip.enc"):
            with zipfile.ZipFile(raw_path) as archive:
                database_members = validate_backup_archive(archive)
                if len(database_members) != 1:
                    raise ValueError("Backup-Archiv muss genau eine SQLite-Datenbank enthalten.")
                source_info = database_members[0]
                with archive.open(source_info) as source:
                    _copy_restore_source(source, restore_source)
        elif raw_path.suffix == ".db":
            if raw_path.stat().st_size > MAX_RESTORE_BYTES:
                raise ValueError("Backup überschreitet die konfigurierte Restore-Größe.")
            shutil.copyfile(raw_path, restore_source)
        else:
            raise ValueError("Nur SQLite-Backupdateien (.db, .zip oder .enc) können wiederhergestellt werden.")
        validate_sqlite_backup(restore_source)
        return restore_source
    except Exception:
        for path in temporary_paths:
            path.unlink(missing_ok=True)
        raise

def validate_backup_archive(archive):
    database_members = []
    total_uncompressed = 0
    for info in archive.infolist():
        member_path = PurePosixPath(info.filename)
        if (
            not info.filename
            or "\x00" in info.filename
            or "\\" in info.filename
            or member_path.is_absolute()
            or any(part in {"", ".", ".."} for part in member_path.parts)
        ):
            raise ValueError("Backup-Archiv enthält einen unsicheren Pfad.")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ValueError("Backup-Archiv enthält einen symbolischen Link.")
        if info.is_dir():
            continue
        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > MAX_RESTORE_BYTES:
            raise ValueError("Entpacktes Backup überschreitet die konfigurierte Restore-Größe.")
        if member_path.suffix.lower() == ".db":
            database_members.append(info)
    return database_members

def validate_sqlite_backup(database_path):
    database_path = Path(database_path)
    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        connection.close()
    except sqlite3.Error as error:
        raise ValueError("Backup ist keine lesbare SQLite-Datenbank.") from error
    if result.lower() != "ok":
        raise ValueError("SQLite-Integritätsprüfung des Backups ist fehlgeschlagen.")

def restore_sqlite_backup(backup_path, database_path=None):
    """Restore a verified SQLite backup atomically while the application is stopped."""
    return backup_restore_service.restore_sqlite_backup(
        backup_path,
        database_path or DATABASE,
        get_backup_encryption,
        MAX_RESTORE_BYTES,
    )

def schedule_backup_jobs(settings):
    if not SCHEDULER_ENABLED:
        app.logger.info("In-Process-Backup-Scheduler ist für diesen Worker deaktiviert.")
        return
    if not BACKUP_SCHEDULER.running:
        BACKUP_SCHEDULER.start()
    BACKUP_SCHEDULER.remove_all_jobs()
    if not settings["backup"]["enabled"]:
        return
    if settings["backup"]["schedule"] != "daily":
        return
    time_value = settings["backup"]["time"] or "02:00"
    hour, minute = [int(part) for part in time_value.split(":")]
    def scheduled_backup():
        with app.app_context():
            db = get_db()
            current_settings, _ = serialize_server_settings(get_server_settings(db))
            run_backup_job(db, current_settings)
    BACKUP_SCHEDULER.add_job(
        scheduled_backup,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_backup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

def load_import_file(file_storage):
    if not file_storage:
        return None, "Keine Datei hochgeladen."
    if request.content_length and request.content_length > MAX_IMPORT_BYTES:
        return None, "Datei ist zu groß."
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None, "Ungültiger Dateiname."
    temp_dir = Path(tempfile.mkdtemp(prefix="inventory_import_"))
    file_path = temp_dir / filename
    file_storage.save(file_path)
    return file_path, None

def validate_import_file(file_path):
    antivirus_cmd = os.environ.get("INVENTORY_ANTIVIRUS_COMMAND")
    if not antivirus_cmd:
        return None
    result = subprocess.run(
        [antivirus_cmd, str(file_path)],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        return result.stderr.strip() or "Datei konnte nicht geprüft werden."
    return None

def validate_import_archive(archive):
    total_uncompressed = 0
    upload_members = []
    for info in archive.infolist():
        member_name = info.filename
        if not member_name or "\x00" in member_name or "\\" in member_name:
            raise ValueError("ZIP-Archiv enthält einen ungültigen Pfad.")
        member_path = PurePosixPath(member_name)
        if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
            raise ValueError("ZIP-Archiv enthält einen unsicheren Pfad.")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ValueError("Symbolische Links sind in Importarchiven nicht zulässig.")
        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > MAX_IMPORT_EXPANDED_BYTES:
            raise ValueError("Entpackter Inhalt überschreitet die zulässige Größe.")
        if info.is_dir() or not member_path.parts or member_path.parts[0] != "uploads":
            continue
        relative_parts = member_path.parts[1:]
        if not relative_parts:
            continue
        upload_members.append((info, Path(*relative_parts)))
    return upload_members

def export_tables(db, tables):
    export_data = {}
    for table in tables:
        rows = db.execute(f"SELECT * FROM {table}").fetchall()
        export_data[table] = [dict(row) for row in rows]
    return export_data

def import_table_rows(db, table, rows, mode):
    if not rows:
        return
    columns = [column["name"] for column in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if not columns:
        return
    placeholders = ", ".join(["?"] * len(columns))
    column_list = ", ".join(columns)
    if mode == "merge":
        statement = f"INSERT OR REPLACE INTO {table} ({column_list}) VALUES ({placeholders})"
    elif mode == "append":
        statement = f"INSERT OR IGNORE INTO {table} ({column_list}) VALUES ({placeholders})"
    else:
        statement = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    for row in rows:
        values = [row.get(column) for column in columns]
        db.execute(statement, values)

def import_data_payload(db, payload, mode, tables):
    if mode == "replace":
        for table in tables:
            db.execute(f"DELETE FROM {table}")
    for table in tables:
        rows = payload.get(table, [])
        import_table_rows(db, table, rows, mode if mode != "replace" else "append")

def import_from_sqlite(db, source_path, mode, tables):
    with sqlite3.connect(source_path) as source:
        source.row_factory = sqlite3.Row
        if mode == "replace":
            for table in tables:
                db.execute(f"DELETE FROM {table}")
        for table in tables:
            rows = source.execute(f"SELECT * FROM {table}").fetchall()
            import_table_rows(db, table, [dict(row) for row in rows], mode if mode != "replace" else "append")

def clone_customization(data):
    return json.loads(json.dumps(data))

def deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base
    merged = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged

def migrate_customization(data):
    if not isinstance(data, dict):
        return clone_customization(DEFAULT_CUSTOMIZATION)

    if ("branding" in data or "formStyle" in data) and "baseTokens" not in data:
        migrated = clone_customization(DEFAULT_CUSTOMIZATION)
        branding = data.get("branding", {})
        form_style = data.get("formStyle", {})
        migrated["branding"]["name"] = branding.get("name", migrated["branding"]["name"])
        migrated["branding"]["tagline"] = branding.get("tagline", migrated["branding"]["tagline"])
        migrated["branding"]["logoDataUrl"] = branding.get("logoDataUrl", migrated["branding"]["logoDataUrl"])
        migrated["baseTokens"]["colors"]["primary"] = branding.get("primary", migrated["baseTokens"]["colors"]["primary"])
        migrated["baseTokens"]["colors"]["accent"] = branding.get("accent", migrated["baseTokens"]["colors"]["accent"])
        migrated["baseTokens"]["colors"]["background"] = branding.get("background", migrated["baseTokens"]["colors"]["background"])
        migrated["baseTokens"]["spacing"]["radius"]["md"] = branding.get("radius", migrated["baseTokens"]["spacing"]["radius"]["md"])
        migrated["layoutPrefs"]["density"] = branding.get("density", migrated["layoutPrefs"]["density"])
        migrated["componentOverrides"]["button"]["primary"]["background"] = form_style.get(
            "buttonColor", migrated["componentOverrides"]["button"]["primary"]["background"]
        )
        migrated["componentOverrides"]["button"]["primary"]["text"] = form_style.get(
            "buttonText", migrated["componentOverrides"]["button"]["primary"]["text"]
        )
        migrated["componentOverrides"]["input"]["background"] = form_style.get(
            "inputBackground", migrated["componentOverrides"]["input"]["background"]
        )
        migrated["componentOverrides"]["input"]["border"] = form_style.get(
            "inputBorder", migrated["componentOverrides"]["input"]["border"]
        )
        migrated["layoutPrefs"]["formSpacing"] = form_style.get("spacing", migrated["layoutPrefs"]["formSpacing"])
        return migrated

    merged = deep_merge(clone_customization(DEFAULT_CUSTOMIZATION), data)
    merged["schemaVersion"] = 1
    return merged

def validate_customization(data):
    errors = []
    if not isinstance(data, dict):
        return False, ["Customization muss ein Objekt sein."]
    if not isinstance(data.get("schemaVersion"), int):
        errors.append("schemaVersion fehlt oder ist ungültig.")
    for key in ("baseTokens", "componentOverrides", "layoutPrefs", "featurePrefs", "branding"):
        if key not in data:
            errors.append(f"{key} fehlt.")
    return len(errors) == 0, errors

def compute_customization_diff(old, new, path=""):
    changes = []
    if isinstance(old, dict) and isinstance(new, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in sorted(all_keys):
            next_path = f"{path}.{key}" if path else key
            changes.extend(compute_customization_diff(old.get(key), new.get(key), next_path))
    elif old != new:
        changes.append({"path": path, "from": old, "to": new})
    return changes

def get_current_user_id(db):
    username = session.get("username")
    if not username:
        return None
    row = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"] if row else None

def get_customization_record(db, user_id, workspace_id=None):
    if workspace_id is None:
        return db.execute(
            "SELECT * FROM ui_customization WHERE user_id = ? AND workspace_id IS NULL",
            (user_id,),
        ).fetchone()
    return db.execute(
        "SELECT * FROM ui_customization WHERE user_id = ? AND workspace_id = ?",
        (user_id, workspace_id),
    ).fetchone()

def save_customization(db, user_id, customization, updated_by, workspace_id=None):
    existing = get_customization_record(db, user_id, workspace_id)
    serialized = json.dumps(customization)
    if existing:
        db.execute(
            """
            UPDATE ui_customization
            SET customization_json = ?, schema_version = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = ?
            """,
            (serialized, customization["schemaVersion"], updated_by, existing["id"]),
        )
        customization_id = existing["id"]
    else:
        db.execute(
            """
            INSERT INTO ui_customization (user_id, workspace_id, schema_version, customization_json, updated_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, workspace_id, customization["schemaVersion"], serialized, updated_by),
        )
        customization_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    diff = []
    if existing:
        diff = compute_customization_diff(json.loads(existing["customization_json"]), customization)
    db.execute(
        """
        INSERT INTO ui_customization_revisions (customization_id, revision_json, diff_json, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (customization_id, serialized, json.dumps(diff), updated_by),
    )
    db.commit()
    return customization_id

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

def seed_health_checks(db):
    default_checks = [
        {
            "name": "CPU Load",
            "slug": "cpu-load",
            "category": "System",
            "check_type": "cpu_load",
            "interval_seconds": 60,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"warn_load": 4, "crit_load": 8, "per_core": True}
        },
        {
            "name": "Memory Usage",
            "slug": "memory-usage",
            "category": "System",
            "check_type": "memory",
            "interval_seconds": 60,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"warn_percent": 80, "crit_percent": 90}
        },
        {
            "name": "Disk Root",
            "slug": "disk-root",
            "category": "System",
            "check_type": "disk",
            "interval_seconds": 300,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"path": "/", "warn_percent": 80, "crit_percent": 90}
        },
        {
            "name": "DB Ping",
            "slug": "db-ping",
            "category": "Infra",
            "check_type": "db_ping",
            "interval_seconds": 120,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"db_path": DATABASE, "warn_ms": 150, "crit_ms": 300}
        },
        {
            "name": "DNS Resolve",
            "slug": "dns-resolve",
            "category": "Network",
            "check_type": "dns",
            "interval_seconds": 120,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"hostname": "example.com"}
        },
        {
            "name": "Internet Reachability",
            "slug": "internet-reach",
            "category": "Network",
            "check_type": "internet",
            "interval_seconds": 300,
            "timeout_seconds": 10,
            "enabled": 1,
            "config": {"url": "https://example.com"}
        },
        {
            "name": "Time Sync",
            "slug": "time-sync",
            "category": "System",
            "check_type": "time_sync",
            "interval_seconds": 600,
            "timeout_seconds": 5,
            "enabled": 1,
            "config": {"max_offset_ms": 100}
        },
        {
            "name": "Service Unit (example)",
            "slug": "service-unit-example",
            "category": "Services",
            "check_type": "service_unit",
            "interval_seconds": 60,
            "timeout_seconds": 5,
            "enabled": 0,
            "config": {"unit": "nginx.service"}
        }
    ]
    for entry in default_checks:
        existing = db.execute(
            "SELECT id FROM health_check_definitions WHERE slug = ?",
            (entry["slug"],)
        ).fetchone()
        if existing:
            continue
        db.execute(
            '''
            INSERT INTO health_check_definitions (
                name, slug, category, check_type, config_json,
                interval_seconds, timeout_seconds, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                entry["name"],
                entry["slug"],
                entry["category"],
                entry["check_type"],
                json.dumps(entry["config"]),
                entry["interval_seconds"],
                entry["timeout_seconds"],
                entry["enabled"]
            )
        )

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

def store_initial_admin_credentials(username, password):
    requested_path = Path(
        INITIAL_ADMIN_CREDENTIALS_PATH
        or APP_INSTANCE_PATH / "initial_admin_credentials.txt"
    )
    requested_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    credentials_path = requested_path
    for attempt in range(9):
        try:
            file_descriptor = os.open(credentials_path, flags, 0o600)
            break
        except FileExistsError:
            if attempt == 8:
                raise
            credentials_path = requested_path.with_name(
                f"{requested_path.stem}-{secrets.token_hex(4)}{requested_path.suffix}"
            )
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as credentials_file:
        credentials_file.write(f"Benutzername: {username}\n")
        credentials_file.write(f"Passwort: {password}\n")
        credentials_file.write("Passwortwechsel beim ersten Login erforderlich.\n")
    os.chmod(credentials_path, 0o600)
    return credentials_path

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

    requested_username = (os.environ.get("INVENTORY_INITIAL_ADMIN_USERNAME") or "").strip()
    configured_password = (os.environ.get("INVENTORY_INITIAL_ADMIN_PASSWORD") or "").strip()
    username_base = requested_username or "admin"
    username = username_base
    while db.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
        username = f"{username_base}-{secrets.token_hex(3)}"

    password = configured_password or secrets.token_urlsafe(12)
    password_hash = generate_password_hash(password)
    cursor = db.execute(
        'INSERT INTO users (username, password_hash, must_change_password) VALUES (?, ?, ?)',
        (username, password_hash, 0 if configured_password else 1)
    )
    assign_user_role(db, cursor.lastrowid, "Admin")

    if configured_password:
        app.logger.warning(
            "Initiales Administratorkonto %s wurde aus geschützter Umgebungskonfiguration erstellt.",
            username,
        )
    else:
        credentials_path = store_initial_admin_credentials(username, password)
        app.logger.warning(
            "Initiales Administratorkonto %s erstellt. Einmalige Zugangsdaten liegen geschützt unter %s.",
            username,
            credentials_path,
        )

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
    user = db.execute('SELECT id, username, email, must_change_password FROM users WHERE username = ?', (username,)).fetchone()
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

@app.context_processor
def inject_security_context():
    return {
        "csrf_token": get_csrf_token(session),
        "csrf_header_name": CSRF_HEADER_NAME,
    }

@app.context_processor
def inject_inventory_links():
    try:
        access = get_user_access(get_db())
    except Exception:
        return {}
    user = access.get("user")
    if not user:
        return {}
    try:
        links = list_inventory_links(get_db(), user["id"])
    except Exception:
        links = []
    return {"inventory_links": links}


@app.context_processor
def inject_app_shell_defaults():
    try:
        access = get_user_access(get_db())
        permissions = access.get("permissions") or set()
        is_superuser = bool(access.get("is_superuser"))
    except Exception:
        permissions = set()
        is_superuser = False

    endpoint = request.endpoint or ""
    path = request.path or "/"
    section = (request.args.get("section") or "server").strip() or "server"

    page_defaults = {
        "page_module": "dashboard",
        "page_section_label": "Workspace",
        "page_title": "Inventory Pro",
        "page_description": "Workspace für Inventar, Service und Betrieb.",
        "page_breadcrumbs": [],
        "now": datetime.now
    }

    defaults_by_endpoint = {
        "index": {
            "page_module": "dashboard",
            "page_section_label": "Inventory",
            "page_title": "Inventar",
            "page_description": "Geräte, Assets und Kategorien zentral verwalten.",
            "hide_page_intro": True
        },
        "locations_page": {
            "page_module": "locations",
            "page_section_label": "Standorte",
            "page_title": "Standorte verwalten",
            "page_description": "Lager, Etagen und Abteilungen zentral pflegen."
        },
        "tickets_page": {
            "page_module": "tickets",
            "page_section_label": "Helpdesk",
            "page_title": "Ticket-System",
            "page_description": "SLA, Prioritäten und Workflows im Blick behalten."
        },
        "knowledge_page": {
            "page_module": "knowledge",
            "page_section_label": "Knowledge Hub",
            "page_title": "Wissensbasis",
            "page_description": "Antworten schnell finden und direkt mit Tickets verknüpfen."
        },
        "roadmap_page": {
            "page_module": "roadmap",
            "page_section_label": "Roadmap",
            "page_title": "Planung & Milestones",
            "page_description": "Initiativen, Verantwortliche und Zieltermine strukturiert steuern."
        },
        "procurement_page": {
            "page_module": "procurement",
            "page_section_label": "Beschaffung",
            "page_title": "Beschaffung & Lieferanten",
            "page_description": "Bestellungen, Anbieter und Vertragsbeziehungen datenorientiert verwalten."
        },
        "dependencies_page": {
            "page_module": "dependencies",
            "page_section_label": "Abhängigkeiten",
            "page_title": "Dependency-Graph",
            "page_description": "Systembeziehungen und Ausfallrisiken transparent nachvollziehen."
        },
        "time_machine_page": {
            "page_module": "time-machine",
            "page_section_label": "Historie",
            "page_title": "Zeitmaschine",
            "page_description": "Änderungen, Zustandsverläufe und Rückverfolgung zentral auswerten."
        },
        "health_page": {
            "page_module": "health",
            "page_section_label": "Health",
            "page_title": "Betriebsstatus",
            "page_description": "Checks, Warnungen und Plattformzustand in einer operativen Sicht."
        },
        "users_page": {
            "page_module": "users",
            "page_section_label": "Administration",
            "page_title": "Benutzer & Rollen",
            "page_description": "Konten, Rechte und Verzeichnisanbindungen professionell steuern."
        },
        "server_settings_page": {
            "page_module": "settings",
            "page_section_label": "Administration",
            "page_title": "Einstellungen",
            "page_description": "Plattform, Sicherheit und Integrationen zentral konfigurieren."
        },
        "terminal_settings_page": {
            "page_module": "settings",
            "page_section_label": "Administration",
            "page_title": "Terminal & Fernwartung",
            "page_description": "Kontrollierte Diagnose- und Wartungszugriffe professionell absichern."
        },
        "stats": {
            "page_module": "stats",
            "page_section_label": "Analyse",
            "page_title": "Statistiken & Reports",
            "page_description": "Kennzahlen, Nutzungsmuster und Trends datenbasiert auswerten."
        }
    }
    page_defaults.update(defaults_by_endpoint.get(endpoint, {}))

    if path.startswith("/inventory-links/"):
        page_defaults.update({
            "page_module": "inventory-links",
            "page_section_label": "Verknüpfte Instanzen",
            "page_title": "Linked Inventory",
            "page_description": "Zwischen verbundenen Inventory-Pro-Instanzen sicher wechseln."
        })

    if endpoint in {"server_settings_page", "terminal_settings_page"}:
        settings_tabs = [
            {"href": "/settings?section=server", "label": "Server", "icon": "server", "active": endpoint == "server_settings_page" and section == "server"},
            {"href": "/settings?section=branding", "label": "Branding", "icon": "image", "active": endpoint == "server_settings_page" and section == "branding"},
            {"href": "/settings?section=notifications", "label": "Benachrichtigungen", "icon": "bell", "active": endpoint == "server_settings_page" and section == "notifications"},
            {"href": "/settings?section=security", "label": "Sicherheit", "icon": "shield", "active": endpoint == "server_settings_page" and section == "security"},
            {"href": "/settings?section=server#inventory-links", "label": "Inventory Links", "icon": "link-2", "active": endpoint == "server_settings_page" and section == "server"}
        ]
        if is_superuser or "terminal.view" in permissions:
            settings_tabs.append(
                {"href": "/settings/terminal", "label": "Terminal", "icon": "terminal", "active": endpoint == "terminal_settings_page"}
            )
        page_defaults["page_tabs"] = settings_tabs

    return page_defaults

def user_can(permission_key):
    access = get_user_access(get_db())
    return access["is_superuser"] or permission_key in access["permissions"]

def must_change_password(db, username):
    row = db.execute(
        'SELECT must_change_password FROM users WHERE username = ?',
        (username,)
    ).fetchone()
    return bool(row and row["must_change_password"])

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
    if access.get("user") and access["user"].get("must_change_password"):
        return url_for('force_password_change')
    if access["is_superuser"]:
        return url_for('index')
    landing_targets = [
        (("categories.view", "categories.manage"), "index"),
        (("tickets.view_all", "tickets.view_own", "tickets.create"), "tickets_page"),
        (("knowledge.view", "knowledge.manage"), "knowledge_page"),
        (("stats.view",), "stats"),
        (("timemachine.view",), "time_machine_page"),
        (("health.view", "health.manage", "health.run"), "health_page"),
        (("users.manage",), "users_page"),
        (("locations.view", "locations.manage"), "locations_page")
    ]
    for permissions, endpoint in landing_targets:
        if any(permission in access["permissions"] for permission in permissions):
            return url_for(endpoint)
    return url_for('index')

def is_ticket_owner(ticket, access):
    if not ticket or not access.get("user"):
        return False
    user_id = access["user"]["id"]
    username = str(access["user"]["username"] or "").strip().casefold()
    if ticket.get("created_by_user_id"):
        return ticket.get("created_by_user_id") == user_id
    created_by = str(ticket.get("created_by") or "").strip().casefold()
    requester_name = str(ticket.get("requester_name") or "").strip().casefold()
    return username in {created_by, requester_name}

def annotate_ticket_access(ticket, access):
    if not ticket:
        return ticket
    owner = is_ticket_owner(ticket, access)
    permissions = access.get("permissions") or set()
    is_superuser = bool(access.get("is_superuser"))
    ticket["is_owner"] = owner
    ticket["access"] = {
        "can_view": bool(ensure_ticket_access(ticket, access)),
        "can_update": bool(is_superuser or "tickets.update" in permissions or ("tickets.update_own" in permissions and owner)),
        "can_delete": bool(is_superuser or "tickets.delete" in permissions or ("tickets.delete_own" in permissions and owner)),
        "can_comment": bool(is_superuser or "tickets.comment" in permissions or ("tickets.comment_own" in permissions and owner)),
        "can_watch": bool(is_superuser or "tickets.watch" in permissions or ("tickets.watch_own" in permissions and owner)),
    }
    return ticket

def ensure_ticket_access(ticket, access, require_owner_permission=False):
    if access["is_superuser"]:
        return True
    if "tickets.view_all" in access["permissions"]:
        return True
    if "tickets.view_own" in access["permissions"]:
        return is_ticket_owner(ticket, access)
    if require_owner_permission:
        return is_ticket_owner(ticket, access)
    return False

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.before_request
def enforce_password_change():
    username = session.get('username')
    if not username:
        return None
    if request.path.startswith('/static/'):
        return None
    if request.path in ('/logout', '/force-password-change'):
        return None
    if request.path.startswith('/api/') and request.path == '/api/force-password-change':
        return None
    db = get_db()
    if must_change_password(db, username):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Passwort muss geändert werden"}), 403
        return redirect(url_for('force_password_change'))

def init_db():
    ensure_runtime_directories()
    with app.app_context():
        db = get_db()
        c = db.cursor()

        # Tabellen erstellen (wie zuvor)
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                password_hash TEXT NOT NULL,
                otp_secret TEXT,
                must_change_password INTEGER DEFAULT 0
            )
        ''')
        try:
            c.execute('ALTER TABLE users ADD COLUMN email TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL')

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
                description TEXT,
                fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT,
                description TEXT,
                fields TEXT,
                binpacking_config TEXT,
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
            CREATE TABLE IF NOT EXISTS asset_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        try:
            c.execute('ALTER TABLE asset_categories ADD COLUMN binpacking_config TEXT')
        except sqlite3.OperationalError:
            pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER,
                notes TEXT,
                specs TEXT,
                acquisition_date TEXT,
                commissioning_date TEXT,
                warranty_end TEXT,
                depreciation_months INTEGER,
                vendor_id INTEGER,
                purchase_order_id INTEGER,
                purchase_cost REAL,
                currency TEXT,
                cost_center TEXT,
                invoice_number TEXT,
                retirement_date TEXT,
                retirement_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES asset_categories(id)
            )
        ''')

        try:
            c.execute('ALTER TABLE categories ADD COLUMN description TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE assets ADD COLUMN notes TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE assets ADD COLUMN specs TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE assets ADD COLUMN category_id INTEGER')
        except sqlite3.OperationalError:
            pass

        for column, column_type in (
            ("acquisition_date", "TEXT"),
            ("commissioning_date", "TEXT"),
            ("warranty_end", "TEXT"),
            ("depreciation_months", "INTEGER"),
            ("vendor_id", "INTEGER"),
            ("purchase_order_id", "INTEGER"),
            ("purchase_cost", "REAL"),
            ("currency", "TEXT"),
            ("cost_center", "TEXT"),
            ("invoice_number", "TEXT"),
            ("retirement_date", "TEXT"),
            ("retirement_reason", "TEXT"),
        ):
            try:
                c.execute(f'ALTER TABLE assets ADD COLUMN {column} {column_type}')
            except sqlite3.OperationalError:
                pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                device_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        ''')

        try:
            c.execute('ALTER TABLE asset_devices ADD COLUMN quantity INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE asset_devices ADD COLUMN notes TEXT')
        except sqlite3.OperationalError:
            pass

        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_category_name ON assets(category_id, name)')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_relation_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                related_asset_id INTEGER NOT NULL,
                relation_type_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_id, related_asset_id, relation_type_id),
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (related_asset_id) REFERENCES assets(id),
                FOREIGN KEY (relation_type_id) REFERENCES asset_relation_types(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ticket_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                asset_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticket_id, asset_id),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id),
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        ''')

        c.execute('INSERT OR IGNORE INTO asset_categories (name) VALUES (?)', ("Assets",))
        default_category_row = db.execute(
            'SELECT id FROM asset_categories WHERE name = ?',
            ("Assets",),
        ).fetchone()
        if default_category_row:
            db.execute(
                'UPDATE assets SET category_id = ? WHERE category_id IS NULL',
                (default_category_row["id"],),
            )

        db.execute('UPDATE asset_devices SET quantity = 1 WHERE quantity IS NULL')
        duplicate_rows = db.execute('''
            SELECT asset_id, device_id,
                   GROUP_CONCAT(id) AS ids,
                   SUM(COALESCE(quantity, 1)) AS total_quantity
            FROM asset_devices
            GROUP BY asset_id, device_id
            HAVING COUNT(*) > 1
        ''').fetchall()
        for row in duplicate_rows:
            ids = [int(item) for item in row["ids"].split(",") if item]
            if not ids:
                continue
            primary_id = ids[0]
            db.execute(
                'UPDATE asset_devices SET quantity = ? WHERE id = ?',
                (row["total_quantity"], primary_id),
            )
            if len(ids) > 1:
                placeholders = ",".join("?" for _ in ids[1:])
                db.execute(
                    f'DELETE FROM asset_devices WHERE id IN ({placeholders})',
                    ids[1:],
                )
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_devices_unique ON asset_devices(asset_id, device_id)')

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
                escalation_level INTEGER DEFAULT 0,
                requester_name TEXT,
                requester_email TEXT,
                created_by_user_id INTEGER,
                created_by TEXT,
                assignee TEXT,
                assignee_email TEXT,
                due_date TEXT,
                resolved_at TEXT,
                resolution_action TEXT,
                resolution_outcome TEXT,
                resolution_notes TEXT,
                tags TEXT,
                custom_fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES ticket_categories(id),
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            )
        ''')

        for column, column_type in (
            ("escalation_level", "INTEGER DEFAULT 0"),
            ("resolved_at", "TEXT"),
            ("resolution_action", "TEXT"),
            ("resolution_outcome", "TEXT"),
            ("resolution_notes", "TEXT"),
            ("created_by_user_id", "INTEGER REFERENCES users(id)"),
        ):
            try:
                c.execute(f'ALTER TABLE tickets ADD COLUMN {column} {column_type}')
            except sqlite3.OperationalError:
                pass
        try:
            c.execute('''
                UPDATE tickets
                SET created_by_user_id = (
                    SELECT id FROM users WHERE users.username = tickets.created_by
                )
                WHERE created_by_user_id IS NULL AND created_by IS NOT NULL
            ''')
        except sqlite3.OperationalError:
            pass

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
            CREATE TABLE IF NOT EXISTS ticket_review_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_ticket_id INTEGER NOT NULL UNIQUE,
                review_ticket_id INTEGER NOT NULL UNIQUE,
                created_by TEXT NOT NULL DEFAULT 'System',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (change_ticket_id != review_ticket_id),
                FOREIGN KEY (change_ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                FOREIGN KEY (review_ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            )
        ''')
        c.execute(
            'CREATE INDEX IF NOT EXISTS idx_ticket_review_links_change '
            'ON ticket_review_links(change_ticket_id)'
        )
        c.execute(
            'CREATE INDEX IF NOT EXISTS idx_ticket_review_links_review '
            'ON ticket_review_links(review_ticket_id)'
        )

        c.execute('''
            CREATE TABLE IF NOT EXISTS saved_ticket_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                filters_json TEXT NOT NULL DEFAULT '{}',
                columns_json TEXT NOT NULL DEFAULT '[]',
                sort_by TEXT NOT NULL DEFAULT 'updated_at',
                sort_direction TEXT NOT NULL DEFAULT 'desc',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_team_shared INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tickets_status_updated ON tickets(status, updated_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tickets_priority_updated ON tickets(priority, updated_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tickets_assignee_updated ON tickets(assignee, updated_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tickets_due_date ON tickets(due_date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ticket_assets_ticket ON ticket_assets(ticket_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ticket_comments_ticket_created ON ticket_comments(ticket_id, created_at)')

        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT,
                content TEXT,
                category_id INTEGER,
                related_ticket_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES knowledge_categories(id),
                FOREIGN KEY (related_ticket_id) REFERENCES tickets(id)
            )
        ''')

        for column, column_type in (
            ("summary", "TEXT"),
            ("content", "TEXT"),
            ("category_id", "INTEGER"),
            ("related_ticket_id", "INTEGER"),
            ("created_by", "TEXT"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ):
            try:
                c.execute(f'ALTER TABLE knowledge_entries ADD COLUMN {column} {column_type}')
            except sqlite3.OperationalError:
                pass

        c.execute('''
            INSERT OR IGNORE INTO knowledge_categories (name, description)
            VALUES
                ('Problemlösungen', 'Dokumentierte Lösungen und Troubleshooting-Schritte.'),
                ('Workflow', 'Abteilungs- und Prozessbeschreibungen.'),
                ('Themen', 'Wissen zu wiederkehrenden Themen und Best Practices.'),
                ('Produktguide', 'Funktionsübersicht und Bedienung der Inventory-Pro-Anwendung.')
        ''')

        c.execute('SELECT COUNT(*) FROM knowledge_entries')
        if c.fetchone()[0] == 0:
            category_rows = c.execute('SELECT id, name FROM knowledge_categories').fetchall()
            category_map = {row["name"]: row["id"] for row in category_rows}
            entries = [
                {
                    "title": "Überblick: Inventory Pro im Alltag",
                    "summary": "Kurzüberblick über die wichtigsten Module und das Zusammenspiel von Inventar, Tickets und Wissen.",
                    "content": (
                        "Inventory Pro kombiniert Inventarisierung, Helpdesk und Wissensmanagement in einer Oberfläche.\n"
                        "Die Startnavigation führt zu Assets, Geräten, Standorten, Tickets, Roadmap, Abhängigkeiten und Statistik.\n"
                        "Alle Aktionen werden im Aktivitätslog dokumentiert, sodass Änderungen jederzeit nachvollziehbar bleiben."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Navigation & Schnellzugriffe",
                    "summary": "So findest du die Hauptbereiche schnell in der linken Navigation.",
                    "content": (
                        "Die linke Seitenleiste zeigt alle Module, die durch deine Rolle freigeschaltet sind.\n"
                        "Nutze die Wissensbasis, um Anleitungen zu öffnen, und die Tickets, um Supportfälle zu bearbeiten.\n"
                        "Die Statistik- und Roadmap-Seiten geben dir einen schnellen Überblick über Status und Planung."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Dashboard-Übersicht",
                    "summary": "Was auf der Startseite sichtbar ist und wie du Kennzahlen interpretierst.",
                    "content": (
                        "Das Dashboard fasst offene Tickets, Geräte- und Assetzahlen sowie aktuelle Aktivitäten zusammen.\n"
                        "Filter helfen dir, die wichtigsten Kennzahlen für dein Team im Blick zu behalten.\n"
                        "Nutze die Zusammenfassung, um schnell offene Aufgaben zu priorisieren."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Inventar: Assets anlegen",
                    "summary": "Schritt-für-Schritt-Anleitung zum Erstellen von Assets.",
                    "content": (
                        "Öffne den Bereich Assets und lege ein neues Asset mit Name, Notizen und Spezifikationen an.\n"
                        "Ergänze Anschaffungs-, Inbetriebnahme- und Garantie-Daten, um den Lebenszyklus zu verfolgen.\n"
                        "Retirement-Daten helfen später beim Ausmustern und Reporting."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Inventar: Geräte verwalten",
                    "summary": "Geräte erfassen, Kategorien zuordnen und Standortinformationen pflegen.",
                    "content": (
                        "Geräte werden einer Kategorie zugeordnet und erhalten optional Seriennummern und Specs.\n"
                        "Der Standort bestimmt, wo das Gerät aktuell eingesetzt wird.\n"
                        "Nutze Tags und Notizen für zusätzliche Kontextinformationen."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Kategorien & dynamische Felder",
                    "summary": "So funktionieren die flexiblen Felder pro Kategorie.",
                    "content": (
                        "Kategorien definieren, welche Felder im Formular angezeigt werden.\n"
                        "Die Felddefinitionen werden als JSON gespeichert und automatisch in Eingabefelder übersetzt.\n"
                        "Füge hier Status-, Hersteller- oder Modellfelder hinzu, ohne den Code anzupassen."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Standorte verwalten",
                    "summary": "Standortdaten strukturiert erfassen und zu Geräten/Assets zuweisen.",
                    "content": (
                        "Standorte helfen, Geräte und Assets geographisch oder organisatorisch zuordnen zu können.\n"
                        "Du kannst jeden Standort mit einer kurzen Beschreibung ergänzen.\n"
                        "In Listen lässt sich jederzeit nachvollziehen, welche Objekte dort hinterlegt sind."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Tags & Notizen bei Geräten",
                    "summary": "Zusätzliche Metadaten zur schnellen Suche und Dokumentation.",
                    "content": (
                        "Tags dienen als schnelle Filterkriterien für Gerätetypen, Projekte oder Besonderheiten.\n"
                        "Notizen ermöglichen Freitext, z. B. für Wartungshinweise oder individuelle Konfigurationen.\n"
                        "Beides ist direkt in der Geräteansicht pflegbar."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Wartungsaufgaben planen",
                    "summary": "Regelmäßige Wartungen erfassen und verfolgen.",
                    "content": (
                        "Wartungsaufgaben hängen an einem Gerät und beinhalten Titel, Fälligkeitsdatum und Status.\n"
                        "Der Status zeigt, ob eine Aufgabe offen oder erledigt ist.\n"
                        "Nutze diese Funktion für wiederkehrende Prüfungen und Sicherheitsupdates."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Asset-Zuweisungen",
                    "summary": "Assets Personen, Standorten oder Services zuordnen.",
                    "content": (
                        "Asset-Zuweisungen dokumentieren, wer oder was ein Asset aktuell nutzt.\n"
                        "Optional lassen sich Standort und Service referenzieren.\n"
                        "Historische Zuweisungen bleiben erhalten, um Nutzung nachzuvollziehen."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Services & SLA",
                    "summary": "Servicekatalog aufbauen und SLA-Werte definieren.",
                    "content": (
                        "Services beschreiben betriebliche Leistungen, z. B. E-Mail oder VPN.\n"
                        "SLA-Stunden definieren Zielzeiten für Tickets und Reports.\n"
                        "Assets können Services zugeordnet werden, damit Abhängigkeiten sichtbar bleiben."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Tickets: Überblick",
                    "summary": "Das Helpdesk-Modul und seine grundlegenden Elemente.",
                    "content": (
                        "Tickets bündeln Supportanfragen mit Titel, Kategorie, Status und Priorität.\n"
                        "Zusätzlich werden SLA-Informationen, Fälligkeiten und verantwortliche Teams gepflegt.\n"
                        "Tickets können mit Assets, Geräten und Wissenseinträgen verknüpft werden."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Tickets erstellen",
                    "summary": "Anleitung zum Erstellen neuer Supportfälle.",
                    "content": (
                        "Nutze die Ticketansicht und erstelle ein neues Ticket mit Titel und Beschreibung.\n"
                        "Wähle Kategorie, Priorität und optional einen Standort oder Service aus.\n"
                        "Damit werden die richtigen Teams automatisch informiert."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Ticket-Status & Priorität",
                    "summary": "So steuerst du den Lebenszyklus von Supportfällen.",
                    "content": (
                        "Statuswerte zeigen, ob ein Ticket offen, in Bearbeitung oder gelöst ist.\n"
                        "Prioritäten helfen bei der Reihenfolge der Bearbeitung.\n"
                        "Änderungen werden im Aktivitätslog aufgezeichnet."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Kommentare & interne Notizen",
                    "summary": "Kommunikation innerhalb und außerhalb des Teams.",
                    "content": (
                        "Kommentare dokumentieren die Kommunikation mit Antragstellern.\n"
                        "Interne Notizen bleiben nur für dein Team sichtbar.\n"
                        "Jeder Kommentar ergänzt die Ticket-Historie."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Watcher & Benachrichtigungen",
                    "summary": "Wie Abonnenten über Ticketänderungen informiert werden.",
                    "content": (
                        "Watcher erhalten Benachrichtigungen, wenn ein Ticket aktualisiert wird.\n"
                        "Lege Watcher-Adressen je Ticket fest oder pflege sie zentral in den Einstellungen.\n"
                        "So bleiben Stakeholder immer informiert."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Eskalationsstufen",
                    "summary": "Eskalationen strukturieren und dokumentieren.",
                    "content": (
                        "Eskalationslevel helfen dabei, dringende Tickets sichtbar zu machen.\n"
                        "Im Ticketformular lassen sich Level setzen und aktualisieren.\n"
                        "Reports können damit zeigen, welche Fälle kritisch sind."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "SLA & Fälligkeitsdaten",
                    "summary": "So nutzt du SLA-Zeiten für die Ticketplanung.",
                    "content": (
                        "Tickets enthalten SLA-Daten, die aus Service- oder Ticketkategorien abgeleitet werden können.\n"
                        "Fälligkeitsdaten helfen bei der Planung und Priorisierung.\n"
                        "Die Statistik-Seite zeigt dir, ob SLAs eingehalten werden."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Wissensbasis: Nutzung",
                    "summary": "Artikel finden, lesen und als Lösung referenzieren.",
                    "content": (
                        "Die Wissensbasis bietet strukturierte Artikel, die Lösungen und Prozesse beschreiben.\n"
                        "Nutze die Filter nach Kategorie und die Suche, um schnell passende Inhalte zu finden.\n"
                        "Tickets können auf relevante Artikel verweisen, um Wiederholungen zu vermeiden."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Wissenskategorien pflegen",
                    "summary": "Themenbereiche für die Wissensbasis anlegen.",
                    "content": (
                        "Wissenskategorien gruppieren Artikel nach Themen oder Workflows.\n"
                        "Neue Kategorien unterstützen Teams dabei, Inhalte konsistent zu organisieren.\n"
                        "Bestehende Kategorien können jederzeit aktualisiert oder erweitert werden."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Roadmap-Planung",
                    "summary": "Maßnahmen planen und Meilensteine verfolgen.",
                    "content": (
                        "Die Roadmap hält geplante Vorhaben inklusive Ticketbezug fest.\n"
                        "Einzelne Schritte lassen sich mit Titeln und Zieldaten hinterlegen.\n"
                        "So bleibt die Planung für langfristige Themen transparent."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Abhängigkeiten & Services",
                    "summary": "Systembeziehungen nachvollziehen.",
                    "content": (
                        "Die Abhängigkeiten-Seite dokumentiert, welche Services oder Software voneinander abhängen.\n"
                        "Verknüpfungen helfen, Auswirkungen von Ausfällen oder Updates zu analysieren.\n"
                        "So lassen sich Change- und Incident-Prozesse besser steuern."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Statistik & Reports",
                    "summary": "Kennzahlen zu Tickets und Inventar interpretieren.",
                    "content": (
                        "Die Statistik-Seite liefert Trends zu Ticket-Volumen, Status und SLA-Verhalten.\n"
                        "Inventarstatistiken zeigen die Verteilung von Geräten und Assets.\n"
                        "Nutze diese Daten für Management-Reports und Kapazitätsplanung."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Time Machine",
                    "summary": "Historische Veränderungen im Blick behalten.",
                    "content": (
                        "Die Time-Machine-Ansicht zeigt Änderungen über die Zeit hinweg.\n"
                        "So kannst du nachvollziehen, wann Assets, Tickets oder Benutzer angepasst wurden.\n"
                        "Diese Historie unterstützt Audit- und Compliance-Anforderungen."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Aktivitätslog",
                    "summary": "Alle Aktionen transparent nachvollziehen.",
                    "content": (
                        "Das Aktivitätslog protokolliert wichtige Änderungen in der Anwendung.\n"
                        "Einträge enthalten Nutzer, Aktion und betroffene Entität.\n"
                        "Damit kannst du jederzeit rekonstruieren, was passiert ist."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Benutzerverwaltung",
                    "summary": "User anlegen, verwalten und deaktivieren.",
                    "content": (
                        "In der Benutzerverwaltung legst du neue Konten an und verwaltest bestehende Nutzer.\n"
                        "Passwörter werden sicher gehasht gespeichert.\n"
                        "Rollen bestimmen, welche Module und Aktionen sichtbar sind."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Rollen & Berechtigungen",
                    "summary": "Feingranulare Zugriffssteuerung.",
                    "content": (
                        "Rollen bündeln Berechtigungen und können Nutzern zugewiesen werden.\n"
                        "Berechtigungen steuern den Zugriff auf Module wie Tickets, Wissensbasis oder Admin-Funktionen.\n"
                        "Superuser-Rollen haben erweiterten Zugriff auf alle Bereiche."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Zwei-Faktor-Authentifizierung",
                    "summary": "Zusätzliche Sicherheit per TOTP.",
                    "content": (
                        "Aktiviere 2FA für Benutzerkonten, um Logins abzusichern.\n"
                        "TOTP-Apps wie Google Authenticator oder Authy können verwendet werden.\n"
                        "Einmal aktiviert, ist bei jedem Login ein zusätzlicher Code erforderlich."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Passwort-Reset",
                    "summary": "Passwort zurücksetzen, wenn der Zugriff verloren geht.",
                    "content": (
                        "Nutzer können ihr Passwort über den Reset-Workflow wiederherstellen.\n"
                        "Der Prozess unterstützt TOTP-basierte Verifizierung.\n"
                        "Admins können Passwörter auch manuell zurücksetzen."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Ticket-Alerts & Automationen",
                    "summary": "Automatische Benachrichtigungen für kritische Ereignisse.",
                    "content": (
                        "Ticket-Alerts reagieren auf Ereignisse wie Statuswechsel oder Prioritätsänderungen.\n"
                        "Regeln können im Admin-Bereich gepflegt werden.\n"
                        "So bleiben Teams bei kritischen Tickets informiert."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Benachrichtigungseinstellungen",
                    "summary": "SMTP und Versandregeln konfigurieren.",
                    "content": (
                        "Im Admin-Bereich kannst du SMTP-Serverdaten hinterlegen.\n"
                        "Aktiviere oder deaktiviere den Versand von Systemmails.\n"
                        "Teste die Konfiguration, bevor produktive Alerts versendet werden."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Software-Inventar",
                    "summary": "Software erfassen und Installationen dokumentieren.",
                    "content": (
                        "Das Software-Modul listet Anwendungen und deren Versionen.\n"
                        "Installationen können einem Asset oder Gerät zugewiesen werden.\n"
                        "So behältst du Lizenzen und Abhängigkeiten im Blick."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Teams & Abteilungen",
                    "summary": "Organisationseinheiten für Tickets und Zuständigkeiten.",
                    "content": (
                        "Abteilungen strukturieren die Organisation und bilden Zuständigkeiten ab.\n"
                        "Teams helfen bei der Zuweisung von Tickets und Aufgaben.\n"
                        "Damit ist klar, wer welche Themen bearbeitet."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Dark Mode & UI-Einstellungen",
                    "summary": "Oberfläche an persönliche Präferenzen anpassen.",
                    "content": (
                        "Die Oberfläche unterstützt helle und dunkle Darstellung.\n"
                        "Das responsive Layout funktioniert auf Desktop und Mobile.\n"
                        "So bleibt die Bedienung auch unterwegs komfortabel."
                    ),
                    "category": "Produktguide",
                },
                {
                    "title": "Best Practices für die Wissensbasis",
                    "summary": "Tipps für strukturierte Dokumentation.",
                    "content": (
                        "Schreibe kurze Zusammenfassungen und detaillierte Inhalte pro Artikel.\n"
                        "Nutze Kategorien und klare Titel, damit Teams Inhalte schnell finden.\n"
                        "Verlinke Tickets mit finalen Lösungen, um Wissen wiederzuverwenden."
                    ),
                    "category": "Themen",
                },
            ]
            for entry in entries:
                c.execute(
                    '''
                    INSERT INTO knowledge_entries (title, summary, content, category_id, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        entry["title"],
                        entry["summary"],
                        entry["content"],
                        category_map.get(entry["category"]),
                        "System",
                    ),
                )

        c.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                owner TEXT,
                sla_hours INTEGER DEFAULT 72,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_id, service_id),
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                user_identifier TEXT NOT NULL,
                location_id INTEGER,
                service_id INTEGER,
                assigned_at TEXT,
                released_at TEXT,
                is_primary INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (location_id) REFERENCES locations(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_assignment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                assigned_to_user_id INTEGER,
                assigned_to_team_id INTEGER,
                status TEXT NOT NULL,
                checked_out_at TEXT,
                due_at TEXT,
                checked_in_at TEXT,
                note TEXT,
                created_by_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (assigned_to_user_id) REFERENCES users(id),
                FOREIGN KEY (assigned_to_team_id) REFERENCES teams(id),
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS asset_lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER,
                uploaded_by_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                department_id INTEGER,
                lead_user TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS software (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                vendor TEXT,
                version TEXT,
                license_type TEXT,
                criticality TEXT DEFAULT 'medium',
                description TEXT,
                owner_team_id INTEGER,
                support_contact TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, vendor, version),
                FOREIGN KEY (owner_team_id) REFERENCES teams(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS software_installations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                software_id INTEGER NOT NULL,
                device_id INTEGER,
                asset_id INTEGER,
                installed_version TEXT,
                environment TEXT DEFAULT 'production',
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (software_id) REFERENCES software(id),
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                vendor_type TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                website TEXT,
                address TEXT,
                rating INTEGER DEFAULT 3,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER,
                name TEXT NOT NULL,
                contract_type TEXT,
                status TEXT DEFAULT 'active',
                start_date TEXT,
                end_date TEXT,
                renewal_type TEXT DEFAULT 'manual',
                renewal_notice_days INTEGER DEFAULT 30,
                cost REAL,
                currency TEXT DEFAULT 'EUR',
                owner TEXT,
                service_level TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER,
                po_number TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'draft',
                order_date TEXT,
                expected_date TEXT,
                received_date TEXT,
                cost_center TEXT,
                requester TEXT,
                approver TEXT,
                subtotal REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total REAL DEFAULT 0,
                currency TEXT DEFAULT 'EUR',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_order_id INTEGER NOT NULL,
                item_type TEXT DEFAULT 'asset',
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                unit_cost REAL,
                total_cost REAL,
                asset_id INTEGER,
                device_id INTEGER,
                software_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id),
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (software_id) REFERENCES software(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS dependency_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT DEFAULT 'depends_on',
                criticality TEXT DEFAULT 'medium',
                redundancy_group TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_type, source_id, target_type, target_id, relation)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS rule_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_key TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                decision TEXT NOT NULL,
                reason TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS rule_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_key TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                outcome TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            CREATE TABLE IF NOT EXISTS server_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                host TEXT DEFAULT '0.0.0.0',
                port INTEGER DEFAULT 5000,
                debug_mode INTEGER DEFAULT 0,
                pro_enabled INTEGER DEFAULT 0,
                backup_enabled INTEGER DEFAULT 0,
                backup_schedule TEXT DEFAULT 'daily',
                backup_time TEXT DEFAULT '02:00',
                backup_retention_days INTEGER DEFAULT 14,
                backup_location TEXT DEFAULT 'backups/',
                backup_compress INTEGER DEFAULT 0,
                backup_encrypt INTEGER DEFAULT 0,
                backup_notify_email TEXT,
                allow_db_import INTEGER DEFAULT 0,
                allow_db_export INTEGER DEFAULT 1,
                export_format TEXT DEFAULT 'sqlite',
                import_mode TEXT DEFAULT 'merge',
                include_uploads INTEGER DEFAULT 1,
                require_https INTEGER DEFAULT 0,
                session_timeout_minutes INTEGER DEFAULT 60,
                max_failed_logins INTEGER DEFAULT 5,
                lockout_minutes INTEGER DEFAULT 15,
                allowed_ip_ranges TEXT,
                password_min_length INTEGER DEFAULT 10,
                enforce_mfa INTEGER DEFAULT 0,
                terminal_enabled INTEGER DEFAULT 0,
                terminal_require_reauth INTEGER DEFAULT 1,
                terminal_ip_allowlist TEXT,
                terminal_allow_db_write INTEGER DEFAULT 0,
                terminal_allow_service_restart INTEGER DEFAULT 0,
                terminal_break_glass INTEGER DEFAULT 0,
                update_policy_json TEXT DEFAULT '{}',
                schema_version INTEGER DEFAULT 1,
                updated_by TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('INSERT OR IGNORE INTO server_settings (id) VALUES (1)')
        c.execute('''
            CREATE TABLE IF NOT EXISTS server_settings_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                settings_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory_links (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                verify_tls INTEGER DEFAULT 1,
                auth_mode TEXT DEFAULT 'apiKey',
                secret_encrypted TEXT,
                allow_private_network INTEGER DEFAULT 1,
                connection_scope TEXT DEFAULT 'internet',
                health_status TEXT,
                health_last_checked_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_inventory_links_user_id ON inventory_links(user_id)')
        try:
            c.execute("ALTER TABLE inventory_links ADD COLUMN connection_scope TEXT DEFAULT 'internet'")
            # Existing plain-HTTP links are treated as LAN links. Other existing
            # links remain Internet links and must satisfy the stricter policy
            # on their next request instead of silently broadening access.
            c.execute("UPDATE inventory_links SET connection_scope = 'local' WHERE lower(base_url) LIKE 'http://%'")
        except sqlite3.OperationalError:
            pass
        c.execute('''
            CREATE TABLE IF NOT EXISTS backup_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                backup_path TEXT,
                backup_size_bytes INTEGER,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS terminal_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                mode TEXT DEFAULT 'maintenance',
                ip TEXT,
                user_agent TEXT,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS terminal_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER,
                action_type TEXT NOT NULL,
                params_json TEXT,
                status TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                output_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (session_id) REFERENCES terminal_sessions(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_check_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE,
                category TEXT,
                check_type TEXT NOT NULL,
                config_json TEXT,
                interval_seconds INTEGER DEFAULT 60,
                timeout_seconds INTEGER DEFAULT 10,
                enabled INTEGER DEFAULT 1,
                last_run_at TEXT,
                last_status TEXT,
                last_duration_ms INTEGER,
                last_summary_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_check_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT DEFAULT 'running',
                triggered_by TEXT,
                initiated_by TEXT,
                summary_json TEXT,
                error_message TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                check_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                severity TEXT,
                reason TEXT,
                observed_at TEXT NOT NULL,
                duration_ms INTEGER,
                metrics_json TEXT,
                details_json TEXT,
                FOREIGN KEY (run_id) REFERENCES health_check_runs(id),
                FOREIGN KEY (check_id) REFERENCES health_check_definitions(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                previous_status TEXT,
                current_status TEXT,
                severity TEXT,
                reason TEXT,
                observed_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (check_id) REFERENCES health_check_definitions(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                summary TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                acknowledged_at TEXT,
                muted_until TEXT,
                last_status TEXT,
                last_observed_at TEXT,
                ticket_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (check_id) REFERENCES health_check_definitions(id),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT PRIMARY KEY,
                failed_count INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ui_customization (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                workspace_id INTEGER,
                schema_version INTEGER NOT NULL DEFAULT 1,
                customization_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                UNIQUE(user_id, workspace_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ui_customization_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customization_id INTEGER NOT NULL,
                revision_json TEXT NOT NULL,
                diff_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (customization_id) REFERENCES ui_customization(id)
            )
        ''')
        for column, column_type in (
            ("backup_enabled", "INTEGER DEFAULT 0"),
            ("backup_schedule", "TEXT DEFAULT 'daily'"),
            ("backup_time", "TEXT DEFAULT '02:00'"),
            ("backup_retention_days", "INTEGER DEFAULT 14"),
            ("backup_location", "TEXT DEFAULT 'backups/'"),
            ("backup_compress", "INTEGER DEFAULT 0"),
            ("backup_encrypt", "INTEGER DEFAULT 0"),
            ("backup_notify_email", "TEXT"),
            ("allow_db_import", "INTEGER DEFAULT 0"),
            ("allow_db_export", "INTEGER DEFAULT 1"),
            ("export_format", "TEXT DEFAULT 'sqlite'"),
            ("import_mode", "TEXT DEFAULT 'merge'"),
            ("include_uploads", "INTEGER DEFAULT 1"),
            ("require_https", "INTEGER DEFAULT 0"),
            ("session_timeout_minutes", "INTEGER DEFAULT 60"),
            ("max_failed_logins", "INTEGER DEFAULT 5"),
            ("lockout_minutes", "INTEGER DEFAULT 15"),
            ("allowed_ip_ranges", "TEXT"),
            ("password_min_length", "INTEGER DEFAULT 10"),
            ("enforce_mfa", "INTEGER DEFAULT 0"),
            ("terminal_enabled", "INTEGER DEFAULT 0"),
            ("terminal_require_reauth", "INTEGER DEFAULT 1"),
            ("terminal_ip_allowlist", "TEXT"),
            ("terminal_allow_db_write", "INTEGER DEFAULT 0"),
            ("terminal_allow_service_restart", "INTEGER DEFAULT 0"),
            ("terminal_break_glass", "INTEGER DEFAULT 0"),
            ("update_policy_json", "TEXT DEFAULT '{}'"),
            ("schema_version", "INTEGER DEFAULT 1"),
            ("updated_by", "TEXT"),
        ):
            try:
                c.execute(f'ALTER TABLE server_settings ADD COLUMN {column} {column_type}')
            except sqlite3.OperationalError:
                pass

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

        c.execute('''
            CREATE TABLE IF NOT EXISTS roadmaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER UNIQUE,
                title TEXT NOT NULL,
                objective TEXT,
                status TEXT DEFAULT 'planned',
                owner TEXT,
                start_date TEXT,
                target_date TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS roadmap_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roadmap_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'planned',
                position INTEGER DEFAULT 0,
                owner TEXT,
                due_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id)
            )
        ''')

        # Default-Kategorien (Geräte)
        default_categories = [
            ("Laptop", "tech:laptop", "Mobile Arbeitsplätze und Notebooks.", json.dumps({
                "CPU": "text",
                "RAM (GB)": "number",
                "Storage": "text",
                "GPU": "text",
                "Display (Zoll)": "number",
                "OS": "text",
                "Dockingfähig": "checkbox",
                "Batterie-Zyklen": "number"
            })),
            ("Desktop / Workstation", "monitor", "Stationäre Arbeitsplätze und Workstations.", json.dumps({
                "CPU": "text",
                "RAM (GB)": "number",
                "Storage": "text",
                "GPU": "text",
                "Formfaktor": {"type": "select", "options": ["Tower", "SFF", "Mini", "All-in-One"]},
                "OS": "text",
                "Netzteil (W)": "number"
            })),
            ("Server", "server", "Physische Server und Host-Systeme.", json.dumps({
                "CPU": "text",
                "Sockets": "number",
                "RAM (GB)": "number",
                "Storage": "text",
                "RAID": "text",
                "Virtualisierung": {"type": "select", "options": ["VMware", "Hyper-V", "KVM", "Bare Metal"]},
                "Rack-Position": "text",
                "IP / Hostname": "text"
            })),
            ("Thin Client", "terminal", "Terminal- und VDI-Endgeräte.", json.dumps({
                "CPU": "text",
                "RAM (GB)": "number",
                "Storage": "text",
                "VDI/Terminal": {"type": "select", "options": ["Citrix", "RDP", "VMware Horizon", "Web"]},
                "OS": "text"
            })),
            ("Monitor / Display", "monitor", "Bildschirme und Displays.", json.dumps({
                "Größe (Zoll)": "number",
                "Auflösung": "text",
                "Panel": {"type": "select", "options": ["IPS", "VA", "TN", "OLED"]},
                "Anschlüsse": "text",
                "HDR": "checkbox"
            })),
            ("Drucker / MFP", "printer", "Drucker, Scanner und Multifunktionsgeräte.", json.dumps({
                "Typ": {"type": "select", "options": ["Laser", "Inkjet", "Thermo", "Label"]},
                "Farbe": "checkbox",
                "Duplex": "checkbox",
                "Seiten/Minute": "number",
                "Netzwerkfähig": "checkbox"
            })),
            ("Smartphone", "smartphone", "Firmenhandys und Mobiltelefone.", json.dumps({
                "OS": {"type": "select", "options": ["iOS", "Android"]},
                "Speicher (GB)": "number",
                "IMEI": "text",
                "SIM / eSIM": "text",
                "MDM verwaltet": "checkbox"
            })),
            ("Tablet", "tablet", "Tablets für mobile Nutzung.", json.dumps({
                "OS": {"type": "select", "options": ["iOS", "Android", "Windows"]},
                "Speicher (GB)": "number",
                "Display (Zoll)": "number",
                "Stift-Unterstützung": "checkbox",
                "MDM verwaltet": "checkbox"
            })),
            ("Switch", "share-2", "Netzwerk-Switches und Verteiler.", json.dumps({
                "Ports": "number",
                "Managed": "checkbox",
                "Port-Speed": {"type": "select", "options": ["1G", "2.5G", "5G", "10G", "25G", "40G"]},
                "PoE": {"type": "select", "options": ["Nein", "PoE", "PoE+", "PoE++"]},
                "Uplink": "text"
            })),
            ("Router / Firewall", "shield", "Gateway-, Router- und Firewall-Systeme.", json.dumps({
                "WAN": "text",
                "VPN": "checkbox",
                "Durchsatz (Gbps)": "number",
                "Firmware": "text",
                "HA-Cluster": "checkbox"
            })),
            ("Access Point", "wifi", "WLAN Access Points.", json.dumps({
                "WiFi-Standard": {"type": "select", "options": ["802.11ac", "802.11ax", "802.11be"]},
                "SSID": "text",
                "Controller": "text",
                "PoE": "checkbox",
                "Montageort": "text"
            })),
            ("Storage / NAS", "hard-drive", "Storage-Systeme und NAS.", json.dumps({
                "Kapazität (TB)": "number",
                "RAID": "text",
                "Protokoll": {"type": "select", "options": ["SMB", "NFS", "iSCSI", "S3"]},
                "Bay-Anzahl": "number",
                "IP / Hostname": "text"
            })),
            ("USV / Power", "battery-charging", "USV, Stromversorgung und Power-Units.", json.dumps({
                "Leistung (VA)": "number",
                "Laufzeit (Min)": "number",
                "Batterie-Typ": "text",
                "Steckdosen": "number",
                "Netzwerk-Management": "checkbox"
            })),
            ("Kamera / CCTV", "camera", "IP-Kameras und Überwachung.", json.dumps({
                "Auflösung": "text",
                "Typ": {"type": "select", "options": ["IP", "Analog"]},
                "IR / Nachtsicht": "checkbox",
                "FOV": "text",
                "Speicherziel": "text"
            })),
            ("Konferenz / AV", "video", "Meetingraum- und AV-Technik.", json.dumps({
                "Typ": {"type": "select", "options": ["Display", "Konferenzkamera", "Audio", "Controller"]},
                "Auflösung": "text",
                "Anschlüsse": "text",
                "Raum": "text"
            })),
            ("IoT / Sensor", "activity", "Sensoren, Gateways und IoT-Geräte.", json.dumps({
                "Sensor-Typ": "text",
                "Protokoll": {"type": "select", "options": ["MQTT", "HTTP", "LoRaWAN", "Zigbee", "BLE"]},
                "Firmware": "text",
                "Batterie": "text",
                "Gateway": "text"
            })),
            ("Peripherie", "mouse-pointer", "Mäuse, Tastaturen, Scanner, Zubehör.", json.dumps({
                "Typ": {"type": "select", "options": ["Maus", "Tastatur", "Scanner", "Dock", "Headset", "Sonstiges"]},
                "Anschluss": {"type": "select", "options": ["USB", "Bluetooth", "RF", "Thunderbolt"]},
                "Kompatibilität": "text"
            })),
            ("CPU", "cpu", "Prozessoren und Server-CPUs.", json.dumps({
                "Cores": "number",
                "Threads": "number",
                "Takt": "text",
                "Hersteller": "text",
                "Sockel": "text"
            })),
            ("GPU", "tech:gpu", "Grafikkarten und Beschleuniger.", json.dumps({
                "VRAM": "text",
                "Modell": "text",
                "Hersteller": "text",
                "Anschluss": "text",
                "Leistungsaufnahme": "text"
            })),
            ("RAM", "tech:ram", "Arbeitsspeicher und Module.", json.dumps({
                "Kapazität": "text",
                "Typ": "text",
                "Takt": "text",
                "Formfaktor": "text"
            }))
        ]
        c.executemany('''
            INSERT OR IGNORE INTO categories (name, icon, description, fields)
            VALUES (?, ?, ?, ?)
        ''', default_categories)

        # Icon-Migrationen für bestehende Datenbanken (alte Feather-Namen -> tech:* Icons)
        c.execute('''
            UPDATE categories
            SET icon = 'tech:gpu'
            WHERE name = 'GPU' AND (icon IS NULL OR icon IN ('gpu', 'feather:gpu'))
        ''')
        c.execute('''
            UPDATE categories
            SET icon = 'tech:ram'
            WHERE name = 'RAM' AND (icon IS NULL OR icon IN ('memory', 'feather:memory', 'ram', 'feather:ram'))
        ''')
        c.execute('''
            UPDATE categories
            SET icon = 'tech:laptop'
            WHERE name = 'Laptop' AND (icon IS NULL OR icon IN ('laptop', 'feather:laptop'))
        ''')

        # Default-Kategorien (Assets)
        default_asset_categories = [
            ("Arbeitsplatz", "briefcase", "Vollständige Arbeitsplatz-Ausstattung.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["aktiv", "in Lager", "ausgemustert", "verliehen"]},
                "Kritikalität": {"type": "select", "options": ["niedrig", "mittel", "hoch", "kritisch"]},
                "Owner": "text",
                "Team / Abteilung": "text",
                "Kostenstelle": "text",
                "Standort": "text",
                "Support-Vertrag": "text"
            })),
            ("Server-Plattform", "server", "Server- und Host-Systeme inkl. Komponenten.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["produktiv", "staging", "test", "außer Betrieb"]},
                "Kritikalität": {"type": "select", "options": ["hoch", "kritisch"]},
                "Owner": "text",
                "Service": "text",
                "RZ / Rack": "text",
                "SLA": {"type": "select", "options": ["Gold", "Silver", "Bronze"]},
                "Support-Vertrag": "text"
            })),
            ("Netzwerk", "share-2", "Switch-/Router-/Firewall-Stacks.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["produktiv", "staging", "test"]},
                "Kritikalität": {"type": "select", "options": ["mittel", "hoch", "kritisch"]},
                "Owner": "text",
                "Segment / VLAN": "text",
                "Standort": "text",
                "Provider": "text",
                "Support-Vertrag": "text"
            })),
            ("Druckerpark", "printer", "Drucker- und Scan-Infrastruktur.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["aktiv", "in Wartung", "außer Betrieb"]},
                "Owner": "text",
                "Standort": "text",
                "Service-Partner": "text",
                "Wartungsfenster": "text"
            })),
            ("Konferenzraum", "video", "Raumtechnik für Meetings.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["aktiv", "eingeschränkt", "außer Betrieb"]},
                "Raum": "text",
                "Kapazität": "number",
                "Owner": "text",
                "Support-Kontakt": "text"
            })),
            ("Mobile Flotte", "smartphone", "Gerätepool für mobile Endgeräte.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["aktiv", "in Lager", "ausgemustert"]},
                "MDM": "text",
                "Owner": "text",
                "Ausgabe-Policy": "text",
                "Service-Provider": "text"
            })),
            ("Storage-Cluster", "hard-drive", "Storage-Systeme inkl. Arrays.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["produktiv", "staging", "test"]},
                "Kritikalität": {"type": "select", "options": ["hoch", "kritisch"]},
                "Owner": "text",
                "Kapazität (TB)": "number",
                "Protokolle": "text",
                "Support-Vertrag": "text"
            })),
            ("Security / CCTV", "shield", "Videoüberwachung und Sicherheitstechnik.", json.dumps({
                "Asset-Tag": "text",
                "Status": {"type": "select", "options": ["aktiv", "eingeschränkt", "außer Betrieb"]},
                "Standort": "text",
                "Owner": "text",
                "Datenschutz-Level": {"type": "select", "options": ["niedrig", "mittel", "hoch"]},
                "Wartungsfenster": "text"
            })),
            ("Software-Lizenz", "code", "Lizenzverträge und Abos.", json.dumps({
                "Lizenztyp": {"type": "select", "options": ["Einzeln", "Volumen", "Abo"]},
                "Hersteller": "text",
                "Vertragspartner": "text",
                "Laufzeit": "text",
                "Compliance": "text",
                "Owner": "text"
            })),
            ("Cloud-Service", "cloud", "Cloud-Services und SaaS.", json.dumps({
                "Service": "text",
                "Provider": "text",
                "Umgebung": {"type": "select", "options": ["prod", "staging", "dev"]},
                "Kritikalität": {"type": "select", "options": ["mittel", "hoch", "kritisch"]},
                "Owner": "text",
                "SLA": "text"
            }))
        ]
        c.executemany('''
            INSERT OR IGNORE INTO asset_categories (name, icon, description, fields)
            VALUES (?, ?, ?, ?)
        ''', default_asset_categories)

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
            ("Change", "Geplante Änderungen und Wartungen", "#7c3aed", 168, 0),
            ("Review", "Kontroll- und Abnahmeaufgaben für Changes", "#0f766e", 72, 0),
            ("Verbesserungen", "Optimierungen, neue Features und Produktideen", "#0ea5e9", 168, 0)
        ]
        c.executemany('''
            INSERT OR IGNORE INTO ticket_categories (name, description, color, sla_hours, is_default)
            VALUES (?, ?, ?, ?, ?)
        ''', default_ticket_categories)
        backfill_ticket_review_links(db)

        default_relation_types = [
            ("hostet", "Asset stellt Ressourcen für ein anderes bereit"),
            ("nutzt", "Asset nutzt ein anderes Asset"),
            ("verbunden mit", "Direkte technische Verbindung"),
            ("gehört zu", "Asset ist Teil eines größeren Systems"),
            ("ersetzt", "Asset ersetzt ein anderes"),
            ("enthält", "Storage-Asset enthält andere Assets"),
            ("gelagert in", "Asset ist in einem Storage-Asset eingelagert"),
        ]
        c.executemany('''
            INSERT OR IGNORE INTO asset_relation_types (name, description)
            VALUES (?, ?)
        ''', default_relation_types)

        try:
            c.execute('ALTER TABLE devices ADD COLUMN location_id INTEGER')
        except sqlite3.OperationalError:
            pass

        seed_permissions(db)
        seed_roles(db)
        ensure_default_roles(db)
        ensure_admin_user(db)
        seed_health_checks(db)
        try:
            apply_migrations(db, Path(__file__).with_name("migrations"))
        except MigrationError as error:
            raise RuntimeError("Datenbankmigration konnte nicht sicher angewendet werden.") from error
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

def redact_payload(payload):
    if isinstance(payload, dict):
        redacted = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if any(token in key_lower for token in HEALTH_REDACT_KEYS):
                redacted[key] = "***"
            else:
                redacted[key] = redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload

def normalize_health_status(status):
    return status if status in HEALTH_STATUS_ORDER else "UNKNOWN"

def worst_health_status(statuses):
    worst = "OK"
    for status in statuses:
        candidate = normalize_health_status(status)
        if HEALTH_STATUS_ORDER[candidate] > HEALTH_STATUS_ORDER[worst]:
            worst = candidate
    return worst

def safe_json_load(value, default=None):
    if not value:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default if default is not None else {}

def safe_sql_identifier(identifier):
    if not identifier:
        return None
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
        return identifier
    return None

def health_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def register_health_check(name):
    def decorator(fn):
        HEALTH_CHECK_REGISTRY[name] = fn
        return fn
    return decorator

def serialize_health_definition(row):
    config = safe_json_load(row["config_json"])
    redacted_config = redact_payload(config)
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "category": row["category"],
        "check_type": row["check_type"],
        "interval_seconds": row["interval_seconds"],
        "timeout_seconds": row["timeout_seconds"],
        "enabled": bool(row["enabled"]),
        "last_run_at": row["last_run_at"],
        "last_status": row["last_status"],
        "last_duration_ms": row["last_duration_ms"],
        "last_summary": safe_json_load(row["last_summary_json"], default={}),
        "config": redacted_config
    }

def store_health_event(db, check_id, previous_status, current_status, severity, reason, observed_at):
    db.execute(
        '''
        INSERT INTO health_events (
            check_id, previous_status, current_status, severity, reason, observed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (check_id, previous_status, current_status, severity, reason, observed_at)
    )

def record_health_incident(db, check_id, summary, observed_at, status):
    db.execute(
        '''
        INSERT INTO health_incidents (
            check_id, status, summary, opened_at, last_status, last_observed_at
        )
        VALUES (?, 'open', ?, ?, ?, ?)
        ''',
        (check_id, summary, observed_at, status, observed_at)
    )

def close_health_incident(db, incident_id, observed_at):
    db.execute(
        '''
        UPDATE health_incidents
        SET status = 'closed',
            closed_at = ?,
            last_status = 'OK',
            last_observed_at = ?
        WHERE id = ?
        ''',
        (observed_at, observed_at, incident_id)
    )

def update_health_incident_state(db, check_id, status, observed_at, config):
    status = normalize_health_status(status)
    incident_open_after_value = config.get("incident_open_after_minutes")
    incident_close_after_value = config.get("incident_close_after_minutes")
    incident_open_after = int(incident_open_after_value) if incident_open_after_value is not None else HEALTH_INCIDENT_OPEN_MINUTES
    incident_close_after = int(incident_close_after_value) if incident_close_after_value is not None else HEALTH_INCIDENT_CLOSE_MINUTES

    active_incident = db.execute(
        '''
        SELECT id, status, opened_at, acknowledged_at, muted_until
        FROM health_incidents
        WHERE check_id = ? AND status = 'open'
        ORDER BY opened_at DESC
        LIMIT 1
        ''',
        (check_id,)
    ).fetchone()

    if status == "CRIT":
        last_non_crit = db.execute(
            '''
            SELECT observed_at
            FROM health_check_results
            WHERE check_id = ? AND status != 'CRIT'
            ORDER BY observed_at DESC
            LIMIT 1
            ''',
            (check_id,)
        ).fetchone()
        if last_non_crit:
            last_non_crit_at = datetime.strptime(last_non_crit["observed_at"], "%Y-%m-%d %H:%M:%S")
            current_time = datetime.strptime(observed_at, "%Y-%m-%d %H:%M:%S")
            duration_minutes = (current_time - last_non_crit_at).total_seconds() / 60
        else:
            duration_minutes = incident_open_after + 1
        if duration_minutes >= incident_open_after and not active_incident:
            record_health_incident(
                db,
                check_id,
                f"CRIT länger als {incident_open_after} Minuten",
                observed_at,
                status
            )
        if active_incident:
            db.execute(
                '''
                UPDATE health_incidents
                SET last_status = ?, last_observed_at = ?
                WHERE id = ?
                ''',
                (status, observed_at, active_incident["id"])
            )
        return

    if active_incident and status == "OK":
        last_non_ok = db.execute(
            '''
            SELECT observed_at
            FROM health_check_results
            WHERE check_id = ? AND status != 'OK'
            ORDER BY observed_at DESC
            LIMIT 1
            ''',
            (check_id,)
        ).fetchone()
        if last_non_ok:
            last_non_ok_at = datetime.strptime(last_non_ok["observed_at"], "%Y-%m-%d %H:%M:%S")
            current_time = datetime.strptime(observed_at, "%Y-%m-%d %H:%M:%S")
            duration_minutes = (current_time - last_non_ok_at).total_seconds() / 60
        else:
            duration_minutes = incident_close_after + 1
        if duration_minutes >= incident_close_after:
            close_health_incident(db, active_incident["id"], observed_at)
        else:
            db.execute(
                '''
                UPDATE health_incidents
                SET last_status = ?, last_observed_at = ?
                WHERE id = ?
                ''',
                (status, observed_at, active_incident["id"])
            )
        return

    if active_incident:
        db.execute(
            '''
            UPDATE health_incidents
            SET last_status = ?, last_observed_at = ?
            WHERE id = ?
            ''',
            (status, observed_at, active_incident["id"])
        )

def record_health_result(db, run_id, check_def, result):
    check_data = dict(check_def)
    observed_at = result.get("observed_at") or health_now()
    status = normalize_health_status(result.get("status"))
    severity = result.get("severity") or status
    reason = result.get("reason") or ""
    metrics = redact_payload(result.get("metrics") or {})
    details = redact_payload(result.get("details") or {})
    duration_ms = int(result.get("duration_ms") or 0)
    db.execute(
        '''
        INSERT INTO health_check_results (
            run_id, check_id, status, severity, reason, observed_at,
            duration_ms, metrics_json, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            run_id,
            check_def["id"],
            status,
            severity,
            reason,
            observed_at,
            duration_ms,
            json.dumps(metrics),
            json.dumps(details)
            )
        )

    previous_status = check_data.get("last_status") or "UNKNOWN"
    if previous_status != status:
        store_health_event(
            db,
            check_data["id"],
            previous_status,
            status,
            severity,
            reason,
            observed_at
        )

    db.execute(
        '''
        UPDATE health_check_definitions
        SET last_run_at = ?,
            last_status = ?,
            last_duration_ms = ?,
            last_summary_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (
            observed_at,
            status,
            duration_ms,
            json.dumps({
                "reason": reason,
                "metrics": metrics
            }),
            check_data["id"]
        )
    )
    update_health_incident_state(db, check_data["id"], status, observed_at, safe_json_load(check_data["config_json"]))

def run_health_check_definition(db, check_def):
    check_type = check_def["check_type"]
    config = safe_json_load(check_def["config_json"])
    timeout_seconds = int(check_def["timeout_seconds"] or 10)
    retries = int(config.get("retries") or 0)
    retry_delay = float(config.get("retry_delay_seconds") or 0)
    result = None
    attempts = 0
    while attempts <= retries:
        attempts += 1
        start_time = time.time()
        try:
            handler = HEALTH_CHECK_REGISTRY.get(check_type)
            if not handler:
                result = {
                    "status": "UNKNOWN",
                    "severity": "UNKNOWN",
                    "reason": f"Check-Typ {check_type} ist nicht registriert",
                    "metrics": {},
                    "details": {}
                }
            else:
                result = handler(config, db, timeout_seconds)
        except Exception as exc:
            result = {
                "status": "UNKNOWN",
                "severity": "UNKNOWN",
                "reason": f"Fehler beim Check: {exc}",
                "metrics": {},
                "details": {}
            }
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        result["observed_at"] = health_now()
        if result.get("status") != "UNKNOWN" or attempts > retries:
            break
        if retry_delay > 0:
            time.sleep(retry_delay)
    return result

def run_health_checks(db, check_ids=None, triggered_by="scheduler", initiated_by=None, run_id=None):
    started_at = health_now()
    if run_id is None:
        cursor = db.execute(
            '''
            INSERT INTO health_check_runs (started_at, status, triggered_by, initiated_by)
            VALUES (?, 'running', ?, ?)
            ''',
            (started_at, triggered_by, initiated_by)
        )
        run_id = cursor.lastrowid
    else:
        db.execute(
            '''
            UPDATE health_check_runs
            SET status = 'running', started_at = ?, triggered_by = ?, initiated_by = ?
            WHERE id = ?
            ''',
            (started_at, triggered_by, initiated_by, run_id)
        )

    if check_ids:
        placeholders = ",".join(["?"] * len(check_ids))
        check_rows = db.execute(
            f'''
            SELECT *
            FROM health_check_definitions
            WHERE id IN ({placeholders})
            ''',
            check_ids
        ).fetchall()
    else:
        check_rows = db.execute(
            '''
            SELECT *
            FROM health_check_definitions
            WHERE enabled = 1
            '''
        ).fetchall()

    statuses = []
    for row in check_rows:
        result = run_health_check_definition(db, row)
        record_health_result(db, run_id, row, result)
        statuses.append(result.get("status") or "UNKNOWN")

    finished_at = health_now()
    overall_status = worst_health_status(statuses)
    db.execute(
        '''
        UPDATE health_check_runs
        SET finished_at = ?, status = ?, summary_json = ?
        WHERE id = ?
        ''',
        (
            finished_at,
            overall_status,
            json.dumps({"status": overall_status, "count": len(statuses)}),
            run_id
        )
    )
    db.commit()
    return run_id, overall_status

def run_health_checks_async(check_ids, initiated_by, run_id):
    with app.app_context():
        db = get_db()
        run_health_checks(db, check_ids=check_ids, triggered_by="manual", initiated_by=initiated_by, run_id=run_id)

def fetch_due_health_checks(db):
    now = datetime.utcnow()
    rows = db.execute(
        '''
        SELECT *
        FROM health_check_definitions
        WHERE enabled = 1
        '''
    ).fetchall()
    due = []
    for row in rows:
        last_run = row["last_run_at"]
        interval = int(row["interval_seconds"] or 60)
        if not last_run:
            due.append(row)
            continue
        try:
            last_run_time = datetime.strptime(last_run, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            due.append(row)
            continue
        if (now - last_run_time).total_seconds() >= interval:
            due.append(row)
    return due

def cleanup_health_retention(db):
    cutoff = datetime.utcnow() - timedelta(days=HEALTH_DEFAULT_RETENTION_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    db.execute('DELETE FROM health_check_results WHERE observed_at < ?', (cutoff_str,))
    db.execute('DELETE FROM health_check_runs WHERE started_at < ?', (cutoff_str,))
    db.execute('DELETE FROM health_events WHERE observed_at < ?', (cutoff_str,))

def scheduled_health_run():
    with app.app_context():
        db = get_db()
        due = fetch_due_health_checks(db)
        if not due:
            return
        check_ids = [row["id"] for row in due]
        run_health_checks(db, check_ids=check_ids, triggered_by="scheduler", initiated_by="system")
        cleanup_health_retention(db)
        db.commit()

def schedule_health_jobs():
    if not SCHEDULER_ENABLED:
        app.logger.info("In-Process-Health-Scheduler ist für diesen Worker deaktiviert.")
        return
    if not HEALTH_SCHEDULER.running:
        HEALTH_SCHEDULER.start()
    HEALTH_SCHEDULER.remove_all_jobs()
    HEALTH_SCHEDULER.add_job(
        scheduled_health_run,
        "interval",
        seconds=60,
        id="health_checks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

def fetch_latest_health_results(db):
    return db.execute(
        '''
        SELECT r.*, d.name, d.slug, d.category, d.check_type, d.enabled
        FROM health_check_results r
        JOIN health_check_definitions d ON d.id = r.check_id
        JOIN (
            SELECT check_id, MAX(observed_at) AS max_observed
            FROM health_check_results
            GROUP BY check_id
        ) latest
        ON latest.check_id = r.check_id AND latest.max_observed = r.observed_at
        WHERE d.enabled = 1
        '''
    ).fetchall()

def serialize_health_result(row):
    data = dict(row)
    return {
        "id": data["id"],
        "check_id": data["check_id"],
        "status": data["status"],
        "severity": data["severity"],
        "reason": data["reason"],
        "observed_at": data["observed_at"],
        "duration_ms": data["duration_ms"],
        "metrics": safe_json_load(data["metrics_json"], default={}),
        "details": safe_json_load(data["details_json"], default={}),
        "check": {
            "name": data.get("name"),
            "slug": data.get("slug"),
            "category": data.get("category"),
            "check_type": data.get("check_type")
        }
    }

@register_health_check("service_unit")
def health_check_service_unit(config, db, timeout_seconds):
    unit = (config.get("unit") or "").strip()
    if not unit:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "systemd Unit fehlt",
            "metrics": {},
            "details": {}
        }
    if not shutil.which("systemctl"):
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "systemctl nicht verfügbar",
            "metrics": {},
            "details": {}
        }
    try:
        output = subprocess.check_output(
            ["systemctl", "show", unit, "--no-page", "--property=ActiveState,SubState,ExecMainStatus,ExecMainExitTimestamp,ActiveEnterTimestamp"],
            text=True,
            timeout=timeout_seconds
        )
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": f"systemctl Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    info = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key] = value
    active_state = info.get("ActiveState", "unknown")
    status = "OK" if active_state == "active" else "CRIT"
    reason = f"Unit {unit} ist {active_state}"
    return {
        "status": status,
        "severity": status,
        "reason": reason,
        "metrics": {
            "active_state": active_state,
            "sub_state": info.get("SubState"),
            "exec_status": info.get("ExecMainStatus")
        },
        "details": {
            "last_exit": info.get("ExecMainExitTimestamp"),
            "active_since": info.get("ActiveEnterTimestamp")
        }
    }

@register_health_check("process")
def health_check_process(config, db, timeout_seconds):
    process_name = (config.get("process_name") or "").strip()
    min_count = int(config.get("min_count") or 1)
    if not process_name:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Prozessname fehlt",
            "metrics": {},
            "details": {}
        }
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        pids = [line for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": f"pgrep Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    count = len(pids)
    status = "OK" if count >= min_count else "CRIT"
    return {
        "status": status,
        "severity": status,
        "reason": f"{count} Prozesse gefunden",
        "metrics": {"process_count": count, "min_count": min_count},
        "details": {"pids": pids[:10]}
    }

@register_health_check("tcp_port")
def health_check_tcp_port(config, db, timeout_seconds):
    host = (config.get("host") or "127.0.0.1").strip()
    port = int(config.get("port") or 0)
    if not port:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Port fehlt",
            "metrics": {},
            "details": {}
        }
    start_time = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "OK",
                "severity": "OK",
                "reason": f"TCP {host}:{port} erreichbar",
                "metrics": {"latency_ms": latency_ms},
                "details": {}
            }
    except Exception as exc:
        return {
            "status": "CRIT",
            "severity": "CRIT",
            "reason": f"TCP {host}:{port} nicht erreichbar: {exc}",
            "metrics": {},
            "details": {}
        }

@register_health_check("http")
def health_check_http(config, db, timeout_seconds):
    url = (config.get("url") or "").strip()
    if not url:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "URL fehlt",
            "metrics": {},
            "details": {}
        }
    method = (config.get("method") or "GET").upper()
    expect_status = int(config.get("expect_status") or 200)
    contains = config.get("contains")
    start_time = time.time()
    request_obj = urllib.request.Request(url, method=method)
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request_obj, timeout=timeout_seconds, context=context) as response:
            body = response.read(4096).decode(errors="ignore")
            latency_ms = int((time.time() - start_time) * 1000)
            status_code = response.getcode()
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = exc.code
        body = exc.read(1024).decode(errors="ignore") if exc.fp else ""
    except Exception as exc:
        return {
            "status": "CRIT",
            "severity": "CRIT",
            "reason": f"HTTP Fehler: {exc}",
            "metrics": {},
            "details": {}
        }

    status = "OK" if status_code == expect_status else "WARN"
    if contains and contains not in body:
        status = "WARN"
    reason = f"HTTP {status_code} in {latency_ms} ms"
    return {
        "status": status,
        "severity": status,
        "reason": reason,
        "metrics": {"status_code": status_code, "latency_ms": latency_ms},
        "details": {"contains_match": bool(contains and contains in body)}
    }

@register_health_check("dns")
def health_check_dns(config, db, timeout_seconds):
    hostname = (config.get("hostname") or "").strip()
    if not hostname:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Hostname fehlt",
            "metrics": {},
            "details": {}
        }
    try:
        start_time = time.time()
        records = socket.getaddrinfo(hostname, None)
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "OK",
            "severity": "OK",
            "reason": f"DNS ok ({len(records)} Records)",
            "metrics": {"records": len(records), "latency_ms": latency_ms},
            "details": {}
        }
    except Exception as exc:
        return {
            "status": "CRIT",
            "severity": "CRIT",
            "reason": f"DNS Fehler: {exc}",
            "metrics": {},
            "details": {}
        }

@register_health_check("internet")
def health_check_internet(config, db, timeout_seconds):
    url = (config.get("url") or "https://example.com").strip()
    return health_check_http({"url": url, "method": "HEAD", "expect_status": 200}, db, timeout_seconds)

@register_health_check("cpu_load")
def health_check_cpu_load(config, db, timeout_seconds):
    load1, load5, load15 = os.getloadavg()
    per_core = bool(config.get("per_core", True))
    cpu_count = os.cpu_count() or 1
    multiplier = cpu_count if per_core else 1
    warn = float(config.get("warn_load") or 1.0 * multiplier)
    crit = float(config.get("crit_load") or 2.0 * multiplier)
    status = "OK"
    if load1 >= crit:
        status = "CRIT"
    elif load1 >= warn:
        status = "WARN"
    return {
        "status": status,
        "severity": status,
        "reason": f"Load {load1:.2f} (1m)",
        "metrics": {"load1": load1, "load5": load5, "load15": load15, "cpu_count": cpu_count},
        "details": {}
    }

@register_health_check("memory")
def health_check_memory(config, db, timeout_seconds):
    meminfo = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split(":")
                if len(parts) < 2:
                    continue
                key = parts[0].strip()
                value = parts[1].strip().split()[0]
                meminfo[key] = int(value)
    except FileNotFoundError:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "/proc/meminfo nicht verfügbar",
            "metrics": {},
            "details": {}
        }
    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    used_percent = 0 if total == 0 else (1 - available / total) * 100
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)
    swap_used_percent = 0 if swap_total == 0 else (1 - swap_free / swap_total) * 100
    warn = float(config.get("warn_percent") or 80)
    crit = float(config.get("crit_percent") or 90)
    status = "OK"
    if used_percent >= crit:
        status = "CRIT"
    elif used_percent >= warn:
        status = "WARN"
    return {
        "status": status,
        "severity": status,
        "reason": f"RAM {used_percent:.1f}% genutzt",
        "metrics": {
            "mem_total_kb": total,
            "mem_available_kb": available,
            "mem_used_percent": round(used_percent, 1),
            "swap_used_percent": round(swap_used_percent, 1)
        },
        "details": {}
    }

@register_health_check("disk")
def health_check_disk(config, db, timeout_seconds):
    path = (config.get("path") or "/").strip()
    warn = float(config.get("warn_percent") or 80)
    crit = float(config.get("crit_percent") or 90)
    warn_inodes = float(config.get("warn_inodes_percent") or 80)
    crit_inodes = float(config.get("crit_inodes_percent") or 90)
    try:
        usage = shutil.disk_usage(path)
        stat = os.statvfs(path)
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": f"Disk Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    used_percent = 0 if usage.total == 0 else (usage.used / usage.total) * 100
    inode_total = stat.f_files
    inode_free = stat.f_ffree
    inode_used_percent = 0 if inode_total == 0 else (1 - inode_free / inode_total) * 100
    status = "OK"
    if used_percent >= crit or inode_used_percent >= crit_inodes:
        status = "CRIT"
    elif used_percent >= warn or inode_used_percent >= warn_inodes:
        status = "WARN"
    read_only = bool(stat.f_flag & getattr(os, "ST_RDONLY", 1))
    if read_only:
        status = "CRIT"
    return {
        "status": status,
        "severity": status,
        "reason": f"Disk {used_percent:.1f}% genutzt",
        "metrics": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "used_percent": round(used_percent, 1),
            "inode_used_percent": round(inode_used_percent, 1)
        },
        "details": {"read_only": read_only}
    }

@register_health_check("time_sync")
def health_check_time_sync(config, db, timeout_seconds):
    max_drift_ms = float(config.get("max_offset_ms") or 100)
    if shutil.which("timedatectl"):
        try:
            output = subprocess.check_output(
                ["timedatectl", "show", "-p", "NTPSynchronized", "-p", "NTPSync", "--value"],
                text=True,
                timeout=timeout_seconds
            )
            values = [value.strip() for value in output.splitlines() if value.strip()]
            is_synced = any(value == "yes" for value in values)
            status = "OK" if is_synced else "WARN"
            return {
                "status": status,
                "severity": status,
                "reason": "NTP synchronisiert" if is_synced else "NTP nicht synchronisiert",
                "metrics": {},
                "details": {}
            }
        except Exception:
            pass
    if shutil.which("chronyc"):
        try:
            output = subprocess.check_output(
                ["chronyc", "tracking"],
                text=True,
                timeout=timeout_seconds
            )
            offset_line = next((line for line in output.splitlines() if "Last offset" in line), "")
            parts = offset_line.split()
            offset_seconds = float(parts[2]) if len(parts) >= 3 else 0
            drift_ms = abs(offset_seconds * 1000)
            status = "OK" if drift_ms <= max_drift_ms else "WARN"
            return {
                "status": status,
                "severity": status,
                "reason": f"NTP Drift {drift_ms:.1f} ms",
                "metrics": {"drift_ms": drift_ms},
                "details": {}
            }
        except Exception:
            pass
    return {
        "status": "UNKNOWN",
        "severity": "UNKNOWN",
        "reason": "Keine NTP-Quelle gefunden",
        "metrics": {},
        "details": {}
    }

@register_health_check("db_ping")
def health_check_db_ping(config, db, timeout_seconds):
    db_path = (config.get("db_path") or DATABASE).strip()
    warn_ms = float(config.get("warn_ms") or 100)
    crit_ms = float(config.get("crit_ms") or 250)
    start_time = time.time()
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
    except Exception as exc:
        return {
            "status": "CRIT",
            "severity": "CRIT",
            "reason": f"DB Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    latency_ms = int((time.time() - start_time) * 1000)
    status = "OK"
    if latency_ms >= crit_ms:
        status = "CRIT"
    elif latency_ms >= warn_ms:
        status = "WARN"
    return {
        "status": status,
        "severity": status,
        "reason": f"DB Ping {latency_ms} ms",
        "metrics": {"latency_ms": latency_ms},
        "details": {}
    }

@register_health_check("queue_depth")
def health_check_queue_depth(config, db, timeout_seconds):
    table = safe_sql_identifier(config.get("queue_table"))
    status_column = safe_sql_identifier(config.get("status_column") or "status")
    pending_values = config.get("pending_values") or []
    heartbeat_table = safe_sql_identifier(config.get("heartbeat_table"))
    heartbeat_column = safe_sql_identifier(config.get("heartbeat_column") or "updated_at")
    max_age_seconds = int(config.get("max_heartbeat_age_seconds") or 300)
    if not table or not status_column:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Queue-Konfiguration fehlt",
            "metrics": {},
            "details": {}
        }
    placeholders = ",".join(["?"] * len(pending_values)) if pending_values else None
    if pending_values:
        count_row = db.execute(
            f"SELECT COUNT(*) as total FROM {table} WHERE {status_column} IN ({placeholders})",
            pending_values
        ).fetchone()
    else:
        count_row = db.execute(
            f"SELECT COUNT(*) as total FROM {table}"
        ).fetchone()
    depth = count_row["total"] if count_row else 0
    status = "OK"
    warn_threshold = int(config.get("warn_depth") or 50)
    crit_threshold = int(config.get("crit_depth") or 100)
    if depth >= crit_threshold:
        status = "CRIT"
    elif depth >= warn_threshold:
        status = "WARN"
    heartbeat_age = None
    if heartbeat_table and heartbeat_column:
        heartbeat_row = db.execute(
            f"SELECT {heartbeat_column} as heartbeat FROM {heartbeat_table} ORDER BY {heartbeat_column} DESC LIMIT 1"
        ).fetchone()
        if heartbeat_row and heartbeat_row["heartbeat"]:
            try:
                last_heartbeat = datetime.strptime(heartbeat_row["heartbeat"], "%Y-%m-%d %H:%M:%S")
                heartbeat_age = (datetime.utcnow() - last_heartbeat).total_seconds()
            except ValueError:
                heartbeat_age = None
    if heartbeat_age is not None and heartbeat_age > max_age_seconds:
        status = "CRIT"
    return {
        "status": status,
        "severity": status,
        "reason": f"Queue Depth {depth}",
        "metrics": {"depth": depth, "heartbeat_age_seconds": heartbeat_age},
        "details": {}
    }

@register_health_check("cache_ping")
def health_check_cache_ping(config, db, timeout_seconds):
    host = (config.get("host") or "127.0.0.1").strip()
    port = int(config.get("port") or 0)
    cache_type = (config.get("type") or "redis").lower()
    if not port:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Cache-Port fehlt",
            "metrics": {},
            "details": {}
        }
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
            sock.settimeout(timeout_seconds)
            if cache_type == "redis":
                sock.sendall(b"PING\r\n")
                response = sock.recv(64)
                if b"PONG" not in response:
                    raise RuntimeError("PING fehlgeschlagen")
            elif cache_type == "memcached":
                sock.sendall(b"version\r\n")
                response = sock.recv(64)
                if b"VERSION" not in response:
                    raise RuntimeError("Version fehlgeschlagen")
    except Exception as exc:
        return {
            "status": "CRIT",
            "severity": "CRIT",
            "reason": f"Cache Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    return {
        "status": "OK",
        "severity": "OK",
        "reason": "Cache erreichbar",
        "metrics": {},
        "details": {}
    }

@register_health_check("log_pattern")
def health_check_log_pattern(config, db, timeout_seconds):
    path = (config.get("path") or "").strip()
    pattern = config.get("pattern")
    if not path or not pattern:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": "Log-Pattern nicht konfiguriert",
            "metrics": {},
            "details": {}
        }
    max_bytes = int(config.get("max_bytes") or 8192)
    must_match = bool(config.get("must_match"))
    try:
        file_size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if file_size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            data = handle.read().decode(errors="ignore")
        matches = re.findall(pattern, data, re.MULTILINE)
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "reason": f"Log-Check Fehler: {exc}",
            "metrics": {},
            "details": {}
        }
    has_match = len(matches) > 0
    status = "OK"
    if must_match and not has_match:
        status = "WARN"
    if not must_match and has_match:
        status = "WARN"
    return {
        "status": status,
        "severity": status,
        "reason": f"{len(matches)} Treffer",
        "metrics": {"matches": len(matches), "must_match": must_match},
        "details": {}
    }

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

def get_login_attempt(db, username):
    return db.execute('SELECT * FROM login_attempts WHERE username = ?', (username,)).fetchone()

def is_user_locked(db, username):
    attempt = get_login_attempt(db, username)
    if not attempt or not attempt["locked_until"]:
        return False
    try:
        locked_until = datetime.fromisoformat(attempt["locked_until"])
    except ValueError:
        return False
    return locked_until > datetime.utcnow()

def record_login_failure(db, username, max_failed, lockout_minutes):
    attempt = get_login_attempt(db, username)
    failed_count = attempt["failed_count"] if attempt else 0
    failed_count += 1
    locked_until = None
    if failed_count >= max_failed:
        locked_until = (datetime.utcnow() + timedelta(minutes=lockout_minutes)).isoformat()
        failed_count = 0
    if attempt:
        db.execute(
            'UPDATE login_attempts SET failed_count = ?, locked_until = ? WHERE username = ?',
            (failed_count, locked_until, username)
        )
    else:
        db.execute(
            'INSERT INTO login_attempts (username, failed_count, locked_until) VALUES (?, ?, ?)',
            (username, failed_count, locked_until)
        )

def clear_login_failures(db, username):
    db.execute('DELETE FROM login_attempts WHERE username = ?', (username,))

def request_comes_from_trusted_proxy():
    if not TRUSTED_PROXY_NETWORKS:
        return False
    remote_address = request.remote_addr or ""
    try:
        remote_ip = ipaddress.ip_address(remote_address)
    except ValueError:
        return False
    for entry in TRUSTED_PROXY_NETWORKS:
        try:
            if remote_ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            app.logger.error("Ungültiges Netzwerk in INVENTORY_TRUSTED_PROXY_NETWORKS konfiguriert.")
    return False

def trusted_forwarded_header(name):
    if not request_comes_from_trusted_proxy():
        return ""
    return (request.headers.get(name) or "").split(",")[0].strip()

def get_client_ip():
    forwarded_for = trusted_forwarded_header("X-Forwarded-For")
    return forwarded_for or request.remote_addr or ""

def request_origin():
    origin = (request.headers.get("Origin") or "").strip().rstrip("/")
    if origin:
        return origin
    referer = (request.headers.get("Referer") or "").strip()
    if not referer:
        return ""
    parsed = urllib.parse.urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

def expected_request_origins():
    forwarded_proto = trusted_forwarded_header("X-Forwarded-Proto")
    forwarded_host = trusted_forwarded_header("X-Forwarded-Host")
    scheme = forwarded_proto or request.scheme
    host = forwarded_host or request.host
    origins = {f"{scheme}://{host}".rstrip("/"), request.host_url.rstrip("/")}
    if PUBLIC_ORIGIN:
        origins.add(PUBLIC_ORIGIN)
    origins.update(ALLOWED_CORS_ORIGINS)
    return origins

@app.before_request
def enforce_same_origin_writes():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    fetch_site = (request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    if fetch_site == "cross-site":
        return jsonify({"error": "Cross-Site-Anfrage abgewiesen."}), 403
    origin = request_origin()
    if origin == "null" and fetch_site == "same-origin":
        origin = ""
    if origin and origin not in expected_request_origins():
        return jsonify({"error": "Anfrageursprung ist nicht zulässig."}), 403
    return None

@app.before_request
def enforce_csrf_protection():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if not app.config["INVENTORY_CSRF_ENABLED"] or app.testing:
        return None
    if not validate_csrf_token(request, session):
        return jsonify({"error": "CSRF-Token fehlt oder ist ungültig."}), 403
    return None

@app.route('/api/csrf-token', methods=['GET'])
def csrf_token_api():
    return jsonify({"csrfToken": get_csrf_token(session), "headerName": CSRF_HEADER_NAME})

@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    frame_ancestors = "'self'" if request.endpoint == "inventory_link_proxy" else "'none'"
    response.headers.setdefault(
        "X-Frame-Options",
        "SAMEORIGIN" if request.endpoint == "inventory_link_proxy" else "DENY",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "base-uri 'self'; "
        f"frame-ancestors {frame_ancestors}; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'",
    )
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    forwarded_proto = trusted_forwarded_header("X-Forwarded-Proto")
    if request.is_secure or forwarded_proto == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    if request.endpoint != "static":
        response.set_cookie(
            "csrf_token",
            get_csrf_token(session),
            secure=app.config["SESSION_COOKIE_SECURE"],
            httponly=False,
            samesite="Lax",
        )
    return response

@app.before_request
def enforce_security_policies():
    if request.endpoint == 'static':
        return None
    db = get_db()
    settings_row = get_server_settings(db)
    settings, _ = serialize_server_settings(settings_row)

    if settings["security"]["forceHttps"]:
        forwarded_proto = trusted_forwarded_header("X-Forwarded-Proto")
        if not request.is_secure and forwarded_proto != "https":
            if request.path.startswith("/api"):
                return jsonify({"error": "HTTPS erforderlich."}), 403
            return redirect(request.url.replace("http://", "https://", 1), code=302)

    ip_whitelist = settings["security"]["ipWhitelist"]
    if ip_whitelist:
        remote_ip = get_client_ip()
        allowed = False
        for entry in ip_whitelist:
            try:
                if "/" in entry:
                    if ipaddress.ip_address(remote_ip) in ipaddress.ip_network(entry, strict=False):
                        allowed = True
                        break
                else:
                    if remote_ip == entry:
                        allowed = True
                        break
            except ValueError:
                continue
        if not allowed:
            if request.path.startswith("/api"):
                return jsonify({"error": "IP nicht erlaubt."}), 403
            return ("", 403)

    if session.get("logged_in"):
        now_ts = time.time()
        last_activity = session.get("last_activity")
        timeout_minutes = settings["security"]["sessionTimeoutMinutes"]
        if last_activity and now_ts - last_activity > timeout_minutes * 60:
            session.clear()
            if request.path.startswith("/api"):
                return jsonify({"error": "Session abgelaufen."}), 401
            return redirect(url_for("login"))
        session["last_activity"] = now_ts
        session.permanent = True
        if settings["security"]["requireMfa"]:
            allowed_paths = {"/verify", "/api/otp/verify", "/api/otp/status", "/api/otp/setup", "/logout"}
            if not session.get("mfa_verified") and request.path not in allowed_paths and not request.path.startswith("/static"):
                if request.path.startswith("/api"):
                    return jsonify({"error": "MFA erforderlich."}), 403
                return redirect(url_for("verify"))
    return None

def log_activity(db, action, entity_type, entity_id=None, details=None):
    username = session.get('username', 'system')
    db.execute('''
        INSERT INTO activity_log (username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, action, entity_type, entity_id, json.dumps(details or {})))

def parse_time_machine_timestamp(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None

def format_time_machine_change(entity_label, action_label, details):
    suffix = ""
    if details:
        for key in ("title", "name", "id"):
            value = details.get(key)
            if value:
                suffix = f" · {value}"
                break
    return f"{entity_label} {action_label}{suffix}"

DEPENDENCY_ENTITY_TYPES = {
    "asset": {"table": "assets", "label": "Asset-Eintrag", "name_col": "name"},
    "device": {"table": "devices", "label": "Gerät", "name_col": "name"},
    "software": {"table": "software", "label": "Software", "name_col": "name"},
    "service": {"table": "services", "label": "Service", "name_col": "name"},
    "team": {"table": "teams", "label": "Team", "name_col": "name"},
    "department": {"table": "departments", "label": "Abteilung", "name_col": "name"},
    "location": {"table": "locations", "label": "Standort", "name_col": "name"},
    "user": {"table": "users", "label": "Benutzer", "name_col": "username"},
    "ticket": {"table": "tickets", "label": "Ticket", "name_col": "title"},
    "roadmap": {"table": "roadmaps", "label": "Roadmap", "name_col": "title"},
    "roadmap_step": {"table": "roadmap_steps", "label": "Roadmap-Schritt", "name_col": "title"}
}

def fetch_entity_label(db, entity_type, entity_id):
    meta = DEPENDENCY_ENTITY_TYPES.get(entity_type)
    if not meta:
        return None
    row = db.execute(
        f"SELECT {meta['name_col']} AS name FROM {meta['table']} WHERE id = ?",
        (entity_id,)
    ).fetchone()
    return row["name"] if row else None

def prune_dependency_links(db):
    rows = db.execute('''
        SELECT *
        FROM dependency_links
        ORDER BY created_at DESC
    ''').fetchall()
    valid_rows = []
    stale_ids = []
    for row in rows:
        if fetch_entity_label(db, row["source_type"], row["source_id"]) and fetch_entity_label(db, row["target_type"], row["target_id"]):
            valid_rows.append(row)
        else:
            stale_ids.append(row["id"])
    if stale_ids:
        placeholders = ",".join("?" for _ in stale_ids)
        db.execute(f'DELETE FROM dependency_links WHERE id IN ({placeholders})', stale_ids)
        db.commit()
    return valid_rows

def fetch_entity_options(db):
    options = {}
    for entity_type, meta in DEPENDENCY_ENTITY_TYPES.items():
        rows = db.execute(
            f"SELECT id, {meta['name_col']} AS name FROM {meta['table']} ORDER BY {meta['name_col']}"
        ).fetchall()
        options[entity_type] = [dict(row) for row in rows]
    return options

def build_dependency_edges(db):
    edges = []
    link_rows = prune_dependency_links(db)
    for row in link_rows:
        edges.append({
            "id": row["id"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "relation": row["relation"],
            "criticality": row["criticality"],
            "redundancy_group": row["redundancy_group"],
            "notes": row["notes"],
            "implicit": False
        })

    asset_device_rows = db.execute('''
        SELECT ad.asset_id, ad.device_id
        FROM asset_devices ad
        JOIN assets a ON a.id = ad.asset_id
        JOIN devices d ON d.id = ad.device_id
    ''').fetchall()
    for row in asset_device_rows:
        edges.append({
            "source_type": "asset",
            "source_id": row["asset_id"],
            "target_type": "device",
            "target_id": row["device_id"],
            "relation": "uses_device",
            "criticality": "medium",
            "redundancy_group": None,
            "notes": None,
            "implicit": True
        })

    asset_service_rows = db.execute('''
        SELECT ads.asset_id, ads.service_id
        FROM asset_services ads
        JOIN assets a ON a.id = ads.asset_id
        JOIN services s ON s.id = ads.service_id
    ''').fetchall()
    for row in asset_service_rows:
        edges.append({
            "source_type": "asset",
            "source_id": row["asset_id"],
            "target_type": "service",
            "target_id": row["service_id"],
            "relation": "consumes_service",
            "criticality": "medium",
            "redundancy_group": None,
            "notes": None,
            "implicit": True
        })

    assignment_rows = db.execute('''
        SELECT aa.asset_id, aa.user_identifier, aa.location_id
        FROM asset_assignments aa
        JOIN assets a ON a.id = aa.asset_id
        WHERE aa.released_at IS NULL OR aa.released_at = ''
    ''').fetchall()
    for row in assignment_rows:
        if row["location_id"]:
            location_row = db.execute('SELECT id FROM locations WHERE id = ?', (row["location_id"],)).fetchone()
            if location_row:
                edges.append({
                    "source_type": "asset",
                    "source_id": row["asset_id"],
                    "target_type": "location",
                    "target_id": row["location_id"],
                    "relation": "located_at",
                    "criticality": "low",
                    "redundancy_group": None,
                    "notes": None,
                    "implicit": True
                })
        if row["user_identifier"]:
            user_row = db.execute('SELECT id FROM users WHERE username = ?', (row["user_identifier"],)).fetchone()
            if user_row:
                edges.append({
                    "source_type": "asset",
                    "source_id": row["asset_id"],
                    "target_type": "user",
                    "target_id": user_row["id"],
                    "relation": "assigned_to",
                    "criticality": "low",
                    "redundancy_group": None,
                    "notes": None,
                    "implicit": True
                })

    installation_rows = db.execute('''
        SELECT si.software_id, si.device_id, si.asset_id
        FROM software_installations si
        JOIN software s ON s.id = si.software_id
    ''').fetchall()
    for row in installation_rows:
        if row["device_id"]:
            device_row = db.execute('SELECT id FROM devices WHERE id = ?', (row["device_id"],)).fetchone()
            if not device_row:
                continue
            edges.append({
                "source_type": "device",
                "source_id": row["device_id"],
                "target_type": "software",
                "target_id": row["software_id"],
                "relation": "runs_software",
                "criticality": "medium",
                "redundancy_group": None,
                "notes": None,
                "implicit": True
            })
        if row["asset_id"]:
            asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (row["asset_id"],)).fetchone()
            if not asset_row:
                continue
            edges.append({
                "source_type": "asset",
                "source_id": row["asset_id"],
                "target_type": "software",
                "target_id": row["software_id"],
                "relation": "runs_software",
                "criticality": "medium",
                "redundancy_group": None,
                "notes": None,
                "implicit": True
            })

    software_rows = db.execute('SELECT id, owner_team_id FROM software WHERE owner_team_id IS NOT NULL').fetchall()
    for row in software_rows:
        edges.append({
            "source_type": "software",
            "source_id": row["id"],
            "target_type": "team",
            "target_id": row["owner_team_id"],
            "relation": "maintained_by",
            "criticality": "medium",
            "redundancy_group": None,
            "notes": None,
            "implicit": True
        })

    team_rows = db.execute('SELECT id, department_id FROM teams WHERE department_id IS NOT NULL').fetchall()
    for row in team_rows:
        edges.append({
            "source_type": "team",
            "source_id": row["id"],
            "target_type": "department",
            "target_id": row["department_id"],
            "relation": "part_of",
            "criticality": "low",
            "redundancy_group": None,
            "notes": None,
            "implicit": True
        })

    ticket_asset_rows = db.execute('SELECT ticket_id, asset_id FROM ticket_assets').fetchall()
    for row in ticket_asset_rows:
        ticket_row = db.execute('SELECT id FROM tickets WHERE id = ?', (row["ticket_id"],)).fetchone()
        asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (row["asset_id"],)).fetchone()
        if ticket_row and asset_row:
            edges.append({
                "source_type": "ticket",
                "source_id": row["ticket_id"],
                "target_type": "asset",
                "target_id": row["asset_id"],
                "relation": "related_asset",
                "criticality": "medium",
                "redundancy_group": None,
                "notes": None,
                "implicit": True
            })

    roadmap_step_rows = db.execute('SELECT id, roadmap_id FROM roadmap_steps WHERE roadmap_id IS NOT NULL').fetchall()
    for row in roadmap_step_rows:
        roadmap_row = db.execute('SELECT id FROM roadmaps WHERE id = ?', (row["roadmap_id"],)).fetchone()
        if roadmap_row:
            edges.append({
                "source_type": "roadmap_step",
                "source_id": row["id"],
                "target_type": "roadmap",
                "target_id": row["roadmap_id"],
                "relation": "part_of",
                "criticality": "low",
                "redundancy_group": None,
                "notes": None,
                "implicit": True
            })

    return edges

def dependency_node_key(entity_type, entity_id):
    return f"{entity_type}:{entity_id}"

def build_dependency_nodes(db):
    nodes = []
    for entity_type, meta in DEPENDENCY_ENTITY_TYPES.items():
        rows = db.execute(
            f"SELECT id, {meta['name_col']} AS name FROM {meta['table']} ORDER BY {meta['name_col']}"
        ).fetchall()
        for row in rows:
            nodes.append({
                "key": dependency_node_key(entity_type, row["id"]),
                "id": row["id"],
                "type": entity_type,
                "label": row["name"]
            })
    return nodes

def build_dependency_graph_data(db):
    nodes = build_dependency_nodes(db)
    node_map = {node["key"]: node for node in nodes}
    edges = build_dependency_edges(db)
    for edge in edges:
        source_key = dependency_node_key(edge["source_type"], edge["source_id"])
        target_key = dependency_node_key(edge["target_type"], edge["target_id"])
        if source_key not in node_map:
            label = fetch_entity_label(db, edge["source_type"], edge["source_id"]) or f"{edge['source_type']} #{edge['source_id']}"
            node_map[source_key] = {
                "key": source_key,
                "id": edge["source_id"],
                "type": edge["source_type"],
                "label": label
            }
        if target_key not in node_map:
            label = fetch_entity_label(db, edge["target_type"], edge["target_id"]) or f"{edge['target_type']} #{edge['target_id']}"
            node_map[target_key] = {
                "key": target_key,
                "id": edge["target_id"],
                "type": edge["target_type"],
                "label": label
            }
    return list(node_map.values()), edges

def find_tickets_for_node(db, entity_type, entity_id):
    ticket_ids = set()
    if entity_type == "ticket":
        ticket_ids.add(entity_id)
    if entity_type == "asset":
        rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (entity_id,)).fetchall()
        ticket_ids.update(row["ticket_id"] for row in rows)
    if entity_type == "device":
        asset_rows = db.execute('SELECT asset_id FROM asset_devices WHERE device_id = ?', (entity_id,)).fetchall()
        for asset_row in asset_rows:
            rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (asset_row["asset_id"],)).fetchall()
            ticket_ids.update(row["ticket_id"] for row in rows)
    if entity_type == "software":
        install_rows = db.execute('''
            SELECT asset_id, device_id
            FROM software_installations
            WHERE software_id = ?
        ''', (entity_id,)).fetchall()
        for install in install_rows:
            if install["asset_id"]:
                rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (install["asset_id"],)).fetchall()
                ticket_ids.update(row["ticket_id"] for row in rows)
            if install["device_id"]:
                asset_rows = db.execute('SELECT asset_id FROM asset_devices WHERE device_id = ?', (install["device_id"],)).fetchall()
                for asset_row in asset_rows:
                    rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (asset_row["asset_id"],)).fetchall()
                    ticket_ids.update(row["ticket_id"] for row in rows)
    if entity_type == "service":
        asset_rows = db.execute('SELECT asset_id FROM asset_services WHERE service_id = ?', (entity_id,)).fetchall()
        for asset_row in asset_rows:
            rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (asset_row["asset_id"],)).fetchall()
            ticket_ids.update(row["ticket_id"] for row in rows)
    if entity_type == "location":
        asset_rows = db.execute('SELECT asset_id FROM asset_assignments WHERE location_id = ?', (entity_id,)).fetchall()
        for asset_row in asset_rows:
            rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (asset_row["asset_id"],)).fetchall()
            ticket_ids.update(row["ticket_id"] for row in rows)
    if entity_type == "user":
        user_row = db.execute('SELECT username FROM users WHERE id = ?', (entity_id,)).fetchone()
        if user_row:
            asset_rows = db.execute('SELECT asset_id FROM asset_assignments WHERE user_identifier = ?', (user_row["username"],)).fetchall()
            for asset_row in asset_rows:
                rows = db.execute('SELECT ticket_id FROM ticket_assets WHERE asset_id = ?', (asset_row["asset_id"],)).fetchall()
                ticket_ids.update(row["ticket_id"] for row in rows)
    if not ticket_ids:
        return []
    placeholders = ",".join("?" for _ in ticket_ids)
    rows = db.execute(f'''
        SELECT id, title, status, priority, escalation_level, due_date
        FROM tickets
        WHERE id IN ({placeholders})
        ORDER BY created_at DESC
    ''', tuple(ticket_ids)).fetchall()
    return [dict(row) for row in rows]

def analyze_dependency_impact(db, source_type, source_id, max_depth=None):
    nodes, edges = build_dependency_graph_data(db)
    node_map = {node["key"]: node for node in nodes}
    reverse_adj = {}
    for edge in edges:
        source_key = dependency_node_key(edge["source_type"], edge["source_id"])
        target_key = dependency_node_key(edge["target_type"], edge["target_id"])
        reverse_adj.setdefault(target_key, []).append({
            "key": source_key,
            "relation": edge["relation"],
            "criticality": edge["criticality"]
        })

    start_key = dependency_node_key(source_type, source_id)
    visited = {start_key}
    impact = []
    queue = [(start_key, 0)]
    while queue:
        current_key, depth = queue.pop(0)
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbor in reverse_adj.get(current_key, []):
            neighbor_key = neighbor["key"]
            if neighbor_key in visited:
                continue
            visited.add(neighbor_key)
            node = node_map.get(neighbor_key, {
                "key": neighbor_key,
                "type": neighbor_key.split(":")[0],
                "id": int(neighbor_key.split(":")[1]),
                "label": neighbor_key
            })
            impact.append({
                "key": neighbor_key,
                "type": node["type"],
                "id": node["id"],
                "label": node["label"],
                "depth": depth + 1,
                "relation": neighbor["relation"],
                "criticality": neighbor["criticality"]
            })
            queue.append((neighbor_key, depth + 1))

    impacted_ticket_ids = set()
    for item in impact:
        ticket_rows = find_tickets_for_node(db, item["type"], item["id"])
        impacted_ticket_ids.update(ticket["id"] for ticket in ticket_rows)
    direct_ticket_rows = find_tickets_for_node(db, source_type, source_id)
    impacted_ticket_ids.update(ticket["id"] for ticket in direct_ticket_rows)

    tickets = []
    if impacted_ticket_ids:
        placeholders = ",".join("?" for _ in impacted_ticket_ids)
        ticket_rows = db.execute(f'''
            SELECT id, title, status, priority, escalation_level, due_date
            FROM tickets
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC
        ''', tuple(impacted_ticket_ids)).fetchall()
        tickets = [dict(row) for row in ticket_rows]

    critical_tickets = [
        ticket for ticket in tickets
        if (ticket.get("priority") or "").lower() in {"high", "urgent", "critical"}
        or (ticket.get("escalation_level") or 0) > 0
    ]
    return impact, tickets, critical_tickets

def calculate_spof_nodes(db):
    rows = db.execute('''
        SELECT source_type, source_id, target_type, target_id, redundancy_group
        FROM dependency_links
    ''').fetchall()
    dependents = {}
    redundancy_targets = set()
    for row in rows:
        target_key = dependency_node_key(row["target_type"], row["target_id"])
        source_key = dependency_node_key(row["source_type"], row["source_id"])
        dependents.setdefault(target_key, set()).add(source_key)
        if row["redundancy_group"]:
            redundancy_targets.add(target_key)
    spof = []
    for target_key, sources in dependents.items():
        if target_key in redundancy_targets:
            continue
        entity_type, entity_id = target_key.split(":")
        label = fetch_entity_label(db, entity_type, int(entity_id)) or target_key
        spof.append({
            "key": target_key,
            "type": entity_type,
            "id": int(entity_id),
            "label": label,
            "dependent_count": len(sources)
        })
    spof.sort(key=lambda item: item["dependent_count"], reverse=True)
    return spof

def pro_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        settings_row = get_server_settings(get_db())
        if not settings_row or not settings_row["pro_enabled"]:
            return jsonify({"error": "Pro-Feature ist deaktiviert."}), 403
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

def normalize_email(value):
    if not value:
        return ""
    return value.strip().lower()

def is_valid_email(value):
    if not value:
        return False
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value))

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

def send_notification_email(settings, recipients, subject, body, html_body=None):
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
    if html_body:
        message.add_alternative(html_body, subtype="html")

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

def send_notification_email_async(settings, recipients, subject, body, html_body=None):
    if not settings or not settings["enabled"]:
        return False
    settings_payload = dict(settings)

    def dispatch():
        success = send_notification_email(
            settings_payload,
            recipients,
            subject,
            body,
            html_body=html_body,
        )
        if not success:
            app.logger.warning("Benachrichtigungs-E-Mail konnte nicht asynchron gesendet werden.")

    threading.Thread(target=dispatch, daemon=True).start()
    return True

def truncate_text(value, limit=240):
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"

def format_change_value(value, placeholder="Nicht gesetzt", limit=240):
    if value is None or value == "":
        return placeholder
    if isinstance(value, str):
        return truncate_text(value, limit=limit)
    return value

def build_ticket_changes(ticket, updates):
    changes = []
    field_map = [
        ("status", "Status"),
        ("priority", "Priorität"),
        ("category_name", "Kategorie"),
        ("assignee", "Zuständig"),
        ("assignee_email", "Zuständig (E-Mail)"),
        ("due_date", "Fällig"),
        ("requester_name", "Anfragender"),
        ("requester_email", "Anfragender (E-Mail)"),
        ("title", "Titel"),
        ("description", "Beschreibung"),
    ]
    for key, label in field_map:
        before = ticket.get(key)
        after = updates.get(key)
        if key == "category_name":
            before = before or "Keine Kategorie"
            after = after or "Keine Kategorie"
        if before != after:
            limit = 400 if key == "description" else 240
            changes.append({
                "key": key,
                "label": label,
                "before": format_change_value(before, limit=limit),
                "after": format_change_value(after, limit=limit),
            })
    return changes

def resolve_ticket_event_type(changes):
    keys = {change["key"] for change in changes}
    if len(changes) == 1:
        if "status" in keys:
            return "status_changed"
        if "priority" in keys:
            return "priority_changed"
        if "assignee" in keys or "assignee_email" in keys:
            return "assignee_changed"
    return "updated"

def determine_ticket_reason(event_type, changes):
    if event_type == "created":
        return "Ticket erstellt"
    if event_type == "commented":
        return "Neuer Kommentar"
    if event_type == "status_changed":
        return "Status geändert"
    if event_type == "priority_changed":
        return "Priorität geändert"
    if event_type == "assignee_changed":
        return "Zuweisung geändert"
    if changes:
        if any(change["key"] == "status" for change in changes):
            return "Status geändert"
        if any(change["key"] == "priority" for change in changes):
            return "Priorität geändert"
        if any(change["key"] in {"assignee", "assignee_email"} for change in changes):
            return "Zuweisung geändert"
    return "Aktualisiert"

def build_ticket_url(ticket_id):
    try:
        base_url = url_for("tickets_page", _external=True)
    except RuntimeError:
        base_url = "/tickets"
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}ticket_id={ticket_id}"

def render_ticket_email(event_type, ticket, changes=None, actor=None, comment=None):
    changes = changes or []
    actor = actor or "System"
    reason = determine_ticket_reason(event_type, changes)
    subject = f"[InventoryPro] Ticket #{ticket['id']} – {reason}"
    ticket_url = build_ticket_url(ticket["id"])
    change_lines = [
        f"- {change['label']}: {change['before']} → {change['after']}"
        for change in changes
    ]
    if not change_lines:
        if event_type == "created":
            change_lines = ["- Ticket wurde erstellt."]
        else:
            change_lines = ["- Ticket wurde aktualisiert."]
    timestamp = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    text_lines = [
        f"Ticket #{ticket['id']} – {ticket['title']}",
        f"Link: {ticket_url}",
        "",
        f"Aktueller Status: {ticket.get('status') or 'Unbekannt'}",
        f"Priorität: {ticket.get('priority') or 'Unbekannt'}",
        f"Kategorie: {ticket.get('category_name') or 'Keine Kategorie'}",
        f"Zuständig: {ticket.get('assignee') or 'Nicht zugewiesen'}",
        f"Fällig: {ticket.get('due_date') or '-'}",
        f"Von: {ticket.get('created_by') or 'Unbekannt'}",
        f"Geändert von: {actor}",
        f"Zeitpunkt: {timestamp}",
        "",
        "Was hat sich geändert?",
        *change_lines,
    ]
    if comment:
        text_lines.extend([
            "",
            "Kommentar:",
            truncate_text(comment, limit=800)
        ])
    text_lines.extend([
        "",
        "Beschreibung:",
        ticket.get('description') or "-"
    ])
    text_body = "\n".join(text_lines)

    escaped_title = html.escape(ticket.get("title") or "")
    escaped_reason = html.escape(reason)
    escaped_actor = html.escape(actor)
    escaped_status = html.escape(ticket.get("status") or "Unbekannt")
    escaped_priority = html.escape(ticket.get("priority") or "Unbekannt")
    escaped_category = html.escape(ticket.get("category_name") or "Keine Kategorie")
    escaped_assignee = html.escape(ticket.get("assignee") or "Nicht zugewiesen")
    escaped_due = html.escape(ticket.get("due_date") or "-")
    escaped_creator = html.escape(ticket.get("created_by") or "Unbekannt")
    change_rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;'>{html.escape(change['label'])}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#64748b;'>{html.escape(str(change['before']))}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:600;color:#0f172a;'>{html.escape(str(change['after']))}</td>"
        f"</tr>"
        for change in changes
    )
    if not change_rows:
        if event_type == "created":
            empty_message = "Ticket wurde erstellt."
        elif event_type == "commented":
            empty_message = "Neuer Kommentar hinzugefügt."
        else:
            empty_message = "Ticket wurde aktualisiert."
        change_rows = (
            "<tr><td colspan='3' style='padding:8px;color:#64748b;'>"
            f"{empty_message}"
            "</td></tr>"
        )
    comment_html = ""
    if comment:
        comment_html = (
            "<div style='margin-top:16px;padding:12px;border-radius:12px;"
            "background:#f8fafc;border:1px solid #e2e8f0;'>"
            f"<p style='margin:0 0 6px;font-weight:600;color:#0f172a;'>Kommentar</p>"
            f"<p style='margin:0;color:#334155;white-space:pre-wrap;'>{html.escape(truncate_text(comment, limit=800))}</p>"
            "</div>"
        )
    html_body = f"""
    <div style="font-family:Arial, sans-serif;background:#f1f5f9;padding:24px;">
      <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:16px;padding:24px;border:1px solid #e2e8f0;">
        <p style="margin:0;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:0.2em;">InventoryPro</p>
        <h1 style="margin:8px 0 4px;font-size:20px;color:#0f172a;">Ticket #{ticket['id']} – {escaped_reason}</h1>
        <p style="margin:0 0 16px;color:#64748b;font-size:14px;">{escaped_title}</p>
        <a href="{ticket_url}" style="display:inline-block;margin-bottom:16px;padding:10px 16px;background:#2563eb;color:white;text-decoration:none;border-radius:12px;font-size:14px;">Ticket öffnen</a>
        <div style="margin-bottom:16px;border:1px solid #e2e8f0;border-radius:12px;padding:12px;background:#f8fafc;">
          <p style="margin:0 0 8px;font-weight:600;color:#0f172a;">Aktueller Status</p>
          <p style="margin:0;color:#334155;">Status: <strong>{escaped_status}</strong></p>
          <p style="margin:4px 0;color:#334155;">Priorität: <strong>{escaped_priority}</strong></p>
          <p style="margin:4px 0;color:#334155;">Kategorie: {escaped_category}</p>
          <p style="margin:4px 0;color:#334155;">Zuständig: {escaped_assignee}</p>
          <p style="margin:4px 0;color:#334155;">Fällig: {escaped_due}</p>
          <p style="margin:4px 0;color:#334155;">Von: {escaped_creator}</p>
          <p style="margin:8px 0 0;color:#94a3b8;font-size:12px;">Geändert von {escaped_actor} • {timestamp}</p>
        </div>
        <h2 style="margin:16px 0 8px;font-size:16px;color:#0f172a;">Was hat sich geändert?</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead>
            <tr>
              <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;">Feld</th>
              <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;">Vorher</th>
              <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;">Nachher</th>
            </tr>
          </thead>
          <tbody>
            {change_rows}
          </tbody>
        </table>
        {comment_html}
        <div style="margin-top:16px;">
          <p style="margin:0 0 4px;font-weight:600;color:#0f172a;">Beschreibung</p>
          <p style="margin:0;color:#334155;white-space:pre-wrap;">{html.escape(ticket.get('description') or '-')}</p>
        </div>
      </div>
    </div>
    """
    return subject, text_body, html_body

def get_ticket_creator_email(db, ticket):
    creator_email = None
    if ticket.get("created_by_user_id"):
        row = db.execute(
            'SELECT email FROM users WHERE id = ?',
            (ticket["created_by_user_id"],)
        ).fetchone()
        creator_email = row["email"] if row and row["email"] else None
    if not creator_email and ticket.get("created_by"):
        row = db.execute(
            'SELECT email FROM users WHERE username = ?',
            (ticket["created_by"],)
        ).fetchone()
        creator_email = row["email"] if row and row["email"] else None
    return creator_email

def trigger_ticket_notifications(db, event_type, ticket, changes=None, actor=None, comment=None):
    settings = get_notification_settings(db)
    if not settings or not settings["enabled"]:
        return
    creator_email = get_ticket_creator_email(db, ticket)
    if not creator_email:
        app.logger.info("Ticket %s: Keine Ersteller-E-Mail hinterlegt, Mailversand übersprungen.", ticket["id"])
        return
    subject, text_body, html_body = render_ticket_email(
        event_type,
        ticket,
        changes=changes,
        actor=actor,
        comment=comment,
    )
    send_notification_email_async(settings, [creator_email], subject, text_body, html_body=html_body)

def fetch_ticket(db, ticket_id):
    ticket = db.execute('''
        SELECT t.*, c.name as category_name, c.color as category_color
        FROM tickets t
        LEFT JOIN ticket_categories c ON t.category_id = c.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()
    return dict(ticket) if ticket else None

def get_ticket_category(db, category_id):
    if not category_id:
        return None
    row = db.execute(
        'SELECT id, name, description, color, sla_hours, is_default FROM ticket_categories WHERE id = ?',
        (category_id,),
    ).fetchone()
    return dict(row) if row else None

def get_ticket_category_by_name(db, name):
    row = db.execute(
        'SELECT id, name, description, color, sla_hours, is_default '
        'FROM ticket_categories WHERE LOWER(name) = LOWER(?)',
        (name,),
    ).fetchone()
    return dict(row) if row else None

def is_ticket_category(ticket, category_name):
    return str((ticket or {}).get("category_name") or "").strip().lower() == category_name.lower()

def get_ticket_review_relation(db, ticket_id):
    row = db.execute(
        '''
        SELECT l.id, l.change_ticket_id, l.review_ticket_id, l.created_by, l.created_at,
               change_ticket.title AS change_title,
               change_ticket.status AS change_status,
               review_ticket.title AS review_title,
               review_ticket.status AS review_status
        FROM ticket_review_links l
        JOIN tickets change_ticket ON change_ticket.id = l.change_ticket_id
        JOIN tickets review_ticket ON review_ticket.id = l.review_ticket_id
        WHERE l.change_ticket_id = ? OR l.review_ticket_id = ?
        LIMIT 1
        ''',
        (ticket_id, ticket_id),
    ).fetchone()
    if not row:
        return None
    relation = dict(row)
    relation["role"] = "change" if relation["change_ticket_id"] == ticket_id else "review"
    relation["approved"] = is_closed_status(relation["review_status"])
    return relation

def create_review_for_change(db, change_ticket, actor="System"):
    existing = get_ticket_review_relation(db, change_ticket["id"])
    if existing:
        return existing["review_ticket_id"]

    review_category = get_ticket_category_by_name(db, "Review")
    if not review_category:
        raise ValueError("Review-Kategorie ist nicht konfiguriert")

    assignee = str(change_ticket.get("assignee") or "").strip() or "pond"
    due_date = str(change_ticket.get("due_date") or "").strip()
    priority = str(change_ticket.get("priority") or "normal").strip()
    change_title = str(change_ticket.get("title") or "").strip()
    review_title = f"Review zu Change #{change_ticket['id']}: {change_title}"
    review_description = (
        f"Kontroll- und Abnahmeauftrag für Change #{change_ticket['id']}. "
        "Prüfe Umsetzung, Akzeptanzkriterien und dokumentierte Testergebnisse. "
        "Der zugehörige Change darf erst nach erfolgreicher Abnahme geschlossen werden."
    )
    cursor = db.execute(
        '''
        INSERT INTO tickets (
            title, description, category_id, priority, status, requester_name,
            created_by, assignee, due_date, tags, custom_fields
        )
        VALUES (?, ?, ?, ?, 'open', 'System', 'System', ?, ?, ?, '[]')
        ''',
        (
            review_title,
            review_description,
            review_category["id"],
            priority,
            assignee,
            due_date,
            json.dumps(["review", "change-control", f"change-{change_ticket['id']}"]),
        ),
    )
    review_ticket_id = cursor.lastrowid
    db.execute(
        '''
        INSERT INTO ticket_review_links (change_ticket_id, review_ticket_id, created_by)
        VALUES (?, ?, ?)
        ''',
        (change_ticket["id"], review_ticket_id, actor or "System"),
    )
    db.execute(
        '''
        INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
        VALUES (?, 'System', ?, 0)
        ''',
        (
            review_ticket_id,
            f"Automatisch erzeugter Kontrollauftrag für Change #{change_ticket['id']}.",
        ),
    )
    db.execute(
        '''
        INSERT INTO activity_log (username, action, entity_type, entity_id, details)
        VALUES ('System', 'create', 'ticket', ?, ?)
        ''',
        (
            review_ticket_id,
            json.dumps({
                "title": review_title,
                "change_ticket_id": change_ticket["id"],
                "source": "change_review_gate",
            }),
        ),
    )
    return review_ticket_id

def link_review_to_change(db, change_ticket_id, review_ticket_id, actor):
    change_ticket = fetch_ticket(db, change_ticket_id)
    review_ticket = fetch_ticket(db, review_ticket_id)
    if not change_ticket or not is_ticket_category(change_ticket, "Change"):
        raise ValueError("Der ausgewählte Bezug ist kein Change-Ticket")
    if is_closed_status(change_ticket.get("status")):
        raise ValueError("Für einen abgeschlossenen Change kann kein neues Review erstellt werden")
    if not review_ticket or not is_ticket_category(review_ticket, "Review"):
        raise ValueError("Das zu verknüpfende Ticket ist kein Review")
    existing = get_ticket_review_relation(db, change_ticket_id)
    if existing:
        raise ValueError(f"Change #{change_ticket_id} ist bereits mit Review #{existing['review_ticket_id']} verknüpft")
    db.execute(
        '''
        INSERT INTO ticket_review_links (change_ticket_id, review_ticket_id, created_by)
        VALUES (?, ?, ?)
        ''',
        (change_ticket_id, review_ticket_id, actor or "System"),
    )

def backfill_ticket_review_links(db):
    review_rows = db.execute(
        '''
        SELECT t.id, t.title
        FROM tickets t
        JOIN ticket_categories c ON c.id = t.category_id
        WHERE LOWER(c.name) = 'review'
        ORDER BY t.id
        '''
    ).fetchall()
    for review in review_rows:
        match = re.match(r"^Review zu Change #(\d+):", review["title"] or "", re.IGNORECASE)
        if not match:
            continue
        change_ticket_id = int(match.group(1))
        change = fetch_ticket(db, change_ticket_id)
        if not change or not is_ticket_category(change, "Change"):
            continue
        db.execute(
            '''
            INSERT OR IGNORE INTO ticket_review_links (change_ticket_id, review_ticket_id, created_by)
            VALUES (?, ?, 'System')
            ''',
            (change_ticket_id, review["id"]),
        )

    open_changes = db.execute(
        '''
        SELECT t.*, c.name AS category_name, c.color AS category_color
        FROM tickets t
        JOIN ticket_categories c ON c.id = t.category_id
        LEFT JOIN ticket_review_links l ON l.change_ticket_id = t.id
        WHERE LOWER(c.name) = 'change'
          AND t.status NOT IN ('closed', 'resolved', 'done')
          AND l.id IS NULL
        ORDER BY t.id
        '''
    ).fetchall()
    for change in open_changes:
        create_review_for_change(db, dict(change), actor="System")

def validate_review_assignment(db, category, change_ticket_id, review_ticket_id=None):
    if not category or category["name"].strip().lower() != "review":
        return None
    parsed_change_id = normalize_optional_int(change_ticket_id)
    if parsed_change_id is None:
        raise ValueError("Für ein Review muss ein zugehöriger Change ausgewählt werden")
    change_ticket = fetch_ticket(db, parsed_change_id)
    if not change_ticket or not is_ticket_category(change_ticket, "Change"):
        raise ValueError("Der ausgewählte Bezug ist kein Change-Ticket")
    if is_closed_status(change_ticket.get("status")):
        raise ValueError("Der ausgewählte Change ist bereits abgeschlossen")
    relation = get_ticket_review_relation(db, parsed_change_id)
    if relation and relation["review_ticket_id"] != review_ticket_id:
        raise ValueError(
            f"Change #{parsed_change_id} ist bereits mit Review #{relation['review_ticket_id']} verknüpft"
        )
    return parsed_change_id

def ensure_change_can_close(db, ticket):
    if not is_ticket_category(ticket, "Change"):
        return None
    relation = get_ticket_review_relation(db, ticket["id"])
    if relation and relation["approved"]:
        return None
    review_ticket_id = relation["review_ticket_id"] if relation else None
    message = "Der Change kann erst nach einem gelösten oder geschlossenen Review abgeschlossen werden"
    return {
        "error": message,
        "code": "change_review_required",
        "change_ticket_id": ticket["id"],
        "review_ticket_id": review_ticket_id,
    }

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
    requester_name = str(ticket.get("requester_name") or "").strip()
    created_by = str(ticket.get("created_by") or "").strip()
    ticket["requester_name"] = requester_name or created_by
    ticket["created_by"] = created_by or requester_name
    ticket["requester_display_name"] = ticket["requester_name"] or "Unbekannt"
    ticket["creator_display_name"] = ticket["created_by"] or "Unbekannt"
    return ticket

def normalize_ticket_activity(row):
    activity = dict(row)
    try:
        details = json.loads(activity.get("details") or "{}")
    except (TypeError, json.JSONDecodeError):
        details = {}
    action_labels = {
        "create": "Ticket erstellt",
        "update": "Ticket aktualisiert",
        "bulk_update": "Mehrfachänderung",
        "comment": "Kommentar hinzugefügt",
        "watch": "Beobachter hinzugefügt",
        "unwatch": "Beobachter entfernt",
        "merge": "Ticket zusammengeführt",
    }
    activity["actor"] = activity.pop("username", None) or "System"
    activity["label"] = action_labels.get(
        activity.get("action"),
        str(activity.get("action") or "Aktivität").replace("_", " ").title(),
    )
    activity["details"] = details
    activity["changes"] = details.get("changes") if isinstance(details.get("changes"), list) else []
    return activity

def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None

def parse_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

def parse_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def normalize_optional_int(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None

def format_binpacking_value(value):
    if value is None or value == "":
        return "-"
    numeric = parse_float(value)
    if numeric is None:
        return str(value)
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}"

def format_binpacking_triplet(dimensions):
    if not dimensions:
        return "-"
    return " × ".join(
        format_binpacking_value(dimensions.get(axis))
        for axis in BINPACKING_DIMENSIONS
    )

def ensure_fk_exists(db, table, value, label):
    if value is None:
        return None
    row = db.execute(f"SELECT id FROM {table} WHERE id = ?", (value,)).fetchone()
    if not row:
        return f"{label} nicht gefunden"
    return None

ALLOWED_DYNAMIC_FIELD_TYPES = {"text", "number", "date", "select", "checkbox"}

def normalize_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "ja", "on"}:
            return True
        if lowered in {"0", "false", "no", "nein", "off"}:
            return False
    return False

def normalize_optional_iso_date(value):
    if value is None:
        return None, None
    if isinstance(value, str):
        raw = value.strip()
    else:
        raw = str(value).strip()
    if not raw:
        return None, None
    try:
        normalized = datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        return normalized, None
    except ValueError:
        return None, "Datum muss im Format JJJJ-MM-TT vorliegen"

def parse_optional_int_field(value, label, min_value=None):
    if value is None or value == "":
        return None, None
    parsed = normalize_optional_int(value)
    if parsed is None:
        return None, f"{label} muss eine ganze Zahl sein"
    if min_value is not None and parsed < min_value:
        return None, f"{label} muss mindestens {min_value} sein"
    return parsed, None

def parse_optional_float_field(value, label, min_value=None):
    if value is None or value == "":
        return None, None
    parsed = parse_float(value)
    if parsed is None:
        return None, f"{label} muss eine Zahl sein"
    if min_value is not None and parsed < min_value:
        return None, f"{label} muss mindestens {min_value} sein"
    return parsed, None

def normalize_field_definition(name, field_config):
    if not isinstance(name, str):
        return None
    field_name = name.strip()
    if not field_name:
        return None

    if isinstance(field_config, str):
        field_type = field_config.strip().lower() or "text"
        options = []
        unit = ""
    elif isinstance(field_config, dict):
        field_type = str(field_config.get("type") or "text").strip().lower()
        raw_options = field_config.get("options") or []
        options = [str(option).strip() for option in raw_options if str(option).strip()]
        unit = str(field_config.get("unit") or "").strip()
    else:
        field_type = "text"
        options = []
        unit = ""

    if field_type not in ALLOWED_DYNAMIC_FIELD_TYPES:
        field_type = "text"
    if field_type != "select":
        options = []
    if field_type in {"checkbox", "date", "select"}:
        unit = ""

    return field_name, {
        "type": field_type,
        "options": options,
        "unit": unit,
    }

def normalize_field_definitions(raw_fields):
    normalized = {}
    if isinstance(raw_fields, dict):
        iterator = raw_fields.items()
    elif isinstance(raw_fields, list):
        iterator = (
            ((field or {}).get("name"), field)
            for field in raw_fields
            if isinstance(field, dict)
        )
    else:
        return normalized

    for raw_name, raw_config in iterator:
        normalized_field = normalize_field_definition(raw_name, raw_config)
        if not normalized_field:
            continue
        field_name, field_config = normalized_field
        normalized[field_name] = field_config
    return normalized

def parse_field_definitions(raw_json):
    try:
        parsed = json.loads(raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = {}
    return normalize_field_definitions(parsed)

def validate_dynamic_specs(specs, field_definitions):
    normalized_specs = {}
    field_errors = {}
    if specs is None:
        return normalized_specs, field_errors
    if not isinstance(specs, dict):
        return normalized_specs, {"specs": "Spezifikationen müssen als Objekt übergeben werden"}

    for raw_key, raw_value in specs.items():
        field_name = str(raw_key or "").strip()
        if not field_name:
            continue

        config = field_definitions.get(field_name, {"type": "text", "options": [], "unit": ""})
        field_type = config.get("type") or "text"
        error_key = f"specs.{field_name}"

        if field_type == "checkbox":
            normalized_specs[field_name] = normalize_boolean(raw_value)
            continue

        if raw_value is None:
            continue

        value = raw_value.strip() if isinstance(raw_value, str) else raw_value
        if value == "":
            continue

        if field_type == "number":
            parsed = parse_float(str(value).replace(",", ".")) if isinstance(value, str) else parse_float(value)
            if parsed is None:
                field_errors[error_key] = "Bitte eine gültige Zahl eingeben"
                continue
            normalized_specs[field_name] = int(parsed) if float(parsed).is_integer() else parsed
            continue

        if field_type == "date":
            normalized_date, date_error = normalize_optional_iso_date(value)
            if date_error:
                field_errors[error_key] = date_error
                continue
            if normalized_date:
                normalized_specs[field_name] = normalized_date
            continue

        if field_type == "select":
            selected_value = str(value).strip()
            options = config.get("options") or []
            if options and selected_value not in options:
                field_errors[error_key] = "Bitte einen gültigen Wert aus der Liste wählen"
                continue
            normalized_specs[field_name] = selected_value
            continue

        normalized_specs[field_name] = str(value).strip()

    return normalized_specs, field_errors

def read_json_object(raw_value, default=None):
    fallback = {} if default is None else default
    if isinstance(raw_value, dict):
        return raw_value
    try:
        parsed = json.loads(raw_value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed if isinstance(parsed, dict) else fallback

def normalize_binpacking_dimension_mapping(raw_mapping):
    mapping = raw_mapping if isinstance(raw_mapping, dict) else {}
    return {
        axis: str(mapping.get(axis) or "").strip()
        for axis in BINPACKING_DIMENSIONS
    }

def parse_binpacking_config(raw_config):
    config = read_json_object(raw_config)
    relation_types = config.get("relation_types") or BINPACKING_DEFAULT_RELATION_TYPES
    normalized_relation_types = []
    for name in relation_types:
        label = str(name or "").strip()
        if label and label not in normalized_relation_types:
            normalized_relation_types.append(label)

    clearance = parse_float(config.get("clearance")) or 0
    return {
        "enabled": normalize_boolean(config.get("enabled")),
        "content_category_id": normalize_optional_int(config.get("content_category_id")),
        "allow_rotation": normalize_boolean(config.get("allow_rotation", True)),
        "clearance": max(clearance, 0),
        "container_fields": normalize_binpacking_dimension_mapping(config.get("container_fields")),
        "item_fields": normalize_binpacking_dimension_mapping(config.get("item_fields")),
        "relation_types": normalized_relation_types or list(BINPACKING_DEFAULT_RELATION_TYPES),
    }

def validate_binpacking_config(db, raw_config):
    config = parse_binpacking_config(raw_config)
    field_errors = {}

    if not config["enabled"]:
        return config, field_errors

    category_error = ensure_fk_exists(db, "asset_categories", config["content_category_id"], "Inhaltskategorie")
    if category_error:
        field_errors["binpacking_config.content_category_id"] = category_error or "Inhaltskategorie ist erforderlich"

    for axis, label in (("width", "Breite"), ("height", "Höhe"), ("depth", "Tiefe")):
        if not config["container_fields"].get(axis):
            field_errors[f"binpacking_config.container_fields.{axis}"] = f"Storage-{label} muss zugeordnet werden"
        if not config["item_fields"].get(axis):
            field_errors[f"binpacking_config.item_fields.{axis}"] = f"Inhalts-{label} muss zugeordnet werden"

    return config, field_errors

def parse_numeric_dimension(specs, field_name):
    if not field_name:
        return None
    specs_object = specs if isinstance(specs, dict) else {}
    raw_value = specs_object.get(field_name)
    if isinstance(raw_value, str):
        raw_value = raw_value.replace(",", ".").strip()
    return parse_float(raw_value)

def resolve_dimension_triplet(specs, mapping, clearance=0):
    values = {}
    missing_fields = []
    invalid_fields = []

    for axis in BINPACKING_DIMENSIONS:
        field_name = str((mapping or {}).get(axis) or "").strip()
        if not field_name:
            missing_fields.append({"axis": axis, "field": ""})
            continue

        parsed_value = parse_numeric_dimension(specs, field_name)
        if parsed_value is None:
            missing_fields.append({"axis": axis, "field": field_name})
            continue
        if parsed_value <= 0:
            invalid_fields.append({"axis": axis, "field": field_name, "value": parsed_value})
            continue
        values[axis] = parsed_value

    if clearance:
        for axis in BINPACKING_DIMENSIONS:
            if axis in values:
                values[axis] = max(values[axis] - (clearance * 2), 0)
                if values[axis] <= 0:
                    invalid_fields.append({"axis": axis, "field": (mapping or {}).get(axis) or "", "value": values[axis]})

    return values, missing_fields, invalid_fields

def enumerate_item_orientations(dimensions, allow_rotation):
    base = [
        dimensions.get("width"),
        dimensions.get("height"),
        dimensions.get("depth"),
    ]
    if any(value is None for value in base):
        return []
    if not allow_rotation:
        return [{
            "width": base[0],
            "height": base[1],
            "depth": base[2],
            "label": f"{base[0]} × {base[1]} × {base[2]}",
        }]

    variants = []
    seen = set()
    for width, height, depth in permutations(base):
        signature = (width, height, depth)
        if signature in seen:
            continue
        seen.add(signature)
        variants.append({
            "width": width,
            "height": height,
            "depth": depth,
            "label": f"{width} × {height} × {depth}",
        })
    return variants

def choose_binpacking_orientation(free_box, item, allow_rotation):
    best_choice = None
    best_score = None
    for orientation in enumerate_item_orientations(item["dimensions"], allow_rotation):
        if (
            orientation["width"] > free_box["width"]
            or orientation["height"] > free_box["height"]
            or orientation["depth"] > free_box["depth"]
        ):
            continue
        width_gap = free_box["width"] - orientation["width"]
        depth_gap = free_box["depth"] - orientation["depth"]
        height_gap = free_box["height"] - orientation["height"]
        leftover_volume = (
            free_box["width"] * free_box["height"] * free_box["depth"]
            - orientation["width"] * orientation["height"] * orientation["depth"]
        )
        face_mismatch = sum(
            1 for gap in (width_gap, depth_gap, height_gap)
            if gap > 0.001
        )
        footprint_gap = width_gap + depth_gap
        height_bias = free_box["z"] + orientation["height"]
        score = (
            leftover_volume,
            face_mismatch,
            max(width_gap, depth_gap, height_gap),
            height_gap,
            footprint_gap,
            abs(width_gap - depth_gap),
            height_bias,
            free_box["z"],
            free_box["y"],
            free_box["x"],
        )
        if best_score is None or score < best_score:
            best_score = score
            best_choice = orientation
    return best_choice

def get_binpacking_box_volume(box):
    return max(box.get("width", 0), 0) * max(box.get("height", 0), 0) * max(box.get("depth", 0), 0)

def binpacking_box_contains(outer_box, inner_box, epsilon=0.001):
    return (
        inner_box["x"] >= outer_box["x"] - epsilon
        and inner_box["y"] >= outer_box["y"] - epsilon
        and inner_box["z"] >= outer_box["z"] - epsilon
        and inner_box["x"] + inner_box["width"] <= outer_box["x"] + outer_box["width"] + epsilon
        and inner_box["y"] + inner_box["depth"] <= outer_box["y"] + outer_box["depth"] + epsilon
        and inner_box["z"] + inner_box["height"] <= outer_box["z"] + outer_box["height"] + epsilon
    )

def prune_binpacking_free_boxes(free_boxes):
    usable_boxes = [
        box for box in free_boxes
        if box["width"] > 0 and box["height"] > 0 and box["depth"] > 0
    ]
    pruned = []
    for index, box in enumerate(usable_boxes):
        is_contained = False
        for other_index, other_box in enumerate(usable_boxes):
            if index == other_index:
                continue
            if get_binpacking_box_volume(other_box) <= get_binpacking_box_volume(box):
                continue
            if binpacking_box_contains(other_box, box):
                is_contained = True
                break
        if not is_contained:
            pruned.append(box)
    return sorted(
        pruned,
        key=lambda box: (
            box["z"],
            box["y"],
            box["x"],
            get_binpacking_box_volume(box),
        ),
    )

def split_binpacking_box(free_box, orientation):
    boxes = []
    width_left = free_box["width"] - orientation["width"]
    depth_left = free_box["depth"] - orientation["depth"]
    height_left = free_box["height"] - orientation["height"]

    if width_left > 0:
        boxes.append({
            "x": free_box["x"] + orientation["width"],
            "y": free_box["y"],
            "z": free_box["z"],
            "width": width_left,
            "depth": free_box["depth"],
            "height": free_box["height"],
        })
    if depth_left > 0:
        boxes.append({
            "x": free_box["x"],
            "y": free_box["y"] + orientation["depth"],
            "z": free_box["z"],
            "width": orientation["width"],
            "depth": depth_left,
            "height": free_box["height"],
        })
    if height_left > 0:
        boxes.append({
            "x": free_box["x"],
            "y": free_box["y"],
            "z": free_box["z"] + orientation["height"],
            "width": orientation["width"],
            "depth": orientation["depth"],
            "height": height_left,
        })
    return boxes

def build_binpacking_layers(placements):
    grouped = {}
    for placement in placements:
        layer_key = placement["z"]
        grouped.setdefault(layer_key, []).append(placement)

    layers = []
    for layer_start in sorted(grouped.keys()):
        items = sorted(grouped[layer_start], key=lambda entry: (entry["y"], entry["x"], entry["asset_name"]))
        layer_height = max(item["height"] for item in items) if items else 0
        layers.append({
            "z": layer_start,
            "height": layer_height,
            "items": items,
        })
    return layers

def build_binpacking_item_sort_key(item, strategy_key):
    dimensions = item["dimensions"]
    volume = dimensions["width"] * dimensions["height"] * dimensions["depth"]
    footprint = dimensions["width"] * dimensions["depth"]
    longest_edge = max(dimensions["width"], dimensions["height"], dimensions["depth"])
    if strategy_key == "footprint_desc":
        return (-footprint, -volume, -dimensions["height"], item["name"].lower())
    if strategy_key == "height_desc":
        return (-dimensions["height"], -footprint, -volume, item["name"].lower())
    if strategy_key == "longest_edge_desc":
        return (-longest_edge, -footprint, -volume, item["name"].lower())
    return (-volume, -footprint, -dimensions["height"], item["name"].lower())

def evaluate_binpacking_candidate(placements, free_boxes):
    placed_volume = sum(
        placement["width"] * placement["height"] * placement["depth"]
        for placement in placements
    )
    used_height = max((placement["z"] + placement["height"] for placement in placements), default=0)
    used_width = max((placement["x"] + placement["width"] for placement in placements), default=0)
    used_depth = max((placement["y"] + placement["depth"] for placement in placements), default=0)
    layer_count = len({placement["z"] for placement in placements})
    largest_free_box_volume = max((
        box["width"] * box["height"] * box["depth"]
        for box in free_boxes
    ), default=0)
    return {
        "placed_volume": placed_volume,
        "used_height": used_height,
        "used_width": used_width,
        "used_depth": used_depth,
        "layer_count": layer_count,
        "fragmentation": len(free_boxes),
        "largest_free_box_volume": largest_free_box_volume,
    }

def pack_assets_into_storage_variant(container_dimensions, items, allow_rotation, strategy_key, strategy_label):
    free_boxes = [{
        "x": 0,
        "y": 0,
        "z": 0,
        "width": container_dimensions["width"],
        "depth": container_dimensions["depth"],
        "height": container_dimensions["height"],
    }]
    placements = []
    unplaced = []
    palette_size = len(BINPACKING_PREVIEW_COLORS)

    sorted_items = sorted(items, key=lambda entry: build_binpacking_item_sort_key(entry, strategy_key))

    for item_index, item in enumerate(sorted_items):
        selected_index = None
        selected_orientation = None
        selected_score = None

        for box_index, free_box in enumerate(free_boxes):
            orientation = choose_binpacking_orientation(free_box, item, allow_rotation)
            if not orientation:
                continue
            resulting_boxes = [
                box for box in split_binpacking_box(free_box, orientation)
                if box["width"] > 0 and box["height"] > 0 and box["depth"] > 0
            ]
            largest_result_box_volume = max((
                box["width"] * box["height"] * box["depth"]
                for box in resulting_boxes
            ), default=0)
            leftover_volume = get_binpacking_box_volume(free_box) - (
                orientation["width"] * orientation["height"] * orientation["depth"]
            )
            width_gap = free_box["width"] - orientation["width"]
            depth_gap = free_box["depth"] - orientation["depth"]
            height_gap = free_box["height"] - orientation["height"]
            footprint_gap = (free_box["width"] * free_box["depth"]) - (
                orientation["width"] * orientation["depth"]
            )
            height_after = free_box["z"] + orientation["height"]
            score = (
                leftover_volume,
                sum(1 for gap in (width_gap, depth_gap, height_gap) if gap > 0.001),
                height_after,
                footprint_gap,
                max(width_gap, depth_gap, height_gap),
                height_gap,
                len(resulting_boxes),
                -largest_result_box_volume,
                free_box["z"],
                free_box["y"],
                free_box["x"],
            )
            if selected_score is None or score < selected_score:
                selected_score = score
                selected_index = box_index
                selected_orientation = orientation

        if selected_index is None or not selected_orientation:
            unplaced.append(item)
            continue

        free_box = free_boxes.pop(selected_index)
        placement = {
            "asset_id": item["id"],
            "asset_name": item["name"],
            "x": free_box["x"],
            "y": free_box["y"],
            "z": free_box["z"],
            "width": selected_orientation["width"],
            "height": selected_orientation["height"],
            "depth": selected_orientation["depth"],
            "orientation_label": selected_orientation["label"],
            "original_dimensions": item["dimensions"],
            "color": BINPACKING_PREVIEW_COLORS[item_index % palette_size],
        }
        placements.append(placement)
        free_boxes.extend(split_binpacking_box(free_box, selected_orientation))
        free_boxes = prune_binpacking_free_boxes(free_boxes)

    metrics = evaluate_binpacking_candidate(placements, free_boxes)
    return placements, unplaced, {
        **metrics,
        "strategy_key": strategy_key,
        "strategy_label": strategy_label,
        "algorithm_label": "3D Best-Fit Decreasing",
    }

def pack_assets_into_storage(container_dimensions, items, allow_rotation):
    best_result = None
    best_score = None

    for strategy_key, strategy_label in BINPACKING_SORT_STRATEGIES:
        placements, unplaced, metadata = pack_assets_into_storage_variant(
            container_dimensions,
            items,
            allow_rotation,
            strategy_key,
            strategy_label,
        )
        score = (
            -len(placements),
            -metadata["placed_volume"],
            len(unplaced),
            metadata["layer_count"],
            metadata["used_height"],
            metadata["fragmentation"],
            -metadata["largest_free_box_volume"],
        )
        if best_score is None or score < best_score:
            best_score = score
            best_result = (placements, unplaced, metadata)

    if best_result is None:
        return [], [], {
            "placed_volume": 0,
            "used_height": 0,
            "used_width": 0,
            "used_depth": 0,
            "layer_count": 0,
            "fragmentation": 0,
            "largest_free_box_volume": 0,
            "strategy_key": BINPACKING_SORT_STRATEGIES[0][0],
            "strategy_label": BINPACKING_SORT_STRATEGIES[0][1],
            "algorithm_label": "3D Best-Fit Decreasing",
        }
    return best_result

def describe_binpacking_zone(placement, container_dimensions):
    def zone_label(center_value, total_value, low, mid, high):
        if total_value <= 0:
            return mid
        relative = center_value / total_value
        if relative < 0.34:
            return low
        if relative > 0.66:
            return high
        return mid

    x_center = placement["x"] + (placement["width"] / 2)
    y_center = placement["y"] + (placement["depth"] / 2)
    z_center = placement["z"] + (placement["height"] / 2)
    return " / ".join([
        zone_label(x_center, container_dimensions["width"], "links", "mittig", "rechts"),
        zone_label(y_center, container_dimensions["depth"], "vorne", "mittig", "hinten"),
        zone_label(z_center, container_dimensions["height"], "unten", "mittig", "oben"),
    ])

def enrich_binpacking_layers(container_dimensions, layers):
    container_base_area = (container_dimensions["width"] * container_dimensions["depth"]) or 0
    step_number = 1
    steps = []

    for layer_index, layer in enumerate(layers, start=1):
        layer_items = layer.get("items") or []
        layer_base_area = sum(item["width"] * item["depth"] for item in layer_items)
        layer_volume = sum(item["width"] * item["depth"] * item["height"] for item in layer_items)
        layer_container_volume = container_base_area * layer["height"] if layer["height"] else 0
        layer["index"] = layer_index
        layer["footprint_percent"] = round((layer_base_area / container_base_area) * 100, 1) if container_base_area else 0
        layer["occupancy_percent"] = round((layer_volume / layer_container_volume) * 100, 1) if layer_container_volume else 0

        for placement in layer_items:
            placement["step"] = step_number
            placement["layer_index"] = layer_index
            placement["zone_label"] = describe_binpacking_zone(placement, container_dimensions)
            steps.append({
                "step": step_number,
                "asset_id": placement["asset_id"],
                "asset_name": placement["asset_name"],
                "layer_index": layer_index,
                "zone_label": placement["zone_label"],
                "orientation_label": placement["orientation_label"],
                "dimensions_label": format_binpacking_triplet({
                    "width": placement["width"],
                    "height": placement["height"],
                    "depth": placement["depth"],
                }),
                "coordinate_label": f"X {format_binpacking_value(placement['x'])} · Y {format_binpacking_value(placement['y'])} · Z {format_binpacking_value(placement['z'])}",
            })
            step_number += 1
    return steps

def build_asset_binpacking_preview(db, asset):
    config = parse_binpacking_config(asset.get("category_binpacking_config"))
    if not config.get("enabled"):
        return None

    container_dimensions, container_missing, container_invalid = resolve_dimension_triplet(
        asset.get("specs") or {},
        config.get("container_fields"),
        config.get("clearance") or 0,
    )
    content_category_id = config.get("content_category_id")
    content_category = db.execute(
        "SELECT id, name FROM asset_categories WHERE id = ?",
        (content_category_id,),
    ).fetchone() if content_category_id else None

    if container_missing or container_invalid:
        return {
            "enabled": True,
            "content_category_id": content_category_id,
            "content_category_name": content_category["name"] if content_category else "",
            "container": container_dimensions,
            "status": "incomplete",
            "message": "Für die Vorschau fehlen gültige Storage-Maße im Asset.",
            "missing_container_fields": container_missing,
            "invalid_container_fields": container_invalid,
            "layers": [],
            "placements": [],
            "placed_count": 0,
            "total_count": 0,
            "unplaced_assets": [],
            "invalid_assets": [],
            "relation_types": config.get("relation_types") or list(BINPACKING_DEFAULT_RELATION_TYPES),
        }

    relation_type_names = [name.lower() for name in (config.get("relation_types") or BINPACKING_DEFAULT_RELATION_TYPES)]
    placeholders = ",".join("?" for _ in relation_type_names)
    relation_filter = f" AND LOWER(COALESCE(rt.name, '')) IN ({placeholders})" if relation_type_names else ""
    query = f'''
        SELECT DISTINCT candidate.id, candidate.name, candidate.specs
        FROM asset_relations ar
        LEFT JOIN asset_relation_types rt ON rt.id = ar.relation_type_id
        JOIN assets candidate
            ON (
                (ar.asset_id = ? AND candidate.id = ar.related_asset_id)
                OR (ar.related_asset_id = ? AND candidate.id = ar.asset_id)
            )
        WHERE candidate.category_id = ?
        {relation_filter}
        ORDER BY candidate.name COLLATE NOCASE, candidate.id
    '''
    params = [asset["id"], asset["id"], content_category_id]
    params.extend(relation_type_names)
    candidate_rows = db.execute(query, params).fetchall() if content_category_id else []

    items = []
    invalid_assets = []
    for row in candidate_rows:
        candidate = dict(row)
        candidate_specs = read_json_object(candidate.get("specs"))
        dimensions, missing_fields, invalid_fields = resolve_dimension_triplet(
            candidate_specs,
            config.get("item_fields"),
            0,
        )
        if missing_fields or invalid_fields:
            invalid_assets.append({
                "id": candidate["id"],
                "name": candidate["name"],
                "missing_fields": missing_fields,
                "invalid_fields": invalid_fields,
            })
            continue
        items.append({
            "id": candidate["id"],
            "name": candidate["name"],
            "dimensions": dimensions,
        })

    placements, unplaced_assets, packing_metadata = pack_assets_into_storage(
        container_dimensions,
        items,
        config.get("allow_rotation", True),
    )
    container_volume = (
        container_dimensions["width"]
        * container_dimensions["height"]
        * container_dimensions["depth"]
    )
    placed_volume = sum(
        placement["width"] * placement["height"] * placement["depth"]
        for placement in placements
    )
    layers = build_binpacking_layers(placements)
    steps = enrich_binpacking_layers(container_dimensions, layers)
    all_assets_placed = bool(items) and not unplaced_assets
    plan_status = "empty"
    plan_status_label = "Keine Inhalte"
    if items:
        plan_status = "complete" if all_assets_placed else "partial"
        plan_status_label = "Vollständig" if all_assets_placed else "Teilweise geplant"
    used_height_percent = round((packing_metadata["used_height"] / container_dimensions["height"]) * 100, 1) if container_dimensions["height"] else 0
    message = "Noch keine verknüpften Inhalte für diese Storage-Kategorie vorhanden."
    if items:
        if all_assets_placed:
            message = "Alle Inhalte passen in das Storage-Asset. Folge den Schritten von oben nach unten."
        else:
            message = (
                f"{len(placements)} von {len(items)} Inhalten wurden eingeplant. "
                "Die Restliste zeigt, was nicht in dieses Storage-Asset passt."
            )

    return {
        "enabled": True,
        "status": "ready",
        "content_category_id": content_category_id,
        "content_category_name": content_category["name"] if content_category else "",
        "allow_rotation": config.get("allow_rotation", True),
        "packing_strategy": packing_metadata["strategy_key"],
        "packing_strategy_label": packing_metadata["strategy_label"],
        "algorithm_label": packing_metadata.get("algorithm_label") or "3D Best-Fit Decreasing",
        "plan_status": plan_status,
        "plan_status_label": plan_status_label,
        "container": {
            **container_dimensions,
            "volume": container_volume,
        },
        "placements": placements,
        "layers": layers,
        "steps": steps,
        "placed_count": len(placements),
        "total_count": len(items),
        "unplaced_count": len(unplaced_assets),
        "invalid_count": len(invalid_assets),
        "layer_count": len(layers),
        "step_count": len(steps),
        "next_step": steps[0] if steps else None,
        "used_height": packing_metadata["used_height"],
        "used_height_percent": used_height_percent,
        "used_volume": placed_volume,
        "free_volume": max(container_volume - placed_volume, 0),
        "invalid_assets": invalid_assets,
        "unplaced_assets": [
            {
                "id": item["id"],
                "name": item["name"],
                "dimensions": item["dimensions"],
            }
            for item in unplaced_assets
        ],
        "efficiency_percent": round((placed_volume / container_volume) * 100, 1) if container_volume else 0,
        "relation_types": config.get("relation_types") or list(BINPACKING_DEFAULT_RELATION_TYPES),
        "message": message,
    }

def validation_error_response(message, field_errors=None, status=400):
    payload = {"error": message}
    if field_errors:
        payload["field_errors"] = field_errors
    return jsonify(payload), status

def validate_device_payload(db, payload):
    data = payload or {}
    field_errors = {}

    name = str(data.get("name") or "").strip()
    if not name:
        field_errors["name"] = "Name ist erforderlich"

    category_id, category_error = parse_optional_int_field(data.get("category_id"), "Kategorie", min_value=1)
    category_row = None
    if category_error:
        field_errors["category_id"] = category_error
    elif category_id is None:
        field_errors["category_id"] = "Kategorie ist erforderlich"
    else:
        category_row = db.execute(
            "SELECT id, fields FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if not category_row:
            field_errors["category_id"] = "Kategorie ist ungültig"

    location_id, location_error = parse_optional_int_field(data.get("location_id"), "Standort", min_value=1)
    if location_error:
        field_errors["location_id"] = location_error
    elif location_id is not None:
        location_row = db.execute("SELECT id FROM locations WHERE id = ?", (location_id,)).fetchone()
        if not location_row:
            field_errors["location_id"] = "Standort ist ungültig"

    field_definitions = parse_field_definitions(category_row["fields"]) if category_row else {}
    specs, spec_errors = validate_dynamic_specs(data.get("specs") or {}, field_definitions)
    field_errors.update(spec_errors)

    return {
        "name": name,
        "category_id": category_id,
        "serial_number": str(data.get("serial_number") or "").strip(),
        "location_id": location_id,
        "specs": specs,
    }, field_errors

def is_closed_status(status):
    return (status or "").strip().lower() in {"closed", "resolved", "done"}

def should_auto_create_roadmap(category_name):
    if not category_name:
        return False
    lowered = category_name.strip().lower()
    keywords = ("verbesser", "improvement", "enhancement", "feature", "upgrade", "optim")
    return any(keyword in lowered for keyword in keywords)

def create_roadmap_for_ticket(db, ticket, category_name=None, created_by=None):
    if not ticket:
        return None
    existing = db.execute('SELECT id FROM roadmaps WHERE ticket_id = ?', (ticket["id"],)).fetchone()
    if existing:
        return existing["id"]
    title = f"Roadmap: {ticket['title']}"
    objective = f"Umsetzungsplan für Ticket #{ticket['id']}: {ticket['title']}"
    owner = ticket.get("assignee") or ticket.get("created_by")
    start_date = datetime.utcnow().strftime("%Y-%m-%d")
    target_date = ticket.get("due_date") or None
    roadmap_cursor = db.execute('''
        INSERT INTO roadmaps (ticket_id, title, objective, status, owner, start_date, target_date, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ticket["id"],
        title,
        objective,
        "planned",
        owner,
        start_date,
        target_date,
        created_by or session.get('username')
    ))
    roadmap_id = roadmap_cursor.lastrowid
    default_steps = [
        ("Analyse & Scope", "Ziele, Anforderungen und Erfolgskriterien definieren.", "planned"),
        ("Konzept & Design", "Architektur, UI/UX und technische Umsetzung planen.", "planned"),
        ("Implementierung", "Features entwickeln und integrieren.", "planned"),
        ("Qualitätssicherung", "Tests, Review und Abnahme durchführen.", "planned"),
        ("Rollout & Monitoring", "Deployment, Dokumentation und Monitoring vorbereiten.", "planned")
    ]
    for position, (step_title, description, status) in enumerate(default_steps, start=1):
        db.execute('''
            INSERT INTO roadmap_steps (roadmap_id, title, description, status, position)
            VALUES (?, ?, ?, ?, ?)
        ''', (roadmap_id, step_title, description, status, position))
    log_activity(db, "create", "roadmap", roadmap_id, {
        "ticket_id": ticket["id"],
        "title": title,
        "category": category_name
    })
    return roadmap_id

def fetch_roadmap(db, roadmap_id):
    row = db.execute('''
        SELECT r.*, t.title as ticket_title, t.status as ticket_status, t.created_by as ticket_owner
        FROM roadmaps r
        LEFT JOIN tickets t ON r.ticket_id = t.id
        WHERE r.id = ?
    ''', (roadmap_id,)).fetchone()
    return dict(row) if row else None

def fetch_roadmap_for_ticket(db, ticket_id):
    row = db.execute('SELECT * FROM roadmaps WHERE ticket_id = ?', (ticket_id,)).fetchone()
    return dict(row) if row else None

def fetch_roadmap_steps(db, roadmap_id):
    rows = db.execute('''
        SELECT *
        FROM roadmap_steps
        WHERE roadmap_id = ?
        ORDER BY position ASC, created_at ASC
    ''', (roadmap_id,)).fetchall()
    return [dict(row) for row in rows]

def warranty_status(warranty_end):
    parsed = parse_date(warranty_end)
    if not parsed:
        return "Unbekannt"
    today = datetime.utcnow().date()
    return "Aktiv" if parsed >= today else "Abgelaufen"

def extract_manufacturer(specs):
    for key in ("Hersteller", "Manufacturer", "Vendor", "Marke"):
        value = specs.get(key)
        if value:
            return value
    return None

def summarize_device_info(device_rows):
    serials = []
    locations = []
    for row in device_rows:
        serial_number = row.get("serial_number") if isinstance(row, dict) else row["serial_number"]
        location_name = row.get("location_name") if isinstance(row, dict) else row["location_name"]
        if serial_number and serial_number not in serials:
            serials.append(serial_number)
        if location_name and location_name not in locations:
            locations.append(location_name)
    return serials, locations

def mark_devices_as_used(db, device_ids):
    unique_ids = [device_id for device_id in dict.fromkeys(device_ids) if device_id]
    if not unique_ids:
        return
    placeholders = ",".join(["?"] * len(unique_ids))
    rows = db.execute(
        f"SELECT id, specs FROM devices WHERE id IN ({placeholders})",
        unique_ids,
    ).fetchall()
    for row in rows:
        try:
            specs = json.loads(row["specs"] or "{}")
        except json.JSONDecodeError:
            specs = {}
        specs["Status"] = "Verwendet"
        db.execute(
            "UPDATE devices SET specs = ? WHERE id = ?",
            (json.dumps(specs), row["id"]),
        )

def mark_devices_as_in_stock(db, device_ids):
    unique_ids = [device_id for device_id in dict.fromkeys(device_ids) if device_id]
    if not unique_ids:
        return
    placeholders = ",".join(["?"] * len(unique_ids))
    rows = db.execute(
        f"SELECT id, specs FROM devices WHERE id IN ({placeholders})",
        unique_ids,
    ).fetchall()
    for row in rows:
        try:
            specs = json.loads(row["specs"] or "{}")
        except json.JSONDecodeError:
            specs = {}
        specs["Status"] = "Lager"
        db.execute(
            "UPDATE devices SET specs = ? WHERE id = ?",
            (json.dumps(specs), row["id"]),
        )

def mark_devices_as_in_stock_if_unassigned(db, device_ids):
    unique_ids = [device_id for device_id in dict.fromkeys(device_ids) if device_id]
    if not unique_ids:
        return
    placeholders = ",".join(["?"] * len(unique_ids))
    assigned_rows = db.execute(
        f'''
            SELECT DISTINCT device_id
            FROM asset_devices
            WHERE device_id IN ({placeholders})
        ''',
        unique_ids,
    ).fetchall()
    assigned_ids = {row["device_id"] for row in assigned_rows}
    to_update = [device_id for device_id in unique_ids if device_id not in assigned_ids]
    if not to_update:
        return
    placeholders = ",".join(["?"] * len(to_update))
    rows = db.execute(
        f"SELECT id, specs FROM devices WHERE id IN ({placeholders})",
        to_update,
    ).fetchall()
    for row in rows:
        try:
            specs = json.loads(row["specs"] or "{}")
        except json.JSONDecodeError:
            specs = {}
        specs["Status"] = "Lager"
        db.execute(
            "UPDATE devices SET specs = ? WHERE id = ?",
            (json.dumps(specs), row["id"]),
        )

def find_device_assignment_conflicts(db, device_ids, asset_id=None):
    unique_ids = [device_id for device_id in dict.fromkeys(device_ids) if device_id]
    if not unique_ids:
        return []
    placeholders = ",".join(["?"] * len(unique_ids))
    params = list(unique_ids)
    query = f'''
        SELECT device_id, asset_id
        FROM asset_devices
        WHERE device_id IN ({placeholders})
    '''
    if asset_id:
        query += ' AND asset_id != ?'
        params.append(asset_id)
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]

def find_missing_device_ids(db, device_ids):
    unique_ids = [device_id for device_id in dict.fromkeys(device_ids) if device_id]
    if not unique_ids:
        return []
    placeholders = ",".join(["?"] * len(unique_ids))
    rows = db.execute(
        f"SELECT id FROM devices WHERE id IN ({placeholders})",
        unique_ids,
    ).fetchall()
    existing_ids = {row["id"] for row in rows}
    return [device_id for device_id in unique_ids if device_id not in existing_ids]

def normalize_device_ids(device_ids):
    normalized_ids = []
    invalid_ids = []
    for device_id in device_ids or []:
        if device_id is None or device_id == "":
            continue
        if isinstance(device_id, (int, float)) and not isinstance(device_id, bool):
            normalized_ids.append(int(device_id))
            continue
        if isinstance(device_id, str):
            value = device_id.strip()
            if value.isdigit():
                normalized_ids.append(int(value))
                continue
        invalid_ids.append(device_id)
    return normalized_ids, invalid_ids

def get_asset_devices_info(db, asset_id):
    rows = db.execute('''
        SELECT d.serial_number, l.name as location_name
        FROM devices d
        JOIN asset_devices ad ON ad.device_id = d.id
        LEFT JOIN locations l ON d.location_id = l.id
        WHERE ad.asset_id = ?
    ''', (asset_id,)).fetchall()
    return [dict(row) for row in rows]

def get_assets_devices_info(db, asset_ids):
    normalized_ids = sorted({
        asset_id
        for asset_id in (normalize_optional_int(value) for value in asset_ids or [])
        if asset_id is not None
    })
    grouped = {asset_id: [] for asset_id in normalized_ids}
    if not normalized_ids:
        return grouped
    placeholders = ",".join("?" for _ in normalized_ids)
    rows = db.execute(
        f'''
        SELECT ad.asset_id, d.serial_number, l.name AS location_name
        FROM asset_devices ad
        JOIN devices d ON d.id = ad.device_id
        LEFT JOIN locations l ON l.id = d.location_id
        WHERE ad.asset_id IN ({placeholders})
        ORDER BY ad.asset_id, d.id
        ''',
        normalized_ids,
    ).fetchall()
    for row in rows:
        grouped.setdefault(row["asset_id"], []).append(dict(row))
    return grouped

def build_asset_summary(db, asset_row, device_rows=None):
    asset = dict(asset_row)
    try:
        asset_specs = json.loads(asset.get('specs') or '{}')
    except json.JSONDecodeError:
        asset_specs = {}
    asset['specs'] = asset_specs
    asset['binpacking_config'] = parse_binpacking_config(asset.get("category_binpacking_config"))
    device_rows = device_rows if device_rows is not None else get_asset_devices_info(db, asset["id"])
    serials, locations = summarize_device_info(device_rows)
    asset['serial_numbers'] = serials
    asset['locations'] = locations
    asset['manufacturer'] = extract_manufacturer(asset_specs)
    asset['warranty_status'] = warranty_status(asset.get("warranty_end"))
    return asset

def build_asset_summaries(db, asset_rows):
    rows = list(asset_rows)
    device_rows_by_asset = get_assets_devices_info(
        db,
        [row["id"] for row in rows],
    )
    return [
        build_asset_summary(db, row, device_rows=device_rows_by_asset.get(row["id"], []))
        for row in rows
    ]

def fetch_asset_assignment_history(db, asset_id, limit=20):
    query = '''
        SELECT ah.*, u.username as assigned_user, t.name as assigned_team, cu.username as created_by
        FROM asset_assignment_history ah
        LEFT JOIN users u ON u.id = ah.assigned_to_user_id
        LEFT JOIN teams t ON t.id = ah.assigned_to_team_id
        LEFT JOIN users cu ON cu.id = ah.created_by_user_id
        WHERE ah.asset_id = ?
        ORDER BY ah.created_at DESC, ah.id DESC
    '''
    params = [asset_id]
    if limit:
        query += ' LIMIT ?'
        params.append(limit)
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]

def fetch_current_asset_assignment(db, asset_id):
    row = db.execute('''
        SELECT ah.*, u.username as assigned_user, t.name as assigned_team
        FROM asset_assignment_history ah
        LEFT JOIN users u ON u.id = ah.assigned_to_user_id
        LEFT JOIN teams t ON t.id = ah.assigned_to_team_id
        WHERE ah.asset_id = ?
        ORDER BY ah.created_at DESC, ah.id DESC
        LIMIT 1
    ''', (asset_id,)).fetchone()
    return dict(row) if row else None

def normalize_attachment_filename(filename):
    safe_name = secure_filename(filename or "")
    return safe_name or "attachment"

def is_attachment_extension_allowed(filename):
    extension = Path(filename).suffix.lower()
    if extension in BLOCKED_ATTACHMENT_EXTENSIONS:
        return False
    return extension in ALLOWED_ATTACHMENT_EXTENSIONS

def build_attachment_storage_path(entity_type, entity_id):
    target_dir = UPLOADS_DIR / "attachments" / entity_type / str(entity_id)
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target_dir, stat.S_IRWXU)
    return target_dir

def validate_attachment_content(file_path, extension):
    signatures = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }
    with Path(file_path).open("rb") as handle:
        sample = handle.read(8192)
    required_signature = signatures.get(extension)
    if required_signature and not sample.startswith(required_signature):
        return "Dateiinhalt passt nicht zum erlaubten Dateityp."
    if extension in {".txt", ".csv"}:
        if b"\x00" in sample:
            return "Textdatei enthält unzulässige Binärdaten."
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return "Textdatei muss UTF-8-kodiert sein."
    return None

def attachment_mime_type(extension):
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".txt": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
    }.get(extension, "application/octet-stream")

def store_attachment_file(file_storage, entity_type, entity_id):
    if not file_storage:
        return None, "Keine Datei hochgeladen."
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return None, "Datei ist zu groß."
    original_filename = normalize_attachment_filename(file_storage.filename)
    if not is_attachment_extension_allowed(original_filename):
        return None, "Dateityp ist nicht erlaubt."
    extension = Path(original_filename).suffix.lower()
    stored_filename = f"{secrets.token_hex(16)}{extension}"
    target_dir = build_attachment_storage_path(entity_type, entity_id)
    file_path = target_dir / stored_filename
    file_storage.save(file_path)
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
    size_bytes = file_path.stat().st_size
    if size_bytes > MAX_UPLOAD_BYTES:
        file_path.unlink(missing_ok=True)
        return None, "Datei ist zu groß."
    antivirus_error = validate_import_file(file_path)
    if antivirus_error:
        file_path.unlink(missing_ok=True)
        return None, antivirus_error
    content_error = validate_attachment_content(file_path, extension)
    if content_error:
        file_path.unlink(missing_ok=True)
        return None, content_error
    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "mime_type": attachment_mime_type(extension),
        "size_bytes": size_bytes,
        "file_path": file_path,
    }, None

def serialize_attachment(row):
    entry = dict(row)
    entry["download_url"] = f"/attachments/{entry['id']}/download"
    return entry

def resolve_assignment_target(db, user_id, team_id):
    if user_id and team_id:
        return None, None, "Bitte nur Benutzer oder Team wählen."
    if not user_id and not team_id:
        return None, None, "Zielperson oder Team ist erforderlich."
    if user_id:
        user_row = db.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user_row:
            return None, None, "Benutzer nicht gefunden."
    if team_id:
        team_row = db.execute('SELECT id FROM teams WHERE id = ?', (team_id,)).fetchone()
        if not team_row:
            return None, None, "Team nicht gefunden."
    return user_id, team_id, None

def validate_assignment_transition(current_status, action):
    if action == "checkin" and current_status != "checked_out":
        return "Asset ist nicht ausgecheckt."
    if action in {"assign", "checkout", "unassign"} and current_status == "checked_out":
        return "Asset ist ausgecheckt. Bitte zuerst einchecken."
    if action == "checkout" and current_status == "checked_out":
        return "Asset ist bereits ausgecheckt."
    return None

def ensure_attachment_entity_access(db, entity_type, entity_id, access):
    if entity_type == "asset":
        asset = db.execute('SELECT id FROM assets WHERE id = ?', (entity_id,)).fetchone()
        if not asset:
            return None, ("Asset nicht gefunden", 404)
        if not (access["is_superuser"] or "assets.view" in access["permissions"] or "assets.manage" in access["permissions"]):
            return None, ("Keine Berechtigung", 403)
        return dict(asset), None
    if entity_type == "ticket":
        ticket_row = db.execute('SELECT * FROM tickets WHERE id = ?', (entity_id,)).fetchone()
        if not ticket_row:
            return None, ("Ticket nicht gefunden", 404)
        ticket = dict(ticket_row)
        if not ensure_ticket_access(ticket, access):
            return None, ("Keine Berechtigung", 403)
        return ticket, None
    if entity_type == "maintenance":
        task = db.execute('SELECT id, device_id FROM maintenance_tasks WHERE id = ?', (entity_id,)).fetchone()
        if not task:
            return None, ("Wartungsaufgabe nicht gefunden", 404)
        if not (access["is_superuser"] or "maintenance.view" in access["permissions"] or "maintenance.manage" in access["permissions"]):
            return None, ("Keine Berechtigung", 403)
        return dict(task), None
    return None, ("Ungültiger Typ", 400)

def fetch_ticket_assets(db, ticket_id):
    rows = db.execute('''
        SELECT a.*, ac.name AS category_name,
               ac.binpacking_config AS category_binpacking_config
        FROM assets a
        JOIN ticket_assets ta ON ta.asset_id = a.id
        LEFT JOIN asset_categories ac ON ac.id = a.category_id
        WHERE ta.ticket_id = ?
        ORDER BY a.name
    ''', (ticket_id,)).fetchall()
    return build_asset_summaries(db, rows)

def merge_ticket_records(db, target_ticket, source_tickets, actor=None, note=None):
    merged_ticket_ids = []
    merged_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    actor_name = actor or session.get('username') or "System"

    for source_ticket in source_tickets:
        if not source_ticket or source_ticket["id"] == target_ticket["id"]:
            continue

        merged_ticket_ids.append(source_ticket["id"])
        resolution_outcome = f"Mit Ticket #{target_ticket['id']} zusammengeführt"
        resolution_notes = note or ""
        merge_summary = [
            f"Zusammengeführt aus Ticket #{source_ticket['id']}: {source_ticket.get('title') or 'Ohne Titel'}",
        ]
        if source_ticket.get("description"):
            merge_summary.extend(["", source_ticket["description"]])
        if note:
            merge_summary.extend(["", f"Hinweis: {note}"])
        db.execute('''
            INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
            VALUES (?, ?, ?, 1)
        ''', (
            target_ticket["id"],
            actor_name,
            "\n".join(merge_summary).strip(),
        ))

        source_comments = db.execute('''
            SELECT author, body, is_internal, created_at
            FROM ticket_comments
            WHERE ticket_id = ?
            ORDER BY created_at ASC, id ASC
        ''', (source_ticket["id"],)).fetchall()
        for comment in source_comments:
            copied_body = (
                f"[Übernommen aus Ticket #{source_ticket['id']} von {comment['author'] or 'System'}"
                f" am {comment['created_at'] or 'unbekannt'}]\n{comment['body'] or ''}"
            ).strip()
            db.execute('''
                INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
                VALUES (?, ?, ?, ?)
            ''', (
                target_ticket["id"],
                actor_name,
                copied_body,
                comment["is_internal"] or 0,
            ))

        watcher_rows = db.execute(
            'SELECT email FROM ticket_watchers WHERE ticket_id = ?',
            (source_ticket["id"],),
        ).fetchall()
        for watcher in watcher_rows:
            db.execute('''
                INSERT OR IGNORE INTO ticket_watchers (ticket_id, email)
                VALUES (?, ?)
            ''', (target_ticket["id"], watcher["email"]))

        asset_rows = db.execute(
            'SELECT asset_id FROM ticket_assets WHERE ticket_id = ?',
            (source_ticket["id"],),
        ).fetchall()
        for asset_row in asset_rows:
            db.execute('''
                INSERT OR IGNORE INTO ticket_assets (ticket_id, asset_id)
                VALUES (?, ?)
            ''', (target_ticket["id"], asset_row["asset_id"]))

        db.execute('''
            UPDATE tickets
            SET status = ?, resolved_at = ?, resolution_action = ?, resolution_outcome = ?,
                resolution_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            "closed",
            merged_at,
            "merged",
            resolution_outcome,
            resolution_notes,
            source_ticket["id"],
        ))
        db.execute('''
            INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
            VALUES (?, ?, ?, 1)
        ''', (
            source_ticket["id"],
            actor_name,
            f"Dieses Ticket wurde mit Ticket #{target_ticket['id']} zusammengeführt.",
        ))
        log_activity(db, "merge", "ticket", source_ticket["id"], {
            "target_ticket_id": target_ticket["id"],
            "title": source_ticket.get("title"),
        })

    if merged_ticket_ids:
        db.execute(
            'UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (target_ticket["id"],),
        )
        log_activity(db, "merge", "ticket", target_ticket["id"], {
            "merged_ticket_ids": merged_ticket_ids,
            "title": target_ticket.get("title"),
        })

    return merged_ticket_ids

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

def get_server_settings(db):
    settings = db.execute('SELECT * FROM server_settings WHERE id = 1').fetchone()
    if not settings:
        db.execute('INSERT INTO server_settings (id) VALUES (1)')
        db.commit()
        settings = db.execute('SELECT * FROM server_settings WHERE id = 1').fetchone()
    return settings

def serialize_server_settings_flat(settings):
    if not settings:
        return {
            "host": DEFAULT_SERVER_SETTINGS["server"]["host"],
            "port": DEFAULT_SERVER_SETTINGS["server"]["port"],
            "debug": DEFAULT_SERVER_SETTINGS["server"]["debug"],
            "pro_enabled": DEFAULT_SERVER_SETTINGS["proFeaturesEnabled"],
            "backup_enabled": DEFAULT_SERVER_SETTINGS["backup"]["enabled"],
            "backup_schedule": DEFAULT_SERVER_SETTINGS["backup"]["schedule"],
            "backup_time": DEFAULT_SERVER_SETTINGS["backup"]["time"],
            "backup_retention_days": DEFAULT_SERVER_SETTINGS["backup"]["retentionDays"],
            "backup_location": DEFAULT_SERVER_SETTINGS["backup"]["directory"],
            "backup_compress": DEFAULT_SERVER_SETTINGS["backup"]["compress"],
            "backup_encrypt": DEFAULT_SERVER_SETTINGS["backup"]["encrypt"],
            "backup_notify_email": DEFAULT_SERVER_SETTINGS["backup"]["notifyEmail"],
            "allow_db_import": DEFAULT_SERVER_SETTINGS["importExport"]["importAllowed"],
            "allow_db_export": DEFAULT_SERVER_SETTINGS["importExport"]["exportAllowed"],
            "export_format": DEFAULT_SERVER_SETTINGS["importExport"]["exportFormat"],
            "import_mode": DEFAULT_SERVER_SETTINGS["importExport"]["importMode"],
            "include_uploads": DEFAULT_SERVER_SETTINGS["importExport"]["includeUploads"],
            "require_https": DEFAULT_SERVER_SETTINGS["security"]["forceHttps"],
            "session_timeout_minutes": DEFAULT_SERVER_SETTINGS["security"]["sessionTimeoutMinutes"],
            "max_failed_logins": DEFAULT_SERVER_SETTINGS["security"]["maxFailedAttempts"],
            "lockout_minutes": DEFAULT_SERVER_SETTINGS["security"]["lockoutMinutes"],
            "allowed_ip_ranges": "",
            "password_min_length": DEFAULT_SERVER_SETTINGS["security"]["minPasswordLength"],
            "enforce_mfa": DEFAULT_SERVER_SETTINGS["security"]["requireMfa"],
            "terminal_enabled": DEFAULT_SERVER_SETTINGS["terminal"]["enabled"],
            "terminal_require_reauth": DEFAULT_SERVER_SETTINGS["terminal"]["requireReauth"],
            "terminal_ip_allowlist": "",
            "terminal_allow_db_write": DEFAULT_SERVER_SETTINGS["terminal"]["allowDbWrite"],
            "terminal_allow_service_restart": DEFAULT_SERVER_SETTINGS["terminal"]["allowServiceRestart"],
            "terminal_break_glass": DEFAULT_SERVER_SETTINGS["terminal"]["breakGlassMode"]
        }
    return {
        "host": settings["host"] or DEFAULT_SERVER_SETTINGS["server"]["host"],
        "port": settings["port"] or DEFAULT_SERVER_SETTINGS["server"]["port"],
        "debug": bool(settings["debug_mode"]),
        "pro_enabled": bool(settings["pro_enabled"]),
        "backup_enabled": bool(settings["backup_enabled"]),
        "backup_schedule": settings["backup_schedule"] or DEFAULT_SERVER_SETTINGS["backup"]["schedule"],
        "backup_time": settings["backup_time"] or DEFAULT_SERVER_SETTINGS["backup"]["time"],
        "backup_retention_days": settings["backup_retention_days"] or DEFAULT_SERVER_SETTINGS["backup"]["retentionDays"],
        "backup_location": settings["backup_location"] or DEFAULT_SERVER_SETTINGS["backup"]["directory"],
        "backup_compress": bool(settings["backup_compress"]),
        "backup_encrypt": bool(settings["backup_encrypt"]),
        "backup_notify_email": settings["backup_notify_email"] or "",
        "allow_db_import": bool(settings["allow_db_import"]),
        "allow_db_export": bool(settings["allow_db_export"]),
        "export_format": settings["export_format"] or DEFAULT_SERVER_SETTINGS["importExport"]["exportFormat"],
        "import_mode": settings["import_mode"] or DEFAULT_SERVER_SETTINGS["importExport"]["importMode"],
        "include_uploads": bool(settings["include_uploads"]),
        "require_https": bool(settings["require_https"]),
        "session_timeout_minutes": settings["session_timeout_minutes"] or DEFAULT_SERVER_SETTINGS["security"]["sessionTimeoutMinutes"],
        "max_failed_logins": settings["max_failed_logins"] or DEFAULT_SERVER_SETTINGS["security"]["maxFailedAttempts"],
        "lockout_minutes": settings["lockout_minutes"] or DEFAULT_SERVER_SETTINGS["security"]["lockoutMinutes"],
        "allowed_ip_ranges": settings["allowed_ip_ranges"] or "",
        "password_min_length": settings["password_min_length"] or DEFAULT_SERVER_SETTINGS["security"]["minPasswordLength"],
        "enforce_mfa": bool(settings["enforce_mfa"]),
        "terminal_enabled": bool(settings["terminal_enabled"]),
        "terminal_require_reauth": bool(settings["terminal_require_reauth"]),
        "terminal_ip_allowlist": settings["terminal_ip_allowlist"] or "",
        "terminal_allow_db_write": bool(settings["terminal_allow_db_write"]),
        "terminal_allow_service_restart": bool(settings["terminal_allow_service_restart"]),
        "terminal_break_glass": bool(settings["terminal_break_glass"])
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
        settings, _ = serialize_server_settings(get_server_settings(db))
        security = settings["security"]
        if is_user_locked(db, username):
            log_activity(db, "login_locked", "user", details={"username": username})
            db.commit()
            return render_template('login.html', error="Account ist gesperrt. Bitte später erneut versuchen.")
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            if security["requireMfa"] and not user['otp_secret']:
                log_activity(db, "login_failed_mfa", "user", user['id'], {"username": username})
                db.commit()
                return render_template('login.html', error="MFA ist erforderlich. Bitte OTP zuerst aktivieren.")
            session['logged_in'] = True
            session['username'] = username
            session['mfa_verified'] = not security["requireMfa"]
            access = get_user_access(db)
            log_activity(db, "login", "user", user['id'], {"username": username})
            clear_login_failures(db, username)
            db.commit()
            if security["requireMfa"]:
                return redirect(url_for("verify"))
            return redirect(get_post_login_redirect(access))

        ad_settings = get_ad_settings(db)
        if authenticate_ad_user(username, password, ad_settings):
            existing_user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if not existing_user:
                placeholder_password = generate_password_hash(os.urandom(24).hex())
                cursor = db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, placeholder_password))
                assign_user_role(db, cursor.lastrowid, DEFAULT_ROLE_NAME)
                existing_user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if security["requireMfa"]:
                user = db.execute('SELECT otp_secret FROM users WHERE username = ?', (username,)).fetchone()
                if not user or not user['otp_secret']:
                    log_activity(db, "login_failed_mfa", "user", details={"username": username, "source": "ad"})
                    db.commit()
                    return render_template('login.html', error="MFA ist erforderlich. Bitte OTP zuerst aktivieren.")
            session['logged_in'] = True
            session['username'] = username
            session['mfa_verified'] = not security["requireMfa"]
            access = get_user_access(db)
            log_activity(db, "login", "user", existing_user['id'], {"username": username, "source": "ad"})
            clear_login_failures(db, username)
            db.commit()
            if security["requireMfa"]:
                return redirect(url_for("verify"))
            return redirect(get_post_login_redirect(access))

        record_login_failure(db, username, security["maxFailedAttempts"], security["lockoutMinutes"])
        log_activity(db, "login_failed", "user", details={"username": username})
        db.commit()
        return render_template('login.html', error="Ungültige Anmeldedaten")

    return render_template('login.html')

@app.route('/force-password-change', methods=['GET', 'POST'])
@login_required
def force_password_change():
    db = get_db()
    username = session.get('username')
    if not must_change_password(db, username):
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_password = request.form.get('new_password') or ''
        confirm_password = request.form.get('confirm_password') or ''
        if new_password != confirm_password:
            return render_template('force_password_change.html', error="Passwörter stimmen nicht überein.")
        min_length = get_password_min_length(db)
        if len(new_password) < min_length:
            return render_template(
                'force_password_change.html',
                error=f"Passwort muss mindestens {min_length} Zeichen lang sein."
            )
        password_hash = generate_password_hash(new_password)
        db.execute(
            'UPDATE users SET password_hash = ?, must_change_password = 0 WHERE username = ?',
            (password_hash, username)
        )
        log_activity(db, "password_change_forced", "user", details={"username": username})
        db.commit()
        return redirect(url_for('index'))

    return render_template('force_password_change.html')

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

@app.route('/settings')
@login_required
@require_permission('server_settings.manage')
def server_settings_page():
    access = get_user_access(get_db())
    initial_section = request.args.get("section") or "server"
    return render_template(
        'server_settings.html',
        username=session.get('username'),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        initial_section=initial_section
    )

@app.route('/settings/terminal')
@login_required
@require_permission('server_settings.manage')
def terminal_settings_page():
    access = get_user_access(get_db())
    if not (access["is_superuser"] or "terminal.view" in access["permissions"]):
        return ("", 403)
    return render_template(
        'server_settings.html',
        username=session.get('username'),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        initial_section="terminal"
    )

@app.route('/inventory-links/<link_id>/portal')
@login_required
def inventory_link_portal(link_id):
    access = get_user_access(get_db())
    db = get_db()
    user = access.get("user")
    if not user:
        return redirect(url_for('login'))
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return ("Link nicht gefunden.", 404)
    return render_template(
        'inventory_link_portal.html',
        username=session.get('username'),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        link=serialize_inventory_link(link),
        active_link_id=link_id
    )

@app.route('/knowledge')
@login_required
@require_permissions('knowledge.view', 'knowledge.manage')
def knowledge_page():
    access = get_user_access(get_db())
    return render_template('knowledge.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/roadmap')
@login_required
@require_permissions('roadmap.view', 'roadmap.manage')
def roadmap_page():
    access = get_user_access(get_db())
    return render_template('roadmap.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/procurement')
@login_required
@require_permissions('procurement.view', 'procurement.manage')
def procurement_page():
    access = get_user_access(get_db())
    return render_template('procurement.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/dependencies')
@login_required
@require_permissions('dependencies.view', 'dependencies.manage')
def dependencies_page():
    access = get_user_access(get_db())
    return render_template('dependencies.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/time-machine')
@login_required
@require_permission('timemachine.view')
def time_machine_page():
    access = get_user_access(get_db())
    return render_template('time_machine.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/health')
@login_required
@require_permissions('health.view', 'health.manage', 'health.run')
def health_page():
    access = get_user_access(get_db())
    return render_template('health.html', username=session.get('username'), permissions=sorted(access["permissions"]), is_superuser=access["is_superuser"])

@app.route('/api/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_category(category_id):
    db = get_db()
    if not user_can('categories.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'PUT':
        try:
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            if not name:
                return validation_error_response("Name ist erforderlich", {"name": "Name ist erforderlich"})
            icon = data.get('icon', 'default').strip()
            description = (data.get('description') or '').strip()
            fields = json.dumps(normalize_field_definitions(data.get('fields')))

            result = db.execute('''
                UPDATE categories 
                SET name = ?, icon = ?, description = ?, fields = ?
                WHERE id = ?
            ''', (name, icon, description, fields, category_id))

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
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return validation_error_response("Name ist erforderlich", {"name": "Name ist erforderlich"})
        fields = normalize_field_definitions(data.get('fields'))
        try:
            cursor = db.execute('''
                INSERT INTO categories (name, icon, description, fields)
                VALUES (?, ?, ?, ?)
            ''', (name, data.get('icon', 'cpu'), (data.get('description') or '').strip(), json.dumps(fields)))
            category_id = cursor.lastrowid
            log_activity(db, "create", "category", category_id, {"name": name})
            db.commit()
            return jsonify({"status": "success", "id": category_id}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Kategorie existiert bereits"}), 400
    
    if not (user_can('categories.view') or user_can('categories.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/asset-categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_asset_category(category_id):
    db = get_db()
    if not user_can('asset_categories.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'PUT':
        try:
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            if not name:
                return validation_error_response("Name ist erforderlich", {"name": "Name ist erforderlich"})
            icon = data.get('icon', 'package').strip()
            description = (data.get('description') or '').strip()
            fields = json.dumps(normalize_field_definitions(data.get('fields')))
            binpacking_config, config_errors = validate_binpacking_config(db, data.get("binpacking_config"))
            if config_errors:
                return validation_error_response("Bitte die Binpacking-Konfiguration prüfen", config_errors)

            result = db.execute('''
                UPDATE asset_categories
                SET name = ?, icon = ?, description = ?, fields = ?, binpacking_config = ?
                WHERE id = ?
            ''', (name, icon, description, fields, json.dumps(binpacking_config), category_id))

            if result.rowcount == 0:
                return jsonify({"error": "Asset-Kategorie nicht gefunden"}), 404

            log_activity(db, "update", "asset_category", category_id, {"name": name})
            db.commit()
            return jsonify({"status": "updated"}), 200

        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Ungültige Daten: {str(e)}"}), 400

    db.execute('UPDATE assets SET category_id = NULL WHERE category_id = ?', (category_id,))
    result = db.execute('DELETE FROM asset_categories WHERE id = ?', (category_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Asset-Kategorie nicht gefunden"}), 404

    log_activity(db, "delete", "asset_category", category_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/asset-categories', methods=['GET', 'POST'])
@login_required
def handle_asset_categories():
    db = get_db()
    if request.method == 'POST':
        if not user_can('asset_categories.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return validation_error_response("Name ist erforderlich", {"name": "Name ist erforderlich"})
        fields = normalize_field_definitions(data.get('fields'))
        binpacking_config, config_errors = validate_binpacking_config(db, data.get("binpacking_config"))
        if config_errors:
            return validation_error_response("Bitte die Binpacking-Konfiguration prüfen", config_errors)
        try:
            cursor = db.execute('''
                INSERT INTO asset_categories (name, icon, description, fields, binpacking_config)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                name,
                data.get('icon', 'package'),
                (data.get('description') or '').strip(),
                json.dumps(fields),
                json.dumps(binpacking_config),
            ))
            category_id = cursor.lastrowid
            log_activity(db, "create", "asset_category", category_id, {"name": name})
            db.commit()
            return jsonify({"status": "success", "id": category_id}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Asset-Kategorie existiert bereits"}), 400

    if not (user_can('asset_categories.view') or user_can('asset_categories.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    categories = db.execute('''
        SELECT ac.*, COUNT(a.id) as asset_count
        FROM asset_categories ac
        LEFT JOIN assets a ON a.category_id = ac.id
        GROUP BY ac.id
        ORDER BY ac.name
    ''').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/devices/<int:device_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_device(device_id):
    db = get_db()
    if not user_can('devices.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'PUT':
        try:
            data = request.get_json(silent=True) or {}
            device_data, field_errors = validate_device_payload(db, data)
            if field_errors:
                return validation_error_response("Bitte die markierten Felder prüfen", field_errors)

            result = db.execute('''
                UPDATE devices 
                SET name = ?, serial_number = ?, specs = ?, category_id = ?, location_id = ?
                WHERE id = ?
            ''', (
                device_data["name"],
                device_data["serial_number"],
                json.dumps(device_data["specs"]),
                device_data["category_id"],
                device_data["location_id"],
                device_id,
            ))

            if result.rowcount == 0:
                return jsonify({"error": "Gerät nicht gefunden"}), 404

            log_activity(db, "update", "device", device_id, {"name": device_data["name"]})
            db.commit()
            return jsonify({"status": "updated"}), 200

        except sqlite3.Error as e:
            return jsonify({"error": f"Datenbankfehler: {str(e)}"}), 500

    elif request.method == 'DELETE':
        db.execute('DELETE FROM asset_devices WHERE device_id = ?', (device_id,))
        db.execute('DELETE FROM software_installations WHERE device_id = ?', (device_id,))
        db.execute('''
            DELETE FROM dependency_links
            WHERE (source_type = 'device' AND source_id = ?)
               OR (target_type = 'device' AND target_id = ?)
        ''', (device_id, device_id))
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
        data = request.get_json(silent=True) or {}
        device_data, field_errors = validate_device_payload(db, data)
        if field_errors:
            return validation_error_response("Bitte die markierten Felder prüfen", field_errors)

        cursor = db.execute('''
            INSERT INTO devices (name, category_id, serial_number, location_id, specs)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            device_data["name"],
            device_data["category_id"],
            device_data["serial_number"],
            device_data["location_id"],
            json.dumps(device_data["specs"])
        ))
        device_id = cursor.lastrowid
        log_activity(db, "create", "device", device_id, {"name": device_data["name"]})
        db.commit()
        return jsonify({"status": "created", "id": device_id}), 201

    except sqlite3.Error as e:
        return jsonify({"error": f"Datenbankfehler: {str(e)}"}), 500

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
@app.route('/api/asset-entries', methods=['GET', 'POST'])
@login_required
def manage_assets():
    db = get_db()
    if request.method == 'POST':
        if not user_can('assets.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403

        data = request.get_json(silent=True) or {}
        field_errors = {}

        name = (data.get('name') or '').strip()
        category_id = normalize_optional_int(data.get('category_id'))
        notes = (data.get('notes') or '').strip()
        currency = (data.get('currency') or '').strip() or None
        cost_center = (data.get('cost_center') or '').strip() or None
        invoice_number = (data.get('invoice_number') or '').strip() or None
        retirement_reason = (data.get('retirement_reason') or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id'))
        purchase_order_id = normalize_optional_int(data.get('purchase_order_id'))
        device_ids = data.get('device_ids') or []
        device_items = data.get('device_items') or []
        relations = data.get('relations') or []

        if not name:
            field_errors['name'] = "Name ist erforderlich"
        if category_id is None:
            field_errors['category_id'] = "Kategorie ist erforderlich"

        category_row = None
        field_definitions = {}
        if category_id is not None:
            category_row = db.execute(
                'SELECT id, fields FROM asset_categories WHERE id = ?',
                (category_id,),
            ).fetchone()
            if not category_row:
                field_errors['category_id'] = "Kategorie nicht gefunden"
            else:
                field_definitions = parse_field_definitions(category_row["fields"])

        acquisition_date, acquisition_error = normalize_optional_iso_date(data.get('acquisition_date'))
        commissioning_date, commissioning_error = normalize_optional_iso_date(data.get('commissioning_date'))
        warranty_end, warranty_error = normalize_optional_iso_date(data.get('warranty_end'))
        retirement_date, retirement_error = normalize_optional_iso_date(data.get('retirement_date'))
        depreciation_months, depreciation_error = parse_optional_int_field(data.get('depreciation_months'), "Abschreibungszeitraum", 0)
        purchase_cost, purchase_cost_error = parse_optional_float_field(data.get('purchase_cost'), "Kaufpreis", 0)

        if acquisition_error:
            field_errors['acquisition_date'] = acquisition_error
        if commissioning_error:
            field_errors['commissioning_date'] = commissioning_error
        if warranty_error:
            field_errors['warranty_end'] = warranty_error
        if retirement_error:
            field_errors['retirement_date'] = retirement_error
        if depreciation_error:
            field_errors['depreciation_months'] = depreciation_error
        if purchase_cost_error:
            field_errors['purchase_cost'] = purchase_cost_error

        specs, spec_errors = validate_dynamic_specs(data.get('specs') or {}, field_definitions)
        field_errors.update(spec_errors)

        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            field_errors['vendor_id'] = fk_error
        fk_error = ensure_fk_exists(db, "purchase_orders", purchase_order_id, "Bestellung")
        if fk_error:
            field_errors['purchase_order_id'] = fk_error

        if device_items:
            device_ids = [item.get("device_id") for item in device_items if item.get("device_id")]

        device_ids, invalid_ids = normalize_device_ids(device_ids)
        if invalid_ids:
            field_errors['device_ids'] = "Ungültige Geräte-IDs"

        missing_ids = find_missing_device_ids(db, device_ids)
        if missing_ids:
            field_errors['device_ids'] = "Ungültige Geräte-IDs"

        if field_errors:
            return validation_error_response("Bitte die markierten Felder prüfen", field_errors)

        conflicts = find_device_assignment_conflicts(db, device_ids)
        if conflicts:
            return validation_error_response(
                "Geräte sind bereits anderen Asset-Einträgen zugewiesen",
                {"device_ids": "Mindestens ein Gerät ist bereits einem anderen Asset zugeordnet"},
                status=409,
            )

        try:
            cursor = db.execute('''
                INSERT INTO assets (
                    name, category_id, notes, specs, acquisition_date, commissioning_date,
                    warranty_end, depreciation_months, vendor_id, purchase_order_id, purchase_cost,
                    currency, cost_center, invoice_number, retirement_date, retirement_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                category_id,
                notes,
                json.dumps(specs),
                acquisition_date,
                commissioning_date,
                warranty_end,
                depreciation_months,
                vendor_id,
                purchase_order_id,
                purchase_cost,
                currency,
                cost_center,
                invoice_number,
                retirement_date,
                retirement_reason
            ))
            asset_id = cursor.lastrowid
            if device_items:
                for item in device_items:
                    device_id = normalize_optional_int(item.get("device_id"))
                    if not device_id:
                        continue
                    quantity, _ = parse_optional_int_field(item.get("quantity"), "Menge", 1)
                    notes_item = (item.get("notes") or "").strip() or None
                    db.execute('''
                        INSERT INTO asset_devices (asset_id, device_id, quantity, notes)
                        VALUES (?, ?, ?, ?)
                    ''', (asset_id, device_id, quantity or 1, notes_item))
            else:
                for device_id in device_ids:
                    db.execute('''
                        INSERT INTO asset_devices (asset_id, device_id, quantity)
                        VALUES (?, ?, 1)
                    ''', (asset_id, device_id))
            mark_devices_as_used(db, device_ids)
            for relation in relations:
                related_asset_id = normalize_optional_int(relation.get("related_asset_id"))
                relation_type_id = normalize_optional_int(relation.get("relation_type_id"))
                if not related_asset_id or related_asset_id == asset_id:
                    continue
                db.execute('''
                    INSERT OR IGNORE INTO asset_relations (asset_id, related_asset_id, relation_type_id)
                    VALUES (?, ?, ?)
                ''', (asset_id, related_asset_id, relation_type_id))
            log_activity(db, "create", "asset_entry", asset_id, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": asset_id}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Eintrag existiert bereits"}), 409
        except sqlite3.Error as e:
            return jsonify({"error": f"Datenbankfehler: {str(e)}"}), 500

    if not (user_can('assets.view') or user_can('assets.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403

    raw_category_id = request.args.get('category_id')
    category_id = normalize_optional_int(raw_category_id)
    if raw_category_id not in (None, "") and category_id is None:
        return validation_error_response("Kategorie ungültig", {"category_id": "Kategorie ist ungültig"})

    query = '''
        SELECT a.*, ac.name as category_name, ac.icon as category_icon, ac.description as category_description,
               ac.binpacking_config as category_binpacking_config,
               v.name as vendor_name, po.po_number as purchase_order_number,
               COUNT(ad.device_id) as device_count
        FROM assets a
        LEFT JOIN asset_categories ac ON a.category_id = ac.id
        LEFT JOIN vendors v ON a.vendor_id = v.id
        LEFT JOIN purchase_orders po ON a.purchase_order_id = po.id
        LEFT JOIN asset_devices ad ON a.id = ad.asset_id
    '''
    params = []
    if category_id:
        query += ' WHERE a.category_id = ?'
        params.append(category_id)
    query += ' GROUP BY a.id ORDER BY a.created_at DESC'
    assets = db.execute(query, params).fetchall()
    result = build_asset_summaries(db, assets)
    return jsonify(result)

@app.route('/api/asset-entries/<int:asset_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def asset_entry_detail(asset_id):
    db = get_db()
    asset_row = db.execute('''
        SELECT a.*, ac.name as category_name, ac.icon as category_icon, ac.description as category_description,
               ac.binpacking_config as category_binpacking_config,
               v.name as vendor_name, po.po_number as purchase_order_number
        FROM assets a
        LEFT JOIN asset_categories ac ON a.category_id = ac.id
        LEFT JOIN vendors v ON a.vendor_id = v.id
        LEFT JOIN purchase_orders po ON a.purchase_order_id = po.id
        WHERE a.id = ?
    ''', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset-Eintrag nicht gefunden"}), 404

    if request.method == 'GET':
        if not (user_can('assets.view') or user_can('assets.manage')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        device_rows = db.execute('''
            SELECT d.*, c.name as category_name, c.icon as category_icon, l.name as location_name,
                   ad.quantity, ad.notes
            FROM devices d
            JOIN asset_devices ad ON ad.device_id = d.id
            JOIN categories c ON d.category_id = c.id
            LEFT JOIN locations l ON d.location_id = l.id
            WHERE ad.asset_id = ?
            ORDER BY d.created_at DESC
        ''', (asset_id,)).fetchall()
        asset = build_asset_summary(db, asset_row, device_rows=[dict(row) for row in device_rows])
        asset['devices'] = [dict(row) for row in device_rows]
        asset["assignment"] = fetch_current_asset_assignment(db, asset_id)
        if user_can("asset.view_history"):
            asset["assignment_history"] = fetch_asset_assignment_history(db, asset_id)
        else:
            asset["assignment_history"] = []
        relation_rows = db.execute('''
            SELECT ar.id, ar.asset_id, ar.related_asset_id, ar.relation_type_id,
                   rt.name as relation_type_name,
                   a.name as asset_name, ra.name as related_asset_name
            FROM asset_relations ar
            LEFT JOIN asset_relation_types rt ON ar.relation_type_id = rt.id
            LEFT JOIN assets a ON ar.asset_id = a.id
            LEFT JOIN assets ra ON ar.related_asset_id = ra.id
            WHERE ar.asset_id = ? OR ar.related_asset_id = ?
            ORDER BY ar.created_at DESC
        ''', (asset_id, asset_id)).fetchall()
        relations = []
        for row in relation_rows:
            item = dict(row)
            item["direction"] = "outgoing" if item["asset_id"] == asset_id else "incoming"
            relations.append(item)
        asset["relations"] = relations
        asset["binpacking"] = build_asset_binpacking_preview(db, asset)
        open_ticket_rows = db.execute('''
            SELECT t.id, t.title, t.status, t.priority, t.created_at
            FROM tickets t
            JOIN ticket_assets ta ON ta.ticket_id = t.id
            WHERE ta.asset_id = ? AND t.status NOT IN ('resolved', 'closed')
            ORDER BY t.created_at DESC
        ''', (asset_id,)).fetchall()
        asset["open_tickets"] = [dict(row) for row in open_ticket_rows]
        return jsonify(asset)

    if request.method == 'PUT':
        if not user_can('assets.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json(silent=True) or {}
        field_errors = {}
        name = (data.get('name') or '').strip()
        category_id = normalize_optional_int(data.get('category_id'))
        notes = (data.get('notes') or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id'))
        purchase_order_id = normalize_optional_int(data.get('purchase_order_id'))
        currency = (data.get('currency') or '').strip() or None
        cost_center = (data.get('cost_center') or '').strip() or None
        invoice_number = (data.get('invoice_number') or '').strip() or None
        retirement_reason = (data.get('retirement_reason') or '').strip()
        device_ids = data.get('device_ids') or []
        device_items = data.get('device_items') or []
        relations = data.get('relations') or []
        if not name:
            field_errors['name'] = "Name ist erforderlich"
        if category_id is None:
            field_errors['category_id'] = "Kategorie ist erforderlich"
        category_row = db.execute(
            'SELECT id, fields FROM asset_categories WHERE id = ?',
            (category_id,),
        ).fetchone()
        if category_id is not None and not category_row:
            field_errors['category_id'] = "Kategorie nicht gefunden"

        acquisition_date, acquisition_error = normalize_optional_iso_date(data.get('acquisition_date'))
        commissioning_date, commissioning_error = normalize_optional_iso_date(data.get('commissioning_date'))
        warranty_end, warranty_error = normalize_optional_iso_date(data.get('warranty_end'))
        retirement_date, retirement_error = normalize_optional_iso_date(data.get('retirement_date'))
        depreciation_months, depreciation_error = parse_optional_int_field(data.get('depreciation_months'), "Abschreibungszeitraum", 0)
        purchase_cost, purchase_cost_error = parse_optional_float_field(data.get('purchase_cost'), "Kaufpreis", 0)

        if acquisition_error:
            field_errors['acquisition_date'] = acquisition_error
        if commissioning_error:
            field_errors['commissioning_date'] = commissioning_error
        if warranty_error:
            field_errors['warranty_end'] = warranty_error
        if retirement_error:
            field_errors['retirement_date'] = retirement_error
        if depreciation_error:
            field_errors['depreciation_months'] = depreciation_error
        if purchase_cost_error:
            field_errors['purchase_cost'] = purchase_cost_error

        specs, spec_errors = validate_dynamic_specs(
            data.get('specs') or {},
            parse_field_definitions(category_row["fields"]) if category_row else {},
        )
        field_errors.update(spec_errors)

        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            field_errors['vendor_id'] = fk_error
        fk_error = ensure_fk_exists(db, "purchase_orders", purchase_order_id, "Bestellung")
        if fk_error:
            field_errors['purchase_order_id'] = fk_error
        if device_items:
            device_ids = [item.get("device_id") for item in device_items if item.get("device_id")]
        device_ids, invalid_ids = normalize_device_ids(device_ids)
        if invalid_ids:
            field_errors['device_ids'] = "Ungültige Geräte-IDs"
        missing_ids = find_missing_device_ids(db, device_ids)
        if missing_ids:
            field_errors['device_ids'] = "Ungültige Geräte-IDs"
        if field_errors:
            return validation_error_response("Bitte die markierten Felder prüfen", field_errors)
        conflicts = find_device_assignment_conflicts(db, device_ids, asset_id=asset_id)
        if conflicts:
            return validation_error_response(
                "Geräte sind bereits anderen Asset-Einträgen zugewiesen",
                {"device_ids": "Mindestens ein Gerät ist bereits einem anderen Asset zugeordnet"},
                status=409,
            )
        db.execute('''
            UPDATE assets
            SET name = ?, category_id = ?, notes = ?, specs = ?, acquisition_date = ?, commissioning_date = ?,
                warranty_end = ?, depreciation_months = ?, vendor_id = ?, purchase_order_id = ?, purchase_cost = ?,
                currency = ?, cost_center = ?, invoice_number = ?, retirement_date = ?, retirement_reason = ?
            WHERE id = ?
        ''', (
            name,
            category_id,
            notes,
            json.dumps(specs),
            acquisition_date,
            commissioning_date,
            warranty_end,
            depreciation_months,
            vendor_id,
            purchase_order_id,
            purchase_cost,
            currency,
            cost_center,
            invoice_number,
            retirement_date,
            retirement_reason,
            asset_id
        ))
        existing_rows = db.execute(
            'SELECT device_id FROM asset_devices WHERE asset_id = ?',
            (asset_id,),
        ).fetchall()
        existing_ids = {row["device_id"] for row in existing_rows}
        db.execute('DELETE FROM asset_devices WHERE asset_id = ?', (asset_id,))
        if device_items:
            for item in device_items:
                device_id = normalize_optional_int(item.get("device_id"))
                if not device_id:
                    continue
                quantity, _ = parse_optional_int_field(item.get("quantity"), "Menge", 1)
                notes_item = (item.get("notes") or "").strip() or None
                db.execute('''
                    INSERT INTO asset_devices (asset_id, device_id, quantity, notes)
                    VALUES (?, ?, ?, ?)
                ''', (asset_id, device_id, quantity or 1, notes_item))
        else:
            for device_id in device_ids:
                db.execute('''
                    INSERT INTO asset_devices (asset_id, device_id, quantity)
                    VALUES (?, ?, 1)
                ''', (asset_id, device_id))
        new_ids = set(device_ids)
        removed_ids = [device_id for device_id in existing_ids if device_id not in new_ids]
        mark_devices_as_used(db, device_ids)
        mark_devices_as_in_stock_if_unassigned(db, removed_ids)
        db.execute('DELETE FROM asset_relations WHERE asset_id = ?', (asset_id,))
        for relation in relations:
            related_asset_id = normalize_optional_int(relation.get("related_asset_id"))
            relation_type_id = normalize_optional_int(relation.get("relation_type_id"))
            if not related_asset_id or related_asset_id == asset_id:
                continue
            db.execute('''
                INSERT OR IGNORE INTO asset_relations (asset_id, related_asset_id, relation_type_id)
                VALUES (?, ?, ?)
            ''', (asset_id, related_asset_id, relation_type_id))
        log_activity(db, "update", "asset_entry", asset_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('assets.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    device_rows = db.execute(
        'SELECT device_id FROM asset_devices WHERE asset_id = ?',
        (asset_id,),
    ).fetchall()
    device_ids = [row["device_id"] for row in device_rows]
    db.execute('DELETE FROM ticket_assets WHERE asset_id = ?', (asset_id,))
    db.execute('DELETE FROM asset_devices WHERE asset_id = ?', (asset_id,))
    db.execute('DELETE FROM asset_relations WHERE asset_id = ? OR related_asset_id = ?', (asset_id, asset_id))
    db.execute('DELETE FROM assets WHERE id = ?', (asset_id,))
    mark_devices_as_in_stock_if_unassigned(db, device_ids)
    log_activity(db, "delete", "asset_entry", asset_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/asset-entries/<int:asset_id>/devices', methods=['GET', 'POST'])
@login_required
def asset_entry_devices(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset-Eintrag nicht gefunden"}), 404

    if request.method == 'GET':
        if not (user_can('assets.view') or user_can('assets.manage')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        device_rows = db.execute('''
            SELECT d.*, c.name as category_name, c.icon as category_icon, l.name as location_name,
                   ad.quantity, ad.notes
            FROM devices d
            JOIN asset_devices ad ON ad.device_id = d.id
            JOIN categories c ON d.category_id = c.id
            LEFT JOIN locations l ON d.location_id = l.id
            WHERE ad.asset_id = ?
            ORDER BY d.created_at DESC
        ''', (asset_id,)).fetchall()
        return jsonify([dict(row) for row in device_rows])

    if not user_can('assets.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    data = request.get_json() or {}
    items = data.get("items") or []
    if not items:
        return jsonify({"error": "Keine Geräte angegeben"}), 400
    device_ids = [item.get("device_id") for item in items if item.get("device_id")]
    device_ids, invalid_ids = normalize_device_ids(device_ids)
    if invalid_ids:
        return jsonify({"error": "Ungültige Geräte-IDs"}), 400
    missing_ids = find_missing_device_ids(db, device_ids)
    if missing_ids:
        return jsonify({"error": "Ungültige Geräte-IDs"}), 400
    conflicts = find_device_assignment_conflicts(db, device_ids, asset_id=asset_id)
    if conflicts:
        return jsonify({"error": "Geräte sind bereits anderen Asset-Einträgen zugewiesen"}), 409
    for item in items:
        device_id = item.get("device_id")
        if not device_id:
            continue
        quantity = item.get("quantity") or 1
        notes_item = (item.get("notes") or "").strip() or None
        try:
            db.execute(
                'INSERT INTO asset_devices (asset_id, device_id, quantity, notes) VALUES (?, ?, ?, ?)',
                (asset_id, device_id, quantity, notes_item),
            )
        except sqlite3.IntegrityError:
            return jsonify({"error": "Gerät bereits zugewiesen"}), 409
    mark_devices_as_used(db, device_ids)
    db.commit()
    return jsonify({"status": "added"}), 201

@app.route('/api/asset-entries/<int:asset_id>/devices/<int:device_id>', methods=['DELETE'])
@login_required
def asset_entry_device_remove(asset_id, device_id):
    db = get_db()
    if not user_can('assets.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset-Eintrag nicht gefunden"}), 404
    db.execute(
        'DELETE FROM asset_devices WHERE asset_id = ? AND device_id = ?',
        (asset_id, device_id),
    )
    mark_devices_as_in_stock_if_unassigned(db, [device_id])
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/assets/<int:asset_id>/history', methods=['GET'])
@login_required
@require_permission('asset.view_history')
def asset_assignment_history(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404
    history = fetch_asset_assignment_history(db, asset_id)
    return jsonify(history)

@app.route('/assets/<int:asset_id>/assign', methods=['POST'])
@login_required
@require_permission('asset.assign')
def assign_asset(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404
    data = request.get_json() or {}
    assigned_to_user_id = data.get("assigned_to_user_id")
    assigned_to_team_id = data.get("assigned_to_team_id")
    note = (data.get("note") or "").strip()
    current = fetch_current_asset_assignment(db, asset_id)
    transition_error = validate_assignment_transition(current["status"] if current else None, "assign")
    if transition_error:
        return jsonify({"error": transition_error}), 400
    assigned_to_user_id, assigned_to_team_id, error = resolve_assignment_target(
        db,
        assigned_to_user_id,
        assigned_to_team_id,
    )
    if error:
        return jsonify({"error": error}), 400
    status = "assigned"
    if current and (
        current.get("assigned_to_user_id") != assigned_to_user_id
        or current.get("assigned_to_team_id") != assigned_to_team_id
    ):
        status = "transferred"
    created_by_user_id = get_current_user_id(db)
    now = datetime.utcnow().isoformat()
    db.execute('''
        INSERT INTO asset_assignment_history (
            asset_id, assigned_to_user_id, assigned_to_team_id, status, note, created_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        asset_id,
        assigned_to_user_id,
        assigned_to_team_id,
        status,
        note,
        created_by_user_id,
        now
    ))
    log_activity(db, "ASSET_ASSIGNED", "asset", asset_id, {
        "assigned_to_user_id": assigned_to_user_id,
        "assigned_to_team_id": assigned_to_team_id,
        "status": status,
        "note": note
    })
    db.commit()
    return jsonify({
        "status": "ok",
        "assignment": fetch_current_asset_assignment(db, asset_id),
        "history": fetch_asset_assignment_history(db, asset_id),
    }), 200

@app.route('/assets/<int:asset_id>/checkout', methods=['POST'])
@login_required
@require_permission('asset.checkout')
def checkout_asset(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404
    data = request.get_json() or {}
    assigned_to_user_id = data.get("assigned_to_user_id")
    assigned_to_team_id = data.get("assigned_to_team_id")
    due_at = (data.get("due_at") or "").strip() or None
    note = (data.get("note") or "").strip()
    current = fetch_current_asset_assignment(db, asset_id)
    transition_error = validate_assignment_transition(current["status"] if current else None, "checkout")
    if transition_error:
        return jsonify({"error": transition_error}), 400
    assigned_to_user_id, assigned_to_team_id, error = resolve_assignment_target(
        db,
        assigned_to_user_id,
        assigned_to_team_id,
    )
    if error:
        return jsonify({"error": error}), 400
    created_by_user_id = get_current_user_id(db)
    now = datetime.utcnow().isoformat()
    db.execute('''
        INSERT INTO asset_assignment_history (
            asset_id, assigned_to_user_id, assigned_to_team_id, status,
            checked_out_at, due_at, note, created_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        asset_id,
        assigned_to_user_id,
        assigned_to_team_id,
        "checked_out",
        now,
        due_at,
        note,
        created_by_user_id,
        now
    ))
    log_activity(db, "ASSET_CHECKED_OUT", "asset", asset_id, {
        "assigned_to_user_id": assigned_to_user_id,
        "assigned_to_team_id": assigned_to_team_id,
        "due_at": due_at,
        "note": note
    })
    db.commit()
    return jsonify({
        "status": "ok",
        "assignment": fetch_current_asset_assignment(db, asset_id),
        "history": fetch_asset_assignment_history(db, asset_id),
    }), 200

@app.route('/assets/<int:asset_id>/checkin', methods=['POST'])
@login_required
@require_permission('asset.checkin')
def checkin_asset(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404
    data = request.get_json() or {}
    note = (data.get("note") or "").strip()
    current = fetch_current_asset_assignment(db, asset_id)
    transition_error = validate_assignment_transition(current["status"] if current else None, "checkin")
    if transition_error:
        return jsonify({"error": transition_error}), 400
    created_by_user_id = get_current_user_id(db)
    now = datetime.utcnow().isoformat()
    db.execute('''
        INSERT INTO asset_assignment_history (
            asset_id, assigned_to_user_id, assigned_to_team_id, status,
            checked_in_at, note, created_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        asset_id,
        current.get("assigned_to_user_id") if current else None,
        current.get("assigned_to_team_id") if current else None,
        "checked_in",
        now,
        note,
        created_by_user_id,
        now
    ))
    log_activity(db, "ASSET_CHECKED_IN", "asset", asset_id, {
        "note": note
    })
    db.commit()
    return jsonify({
        "status": "ok",
        "assignment": fetch_current_asset_assignment(db, asset_id),
        "history": fetch_asset_assignment_history(db, asset_id),
    }), 200

@app.route('/assets/<int:asset_id>/unassign', methods=['POST'])
@login_required
@require_permission('asset.assign')
def unassign_asset(asset_id):
    db = get_db()
    asset_row = db.execute('SELECT id FROM assets WHERE id = ?', (asset_id,)).fetchone()
    if not asset_row:
        return jsonify({"error": "Asset nicht gefunden"}), 404
    data = request.get_json() or {}
    note = (data.get("note") or "").strip()
    current = fetch_current_asset_assignment(db, asset_id)
    transition_error = validate_assignment_transition(current["status"] if current else None, "unassign")
    if transition_error:
        return jsonify({"error": transition_error}), 400
    created_by_user_id = get_current_user_id(db)
    now = datetime.utcnow().isoformat()
    db.execute('''
        INSERT INTO asset_assignment_history (
            asset_id, assigned_to_user_id, assigned_to_team_id, status, note, created_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        asset_id,
        None,
        None,
        "unassigned",
        note,
        created_by_user_id,
        now
    ))
    log_activity(db, "ASSET_UNASSIGNED", "asset", asset_id, {"note": note})
    db.commit()
    return jsonify({
        "status": "ok",
        "assignment": fetch_current_asset_assignment(db, asset_id),
        "history": fetch_asset_assignment_history(db, asset_id),
    }), 200

@app.route('/api/asset-assignments/options', methods=['GET'])
@login_required
@require_permissions('asset.assign', 'asset.checkout')
def asset_assignment_options():
    db = get_db()
    users = db.execute('SELECT id, username FROM users ORDER BY username').fetchall()
    teams = db.execute('SELECT id, name FROM teams ORDER BY name').fetchall()
    return jsonify({
        "users": [dict(row) for row in users],
        "teams": [dict(row) for row in teams],
    })

@app.route('/attachments', methods=['GET'])
@login_required
@require_permission('attachment.download')
def list_attachments():
    db = get_db()
    entity_type = (request.args.get("entity_type") or "").strip()
    entity_id = request.args.get("entity_id", type=int)
    if not entity_type or not entity_id:
        return jsonify({"error": "Entität fehlt"}), 400
    access = get_user_access(db)
    _, error = ensure_attachment_entity_access(db, entity_type, entity_id, access)
    if error:
        message, status = error
        return jsonify({"error": message}), status
    rows = db.execute('''
        SELECT a.*, u.username as uploaded_by
        FROM attachments a
        LEFT JOIN users u ON u.id = a.uploaded_by_user_id
        WHERE a.entity_type = ? AND a.entity_id = ? AND a.deleted_at IS NULL
        ORDER BY a.created_at DESC
    ''', (entity_type, entity_id)).fetchall()
    return jsonify([serialize_attachment(row) for row in rows])

@app.route('/attachments/upload', methods=['POST'])
@login_required
@require_permission('attachment.upload')
def upload_attachment():
    db = get_db()
    entity_type = (request.form.get("entity_type") or "").strip()
    entity_id = request.form.get("entity_id", type=int)
    if not entity_type or not entity_id:
        return jsonify({"error": "Entität fehlt"}), 400
    access = get_user_access(db)
    _, error = ensure_attachment_entity_access(db, entity_type, entity_id, access)
    if error:
        message, status = error
        return jsonify({"error": message}), status
    file_storage = request.files.get("file")
    payload, error_message = store_attachment_file(file_storage, entity_type, entity_id)
    if error_message:
        return jsonify({"error": error_message}), 400
    user_id = get_current_user_id(db)
    cursor = db.execute('''
        INSERT INTO attachments (
            entity_type, entity_id, original_filename, stored_filename, mime_type, size_bytes, uploaded_by_user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        entity_type,
        entity_id,
        payload["original_filename"],
        payload["stored_filename"],
        payload["mime_type"],
        payload["size_bytes"],
        user_id
    ))
    attachment_id = cursor.lastrowid
    log_activity(db, "ATTACHMENT_UPLOADED", "attachment", attachment_id, {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "filename": payload["original_filename"]
    })
    db.commit()
    row = db.execute('''
        SELECT a.*, u.username as uploaded_by
        FROM attachments a
        LEFT JOIN users u ON u.id = a.uploaded_by_user_id
        WHERE a.id = ?
    ''', (attachment_id,)).fetchone()
    return jsonify(serialize_attachment(row)), 201

@app.route('/attachments/<int:attachment_id>/download', methods=['GET'])
@login_required
@require_permission('attachment.download')
def download_attachment(attachment_id):
    db = get_db()
    row = db.execute('''
        SELECT *
        FROM attachments
        WHERE id = ? AND deleted_at IS NULL
    ''', (attachment_id,)).fetchone()
    if not row:
        return jsonify({"error": "Anhang nicht gefunden"}), 404
    access = get_user_access(db)
    _, error = ensure_attachment_entity_access(db, row["entity_type"], row["entity_id"], access)
    if error:
        message, status = error
        return jsonify({"error": message}), status
    file_path = UPLOADS_DIR / "attachments" / row["entity_type"] / str(row["entity_id"]) / row["stored_filename"]
    if not file_path.exists():
        return jsonify({"error": "Datei nicht gefunden"}), 404
    return send_file(
        file_path,
        as_attachment=True,
        download_name=row["original_filename"],
        mimetype=row["mime_type"] or "application/octet-stream",
    )

@app.route('/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
@require_permission('attachment.delete')
def delete_attachment(attachment_id):
    db = get_db()
    row = db.execute('''
        SELECT *
        FROM attachments
        WHERE id = ? AND deleted_at IS NULL
    ''', (attachment_id,)).fetchone()
    if not row:
        return jsonify({"error": "Anhang nicht gefunden"}), 404
    access = get_user_access(db)
    _, error = ensure_attachment_entity_access(db, row["entity_type"], row["entity_id"], access)
    if error:
        message, status = error
        return jsonify({"error": message}), status
    deleted_at = datetime.utcnow().isoformat()
    db.execute('UPDATE attachments SET deleted_at = ? WHERE id = ?', (deleted_at, attachment_id))
    log_activity(db, "ATTACHMENT_DELETED", "attachment", attachment_id, {
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "filename": row["original_filename"]
    })
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/asset-relation-types', methods=['GET'])
@login_required
def asset_relation_types():
    db = get_db()
    if not (user_can('assets.view') or user_can('assets.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('''
        SELECT id, name, description
        FROM asset_relation_types
        ORDER BY name
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

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
    existing_category = get_ticket_category(db, category_id)
    if not existing_category:
        return jsonify({"error": "Kategorie nicht gefunden"}), 404
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
        if (
            existing_category["name"].strip().lower() in {"change", "review"}
            and name.strip().lower() != existing_category["name"].strip().lower()
        ):
            return jsonify({
                "error": "Die Workflow-Kategorien Change und Review können nicht umbenannt werden",
                "code": "protected_ticket_category",
            }), 409
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
    if existing_category["name"].strip().lower() in {"change", "review"}:
        return jsonify({
            "error": "Die Workflow-Kategorien Change und Review können nicht gelöscht werden",
            "code": "protected_ticket_category",
        }), 409
    affected_tickets = db.execute(
        'SELECT id FROM tickets WHERE category_id = ?',
        (category_id,)
    ).fetchall()
    if affected_tickets:
        db.execute('UPDATE tickets SET category_id = NULL WHERE category_id = ?', (category_id,))
    result = db.execute('DELETE FROM ticket_categories WHERE id = ?', (category_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Kategorie nicht gefunden"}), 404
    log_activity(
        db,
        "delete",
        "ticket_category",
        category_id,
        {"updated_tickets": len(affected_tickets)}
    )
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/roadmaps', methods=['GET', 'POST'])
@login_required
def roadmaps():
    db = get_db()
    access = get_user_access(db)
    if request.method == 'POST':
        if not user_can('roadmap.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        ticket_id = data.get('ticket_id')
        title = (data.get('title') or '').strip()
        objective = (data.get('objective') or '').strip()
        status = (data.get('status') or 'planned').strip()
        owner = (data.get('owner') or '').strip()
        start_date = (data.get('start_date') or '').strip()
        target_date = (data.get('target_date') or '').strip()
        steps = data.get('steps') or []
        ticket = None
        if ticket_id:
            ticket = fetch_ticket(db, ticket_id)
            if not ticket:
                return jsonify({"error": "Ticket nicht gefunden"}), 404
            if not ensure_ticket_access(ticket, access, require_owner_permission=True):
                return jsonify({"error": "Keine Berechtigung"}), 403
            existing = db.execute('SELECT id FROM roadmaps WHERE ticket_id = ?', (ticket_id,)).fetchone()
            if existing:
                return jsonify({"error": "Roadmap für dieses Ticket existiert bereits"}), 400
            if not title:
                title = f"Roadmap: {ticket['title']}"
            if not objective:
                objective = f"Umsetzungsplan für Ticket #{ticket['id']}: {ticket['title']}"
            if not owner:
                owner = ticket.get("assignee") or ticket.get("created_by") or ''

        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400

        cursor = db.execute('''
            INSERT INTO roadmaps (ticket_id, title, objective, status, owner, start_date, target_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            title,
            objective,
            status,
            owner,
            start_date or None,
            target_date or None,
            session.get('username')
        ))
        roadmap_id = cursor.lastrowid
        for index, step in enumerate(steps, start=1):
            step_title = (step.get('title') or '').strip()
            if not step_title:
                continue
            db.execute('''
                INSERT INTO roadmap_steps (roadmap_id, title, description, status, position, owner, due_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                roadmap_id,
                step_title,
                (step.get('description') or '').strip(),
                (step.get('status') or 'planned').strip(),
                int(step.get('position') or index),
                (step.get('owner') or '').strip(),
                (step.get('due_date') or '').strip() or None
            ))
        log_activity(db, "create", "roadmap", roadmap_id, {"title": title, "ticket_id": ticket_id})
        db.commit()
        return jsonify({"status": "created", "id": roadmap_id}), 201

    if not user_can('roadmap.view'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    filters = []
    params = []
    status = (request.args.get('status') or '').strip()
    search = (request.args.get('search') or '').strip()
    ticket_id = request.args.get('ticket_id')
    mine = request.args.get('mine')

    if status:
        filters.append('r.status = ?')
        params.append(status)
    if ticket_id:
        filters.append('r.ticket_id = ?')
        params.append(ticket_id)
    if search:
        filters.append('(r.title LIKE ? OR r.objective LIKE ? OR t.title LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if mine:
        filters.append('(r.created_by = ? OR t.created_by = ?)')
        params.extend([session.get('username'), session.get('username')])
    if not access["is_superuser"] and 'tickets.view_all' not in access["permissions"]:
        filters.append('(t.created_by = ? OR r.created_by = ?)')
        params.extend([session.get('username'), session.get('username')])

    query = '''
        SELECT r.*, t.title as ticket_title, t.status as ticket_status,
               c.name as category_name, c.color as category_color,
               (SELECT COUNT(*) FROM roadmap_steps rs WHERE rs.roadmap_id = r.id) as step_count
        FROM roadmaps r
        LEFT JOIN tickets t ON r.ticket_id = t.id
        LEFT JOIN ticket_categories c ON t.category_id = c.id
    '''
    if filters:
        query += ' WHERE ' + ' AND '.join(filters)
    query += ' ORDER BY r.updated_at DESC, r.created_at DESC'
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/roadmaps/<int:roadmap_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def roadmap_detail(roadmap_id):
    db = get_db()
    access = get_user_access(db)
    roadmap = fetch_roadmap(db, roadmap_id)
    if not roadmap:
        return jsonify({"error": "Roadmap nicht gefunden"}), 404
    if roadmap.get("ticket_id"):
        ticket = fetch_ticket(db, roadmap["ticket_id"])
        if not ensure_ticket_access(ticket, access):
            return jsonify({"error": "Keine Berechtigung"}), 403
    elif not user_can('roadmap.view'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    if request.method == 'GET':
        roadmap["steps"] = fetch_roadmap_steps(db, roadmap_id)
        return jsonify(roadmap)

    if request.method == 'PUT':
        if not user_can('roadmap.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        title = (data.get('title') or roadmap.get('title') or '').strip()
        objective = (data.get('objective') or roadmap.get('objective') or '').strip()
        status = (data.get('status') or roadmap.get('status') or 'planned').strip()
        owner = (data.get('owner') or roadmap.get('owner') or '').strip()
        start_date = (data.get('start_date') or roadmap.get('start_date') or '').strip()
        target_date = (data.get('target_date') or roadmap.get('target_date') or '').strip()
        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400
        db.execute('''
            UPDATE roadmaps
            SET title = ?, objective = ?, status = ?, owner = ?, start_date = ?, target_date = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, objective, status, owner, start_date or None, target_date or None, roadmap_id))
        log_activity(db, "update", "roadmap", roadmap_id, {"title": title})
        db.commit()
        return jsonify({"status": "updated"}), 200

    if not user_can('roadmap.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    db.execute('DELETE FROM roadmap_steps WHERE roadmap_id = ?', (roadmap_id,))
    db.execute('DELETE FROM roadmaps WHERE id = ?', (roadmap_id,))
    log_activity(db, "delete", "roadmap", roadmap_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/roadmaps/<int:roadmap_id>/steps', methods=['POST'])
@login_required
def roadmap_steps_create(roadmap_id):
    db = get_db()
    access = get_user_access(db)
    roadmap = fetch_roadmap(db, roadmap_id)
    if not roadmap:
        return jsonify({"error": "Roadmap nicht gefunden"}), 404
    if roadmap.get("ticket_id"):
        ticket = fetch_ticket(db, roadmap["ticket_id"])
        if not ensure_ticket_access(ticket, access):
            return jsonify({"error": "Keine Berechtigung"}), 403
    if not user_can('roadmap.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "Titel ist erforderlich"}), 400
    description = (data.get('description') or '').strip()
    status = (data.get('status') or 'planned').strip()
    owner = (data.get('owner') or '').strip()
    due_date = (data.get('due_date') or '').strip()
    position = int(data.get('position') or 0)
    if position <= 0:
        row = db.execute('SELECT MAX(position) as max_pos FROM roadmap_steps WHERE roadmap_id = ?', (roadmap_id,)).fetchone()
        position = (row["max_pos"] or 0) + 1
    cursor = db.execute('''
        INSERT INTO roadmap_steps (roadmap_id, title, description, status, position, owner, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (roadmap_id, title, description, status, position, owner, due_date or None))
    db.execute('UPDATE roadmaps SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (roadmap_id,))
    log_activity(db, "create", "roadmap_step", cursor.lastrowid, {"roadmap_id": roadmap_id, "title": title})
    db.commit()
    return jsonify({"status": "created", "id": cursor.lastrowid}), 201

@app.route('/api/roadmaps/<int:roadmap_id>/steps/<int:step_id>', methods=['PUT', 'DELETE'])
@login_required
def roadmap_steps_detail(roadmap_id, step_id):
    db = get_db()
    access = get_user_access(db)
    roadmap = fetch_roadmap(db, roadmap_id)
    if not roadmap:
        return jsonify({"error": "Roadmap nicht gefunden"}), 404
    if roadmap.get("ticket_id"):
        ticket = fetch_ticket(db, roadmap["ticket_id"])
        if not ensure_ticket_access(ticket, access):
            return jsonify({"error": "Keine Berechtigung"}), 403
    if not user_can('roadmap.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    step = db.execute('SELECT * FROM roadmap_steps WHERE id = ? AND roadmap_id = ?', (step_id, roadmap_id)).fetchone()
    if not step:
        return jsonify({"error": "Step nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        title = (data.get('title') or step["title"]).strip()
        description = (data.get('description') or step["description"] or '').strip()
        status = (data.get('status') or step["status"] or 'planned').strip()
        owner = (data.get('owner') or step["owner"] or '').strip()
        due_date = (data.get('due_date') or step["due_date"] or '').strip()
        position = int(data.get('position') or step["position"] or 0)
        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400
        db.execute('''
            UPDATE roadmap_steps
            SET title = ?, description = ?, status = ?, owner = ?, due_date = ?, position = ?
            WHERE id = ? AND roadmap_id = ?
        ''', (title, description, status, owner, due_date or None, position, step_id, roadmap_id))
        db.execute('UPDATE roadmaps SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (roadmap_id,))
        log_activity(db, "update", "roadmap_step", step_id, {"roadmap_id": roadmap_id, "title": title})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM roadmap_steps WHERE id = ? AND roadmap_id = ?', (step_id, roadmap_id))
    db.execute('UPDATE roadmaps SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (roadmap_id,))
    log_activity(db, "delete", "roadmap_step", step_id, {"roadmap_id": roadmap_id})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/departments', methods=['GET', 'POST'])
@login_required
def departments():
    db = get_db()
    if request.method == 'POST':
        if not user_can('departments.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO departments (name, description)
                VALUES (?, ?)
            ''', (name, description))
            log_activity(db, "create", "department", cursor.lastrowid, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Abteilung existiert bereits"}), 400

    if not (user_can('departments.view') or user_can('departments.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/departments/<int:department_id>', methods=['PUT', 'DELETE'])
@login_required
def department_detail(department_id):
    db = get_db()
    if not user_can('departments.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    department = db.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    if not department:
        return jsonify({"error": "Abteilung nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or department["name"] or '').strip()
        description = (data.get('description') or department["description"] or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        db.execute('''
            UPDATE departments
            SET name = ?, description = ?
            WHERE id = ?
        ''', (name, description, department_id))
        log_activity(db, "update", "department", department_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM departments WHERE id = ?', (department_id,))
    log_activity(db, "delete", "department", department_id, {"name": department["name"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/teams', methods=['GET', 'POST'])
@login_required
def teams():
    db = get_db()
    if request.method == 'POST':
        if not user_can('teams.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        department_id = data.get('department_id')
        lead_user = (data.get('lead_user') or '').strip()
        notes = (data.get('notes') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO teams (name, department_id, lead_user, notes)
                VALUES (?, ?, ?, ?)
            ''', (name, department_id, lead_user, notes))
            log_activity(db, "create", "team", cursor.lastrowid, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Team existiert bereits"}), 400

    if not (user_can('teams.view') or user_can('teams.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('''
        SELECT t.*, d.name as department_name
        FROM teams t
        LEFT JOIN departments d ON t.department_id = d.id
        ORDER BY t.name
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/teams/<int:team_id>', methods=['PUT', 'DELETE'])
@login_required
def team_detail(team_id):
    db = get_db()
    if not user_can('teams.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    team = db.execute('SELECT * FROM teams WHERE id = ?', (team_id,)).fetchone()
    if not team:
        return jsonify({"error": "Team nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or team["name"] or '').strip()
        department_id = data.get('department_id')
        lead_user = (data.get('lead_user') or team["lead_user"] or '').strip()
        notes = (data.get('notes') or team["notes"] or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        db.execute('''
            UPDATE teams
            SET name = ?, department_id = ?, lead_user = ?, notes = ?
            WHERE id = ?
        ''', (name, department_id, lead_user, notes, team_id))
        log_activity(db, "update", "team", team_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM teams WHERE id = ?', (team_id,))
    log_activity(db, "delete", "team", team_id, {"name": team["name"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/software', methods=['GET', 'POST'])
@login_required
def software_inventory():
    db = get_db()
    if request.method == 'POST':
        if not user_can('software.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        vendor = (data.get('vendor') or '').strip()
        version = (data.get('version') or '').strip()
        license_type = (data.get('license_type') or '').strip()
        criticality = (data.get('criticality') or 'medium').strip()
        description = (data.get('description') or '').strip()
        owner_team_id = data.get('owner_team_id')
        support_contact = (data.get('support_contact') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO software (name, vendor, version, license_type, criticality, description, owner_team_id, support_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, vendor, version, license_type, criticality, description, owner_team_id, support_contact))
            log_activity(db, "create", "software", cursor.lastrowid, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Software existiert bereits"}), 400

    if not (user_can('software.view') or user_can('software.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('''
        SELECT s.*, t.name as owner_team_name
        FROM software s
        LEFT JOIN teams t ON s.owner_team_id = t.id
        ORDER BY s.name
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/software/<int:software_id>', methods=['PUT', 'DELETE'])
@login_required
def software_detail(software_id):
    db = get_db()
    if not user_can('software.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    software_row = db.execute('SELECT * FROM software WHERE id = ?', (software_id,)).fetchone()
    if not software_row:
        return jsonify({"error": "Software nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or software_row["name"] or '').strip()
        vendor = (data.get('vendor') or software_row["vendor"] or '').strip()
        version = (data.get('version') or software_row["version"] or '').strip()
        license_type = (data.get('license_type') or software_row["license_type"] or '').strip()
        criticality = (data.get('criticality') or software_row["criticality"] or 'medium').strip()
        description = (data.get('description') or software_row["description"] or '').strip()
        owner_team_id = data.get('owner_team_id')
        support_contact = (data.get('support_contact') or software_row["support_contact"] or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        db.execute('''
            UPDATE software
            SET name = ?, vendor = ?, version = ?, license_type = ?, criticality = ?, description = ?, owner_team_id = ?, support_contact = ?
            WHERE id = ?
        ''', (name, vendor, version, license_type, criticality, description, owner_team_id, support_contact, software_id))
        log_activity(db, "update", "software", software_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM software WHERE id = ?', (software_id,))
    log_activity(db, "delete", "software", software_id, {"name": software_row["name"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/software-installations', methods=['GET', 'POST'])
@login_required
def software_installations():
    db = get_db()
    if request.method == 'POST':
        if not user_can('software.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        software_id = data.get('software_id')
        device_id = data.get('device_id')
        asset_id = data.get('asset_id')
        if not software_id or not (device_id or asset_id):
            return jsonify({"error": "Software sowie Gerät oder Asset sind erforderlich"}), 400
        installed_version = (data.get('installed_version') or '').strip()
        environment = (data.get('environment') or 'production').strip()
        status = (data.get('status') or 'active').strip()
        notes = (data.get('notes') or '').strip()
        cursor = db.execute('''
            INSERT INTO software_installations (
                software_id, device_id, asset_id, installed_version, environment, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (software_id, device_id, asset_id, installed_version, environment, status, notes))
        log_activity(db, "create", "software_installation", cursor.lastrowid, {
            "software_id": software_id,
            "device_id": device_id,
            "asset_id": asset_id
        })
        db.commit()
        return jsonify({"status": "created", "id": cursor.lastrowid}), 201

    if not (user_can('software.view') or user_can('software.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    software_id = request.args.get('software_id')
    device_id = request.args.get('device_id')
    asset_id = request.args.get('asset_id')
    query = '''
        SELECT si.*, s.name as software_name, d.name as device_name, a.name as asset_name
        FROM software_installations si
        JOIN software s ON si.software_id = s.id
        LEFT JOIN devices d ON si.device_id = d.id
        LEFT JOIN assets a ON si.asset_id = a.id
    '''
    conditions = []
    params = []
    if software_id:
        conditions.append('si.software_id = ?')
        params.append(software_id)
    if device_id:
        conditions.append('si.device_id = ?')
        params.append(device_id)
    if asset_id:
        conditions.append('si.asset_id = ?')
        params.append(asset_id)
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY si.created_at DESC'
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/software-installations/<int:installation_id>', methods=['PUT', 'DELETE'])
@login_required
def software_installation_detail(installation_id):
    db = get_db()
    if not user_can('software.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    installation = db.execute('SELECT * FROM software_installations WHERE id = ?', (installation_id,)).fetchone()
    if not installation:
        return jsonify({"error": "Installation nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        installed_version = (data.get('installed_version') or installation["installed_version"] or '').strip()
        environment = (data.get('environment') or installation["environment"] or 'production').strip()
        status = (data.get('status') or installation["status"] or 'active').strip()
        notes = (data.get('notes') or installation["notes"] or '').strip()
        db.execute('''
            UPDATE software_installations
            SET installed_version = ?, environment = ?, status = ?, notes = ?
            WHERE id = ?
        ''', (installed_version, environment, status, notes, installation_id))
        log_activity(db, "update", "software_installation", installation_id, {"software_id": installation["software_id"]})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM software_installations WHERE id = ?', (installation_id,))
    log_activity(db, "delete", "software_installation", installation_id, {"software_id": installation["software_id"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/vendors', methods=['GET', 'POST'])
@login_required
def vendors():
    db = get_db()
    if request.method == 'POST':
        if not user_can('procurement.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        vendor_type = (data.get('vendor_type') or '').strip()
        contact_name = (data.get('contact_name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()
        website = (data.get('website') or '').strip()
        address = (data.get('address') or '').strip()
        notes = (data.get('notes') or '').strip()
        rating = normalize_optional_int(data.get('rating')) or 3
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        if rating < 1 or rating > 5:
            return jsonify({"error": "Bewertung muss zwischen 1 und 5 liegen"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO vendors (name, vendor_type, contact_name, email, phone, website, address, rating, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, vendor_type, contact_name, email, phone, website, address, rating, notes))
            log_activity(db, "create", "vendor", cursor.lastrowid, {"name": name})
            db.commit()
            return jsonify({"status": "created", "id": cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Lieferant existiert bereits"}), 400

    if not (user_can('procurement.view') or user_can('procurement.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('SELECT * FROM vendors ORDER BY name').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/vendors/<int:vendor_id>', methods=['PUT', 'DELETE'])
@login_required
def vendor_detail(vendor_id):
    db = get_db()
    if not user_can('procurement.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    vendor = db.execute('SELECT * FROM vendors WHERE id = ?', (vendor_id,)).fetchone()
    if not vendor:
        return jsonify({"error": "Lieferant nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or vendor["name"] or '').strip()
        vendor_type = (data.get('vendor_type') or vendor["vendor_type"] or '').strip()
        contact_name = (data.get('contact_name') or vendor["contact_name"] or '').strip()
        email = (data.get('email') or vendor["email"] or '').strip()
        phone = (data.get('phone') or vendor["phone"] or '').strip()
        website = (data.get('website') or vendor["website"] or '').strip()
        address = (data.get('address') or vendor["address"] or '').strip()
        notes = (data.get('notes') or vendor["notes"] or '').strip()
        rating = normalize_optional_int(data.get('rating')) or vendor["rating"] or 3
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        if rating < 1 or rating > 5:
            return jsonify({"error": "Bewertung muss zwischen 1 und 5 liegen"}), 400
        db.execute('''
            UPDATE vendors
            SET name = ?, vendor_type = ?, contact_name = ?, email = ?, phone = ?, website = ?, address = ?, rating = ?, notes = ?
            WHERE id = ?
        ''', (name, vendor_type, contact_name, email, phone, website, address, rating, notes, vendor_id))
        log_activity(db, "update", "vendor", vendor_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('UPDATE assets SET vendor_id = NULL WHERE vendor_id = ?', (vendor_id,))
    db.execute('UPDATE contracts SET vendor_id = NULL WHERE vendor_id = ?', (vendor_id,))
    db.execute('UPDATE purchase_orders SET vendor_id = NULL WHERE vendor_id = ?', (vendor_id,))
    db.execute('DELETE FROM vendors WHERE id = ?', (vendor_id,))
    log_activity(db, "delete", "vendor", vendor_id, {"name": vendor["name"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/contracts', methods=['GET', 'POST'])
@login_required
def contracts():
    db = get_db()
    if request.method == 'POST':
        if not user_can('procurement.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id'))
        contract_type = (data.get('contract_type') or '').strip()
        status = (data.get('status') or 'active').strip()
        start_date = (data.get('start_date') or '').strip() or None
        end_date = (data.get('end_date') or '').strip() or None
        renewal_type = (data.get('renewal_type') or 'manual').strip()
        renewal_notice_days = normalize_optional_int(data.get('renewal_notice_days')) or 30
        cost = parse_float(data.get('cost'))
        currency = (data.get('currency') or 'EUR').strip() or None
        owner = (data.get('owner') or '').strip()
        service_level = (data.get('service_level') or '').strip()
        notes = (data.get('notes') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            return jsonify({"error": fk_error}), 400
        cursor = db.execute('''
            INSERT INTO contracts (
                vendor_id, name, contract_type, status, start_date, end_date, renewal_type,
                renewal_notice_days, cost, currency, owner, service_level, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vendor_id,
            name,
            contract_type,
            status,
            start_date,
            end_date,
            renewal_type,
            renewal_notice_days,
            cost,
            currency,
            owner,
            service_level,
            notes
        ))
        log_activity(db, "create", "contract", cursor.lastrowid, {"name": name})
        db.commit()
        return jsonify({"status": "created", "id": cursor.lastrowid}), 201

    if not (user_can('procurement.view') or user_can('procurement.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('''
        SELECT c.*, v.name as vendor_name
        FROM contracts c
        LEFT JOIN vendors v ON c.vendor_id = v.id
        ORDER BY c.end_date IS NULL, c.end_date, c.name
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/contracts/<int:contract_id>', methods=['PUT', 'DELETE'])
@login_required
def contract_detail(contract_id):
    db = get_db()
    if not user_can('procurement.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    contract = db.execute('SELECT * FROM contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        return jsonify({"error": "Vertrag nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or contract["name"] or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id')) if "vendor_id" in data else contract["vendor_id"]
        contract_type = (data.get('contract_type') or contract["contract_type"] or '').strip()
        status = (data.get('status') or contract["status"] or 'active').strip()
        start_date = (data.get('start_date') or contract["start_date"] or '').strip() or None
        end_date = (data.get('end_date') or contract["end_date"] or '').strip() or None
        renewal_type = (data.get('renewal_type') or contract["renewal_type"] or 'manual').strip()
        renewal_notice_days = normalize_optional_int(data.get('renewal_notice_days')) or contract["renewal_notice_days"] or 30
        cost = parse_float(data.get('cost')) if "cost" in data else contract["cost"]
        currency = (data.get('currency') or contract["currency"] or 'EUR').strip()
        owner = (data.get('owner') or contract["owner"] or '').strip()
        service_level = (data.get('service_level') or contract["service_level"] or '').strip()
        notes = (data.get('notes') or contract["notes"] or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            return jsonify({"error": fk_error}), 400
        db.execute('''
            UPDATE contracts
            SET vendor_id = ?, name = ?, contract_type = ?, status = ?, start_date = ?, end_date = ?,
                renewal_type = ?, renewal_notice_days = ?, cost = ?, currency = ?, owner = ?, service_level = ?, notes = ?
            WHERE id = ?
        ''', (
            vendor_id,
            name,
            contract_type,
            status,
            start_date,
            end_date,
            renewal_type,
            renewal_notice_days,
            cost,
            currency,
            owner,
            service_level,
            notes,
            contract_id
        ))
        log_activity(db, "update", "contract", contract_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM contracts WHERE id = ?', (contract_id,))
    log_activity(db, "delete", "contract", contract_id, {"name": contract["name"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

def calculate_purchase_order_totals(db, purchase_order_id, tax_override=None):
    rows = db.execute(
        'SELECT quantity, unit_cost FROM purchase_order_items WHERE purchase_order_id = ?',
        (purchase_order_id,),
    ).fetchall()
    subtotal = 0.0
    for row in rows:
        qty = row["quantity"] or 0
        unit_cost = row["unit_cost"] or 0
        subtotal += float(qty) * float(unit_cost)
    existing = db.execute('SELECT tax FROM purchase_orders WHERE id = ?', (purchase_order_id,)).fetchone()
    tax = tax_override if tax_override is not None else (existing["tax"] if existing else 0)
    total = subtotal + (tax or 0)
    db.execute(
        '''
        UPDATE purchase_orders
        SET subtotal = ?, tax = ?, total = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (subtotal, tax or 0, total, purchase_order_id),
    )
    return subtotal, tax or 0, total

@app.route('/api/purchase-orders', methods=['GET', 'POST'])
@login_required
def purchase_orders():
    db = get_db()
    if request.method == 'POST':
        if not user_can('procurement.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        po_number = (data.get('po_number') or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id'))
        status = (data.get('status') or 'draft').strip()
        order_date = (data.get('order_date') or '').strip() or None
        expected_date = (data.get('expected_date') or '').strip() or None
        received_date = (data.get('received_date') or '').strip() or None
        cost_center = (data.get('cost_center') or '').strip()
        requester = (data.get('requester') or '').strip()
        approver = (data.get('approver') or '').strip()
        currency = (data.get('currency') or 'EUR').strip()
        notes = (data.get('notes') or '').strip()
        items = data.get('items') or []
        tax = parse_float(data.get('tax')) or 0
        if not po_number:
            return jsonify({"error": "Bestellnummer ist erforderlich"}), 400
        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            return jsonify({"error": fk_error}), 400
        try:
            cursor = db.execute('''
                INSERT INTO purchase_orders (
                    vendor_id, po_number, status, order_date, expected_date, received_date, cost_center,
                    requester, approver, subtotal, tax, total, currency, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?)
            ''', (
                vendor_id,
                po_number,
                status,
                order_date,
                expected_date,
                received_date,
                cost_center,
                requester,
                approver,
                tax,
                currency,
                notes
            ))
        except sqlite3.IntegrityError:
            return jsonify({"error": "Bestellnummer existiert bereits"}), 400
        purchase_order_id = cursor.lastrowid
        for item in items:
            item_name = (item.get("item_name") or "").strip()
            if not item_name:
                continue
            quantity = normalize_optional_int(item.get("quantity")) or 1
            unit_cost = parse_float(item.get("unit_cost")) or 0
            total_cost = quantity * unit_cost
            item_type = (item.get("item_type") or "asset").strip()
            notes_item = (item.get("notes") or "").strip()
            db.execute('''
                INSERT INTO purchase_order_items (
                    purchase_order_id, item_type, item_name, quantity, unit_cost, total_cost, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                purchase_order_id,
                item_type,
                item_name,
                quantity,
                unit_cost,
                total_cost,
                notes_item
            ))
        subtotal, _, total = calculate_purchase_order_totals(db, purchase_order_id, tax_override=tax)
        log_activity(db, "create", "purchase_order", purchase_order_id, {"po_number": po_number})
        db.commit()
        return jsonify({"status": "created", "id": purchase_order_id, "subtotal": subtotal, "total": total}), 201

    if not (user_can('procurement.view') or user_can('procurement.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('''
        SELECT po.*, v.name as vendor_name,
               (SELECT COUNT(*) FROM purchase_order_items i WHERE i.purchase_order_id = po.id) as item_count
        FROM purchase_orders po
        LEFT JOIN vendors v ON po.vendor_id = v.id
        ORDER BY po.created_at DESC
    ''').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/purchase-orders/<int:purchase_order_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def purchase_order_detail(purchase_order_id):
    db = get_db()
    if request.method == 'GET':
        if not (user_can('procurement.view') or user_can('procurement.manage')):
            return jsonify({"error": "Keine Berechtigung"}), 403
        order = db.execute('''
            SELECT po.*, v.name as vendor_name
            FROM purchase_orders po
            LEFT JOIN vendors v ON po.vendor_id = v.id
            WHERE po.id = ?
        ''', (purchase_order_id,)).fetchone()
        if not order:
            return jsonify({"error": "Bestellung nicht gefunden"}), 404
        items = db.execute('''
            SELECT *
            FROM purchase_order_items
            WHERE purchase_order_id = ?
            ORDER BY id ASC
        ''', (purchase_order_id,)).fetchall()
        payload = dict(order)
        payload["items"] = [dict(row) for row in items]
        return jsonify(payload)

    if not user_can('procurement.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    order = db.execute('SELECT * FROM purchase_orders WHERE id = ?', (purchase_order_id,)).fetchone()
    if not order:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        po_number = (data.get('po_number') or order["po_number"] or '').strip()
        vendor_id = normalize_optional_int(data.get('vendor_id')) if "vendor_id" in data else order["vendor_id"]
        status = (data.get('status') or order["status"] or 'draft').strip()
        order_date = (data.get('order_date') or order["order_date"] or '').strip() or None
        expected_date = (data.get('expected_date') or order["expected_date"] or '').strip() or None
        received_date = (data.get('received_date') or order["received_date"] or '').strip() or None
        cost_center = (data.get('cost_center') or order["cost_center"] or '').strip()
        requester = (data.get('requester') or order["requester"] or '').strip()
        approver = (data.get('approver') or order["approver"] or '').strip()
        currency = (data.get('currency') or order["currency"] or 'EUR').strip()
        notes = (data.get('notes') or order["notes"] or '').strip()
        tax = parse_float(data.get('tax')) if "tax" in data else order["tax"] or 0
        items = data.get('items')
        if not po_number:
            return jsonify({"error": "Bestellnummer ist erforderlich"}), 400
        fk_error = ensure_fk_exists(db, "vendors", vendor_id, "Lieferant")
        if fk_error:
            return jsonify({"error": fk_error}), 400
        db.execute('''
            UPDATE purchase_orders
            SET vendor_id = ?, po_number = ?, status = ?, order_date = ?, expected_date = ?, received_date = ?,
                cost_center = ?, requester = ?, approver = ?, currency = ?, notes = ?, tax = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            vendor_id,
            po_number,
            status,
            order_date,
            expected_date,
            received_date,
            cost_center,
            requester,
            approver,
            currency,
            notes,
            tax,
            purchase_order_id
        ))
        if items is not None:
            db.execute('DELETE FROM purchase_order_items WHERE purchase_order_id = ?', (purchase_order_id,))
            for item in items:
                item_name = (item.get("item_name") or "").strip()
                if not item_name:
                    continue
                quantity = normalize_optional_int(item.get("quantity")) or 1
                unit_cost = parse_float(item.get("unit_cost")) or 0
                total_cost = quantity * unit_cost
                item_type = (item.get("item_type") or "asset").strip()
                notes_item = (item.get("notes") or "").strip()
                db.execute('''
                    INSERT INTO purchase_order_items (
                        purchase_order_id, item_type, item_name, quantity, unit_cost, total_cost, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    purchase_order_id,
                    item_type,
                    item_name,
                    quantity,
                    unit_cost,
                    total_cost,
                    notes_item
                ))
        calculate_purchase_order_totals(db, purchase_order_id, tax_override=tax)
        log_activity(db, "update", "purchase_order", purchase_order_id, {"po_number": po_number})
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('UPDATE assets SET purchase_order_id = NULL WHERE purchase_order_id = ?', (purchase_order_id,))
    db.execute('DELETE FROM purchase_order_items WHERE purchase_order_id = ?', (purchase_order_id,))
    db.execute('DELETE FROM purchase_orders WHERE id = ?', (purchase_order_id,))
    log_activity(db, "delete", "purchase_order", purchase_order_id, {"po_number": order["po_number"]})
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/procurement/renewals', methods=['GET'])
@login_required
def procurement_renewals():
    db = get_db()
    if not (user_can('procurement.view') or user_can('procurement.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    try:
        days = int(request.args.get('days', 90))
    except (TypeError, ValueError):
        days = 90
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=days)

    contract_rows = db.execute('''
        SELECT c.*, v.name as vendor_name
        FROM contracts c
        LEFT JOIN vendors v ON c.vendor_id = v.id
        WHERE c.end_date IS NOT NULL
    ''').fetchall()
    contracts_due = []
    for row in contract_rows:
        end_date = parse_date(row["end_date"])
        if not end_date:
            continue
        if end_date < today or end_date > cutoff:
            continue
        status = (row["status"] or "").lower()
        if status in {"closed", "expired", "cancelled"}:
            continue
        entry = dict(row)
        entry["days_left"] = (end_date - today).days
        contracts_due.append(entry)

    asset_rows = db.execute('''
        SELECT a.id, a.name, a.warranty_end, a.retirement_date, v.name as vendor_name
        FROM assets a
        LEFT JOIN vendors v ON a.vendor_id = v.id
        WHERE a.warranty_end IS NOT NULL
    ''').fetchall()
    warranties_due = []
    for row in asset_rows:
        warranty_end = parse_date(row["warranty_end"])
        if not warranty_end:
            continue
        if warranty_end < today or warranty_end > cutoff:
            continue
        retirement_date = parse_date(row["retirement_date"])
        if retirement_date and retirement_date <= today:
            continue
        entry = dict(row)
        entry["days_left"] = (warranty_end - today).days
        warranties_due.append(entry)

    return jsonify({
        "days": days,
        "contracts": contracts_due,
        "warranties": warranties_due
    })

@app.route('/api/dependency-links', methods=['GET', 'POST'])
@login_required
def dependency_links():
    db = get_db()
    if request.method == 'POST':
        if not user_can('dependencies.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        source_type = (data.get('source_type') or '').strip()
        source_id = data.get('source_id')
        target_type = (data.get('target_type') or '').strip()
        target_id = data.get('target_id')
        relation = (data.get('relation') or 'depends_on').strip()
        criticality = (data.get('criticality') or 'medium').strip()
        redundancy_group = (data.get('redundancy_group') or '').strip() or None
        notes = (data.get('notes') or '').strip()
        if source_type not in DEPENDENCY_ENTITY_TYPES or target_type not in DEPENDENCY_ENTITY_TYPES:
            return jsonify({"error": "Ungültiger Entity-Typ"}), 400
        if not source_id or not target_id:
            return jsonify({"error": "Quelle und Ziel sind erforderlich"}), 400
        try:
            source_id = int(source_id)
            target_id = int(target_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Ungültige IDs"}), 400
        if not fetch_entity_label(db, source_type, source_id) or not fetch_entity_label(db, target_type, target_id):
            return jsonify({"error": "Quelle oder Ziel existiert nicht"}), 400
        try:
            cursor = db.execute('''
                INSERT INTO dependency_links (
                    source_type, source_id, target_type, target_id, relation, criticality, redundancy_group, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (source_type, source_id, target_type, target_id, relation, criticality, redundancy_group, notes))
            log_activity(db, "create", "dependency_link", cursor.lastrowid, {
                "source_type": source_type,
                "source_id": source_id,
                "target_type": target_type,
                "target_id": target_id
            })
            db.commit()
            return jsonify({"status": "created", "id": cursor.lastrowid}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Abhängigkeit existiert bereits"}), 400

    if not (user_can('dependencies.view') or user_can('dependencies.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = prune_dependency_links(db)
    links = []
    for row in rows:
        source_label = fetch_entity_label(db, row["source_type"], row["source_id"]) or f"{row['source_type']} #{row['source_id']}"
        target_label = fetch_entity_label(db, row["target_type"], row["target_id"]) or f"{row['target_type']} #{row['target_id']}"
        links.append({
            **dict(row),
            "source_label": source_label,
            "target_label": target_label
        })
    return jsonify(links)

@app.route('/api/dependency-links/<int:link_id>', methods=['PUT', 'DELETE'])
@login_required
def dependency_link_detail(link_id):
    db = get_db()
    if not user_can('dependencies.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    link_row = db.execute('SELECT * FROM dependency_links WHERE id = ?', (link_id,)).fetchone()
    if not link_row:
        return jsonify({"error": "Abhängigkeit nicht gefunden"}), 404

    if request.method == 'PUT':
        data = request.get_json() or {}
        relation = (data.get('relation') or link_row["relation"] or 'depends_on').strip()
        criticality = (data.get('criticality') or link_row["criticality"] or 'medium').strip()
        redundancy_group = (data.get('redundancy_group') or link_row["redundancy_group"] or '').strip() or None
        notes = (data.get('notes') or link_row["notes"] or '').strip()
        db.execute('''
            UPDATE dependency_links
            SET relation = ?, criticality = ?, redundancy_group = ?, notes = ?
            WHERE id = ?
        ''', (relation, criticality, redundancy_group, notes, link_id))
        log_activity(db, "update", "dependency_link", link_id, {
            "source_type": link_row["source_type"],
            "source_id": link_row["source_id"]
        })
        db.commit()
        return jsonify({"status": "updated"}), 200

    db.execute('DELETE FROM dependency_links WHERE id = ?', (link_id,))
    log_activity(db, "delete", "dependency_link", link_id, {
        "source_type": link_row["source_type"],
        "source_id": link_row["source_id"]
    })
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/dependency-nodes', methods=['GET'])
@login_required
def dependency_nodes():
    db = get_db()
    if not (user_can('dependencies.view') or user_can('dependencies.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    return jsonify(fetch_entity_options(db))

@app.route('/api/dependency-graph', methods=['GET'])
@login_required
def dependency_graph():
    db = get_db()
    if not (user_can('dependencies.view') or user_can('dependencies.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    nodes, edges = build_dependency_graph_data(db)
    graph_edges = []
    for edge in edges:
        source_key = dependency_node_key(edge["source_type"], edge["source_id"])
        target_key = dependency_node_key(edge["target_type"], edge["target_id"])
        graph_edges.append({
            "source": source_key,
            "target": target_key,
            "relation": edge["relation"],
            "criticality": edge["criticality"],
            "implicit": edge["implicit"]
        })
    return jsonify({
        "nodes": nodes,
        "edges": graph_edges
    })

@app.route('/api/impact-analysis', methods=['GET'])
@login_required
def impact_analysis():
    db = get_db()
    if not (user_can('dependencies.view') or user_can('dependencies.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    source_type = (request.args.get('source_type') or '').strip()
    source_id = request.args.get('source_id')
    max_depth = request.args.get('depth')
    if source_type not in DEPENDENCY_ENTITY_TYPES or not source_id:
        return jsonify({"error": "Quelle ist erforderlich"}), 400
    label = fetch_entity_label(db, source_type, int(source_id))
    if not label:
        return jsonify({"error": "Quelle nicht gefunden"}), 404
    depth_value = int(max_depth) if max_depth is not None and str(max_depth).isdigit() else None
    impact, tickets, critical_tickets = analyze_dependency_impact(db, source_type, int(source_id), depth_value)
    return jsonify({
        "source": {
            "type": source_type,
            "id": int(source_id),
            "label": label
        },
        "impact": impact,
        "tickets": tickets,
        "critical_tickets": critical_tickets,
        "spof": calculate_spof_nodes(db)
    })

@app.route('/api/single-points', methods=['GET'])
@login_required
def single_points():
    db = get_db()
    if not (user_can('dependencies.view') or user_can('dependencies.manage')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    return jsonify(calculate_spof_nodes(db))

@app.route('/api/health/summary', methods=['GET'])
@login_required
@require_permissions('health.view', 'health.manage', 'health.run')
def health_summary():
    db = get_db()
    latest_results = fetch_latest_health_results(db)
    statuses = [row["status"] for row in latest_results]
    overall_status = worst_health_status(statuses)
    last_updated = None
    if latest_results:
        last_updated = max(row["observed_at"] for row in latest_results)
    status_counts = {status: 0 for status in HEALTH_STATUS_ORDER.keys()}
    for row in latest_results:
        status_counts[normalize_health_status(row["status"])] += 1

    services_results = [row for row in latest_results if row["check_type"] in ("service_unit", "process")]
    services_status = worst_health_status([row["status"] for row in services_results]) if services_results else "UNKNOWN"

    summary_cards = [
        {
            "key": "services",
            "label": "Services",
            "status": services_status
        }
    ]

    def card_for(check_type, label, metric_key=None):
        match = next((row for row in latest_results if row["check_type"] == check_type), None)
        if not match:
            return {"key": check_type, "label": label, "status": "UNKNOWN"}
        metrics = safe_json_load(match["metrics_json"], default={})
        return {
            "key": check_type,
            "label": label,
            "status": match["status"],
            "metric": metrics.get(metric_key) if metric_key else None
        }

    summary_cards.extend([
        card_for("cpu_load", "CPU/Load", "load1"),
        card_for("memory", "Memory", "mem_used_percent"),
        card_for("disk", "Disk", "used_percent"),
        card_for("db_ping", "DB", "latency_ms"),
        card_for("internet", "Network", "latency_ms")
    ])

    events = db.execute(
        '''
        SELECT e.*, d.name
        FROM health_events e
        JOIN health_check_definitions d ON d.id = e.check_id
        ORDER BY e.observed_at DESC
        LIMIT 8
        '''
    ).fetchall()
    incidents = db.execute(
        '''
        SELECT i.*, d.name
        FROM health_incidents i
        JOIN health_check_definitions d ON d.id = i.check_id
        WHERE i.status = 'open'
        ORDER BY i.opened_at DESC
        '''
    ).fetchall()

    return jsonify({
        "overall_status": overall_status,
        "last_updated": last_updated,
        "counts": status_counts,
        "summary_cards": summary_cards,
        "events": [dict(row) for row in events],
        "incidents": [dict(row) for row in incidents]
    })

@app.route('/api/health/services', methods=['GET'])
@login_required
@require_permissions('health.view', 'health.manage', 'health.run')
def health_services():
    db = get_db()
    latest_results = fetch_latest_health_results(db)
    services = []
    for row in latest_results:
        if row["check_type"] not in ("service_unit", "process"):
            continue
        details = safe_json_load(row["details_json"], default={})
        metrics = safe_json_load(row["metrics_json"], default={})
        services.append({
            "check_id": row["check_id"],
            "name": row["name"],
            "status": row["status"],
            "uptime": details.get("active_since"),
            "last_restart": details.get("active_since"),
            "last_exit": details.get("last_exit"),
            "metrics": metrics
        })
    return jsonify({"services": services})

@app.route('/api/health/checks', methods=['GET', 'POST'])
@login_required
def health_checks():
    db = get_db()
    if request.method == 'POST':
        if not user_can('health.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        check_type = (data.get("check_type") or "").strip()
        category = (data.get("category") or "Custom").strip()
        interval_seconds = int(data.get("interval_seconds") or 60)
        timeout_seconds = int(data.get("timeout_seconds") or 10)
        enabled = 1 if data.get("enabled", True) else 0
        config = data.get("config") or {}
        if not name or not check_type:
            return jsonify({"error": "Name und Check-Typ sind erforderlich"}), 400
        slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"check-{secrets.token_hex(2)}"
        slug = slug_base
        while db.execute("SELECT 1 FROM health_check_definitions WHERE slug = ?", (slug,)).fetchone():
            slug = f"{slug_base}-{secrets.token_hex(2)}"
        cursor = db.execute(
            '''
            INSERT INTO health_check_definitions (
                name, slug, category, check_type, config_json,
                interval_seconds, timeout_seconds, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                name,
                slug,
                category,
                check_type,
                json.dumps(config),
                interval_seconds,
                timeout_seconds,
                enabled
            )
        )
        db.commit()
        new_row = db.execute(
            "SELECT * FROM health_check_definitions WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()
        return jsonify({"check": serialize_health_definition(new_row)}), 201

    if not (user_can('health.view') or user_can('health.manage') or user_can('health.run')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute('SELECT * FROM health_check_definitions ORDER BY category, name').fetchall()
    return jsonify({"checks": [serialize_health_definition(row) for row in rows]})

@app.route('/api/health/checks/<int:check_id>', methods=['GET', 'PATCH'])
@login_required
def health_check_detail(check_id):
    db = get_db()
    row = db.execute('SELECT * FROM health_check_definitions WHERE id = ?', (check_id,)).fetchone()
    if not row:
        return jsonify({"error": "Check nicht gefunden"}), 404
    if request.method == 'PATCH':
        if not user_can('health.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        updates = {
            "name": data.get("name", row["name"]),
            "category": data.get("category", row["category"]),
            "check_type": data.get("check_type", row["check_type"]),
            "interval_seconds": int(data.get("interval_seconds") or row["interval_seconds"] or 60),
            "timeout_seconds": int(data.get("timeout_seconds") or row["timeout_seconds"] or 10),
            "enabled": 1 if data.get("enabled", row["enabled"]) else 0,
            "config_json": json.dumps(data.get("config") or safe_json_load(row["config_json"]))
        }
        db.execute(
            '''
            UPDATE health_check_definitions
            SET name = ?, category = ?, check_type = ?, interval_seconds = ?,
                timeout_seconds = ?, enabled = ?, config_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (
                updates["name"],
                updates["category"],
                updates["check_type"],
                updates["interval_seconds"],
                updates["timeout_seconds"],
                updates["enabled"],
                updates["config_json"],
                check_id
            )
        )
        db.commit()
        row = db.execute('SELECT * FROM health_check_definitions WHERE id = ?', (check_id,)).fetchone()
        return jsonify({"check": serialize_health_definition(row)})

    if not (user_can('health.view') or user_can('health.manage') or user_can('health.run')):
        return jsonify({"error": "Keine Berechtigung"}), 403
    results = db.execute(
        '''
        SELECT r.*, d.name, d.slug, d.category, d.check_type
        FROM health_check_results r
        JOIN health_check_definitions d ON d.id = r.check_id
        WHERE r.check_id = ?
        ORDER BY r.observed_at DESC
        LIMIT 20
        ''',
        (check_id,)
    ).fetchall()
    events = db.execute(
        '''
        SELECT *
        FROM health_events
        WHERE check_id = ?
        ORDER BY observed_at DESC
        LIMIT 20
        ''',
        (check_id,)
    ).fetchall()
    return jsonify({
        "check": serialize_health_definition(row),
        "results": [serialize_health_result(result) for result in results],
        "events": [dict(event) for event in events]
    })

@app.route('/api/health/run', methods=['POST'])
@login_required
@require_permission('health.run')
def health_run_now():
    db = get_db()
    data = request.get_json() or {}
    check_ids = data.get("check_ids")
    if check_ids:
        check_ids = [int(item) for item in check_ids]
    cursor = db.execute(
        '''
        INSERT INTO health_check_runs (started_at, status, triggered_by, initiated_by)
        VALUES (?, 'queued', 'manual', ?)
        ''',
        (health_now(), session.get("username"))
    )
    run_id = cursor.lastrowid
    db.commit()
    thread = threading.Thread(
        target=run_health_checks_async,
        args=(check_ids, session.get("username"), run_id),
        daemon=True
    )
    thread.start()
    return jsonify({"run_id": run_id, "status": "queued"})

@app.route('/api/health/history', methods=['GET'])
@login_required
@require_permissions('health.view', 'health.manage', 'health.run')
def health_history():
    db = get_db()
    days = int(request.args.get("days") or 1)
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    events = db.execute(
        '''
        SELECT observed_at, current_status
        FROM health_events
        WHERE observed_at >= ?
        ORDER BY observed_at ASC
        ''',
        (cutoff,)
    ).fetchall()
    metrics_rows = db.execute(
        '''
        SELECT r.observed_at, r.metrics_json, d.check_type
        FROM health_check_results r
        JOIN health_check_definitions d ON d.id = r.check_id
        WHERE r.observed_at >= ?
          AND d.check_type IN ('cpu_load', 'memory', 'disk')
        ORDER BY r.observed_at ASC
        ''',
        (cutoff,)
    ).fetchall()
    metrics = {"cpu_load": [], "memory": [], "disk": []}
    for row in metrics_rows:
        metrics_data = safe_json_load(row["metrics_json"], default={})
        metrics[row["check_type"]].append({
            "observed_at": row["observed_at"],
            "value": metrics_data.get("load1") if row["check_type"] == "cpu_load" else
                     metrics_data.get("mem_used_percent") if row["check_type"] == "memory" else
                     metrics_data.get("used_percent")
        })
    return jsonify({
        "events": [dict(row) for row in events],
        "metrics": metrics,
        "window_days": days
    })

@app.route('/api/health/incidents', methods=['GET'])
@login_required
@require_permissions('health.view', 'health.manage', 'health.run')
def health_incidents():
    db = get_db()
    rows = db.execute(
        '''
        SELECT i.*, d.name, d.slug
        FROM health_incidents i
        JOIN health_check_definitions d ON d.id = i.check_id
        ORDER BY i.opened_at DESC
        '''
    ).fetchall()
    return jsonify({"incidents": [dict(row) for row in rows]})

@app.route('/api/health/incidents/<int:incident_id>/ack', methods=['POST'])
@login_required
@require_permission('health.manage')
def health_incident_ack(incident_id):
    db = get_db()
    db.execute(
        '''
        UPDATE health_incidents
        SET acknowledged_at = ?
        WHERE id = ?
        ''',
        (health_now(), incident_id)
    )
    db.commit()
    return jsonify({"status": "acknowledged"})

@app.route('/api/health/incidents/<int:incident_id>/mute', methods=['POST'])
@login_required
@require_permission('health.manage')
def health_incident_mute(incident_id):
    db = get_db()
    data = request.get_json() or {}
    minutes = int(data.get("minutes") or 30)
    muted_until = (datetime.utcnow() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        '''
        UPDATE health_incidents
        SET muted_until = ?
        WHERE id = ?
        ''',
        (muted_until, incident_id)
    )
    db.commit()
    return jsonify({"status": "muted", "muted_until": muted_until})

@app.route('/api/health/incidents/<int:incident_id>/ticket', methods=['POST'])
@login_required
@require_permission('health.manage')
def health_incident_ticket(incident_id):
    db = get_db()
    incident = db.execute(
        '''
        SELECT i.*, d.name
        FROM health_incidents i
        JOIN health_check_definitions d ON d.id = i.check_id
        WHERE i.id = ?
        ''',
        (incident_id,)
    ).fetchone()
    if not incident:
        return jsonify({"error": "Incident nicht gefunden"}), 404
    title = f"Health Incident: {incident['name']}"
    description = (
        f"Incident für Check {incident['name']}.\n"
        f"Status: {incident['status']}\n"
        f"Seit: {incident['opened_at']}\n"
        f"Aktuell: {incident['last_status']}"
    )
    creator_id = get_current_user_id(db)
    cursor = db.execute(
        '''
        INSERT INTO tickets (title, description, priority, status, requester_name, created_by_user_id, created_by, tags)
        VALUES (?, ?, ?, 'open', ?, ?, ?, ?)
        ''',
        (
            title,
            description,
            "high",
            session.get("username"),
            creator_id,
            session.get("username"),
            json.dumps(["health", "incident"])
        )
    )
    ticket_id = cursor.lastrowid
    db.execute(
        '''
        UPDATE health_incidents
        SET ticket_id = ?
        WHERE id = ?
        ''',
        (ticket_id, incident_id)
    )
    db.commit()
    return jsonify({"status": "ticket_created", "ticket_id": ticket_id})

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
        raw_category_id = data.get('category_id')
        category_id = normalize_optional_int(raw_category_id)
        priority = (data.get('priority') or 'normal').strip()
        status = (data.get('status') or 'open').strip()
        escalation_level = int(data.get('escalation_level') or 0)
        current_user = access.get("user") or {}
        current_username = str(current_user.get("username") or session.get('username') or '').strip()
        requester_name = current_username
        requester_email = normalize_email(current_user.get("email") or "")
        assignee = (data.get('assignee') or '').strip()
        assignee_email = (data.get('assignee_email') or '').strip()
        due_date = (data.get('due_date') or '').strip()
        resolution_action = (data.get('resolution_action') or '').strip()
        resolution_outcome = (data.get('resolution_outcome') or '').strip()
        resolution_notes = (data.get('resolution_notes') or '').strip()
        if not user_can('tickets.update'):
            status = 'open'
            assignee = ''
            assignee_email = ''
            due_date = ''
            escalation_level = 0
            resolution_action = ''
            resolution_outcome = ''
            resolution_notes = ''
        tags = json.dumps(data.get('tags') or [])
        custom_fields = json.dumps(data.get('custom_fields') or [])
        asset_ids = data.get('asset_ids') or []
        resolved_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if is_closed_status(status) else None
        field_errors = {}
        if not title:
            field_errors["title"] = "Titel ist erforderlich"
        if not description:
            field_errors["description"] = "Beschreibung ist erforderlich"
        if raw_category_id not in (None, "") and category_id is None:
            field_errors["category_id"] = "Kategorie ist ungültig"
        if field_errors:
            return validation_error_response("Bitte Ticketangaben prüfen", field_errors)
        creator_id = current_user.get("id") or get_current_user_id(db)
        category = get_ticket_category(db, category_id)
        if category_id and not category:
            return validation_error_response(
                "Bitte Ticketangaben prüfen",
                {"category_id": "Kategorie ist ungültig"},
            )
        category_name = category["name"] if category else None
        try:
            change_ticket_id = validate_review_assignment(
                db,
                category,
                data.get("change_ticket_id"),
            )
        except ValueError as exc:
            return validation_error_response(
                "Bitte Ticketangaben prüfen",
                {"change_ticket_id": str(exc)},
            )
        if category_name and category_name.strip().lower() == "review":
            status = "open"
            resolved_at = None
        if category_name and category_name.strip().lower() == "change" and is_closed_status(status):
            return jsonify({
                "error": "Ein neuer Change kann erst nach abgeschlossenem Review gelöst oder geschlossen werden",
                "code": "change_review_required",
            }), 409
        cursor = db.execute('''
            INSERT INTO tickets (
                title, description, category_id, priority, status, requester_name,
                requester_email, created_by_user_id, created_by, assignee, assignee_email, due_date, escalation_level,
                resolved_at, resolution_action, resolution_outcome, resolution_notes, tags, custom_fields
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, description, category_id, priority, status, requester_name, requester_email,
            creator_id, current_username, assignee, assignee_email, due_date, escalation_level,
            resolved_at, resolution_action, resolution_outcome, resolution_notes, tags, custom_fields
        ))
        ticket_id = cursor.lastrowid
        for asset_id in asset_ids:
            db.execute('''
                INSERT OR IGNORE INTO ticket_assets (ticket_id, asset_id)
                VALUES (?, ?)
            ''', (ticket_id, asset_id))
        new_ticket = {
            "id": ticket_id,
            "title": title,
            "description": description,
            "category_id": category_id,
            "priority": priority,
            "status": status,
            "requester_name": requester_name,
            "requester_email": requester_email,
            "created_by_user_id": creator_id,
            "created_by": current_username,
            "assignee": assignee,
            "assignee_email": assignee_email,
            "due_date": due_date
        }
        review_ticket_id = None
        if category_name and category_name.strip().lower() == "review":
            link_review_to_change(db, change_ticket_id, ticket_id, current_username)
        elif category_name and category_name.strip().lower() == "change":
            review_ticket_id = create_review_for_change(db, new_ticket, actor=current_username)
        if should_auto_create_roadmap(category_name):
            create_roadmap_for_ticket(db, new_ticket, category_name, created_by=current_username)
        log_activity(db, "create", "ticket", ticket_id, {"title": title})
        db.commit()
        ticket = fetch_ticket(db, ticket_id)
        if ticket:
            ticket = normalize_ticket_row(ticket)
            trigger_ticket_notifications(db, "created", ticket, actor=current_username)
        return jsonify({
            "status": "created",
            "id": ticket_id,
            "review_ticket_id": review_ticket_id,
            "change_ticket_id": change_ticket_id,
        }), 201

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
        owner_filter = '(t.created_by_user_id = ? OR (t.created_by_user_id IS NULL AND t.created_by = ?))'
        filters.append(owner_filter)
        params.extend([access["user"]["id"], access["user"]["username"]])
    if not access["is_superuser"] and 'tickets.view_all' not in access["permissions"]:
        owner_filter = '(t.created_by_user_id = ? OR (t.created_by_user_id IS NULL AND t.created_by = ?))'
        filters.append(owner_filter)
        params.extend([access["user"]["id"], access["user"]["username"]])
    if search:
        search_term = search.lstrip("#").strip()
        like_search = f'%{search_term}%'
        search_filters = [
            "t.title LIKE ?",
            "t.description LIKE ?",
            "t.requester_name LIKE ?",
            "t.requester_email LIKE ?",
            "t.created_by LIKE ?",
            "t.assignee LIKE ?",
            "t.assignee_email LIKE ?",
            "c.name LIKE ?",
            '''
            EXISTS (
                SELECT 1
                FROM ticket_assets ta
                JOIN assets a ON a.id = ta.asset_id
                LEFT JOIN asset_categories ac ON ac.id = a.category_id
                WHERE ta.ticket_id = t.id
                  AND (
                    a.name LIKE ?
                    OR a.notes LIKE ?
                    OR a.specs LIKE ?
                    OR ac.name LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM asset_devices ad
                        JOIN devices d ON d.id = ad.device_id
                        LEFT JOIN locations l ON l.id = d.location_id
                        WHERE ad.asset_id = a.id
                          AND (
                            d.name LIKE ?
                            OR d.serial_number LIKE ?
                            OR d.specs LIKE ?
                            OR l.name LIKE ?
                          )
                    )
                  )
            )
            ''',
        ]
        params.extend([like_search] * 16)
        if search_term.isdigit():
            search_filters.insert(0, "t.id = ?")
            params.insert(len(params) - 16, int(search_term))
        filters.append(f"({' OR '.join(search_filters)})")

    sort_columns = {
        'id': 't.id',
        'status': 't.status',
        'priority': 't.priority',
        'title': 't.title',
        'requester': 't.requester_name',
        'assignee': 't.assignee',
        'category': 'c.name',
        'created_at': 't.created_at',
        'updated_at': 't.updated_at',
        'due_date': 't.due_date',
    }
    sort_by = request.args.get('sort', 'updated_at')
    sort_direction = 'ASC' if request.args.get('direction', 'desc').lower() == 'asc' else 'DESC'
    queue = request.args.get('queue')
    if queue == 'my-work':
        filters.append('(LOWER(COALESCE(t.assignee, "")) = LOWER(?) OR t.created_by_user_id = ?)')
        params.extend([access["user"]["username"], access["user"]["id"]])
        filters.append("t.status NOT IN ('closed', 'resolved')")
    elif queue == 'all-open':
        filters.append("t.status NOT IN ('closed', 'resolved')")
    elif queue == 'unassigned':
        filters.append("(t.assignee IS NULL OR TRIM(t.assignee) = '')")
        filters.append("t.status NOT IN ('closed', 'resolved')")
    elif queue == 'mine':
        filters.append('LOWER(COALESCE(t.assignee, "")) = LOWER(?)')
        params.append(access["user"]["username"])
        filters.append("t.status NOT IN ('closed', 'resolved')")
    elif queue == 'overdue':
        filters.append("t.due_date IS NOT NULL AND t.due_date != '' AND date(t.due_date) < date('now')")
        filters.append("t.status NOT IN ('closed', 'resolved')")
    elif queue == 'due-today':
        filters.append("date(t.due_date) = date('now')")
    elif queue == 'escalated':
        filters.append('COALESCE(t.escalation_level, 0) > 0')
    elif queue == 'waiting':
        filters.append("t.status IN ('pending', 'waiting', 'waiting_customer', 'waiting_internal')")
    elif queue == 'recently-closed':
        filters.append("t.status IN ('closed', 'resolved')")
        filters.append("datetime(COALESCE(t.resolved_at, t.updated_at)) >= datetime('now', '-7 days')")

    base_from = '''
        FROM tickets t
        LEFT JOIN ticket_categories c ON t.category_id = c.id
    '''
    where_clause = (' WHERE ' + ' AND '.join(filters)) if filters else ''
    query = '''
        SELECT t.*, c.name as category_name, c.color as category_color,
               (SELECT COUNT(*) FROM ticket_assets ta WHERE ta.ticket_id = t.id) AS asset_count
    ''' + base_from + where_clause
    query += f' ORDER BY {sort_columns.get(sort_by, "t.updated_at")} {sort_direction}, t.id DESC'

    paginate = 'page' in request.args or 'per_page' in request.args
    if paginate:
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(10, request.args.get('per_page', 25, type=int)))
        total = db.execute('SELECT COUNT(*) ' + base_from + where_clause, params).fetchone()[0]
        query += ' LIMIT ? OFFSET ?'
        rows = db.execute(query, [*params, per_page, (page - 1) * per_page]).fetchall()
        return jsonify({
            "items": [normalize_ticket_row(row) for row in rows],
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max(1, (total + per_page - 1) // per_page),
        })

    rows = db.execute(query, params).fetchall()
    tickets = [annotate_ticket_access(normalize_ticket_row(row), access) for row in rows]
    return jsonify(tickets)

@app.route('/api/tickets/queues', methods=['GET'])
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own')
def ticket_queue_counts():
    db = get_db()
    access = get_user_access(db)
    scope = ''
    params = []
    if not access["is_superuser"] and 'tickets.view_all' not in access["permissions"]:
        scope = ' AND (created_by_user_id = ? OR (created_by_user_id IS NULL AND created_by = ?))'
        params = [access["user"]["id"], access["user"]["username"]]
    username = access["user"]["username"]
    definitions = {
        "my-work": ("status NOT IN ('closed', 'resolved') AND (LOWER(COALESCE(assignee, '')) = LOWER(?) OR created_by_user_id = ?)", [username, access["user"]["id"]]),
        "unassigned": ("status NOT IN ('closed', 'resolved') AND (assignee IS NULL OR TRIM(assignee) = '')", []),
        "mine": ("status NOT IN ('closed', 'resolved') AND LOWER(COALESCE(assignee, '')) = LOWER(?)", [username]),
        "all-open": ("status NOT IN ('closed', 'resolved')", []),
        "waiting": ("status IN ('pending', 'waiting', 'waiting_customer', 'waiting_internal')", []),
        "overdue": ("status NOT IN ('closed', 'resolved') AND due_date != '' AND date(due_date) < date('now')", []),
        "escalated": ("COALESCE(escalation_level, 0) > 0", []),
        "due-today": ("date(due_date) = date('now')", []),
        "recently-closed": ("status IN ('closed', 'resolved') AND datetime(COALESCE(resolved_at, updated_at)) >= datetime('now', '-7 days')", []),
    }
    counts = {}
    for key, (condition, condition_params) in definitions.items():
        counts[key] = db.execute(
            f'SELECT COUNT(*) FROM tickets WHERE {condition}{scope}',
            [*condition_params, *params],
        ).fetchone()[0]
    return jsonify(counts)

@app.route('/api/tickets/bulk', methods=['PATCH'])
@login_required
@require_permission('tickets.update')
def bulk_update_tickets():
    db = get_db()
    data = request.get_json() or {}
    ticket_ids = sorted({int(value) for value in data.get('ticket_ids', []) if str(value).isdigit()})
    allowed = {'status', 'priority', 'assignee', 'category_id', 'due_date', 'escalation_level'}
    changes = {key: value for key, value in (data.get('changes') or {}).items() if key in allowed}
    if not ticket_ids or not changes:
        return jsonify({"error": "Tickets und Änderungen sind erforderlich"}), 400
    placeholders = ','.join('?' for _ in ticket_ids)
    target_rows = db.execute(
        f'''
        SELECT t.*, c.name AS category_name, c.color AS category_color
        FROM tickets t
        LEFT JOIN ticket_categories c ON c.id = t.category_id
        WHERE t.id IN ({placeholders})
        ''',
        ticket_ids,
    ).fetchall()
    target_tickets = [dict(row) for row in target_rows]
    if len(target_tickets) != len(ticket_ids):
        return jsonify({"error": "Mindestens ein Ticket wurde nicht gefunden"}), 404

    requested_status = str(changes.get("status") or "").strip()
    if requested_status and is_closed_status(requested_status):
        blocked = []
        for ticket in target_tickets:
            gate_error = ensure_change_can_close(db, ticket)
            if gate_error:
                blocked.append(gate_error)
        if blocked:
            return jsonify({
                "error": "Mindestens ein Change wartet noch auf ein abgeschlossenes Review",
                "code": "change_review_required",
                "blocked": blocked,
            }), 409

    requested_category = None
    if "category_id" in changes:
        requested_category = get_ticket_category(db, normalize_optional_int(changes["category_id"]))
        if not requested_category:
            return validation_error_response(
                "Bitte Ticketangaben prüfen",
                {"category_id": "Kategorie ist ungültig"},
            )
        if requested_category["name"].strip().lower() == "review":
            return validation_error_response(
                "Reviews müssen einzeln erstellt werden",
                {"change_ticket_id": "Für jedes Review muss ein Change ausgewählt werden"},
            )
        for ticket in target_tickets:
            relation = get_ticket_review_relation(db, ticket["id"])
            if relation and normalize_optional_int(changes["category_id"]) != ticket.get("category_id"):
                return jsonify({
                    "error": "Die Kategorie verknüpfter Change-/Review-Tickets kann nicht per Mehrfachbearbeitung geändert werden",
                    "code": "ticket_review_relation_locked",
                    "ticket_id": ticket["id"],
                }), 409

    if "category_id" in changes:
        changes["category_id"] = normalize_optional_int(changes["category_id"])
    assignments = ', '.join(f'{key} = ?' for key in changes)
    if requested_status:
        assignments += ", resolved_at = ?"
        resolved_at = (
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            if is_closed_status(requested_status)
            else None
        )
        update_values = [*changes.values(), resolved_at, *ticket_ids]
    else:
        update_values = [*changes.values(), *ticket_ids]
    db.execute(
        f'UPDATE tickets SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})',
        update_values,
    )
    for ticket_id in ticket_ids:
        log_activity(db, 'bulk_update', 'ticket', ticket_id, changes)
    if requested_category and requested_category["name"].strip().lower() == "change":
        for ticket_id in ticket_ids:
            change_ticket = fetch_ticket(db, ticket_id)
            create_review_for_change(db, change_ticket, actor=session.get("username"))
    db.commit()
    return jsonify({"status": "updated", "count": len(ticket_ids)})

@app.route('/api/ticket-views', methods=['GET', 'POST'])
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own')
def saved_ticket_views():
    db = get_db()
    user_id = get_current_user_id(db)
    if request.method == 'GET':
        rows = db.execute(
            'SELECT * FROM saved_ticket_views WHERE user_id = ? OR is_team_shared = 1 ORDER BY is_favorite DESC, name',
            (user_id,),
        ).fetchall()
        return jsonify([{
            **dict(row),
            "filters": safe_json_load(row["filters_json"], {}),
            "columns": safe_json_load(row["columns_json"], []),
        } for row in rows])
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Name ist erforderlich"}), 400
    if data.get('is_default'):
        db.execute('UPDATE saved_ticket_views SET is_default = 0 WHERE user_id = ?', (user_id,))
    cursor = db.execute('''
        INSERT INTO saved_ticket_views (
            user_id, name, filters_json, columns_json, sort_by, sort_direction,
            is_favorite, is_default, is_team_shared
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, name, json.dumps(data.get('filters') or {}), json.dumps(data.get('columns') or []),
        data.get('sort_by') or 'updated_at', data.get('sort_direction') or 'desc',
        1 if data.get('is_favorite') else 0, 1 if data.get('is_default') else 0,
        1 if data.get('is_team_shared') and user_can('tickets.update') else 0,
    ))
    db.commit()
    return jsonify({"status": "created", "id": cursor.lastrowid}), 201

@app.route('/api/ticket-views/<int:view_id>', methods=['DELETE'])
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own')
def delete_saved_ticket_view(view_id):
    db = get_db()
    cursor = db.execute(
        'DELETE FROM saved_ticket_views WHERE id = ? AND user_id = ?',
        (view_id, get_current_user_id(db)),
    )
    db.commit()
    return jsonify({"status": "deleted", "count": cursor.rowcount})

@app.route('/api/tickets/reviewable-changes', methods=['GET'])
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own', 'tickets.create')
def reviewable_change_tickets():
    db = get_db()
    access = get_user_access(db)
    search = (request.args.get("search") or "").strip()
    filters = [
        "LOWER(c.name) = 'change'",
        "t.status NOT IN ('closed', 'resolved', 'done')",
        "l.id IS NULL",
    ]
    params = []
    if not access["is_superuser"] and "tickets.view_all" not in access["permissions"]:
        filters.append(
            "(t.created_by_user_id = ? OR (t.created_by_user_id IS NULL AND t.created_by = ?))"
        )
        params.extend([access["user"]["id"], access["user"]["username"]])
    if search:
        if search.lstrip("#").isdigit():
            filters.append("(t.id = ? OR t.title LIKE ?)")
            params.extend([int(search.lstrip("#")), f"%{search}%"])
        else:
            filters.append("t.title LIKE ?")
            params.append(f"%{search}%")
    rows = db.execute(
        f'''
        SELECT t.id, t.title, t.status, t.priority, t.assignee, t.updated_at
        FROM tickets t
        JOIN ticket_categories c ON c.id = t.category_id
        LEFT JOIN ticket_review_links l ON l.change_ticket_id = t.id
        WHERE {' AND '.join(filters)}
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 100
        ''',
        params,
    ).fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/ticket-assets/search', methods=['GET'])
@login_required
@require_permissions('tickets.view_all', 'tickets.view_own', 'tickets.create')
def search_ticket_assets():
    db = get_db()
    search = (request.args.get('search') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(50, max(10, request.args.get('per_page', 20, type=int)))
    filters, params = [], []
    if search:
        filters.append('''(
            a.name LIKE ? OR a.specs LIKE ? OR EXISTS (
                SELECT 1
                FROM asset_devices ad
                JOIN devices d ON d.id = ad.device_id
                LEFT JOIN locations l ON l.id = d.location_id
                WHERE ad.asset_id = a.id
                  AND (d.name LIKE ? OR d.serial_number LIKE ? OR l.name LIKE ?)
            )
        )''')
        params.extend([f'%{search}%'] * 5)
    where_clause = (' WHERE ' + ' AND '.join(filters)) if filters else ''
    base = '''
        FROM assets a
        LEFT JOIN asset_categories c ON c.id = a.category_id
    '''
    total = db.execute('SELECT COUNT(*) ' + base + where_clause, params).fetchone()[0]
    rows = db.execute(
        '''SELECT a.*, c.name AS category_name
        ''' + base + where_clause + ' ORDER BY a.name LIMIT ? OFFSET ?',
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    return jsonify({
        "items": build_asset_summaries(db, rows),
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    })

def ticket_context_terms(ticket):
    ignored_terms = {
        "aber", "alle", "auch", "beim", "dass", "deine", "der", "den", "dem", "des", "die",
        "eine", "einem", "einen", "einer", "eines", "für", "habe", "hier", "ihre", "ihren",
        "ist", "mit", "nach", "nicht", "noch", "oder", "sich", "sind", "ticket", "und", "von",
        "wird", "wurde", "zum", "zur",
    }
    source = f"{ticket.get('title') or ''} {ticket.get('description') or ''}".casefold()
    terms = []
    for term in re.findall(r"[\w-]+", source, flags=re.UNICODE):
        if len(term) < 4 or term in ignored_terms or term.isdigit() or term in terms:
            continue
        terms.append(term)
        if len(terms) == 6:
            break
    return terms

def ticket_context_preview(value, limit=240):
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 1].rstrip()}…"

def build_ticket_work_context(db, ticket, access):
    """Find reusable, visible knowledge without crossing ticket permission boundaries."""
    terms = ticket_context_terms(ticket)
    work_context = {"knowledge_entries": [], "similar_resolved_tickets": []}
    knowledge_allowed = access["is_superuser"] or bool(
        {"knowledge.view", "knowledge.manage"}.intersection(access["permissions"])
    )

    if knowledge_allowed:
        knowledge_filters = ["ke.related_ticket_id = ?"]
        knowledge_params = [ticket["id"]]
        if terms:
            matching_terms = []
            for term in terms:
                matching_terms.append(
                    "(lower(ke.title) LIKE ? OR lower(ke.summary) LIKE ? OR lower(ke.content) LIKE ?)"
                )
                like = f"%{term}%"
                knowledge_params.extend([like, like, like])
            knowledge_filters.append("(" + " OR ".join(matching_terms) + ")")
        knowledge_rows = db.execute(
            f'''
            SELECT ke.id, ke.title, ke.summary, ke.content, ke.category_id, ke.related_ticket_id,
                   ke.created_by, ke.created_at, ke.updated_at, kc.name AS category_name
            FROM knowledge_entries ke
            LEFT JOIN knowledge_categories kc ON kc.id = ke.category_id
            WHERE {' OR '.join(knowledge_filters)}
            ORDER BY CASE WHEN ke.related_ticket_id = ? THEN 0 ELSE 1 END,
                     ke.updated_at DESC, ke.created_at DESC
            LIMIT 60
            ''',
            [*knowledge_params, ticket["id"]],
        ).fetchall()
        knowledge_entries = []
        for row in knowledge_rows:
            haystack = f"{row['title'] or ''} {row['summary'] or ''} {row['content'] or ''}".casefold()
            score = sum(1 for term in terms if term in haystack)
            if row["related_ticket_id"] == ticket["id"]:
                score += 100
            knowledge_entries.append({
                "id": row["id"],
                "title": row["title"],
                "summary": ticket_context_preview(row["summary"] or row["content"]),
                "category_name": row["category_name"],
                "related_ticket_id": row["related_ticket_id"],
                "updated_at": row["updated_at"] or row["created_at"],
                "score": score,
            })
        knowledge_entries.sort(key=lambda item: (item["score"], item["updated_at"] or "", item["id"]), reverse=True)
        work_context["knowledge_entries"] = knowledge_entries[:6]

    resolved_filters = ["t.id != ?", "lower(t.status) IN ('resolved', 'closed', 'done')"]
    resolved_params = [ticket["id"]]
    term_filters = []
    for term in terms:
        term_filters.append("(lower(t.title) LIKE ? OR lower(t.description) LIKE ?)")
        like = f"%{term}%"
        resolved_params.extend([like, like])
    if term_filters:
        if ticket.get("category_id"):
            resolved_filters.append("(t.category_id = ? OR " + " OR ".join(term_filters) + ")")
            resolved_params.insert(1, ticket["category_id"])
        else:
            resolved_filters.append("(" + " OR ".join(term_filters) + ")")
    elif ticket.get("category_id"):
        resolved_filters.append("t.category_id = ?")
        resolved_params.append(ticket["category_id"])
    else:
        return work_context

    candidate_rows = db.execute(
        f'''
        SELECT t.*, c.name AS category_name
        FROM tickets t
        LEFT JOIN ticket_categories c ON c.id = t.category_id
        WHERE {' AND '.join(resolved_filters)}
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 80
        ''',
        resolved_params,
    ).fetchall()
    similar_tickets = []
    for row in candidate_rows:
        candidate = dict(row)
        if not ensure_ticket_access(candidate, access):
            continue
        haystack = f"{candidate.get('title') or ''} {candidate.get('description') or ''}".casefold()
        score = sum(1 for term in terms if term in haystack)
        if ticket.get("category_id") and candidate.get("category_id") == ticket.get("category_id"):
            score += 1
        resolution = (
            candidate.get("resolution_outcome")
            or candidate.get("resolution_notes")
            or candidate.get("resolution_action")
            or "Keine dokumentierte Lösung hinterlegt."
        )
        similar_tickets.append({
            "id": candidate["id"],
            "title": candidate["title"],
            "category_name": candidate.get("category_name"),
            "status": candidate["status"],
            "resolution": ticket_context_preview(resolution),
            "updated_at": candidate.get("updated_at"),
            "score": score,
        })
    similar_tickets.sort(key=lambda item: (item["score"], item["updated_at"] or "", item["id"]), reverse=True)
    work_context["similar_resolved_tickets"] = similar_tickets[:5]
    return work_context

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
        ticket = annotate_ticket_access(normalize_ticket_row(ticket), access)
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
        ticket_assets = fetch_ticket_assets(db, ticket_id)
        ticket['assets'] = ticket_assets
        ticket['asset_ids'] = [asset["id"] for asset in ticket_assets]
        roadmap = fetch_roadmap_for_ticket(db, ticket_id)
        if roadmap:
            roadmap["steps"] = fetch_roadmap_steps(db, roadmap["id"])
        ticket['roadmap'] = roadmap
        ticket['review_relation'] = get_ticket_review_relation(db, ticket_id)
        ticket['work_context'] = build_ticket_work_context(db, ticket, access)
        activities = db.execute(
            '''
            SELECT id, username, action, details, created_at
            FROM activity_log
            WHERE entity_type = 'ticket' AND entity_id = ?
            ORDER BY created_at DESC, id DESC
            ''',
            (ticket_id,),
        ).fetchall()
        ticket['activity'] = [normalize_ticket_activity(row) for row in activities]
        return jsonify(ticket)

    if request.method == 'PUT':
        can_update = user_can('tickets.update')
        can_update_own = user_can('tickets.update_own')
        if not can_update and not (can_update_own and is_ticket_owner(ticket, access)):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        if "created_by" in data or "created_by_user_id" in data:
            return jsonify({"error": "Ticket-Ersteller kann nicht geändert werden"}), 400
        expected_updated_at = str(data.get("updated_at") or "").strip()
        if expected_updated_at and expected_updated_at != str(ticket.get("updated_at") or ""):
            return jsonify({
                "error": "Das Ticket wurde zwischenzeitlich geändert. Bitte aktuelle Daten laden und die Änderung erneut prüfen.",
                "code": "ticket_update_conflict",
                "ticket_id": ticket_id,
                "latest_updated_at": ticket.get("updated_at"),
            }), 409
        title = (data.get('title') or ticket['title']).strip()
        description = (data.get('description') or ticket['description']).strip()
        raw_category_id = data.get('category_id') if 'category_id' in data else ticket.get('category_id')
        category_id = normalize_optional_int(raw_category_id)
        priority = (data.get('priority') or ticket['priority']).strip()
        status = (data.get('status') or ticket['status']).strip()
        escalation_level = int(data.get('escalation_level') or ticket.get('escalation_level') or 0)
        requester_name = (data.get('requester_name') or ticket.get('requester_name') or '').strip()
        requester_email = (data.get('requester_email') or ticket.get('requester_email') or '').strip()
        assignee = (data.get('assignee') or ticket.get('assignee') or '').strip()
        assignee_email = (data.get('assignee_email') or ticket.get('assignee_email') or '').strip()
        due_date = (data.get('due_date') or ticket.get('due_date') or '').strip()
        resolution_action = (data.get('resolution_action') or ticket.get('resolution_action') or '').strip()
        resolution_outcome = (data.get('resolution_outcome') or ticket.get('resolution_outcome') or '').strip()
        resolution_notes = (data.get('resolution_notes') or ticket.get('resolution_notes') or '').strip()
        field_errors = {}
        if not title:
            field_errors["title"] = "Titel ist erforderlich"
        if not description:
            field_errors["description"] = "Beschreibung ist erforderlich"
        if raw_category_id not in (None, "") and category_id is None:
            field_errors["category_id"] = "Kategorie ist ungültig"
        if field_errors:
            return validation_error_response("Bitte Ticketangaben prüfen", field_errors)
        category = get_ticket_category(db, category_id)
        if category_id and not category:
            return validation_error_response(
                "Bitte Ticketangaben prüfen",
                {"category_id": "Kategorie ist ungültig"},
            )
        category_name = category["name"] if category else None
        existing_relation = get_ticket_review_relation(db, ticket_id)
        category_changed = category_id != ticket.get("category_id")
        if category_changed and existing_relation:
            return jsonify({
                "error": "Die Kategorie eines verknüpften Change-/Review-Tickets kann nicht geändert werden",
                "code": "ticket_review_relation_locked",
                "ticket_id": ticket_id,
            }), 409
        change_ticket_id = None
        if category_name and category_name.strip().lower() == "review":
            if existing_relation and existing_relation["role"] == "review":
                change_ticket_id = existing_relation["change_ticket_id"]
            else:
                try:
                    change_ticket_id = validate_review_assignment(
                        db,
                        category,
                        data.get("change_ticket_id"),
                        review_ticket_id=ticket_id,
                    )
                except ValueError as exc:
                    return validation_error_response(
                        "Bitte Ticketangaben prüfen",
                        {"change_ticket_id": str(exc)},
                    )
        candidate_ticket = {
            **ticket,
            "category_id": category_id,
            "category_name": category_name,
            "status": status,
        }
        if is_closed_status(status):
            gate_error = ensure_change_can_close(db, candidate_ticket)
            if gate_error:
                return jsonify(gate_error), 409
        if (
            existing_relation
            and existing_relation["role"] == "review"
            and is_closed_status(ticket.get("status"))
            and not is_closed_status(status)
            and is_closed_status(existing_relation["change_status"])
        ):
            return jsonify({
                "error": "Der Review kann erst wieder geöffnet werden, nachdem der zugehörige Change wieder geöffnet wurde",
                "code": "closed_change_review_locked",
                "change_ticket_id": existing_relation["change_ticket_id"],
            }), 409
        tags = json.dumps(data.get('tags') or json.loads(ticket.get('tags') or '[]'))
        custom_fields = json.dumps(data.get('custom_fields') or json.loads(ticket.get('custom_fields') or '[]'))
        asset_ids = data.get('asset_ids')
        status_changed = status != ticket.get('status')
        resolved_at = ticket.get('resolved_at')
        if status_changed:
            if is_closed_status(status):
                resolved_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            else:
                resolved_at = None
        changes = build_ticket_changes(ticket, {
            "title": title,
            "description": description,
            "category_name": category_name,
            "priority": priority,
            "status": status,
            "assignee": assignee,
            "assignee_email": assignee_email,
            "due_date": due_date,
            "requester_name": requester_name,
            "requester_email": requester_email,
        })
        previous_asset_ids = [
            row["asset_id"]
            for row in db.execute(
                "SELECT asset_id FROM ticket_assets WHERE ticket_id = ? ORDER BY asset_id",
                (ticket_id,),
            ).fetchall()
        ]
        if asset_ids is not None:
            normalized_asset_ids = sorted({
                asset_id
                for asset_id in (normalize_optional_int(value) for value in asset_ids)
                if asset_id is not None
            })
            if normalized_asset_ids != previous_asset_ids:
                changes.append({
                    "key": "asset_ids",
                    "label": "Assets",
                    "before": f"{len(previous_asset_ids)} verknüpft",
                    "after": f"{len(normalized_asset_ids)} verknüpft",
                })
            asset_ids = normalized_asset_ids

        update_sql = '''
            UPDATE tickets
            SET title = ?, description = ?, category_id = ?, priority = ?, status = ?,
                escalation_level = ?,
                requester_name = ?, requester_email = ?, assignee = ?, assignee_email = ?,
                due_date = ?, resolved_at = ?, resolution_action = ?, resolution_outcome = ?, resolution_notes = ?,
                tags = ?, custom_fields = ?, updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = ?
        '''
        update_params = [
            title, description, category_id, priority, status, escalation_level, requester_name, requester_email,
            assignee, assignee_email, due_date, resolved_at, resolution_action, resolution_outcome, resolution_notes,
            tags, custom_fields, ticket_id
        ]
        if expected_updated_at:
            update_sql += " AND updated_at = ?"
            update_params.append(expected_updated_at)
        update_cursor = db.execute(update_sql, update_params)
        if update_cursor.rowcount != 1:
            db.rollback()
            latest_ticket = fetch_ticket(db, ticket_id)
            return jsonify({
                "error": "Das Ticket wurde zwischenzeitlich geändert. Bitte aktuelle Daten laden und die Änderung erneut prüfen.",
                "code": "ticket_update_conflict",
                "ticket_id": ticket_id,
                "latest_updated_at": (latest_ticket or {}).get("updated_at"),
            }), 409
        if asset_ids is not None:
            db.execute('DELETE FROM ticket_assets WHERE ticket_id = ?', (ticket_id,))
            for asset_id in asset_ids:
                db.execute('''
                    INSERT OR IGNORE INTO ticket_assets (ticket_id, asset_id)
                    VALUES (?, ?)
                ''', (ticket_id, asset_id))
        review_ticket_id = None
        if category_name and category_name.strip().lower() == "review" and not existing_relation:
            link_review_to_change(db, change_ticket_id, ticket_id, session.get("username"))
        elif category_name and category_name.strip().lower() == "change":
            updated_for_review = {
                **candidate_ticket,
                "title": title,
                "priority": priority,
                "assignee": assignee,
                "due_date": due_date,
            }
            review_ticket_id = create_review_for_change(
                db,
                updated_for_review,
                actor=session.get("username"),
            )
        log_activity(db, "update", "ticket", ticket_id, {
            "title": title,
            "changes": changes,
        })
        if should_auto_create_roadmap(category_name):
            updated_ticket = {
                "id": ticket_id,
                "title": title,
                "description": description,
                "category_id": category_id,
                "priority": priority,
                "status": status,
                "requester_name": requester_name,
                "requester_email": requester_email,
                "created_by": ticket.get('created_by'),
                "assignee": assignee,
                "assignee_email": assignee_email,
                "due_date": due_date
            }
            create_roadmap_for_ticket(db, updated_ticket, category_name, created_by=session.get('username'))
        db.commit()
        updated_ticket = fetch_ticket(db, ticket_id)
        if updated_ticket:
            normalized = normalize_ticket_row(updated_ticket)
            event_type = resolve_ticket_event_type(changes)
            trigger_ticket_notifications(db, event_type, normalized, changes=changes, actor=session.get('username'))
        return jsonify({
            "status": "updated",
            "review_ticket_id": review_ticket_id,
            "change_ticket_id": change_ticket_id,
            "updated_at": (updated_ticket or {}).get("updated_at"),
        }), 200

    can_delete = user_can('tickets.delete')
    can_delete_own = user_can('tickets.delete_own')
    if not can_delete and not (can_delete_own and is_ticket_owner(ticket, access)):
        return jsonify({"error": "Keine Berechtigung"}), 403
    review_relation = get_ticket_review_relation(db, ticket_id)
    if review_relation:
        return jsonify({
            "error": "Verknüpfte Change-/Review-Tickets können aus Gründen der Nachvollziehbarkeit nicht gelöscht werden",
            "code": "ticket_review_relation_locked",
            "change_ticket_id": review_relation["change_ticket_id"],
            "review_ticket_id": review_relation["review_ticket_id"],
        }), 409
    db.execute('DELETE FROM ticket_comments WHERE ticket_id = ?', (ticket_id,))
    db.execute('DELETE FROM ticket_watchers WHERE ticket_id = ?', (ticket_id,))
    db.execute('DELETE FROM ticket_assets WHERE ticket_id = ?', (ticket_id,))
    db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
    log_activity(db, "delete", "ticket", ticket_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/tickets/merge', methods=['POST'])
@login_required
def merge_tickets():
    db = get_db()
    access = get_user_access(db)
    if not user_can('tickets.update'):
        return jsonify({"error": "Keine Berechtigung"}), 403

    data = request.get_json(silent=True) or {}
    target_ticket_id = normalize_optional_int(data.get('target_ticket_id'))
    raw_source_ids = data.get('source_ticket_ids') or []
    note = (data.get('note') or '').strip()

    if not isinstance(raw_source_ids, list):
        return validation_error_response(
            "Bitte mindestens zwei Tickets auswählen",
            {"source_ticket_ids": "Ungültige Ticket-Auswahl"},
        )

    ticket_ids = []
    invalid_ids = []
    for raw_ticket_id in raw_source_ids:
        parsed_id = normalize_optional_int(raw_ticket_id)
        if parsed_id is None:
            invalid_ids.append(raw_ticket_id)
            continue
        ticket_ids.append(parsed_id)
    ticket_ids = list(dict.fromkeys(ticket_ids))

    if invalid_ids:
        return validation_error_response(
            "Bitte mindestens zwei Tickets auswählen",
            {"source_ticket_ids": "Mindestens eine Ticket-ID ist ungültig"},
        )
    if target_ticket_id is None:
        return validation_error_response(
            "Ziel-Ticket fehlt",
            {"target_ticket_id": "Bitte ein Ziel-Ticket wählen"},
        )
    if target_ticket_id not in ticket_ids:
        ticket_ids.insert(0, target_ticket_id)
        ticket_ids = list(dict.fromkeys(ticket_ids))
    if len(ticket_ids) < 2:
        return validation_error_response(
            "Bitte mindestens zwei Tickets auswählen",
            {"source_ticket_ids": "Zum Zusammenführen werden mindestens zwei Tickets benötigt"},
        )

    target_ticket = fetch_ticket(db, target_ticket_id)
    if not target_ticket:
        return jsonify({"error": "Ziel-Ticket nicht gefunden"}), 404
    if not ensure_ticket_access(target_ticket, access):
        return jsonify({"error": "Keine Berechtigung"}), 403

    source_tickets = []
    for ticket_id in ticket_ids:
        ticket = fetch_ticket(db, ticket_id)
        if not ticket:
            return jsonify({"error": f"Ticket #{ticket_id} nicht gefunden"}), 404
        if not ensure_ticket_access(ticket, access):
            return jsonify({"error": "Keine Berechtigung"}), 403
        relation = get_ticket_review_relation(db, ticket_id)
        if relation:
            return jsonify({
                "error": "Verknüpfte Change-/Review-Tickets können nicht zusammengeführt werden",
                "code": "ticket_review_relation_locked",
                "ticket_id": ticket_id,
                "change_ticket_id": relation["change_ticket_id"],
                "review_ticket_id": relation["review_ticket_id"],
            }), 409
        if ticket_id != target_ticket_id:
            source_tickets.append(ticket)

    merged_ticket_ids = merge_ticket_records(
        db,
        target_ticket,
        source_tickets,
        actor=session.get('username'),
        note=note,
    )
    if not merged_ticket_ids:
        return validation_error_response(
            "Bitte mindestens zwei unterschiedliche Tickets auswählen",
            {"source_ticket_ids": "Keine zusammenführbaren Tickets ausgewählt"},
        )

    db.commit()
    return jsonify({
        "status": "merged",
        "target_ticket_id": target_ticket_id,
        "merged_ticket_ids": merged_ticket_ids,
    }), 200

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
        if not can_comment and not (can_comment_own and is_ticket_owner(ticket, access)):
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
        db.execute(
            "UPDATE tickets SET updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (ticket_id,),
        )
        log_activity(db, "comment", "ticket", ticket_id, {
            "is_internal": bool(is_internal),
            "preview": truncate_text(body, limit=180),
        })
        db.commit()
        ticket = fetch_ticket(db, ticket_id)
        if ticket:
            ticket = normalize_ticket_row(ticket)
            trigger_ticket_notifications(db, "commented", ticket, comment=body, actor=session.get('username'))
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
        if not can_watch and not (can_watch_own and is_ticket_owner(ticket, access)):
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
    if not can_watch and not (can_watch_own and is_ticket_owner(ticket, access)):
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

def serialize_knowledge_entry(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "content": row["content"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "related_ticket_id": row["related_ticket_id"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

@app.route('/api/knowledge/categories', methods=['GET', 'POST'])
@login_required
def knowledge_categories():
    db = get_db()
    if request.method == 'POST':
        if not user_can('knowledge.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        db.execute('''
            INSERT INTO knowledge_categories (name, description)
            VALUES (?, ?)
        ''', (name, description))
        log_activity(db, "create", "knowledge_category", details={"name": name})
        db.commit()
        return jsonify({"status": "created"}), 201

    if not user_can('knowledge.view') and not user_can('knowledge.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    categories = db.execute('''
        SELECT id, name, description, created_at
        FROM knowledge_categories
        ORDER BY name
    ''').fetchall()
    return jsonify([dict(row) for row in categories])

@app.route('/api/knowledge/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def knowledge_category_detail(category_id):
    db = get_db()
    if not user_can('knowledge.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'PUT':
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        result = db.execute('''
            UPDATE knowledge_categories
            SET name = ?, description = ?
            WHERE id = ?
        ''', (name, description, category_id))
        if result.rowcount == 0:
            return jsonify({"error": "Kategorie nicht gefunden"}), 404
        log_activity(db, "update", "knowledge_category", category_id, {"name": name})
        db.commit()
        return jsonify({"status": "updated"}), 200

    result = db.execute('DELETE FROM knowledge_categories WHERE id = ?', (category_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Kategorie nicht gefunden"}), 404
    log_activity(db, "delete", "knowledge_category", category_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/knowledge/entries', methods=['GET', 'POST'])
@login_required
def knowledge_entries():
    db = get_db()
    if request.method == 'POST':
        if not user_can('knowledge.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        summary = (data.get('summary') or '').strip()
        content = (data.get('content') or '').strip()
        category_id = data.get('category_id') or None
        related_ticket_id = data.get('related_ticket_id') or None
        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400
        db.execute('''
            INSERT INTO knowledge_entries (title, summary, content, category_id, related_ticket_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, summary, content, category_id, related_ticket_id, session.get('username')))
        log_activity(db, "create", "knowledge_entry", details={"title": title})
        db.commit()
        return jsonify({"status": "created"}), 201

    if not user_can('knowledge.view') and not user_can('knowledge.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    category_id = request.args.get('category_id')
    search = (request.args.get('search') or '').strip().lower()
    params = []
    where_clauses = []
    if category_id:
        where_clauses.append("ke.category_id = ?")
        params.append(category_id)
    if search:
        where_clauses.append("(lower(ke.title) LIKE ? OR lower(ke.summary) LIKE ? OR lower(ke.content) LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    entries = db.execute(f'''
        SELECT ke.id, ke.title, ke.summary, ke.content, ke.category_id, ke.related_ticket_id,
               ke.created_by, ke.created_at, ke.updated_at, kc.name AS category_name
        FROM knowledge_entries ke
        LEFT JOIN knowledge_categories kc ON kc.id = ke.category_id
        {where_sql}
        ORDER BY ke.updated_at DESC, ke.created_at DESC
    ''', params).fetchall()
    return jsonify([serialize_knowledge_entry(row) for row in entries])

@app.route('/api/knowledge/entries/<int:entry_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def knowledge_entry_detail(entry_id):
    db = get_db()
    if request.method == 'GET':
        if not user_can('knowledge.view') and not user_can('knowledge.manage'):
            return jsonify({"error": "Keine Berechtigung"}), 403
        entry = db.execute('''
            SELECT ke.id, ke.title, ke.summary, ke.content, ke.category_id, ke.related_ticket_id,
                   ke.created_by, ke.created_at, ke.updated_at, kc.name AS category_name
            FROM knowledge_entries ke
            LEFT JOIN knowledge_categories kc ON kc.id = ke.category_id
            WHERE ke.id = ?
        ''', (entry_id,)).fetchone()
        if not entry:
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        return jsonify(serialize_knowledge_entry(entry))

    if not user_can('knowledge.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    if request.method == 'PUT':
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        summary = (data.get('summary') or '').strip()
        content = (data.get('content') or '').strip()
        category_id = data.get('category_id') or None
        related_ticket_id = data.get('related_ticket_id') or None
        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400
        result = db.execute('''
            UPDATE knowledge_entries
            SET title = ?, summary = ?, content = ?, category_id = ?, related_ticket_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, summary, content, category_id, related_ticket_id, entry_id))
        if result.rowcount == 0:
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        log_activity(db, "update", "knowledge_entry", entry_id, {"title": title})
        db.commit()
        return jsonify({"status": "updated"}), 200

    result = db.execute('DELETE FROM knowledge_entries WHERE id = ?', (entry_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Eintrag nicht gefunden"}), 404
    log_activity(db, "delete", "knowledge_entry", entry_id)
    db.commit()
    return jsonify({"status": "deleted"}), 200

@app.route('/api/knowledge/suggestions', methods=['GET'])
@login_required
def knowledge_suggestions():
    db = get_db()
    if not user_can('knowledge.view') and not user_can('knowledge.manage'):
        return jsonify({"error": "Keine Berechtigung"}), 403
    query = (request.args.get('query') or '').strip().lower()
    ticket_id = request.args.get('ticket_id')
    if not query and not ticket_id:
        return jsonify([])
    where_clauses = []
    params = []
    if query:
        where_clauses.append("(lower(ke.title) LIKE ? OR lower(ke.summary) LIKE ? OR lower(ke.content) LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])
    if ticket_id:
        where_clauses.append("ke.related_ticket_id = ?")
        params.append(ticket_id)
    where_sql = "WHERE " + " OR ".join(where_clauses)
    entries = db.execute(f'''
        SELECT ke.id, ke.title, ke.summary, ke.content, ke.category_id, ke.related_ticket_id,
               ke.created_by, ke.created_at, ke.updated_at, kc.name AS category_name
        FROM knowledge_entries ke
        LEFT JOIN knowledge_categories kc ON kc.id = ke.category_id
        {where_sql}
        ORDER BY ke.updated_at DESC, ke.created_at DESC
        LIMIT 6
    ''', params).fetchall()
    return jsonify([serialize_knowledge_entry(row) for row in entries])

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
    settings_row = get_server_settings(get_db())
    settings, _ = serialize_server_settings(settings_row)
    return jsonify({
        "pro_enabled": bool(settings["proFeaturesEnabled"]),
        "pro_features": PRO_FEATURES,
        "free_features": FREE_FEATURES
    })

@app.route('/api/time-machine/changes', methods=['GET'])
@login_required
@require_permission('timemachine.view')
def time_machine_changes():
    db = get_db()
    activity_rows = db.execute('''
        SELECT id, action, entity_type, entity_id, details, created_at, username
        FROM activity_log
        ORDER BY created_at ASC
    ''').fetchall()

    action_labels = {
        "create": "erstellt",
        "update": "aktualisiert",
        "delete": "gelöscht",
        "comment": "kommentiert",
        "watch": "beobachtet",
        "unwatch": "Beobachtung beendet",
        "login": "angemeldet",
        "logout": "abgemeldet"
    }
    entity_labels = {
        "asset": "Asset-Eintrag",
        "asset_entry": "Asset-Eintrag",
        "asset_category": "Asset-Kategorie",
        "device": "Gerät",
        "ticket": "Ticket",
        "roadmap": "Roadmap",
        "roadmap_step": "Roadmap-Schritt",
        "dependency_link": "Dependency",
        "team": "Team",
        "department": "Abteilung",
        "software": "Software",
        "location": "Standort",
        "user": "Benutzer"
    }
    layer_map = {
        "asset": "assets",
        "asset_entry": "assets",
        "asset_category": "assets",
        "device": "devices",
        "ticket": "tickets",
        "roadmap": "roadmaps",
        "roadmap_step": "roadmaps",
        "dependency_link": "dependencies",
        "team": "organisation",
        "department": "organisation",
        "software": "assets",
        "location": "assets",
        "user": "organisation"
    }

    changes = []
    for row in activity_rows:
        try:
            details = json.loads(row["details"]) if row["details"] else {}
        except json.JSONDecodeError:
            details = {}
        action_label = action_labels.get(row["action"], row["action"])
        entity_label = entity_labels.get(row["entity_type"], row["entity_type"])
        timestamp = parse_time_machine_timestamp(row["created_at"])
        if not timestamp:
            continue
        changes.append({
            "key": f"activity-{row['id']}",
            "timestamp": timestamp.isoformat(),
            "title": format_time_machine_change(entity_label, action_label, details),
            "description": details.get("description") or details.get("notes") or row["action"],
            "layer": layer_map.get(row["entity_type"], "events"),
            "layer_label": entity_label,
            "source": "Aktivitätslog",
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "impact": details.get("impact", "n/a"),
            "is_planned": False
        })

    roadmap_rows = db.execute('''
        SELECT id, title, status, start_date, target_date, owner, created_at
        FROM roadmaps
        ORDER BY created_at ASC
    ''').fetchall()
    roadmap_step_rows = db.execute('''
        SELECT id, roadmap_id, title, status, due_date, created_at
        FROM roadmap_steps
        ORDER BY created_at ASC
    ''').fetchall()

    roadmaps = []
    for row in roadmap_rows:
        roadmaps.append({
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "start_date": row["start_date"],
            "target_date": row["target_date"],
            "owner": row["owner"]
        })

        start_timestamp = parse_time_machine_timestamp(row["start_date"]) or parse_time_machine_timestamp(row["created_at"])
        if start_timestamp:
            changes.append({
                "key": f"roadmap-start-{row['id']}",
                "timestamp": start_timestamp.isoformat(),
                "title": f"Roadmap gestartet · {row['title']}",
                "description": "Roadmap-Start geplant oder umgesetzt.",
                "layer": "roadmaps",
                "layer_label": "Roadmap",
                "source": "Roadmap",
                "entity_type": "roadmap",
                "entity_id": row["id"],
                "roadmap_id": row["id"],
                "impact": row["status"] or "planned",
                "is_planned": True
            })
        target_timestamp = parse_time_machine_timestamp(row["target_date"])
        if target_timestamp:
            changes.append({
                "key": f"roadmap-target-{row['id']}",
                "timestamp": target_timestamp.isoformat(),
                "title": f"Roadmap Zieltermin · {row['title']}",
                "description": "Geplanter Abschluss oder Meilenstein.",
                "layer": "roadmaps",
                "layer_label": "Roadmap",
                "source": "Roadmap",
                "entity_type": "roadmap",
                "entity_id": row["id"],
                "roadmap_id": row["id"],
                "impact": "target",
                "is_planned": True
            })

    for row in roadmap_step_rows:
        step_timestamp = parse_time_machine_timestamp(row["due_date"]) or parse_time_machine_timestamp(row["created_at"])
        if not step_timestamp:
            continue
        changes.append({
            "key": f"roadmap-step-{row['id']}",
            "timestamp": step_timestamp.isoformat(),
            "title": f"Roadmap-Schritt · {row['title']}",
            "description": "Geplanter Change aus Roadmap.",
            "layer": "roadmaps",
            "layer_label": "Roadmap",
            "source": "Roadmap",
            "entity_type": "roadmap_step",
            "entity_id": row["id"],
            "roadmap_id": row["roadmap_id"],
            "impact": row["status"] or "planned",
            "is_planned": True
        })

    ticket_rows = db.execute('''
        SELECT id, title, status, created_at, resolved_at
        FROM tickets
        ORDER BY created_at DESC
    ''').fetchall()
    tickets = [dict(row) for row in ticket_rows]

    timestamps = [parse_time_machine_timestamp(change["timestamp"]) for change in changes]
    timestamps = [ts for ts in timestamps if ts]
    now = datetime.utcnow()
    range_start = min(timestamps) if timestamps else now
    range_end = max(timestamps) if timestamps else now

    return jsonify({
        "changes": changes,
        "roadmaps": roadmaps,
        "tickets": tickets,
        "range": {
            "start": range_start.isoformat(),
            "end": range_end.isoformat()
        }
    })

@app.route('/api/time-machine/state', methods=['GET'])
@login_required
@require_permission('timemachine.view')
def time_machine_state():
    db = get_db()
    timestamp_raw = request.args.get('timestamp')
    timestamp = parse_time_machine_timestamp(timestamp_raw) or datetime.utcnow()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    assets = db.execute('''
        SELECT COUNT(*) as total
        FROM assets
        WHERE created_at <= ?
          AND (retirement_date IS NULL OR retirement_date = '' OR retirement_date > ?)
    ''', (timestamp_str, timestamp_str)).fetchone()["total"]
    devices = db.execute('''
        SELECT COUNT(*) as total
        FROM devices
        WHERE created_at <= ?
    ''', (timestamp_str,)).fetchone()["total"]
    tickets_total = db.execute('''
        SELECT COUNT(*) as total
        FROM tickets
        WHERE created_at <= ?
    ''', (timestamp_str,)).fetchone()["total"]
    tickets_open = db.execute('''
        SELECT COUNT(*) as total
        FROM tickets
        WHERE created_at <= ?
          AND (resolved_at IS NULL OR resolved_at = '' OR resolved_at > ?)
    ''', (timestamp_str, timestamp_str)).fetchone()["total"]
    roadmaps_total = db.execute('''
        SELECT COUNT(*) as total
        FROM roadmaps
        WHERE created_at <= ?
    ''', (timestamp_str,)).fetchone()["total"]
    dependencies_total = db.execute('''
        SELECT COUNT(*) as total
        FROM dependency_links
        WHERE created_at <= ?
    ''', (timestamp_str,)).fetchone()["total"]
    last_change_row = db.execute('''
        SELECT action, entity_type, details, created_at
        FROM activity_log
        WHERE created_at <= ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (timestamp_str,)).fetchone()
    last_change_label = "—"
    if last_change_row:
        entity_labels = {
            "asset": "Asset-Eintrag",
            "asset_entry": "Asset-Eintrag",
            "asset_category": "Asset-Kategorie",
            "device": "Gerät",
            "ticket": "Ticket",
            "roadmap": "Roadmap",
            "roadmap_step": "Roadmap-Schritt",
            "dependency_link": "Dependency",
            "team": "Team",
            "department": "Abteilung",
            "software": "Software",
            "location": "Standort",
            "user": "Benutzer"
        }
        action_labels = {
            "create": "erstellt",
            "update": "aktualisiert",
            "delete": "gelöscht",
            "comment": "kommentiert",
            "watch": "beobachtet",
            "unwatch": "Beobachtung beendet",
            "login": "angemeldet",
            "logout": "abgemeldet"
        }
        try:
            details = json.loads(last_change_row["details"]) if last_change_row["details"] else {}
        except json.JSONDecodeError:
            details = {}
        entity_label = entity_labels.get(last_change_row["entity_type"], last_change_row["entity_type"])
        action_label = action_labels.get(last_change_row["action"], last_change_row["action"])
        last_change_label = format_time_machine_change(entity_label, action_label, details)

    return jsonify({
        "timestamp": timestamp.isoformat(),
        "assets": assets,
        "devices": devices,
        "tickets": tickets_total,
        "tickets_open": tickets_open,
        "roadmaps": roadmaps_total,
        "dependencies": dependencies_total,
        "last_change": last_change_label
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

def scalar_int(db, query, params=()):
    row = db.execute(query, params).fetchone()
    if not row:
        return 0
    value = row[0] if not isinstance(row, dict) else next(iter(row.values()), 0)
    return int(value or 0)

def build_enterprise_workflow_hub(db):
    total_devices = scalar_int(db, "SELECT COUNT(*) FROM devices")
    total_assets = scalar_int(db, "SELECT COUNT(*) FROM assets")
    devices_missing_location = scalar_int(db, '''
        SELECT COUNT(*) FROM devices
        WHERE location_id IS NULL OR location_id = ''
    ''')
    devices_missing_serial = scalar_int(db, '''
        SELECT COUNT(*) FROM devices
        WHERE serial_number IS NULL OR TRIM(serial_number) = ''
    ''')
    devices_without_asset = scalar_int(db, '''
        SELECT COUNT(*)
        FROM devices d
        WHERE NOT EXISTS (
            SELECT 1 FROM asset_devices ad WHERE ad.device_id = d.id
        )
    ''')
    assets_missing_category = scalar_int(db, '''
        SELECT COUNT(*) FROM assets
        WHERE category_id IS NULL OR category_id = ''
    ''')
    assets_without_devices = scalar_int(db, '''
        SELECT COUNT(*)
        FROM assets a
        WHERE NOT EXISTS (
            SELECT 1 FROM asset_devices ad WHERE ad.asset_id = a.id
        )
    ''')
    assets_without_lifecycle = scalar_int(db, '''
        SELECT COUNT(*) FROM assets
        WHERE (acquisition_date IS NULL OR TRIM(acquisition_date) = '')
          AND (commissioning_date IS NULL OR TRIM(commissioning_date) = '')
          AND (warranty_end IS NULL OR TRIM(warranty_end) = '')
    ''')
    linked_assets = scalar_int(db, '''
        SELECT COUNT(*)
        FROM assets a
        WHERE EXISTS (SELECT 1 FROM asset_devices ad WHERE ad.asset_id = a.id)
           OR EXISTS (SELECT 1 FROM ticket_assets ta WHERE ta.asset_id = a.id)
           OR EXISTS (SELECT 1 FROM asset_relations ar WHERE ar.asset_id = a.id OR ar.related_asset_id = a.id)
           OR EXISTS (SELECT 1 FROM asset_assignments aa WHERE aa.asset_id = a.id)
           OR EXISTS (SELECT 1 FROM asset_services src WHERE src.asset_id = a.id)
           OR (a.purchase_order_id IS NOT NULL AND a.purchase_order_id != '')
    ''')

    issues_total = (
        devices_missing_location
        + devices_missing_serial
        + devices_without_asset
        + assets_missing_category
        + assets_without_devices
        + assets_without_lifecycle
    )
    denominator = max(total_devices + total_assets, 1)
    quality_score = max(0, min(100, round(100 - ((issues_total / denominator) * 28))))
    integration_score = round((linked_assets / max(total_assets, 1)) * 100) if total_assets else 100

    signals = [
        {
            "key": "device_identity",
            "label": "Geräte-Identität",
            "value": devices_missing_location + devices_missing_serial,
            "severity": "warning" if devices_missing_location or devices_missing_serial else "good",
            "icon": "monitor",
            "description": "Geräte ohne Standort oder Inventar-/Seriennummer bremsen Support, Audit und Übergabe.",
            "action_label": "Geräte prüfen",
            "target_url": "/?view=devices#device-inventory",
        },
        {
            "key": "asset_structure",
            "label": "Asset-Struktur",
            "value": assets_missing_category + assets_without_devices,
            "severity": "critical" if assets_missing_category else ("warning" if assets_without_devices else "good"),
            "icon": "package",
            "description": "Asset-Einträge sollten kategorisiert und mit Geräten, Komponenten oder Bestellungen verbunden sein.",
            "action_label": "Assets verknüpfen",
            "target_url": "/?view=assets",
        },
        {
            "key": "lifecycle",
            "label": "Lifecycle-Daten",
            "value": assets_without_lifecycle,
            "severity": "warning" if assets_without_lifecycle else "good",
            "icon": "clock",
            "description": "Beschaffung, Inbetriebnahme und Garantie fehlen noch bei Teilen des Bestands.",
            "action_label": "Lifecycle pflegen",
            "target_url": "/?view=assets",
        },
        {
            "key": "integration_depth",
            "label": "Verknüpfungstiefe",
            "value": integration_score,
            "severity": "critical" if integration_score < 35 else ("warning" if integration_score < 70 else "good"),
            "icon": "share-2",
            "description": "Je stärker Assets mit Tickets, Geräten, Services und Beschaffung verbunden sind, desto leichter führt das System durch den Workflow.",
            "action_label": "Abhängigkeiten öffnen",
            "target_url": "/dependencies",
            "unit": "%",
        },
    ]

    workflows = [
        {
            "key": "connect_inventory",
            "title": "Inventar zusammenführen",
            "description": "Geräte ohne Asset-Kontext und Assets ohne Gerätebezug nacheinander verbinden.",
            "count": devices_without_asset + assets_without_devices,
            "target_url": "/?view=assets",
            "action_label": "Verknüpfungen schließen",
            "icon": "link",
        },
        {
            "key": "clean_identity",
            "title": "Audit-fähige Gerätebasis",
            "description": "Standort, Kategorie und Inventar-/Seriennummer vollständig halten.",
            "count": devices_missing_location + devices_missing_serial,
            "target_url": "/?view=devices#device-inventory",
            "action_label": "Geräte bereinigen",
            "icon": "check-square",
        },
    ]

    if user_can('tickets.view_all') or user_can('tickets.view_own'):
        open_ticket_filter = "LOWER(COALESCE(status, '')) NOT IN ('resolved', 'closed')"
        open_tickets_without_assets = scalar_int(db, f'''
            SELECT COUNT(*)
            FROM tickets t
            WHERE {open_ticket_filter}
              AND NOT EXISTS (
                  SELECT 1 FROM ticket_assets ta WHERE ta.ticket_id = t.id
              )
        ''')
        overdue_tickets = scalar_int(db, f'''
            SELECT COUNT(*)
            FROM tickets
            WHERE {open_ticket_filter}
              AND due_date IS NOT NULL
              AND TRIM(due_date) != ''
              AND date(due_date) < date('now')
        ''')
        stale_tickets = scalar_int(db, f'''
            SELECT COUNT(*)
            FROM tickets
            WHERE {open_ticket_filter}
              AND datetime(updated_at) < datetime('now', '-14 days')
        ''')
        signals.append({
            "key": "service_context",
            "label": "Service-Kontext",
            "value": open_tickets_without_assets,
            "severity": "warning" if open_tickets_without_assets else "good",
            "icon": "life-buoy",
            "description": "Offene Tickets ohne Asset-Bezug erschweren Ursachenanalyse, Historie und Eskalation.",
            "action_label": "Tickets verknüpfen",
            "target_url": "/tickets?queue=all-open",
        })
        signals.append({
            "key": "service_risk",
            "label": "Service-Risiko",
            "value": overdue_tickets + stale_tickets,
            "severity": "critical" if overdue_tickets else ("warning" if stale_tickets else "good"),
            "icon": "alert-triangle",
            "description": "Überfällige oder länger nicht bewegte Tickets brauchen klare nächste Schritte.",
            "action_label": "Queues prüfen",
            "target_url": "/tickets?queue=overdue",
        })
        workflows.append({
            "key": "ticket_asset_context",
            "title": "Tickets mit Bestand verknüpfen",
            "description": "Offene Tickets direkt mit Assets verbinden, damit Verlauf, Anhänge und Verantwortung zusammenlaufen.",
            "count": open_tickets_without_assets,
            "target_url": "/tickets?queue=all-open",
            "action_label": "Service-Kontext schließen",
            "icon": "life-buoy",
        })

    if user_can('maintenance.view') or user_can('maintenance.manage'):
        overdue_maintenance = scalar_int(db, '''
            SELECT COUNT(*)
            FROM maintenance_tasks
            WHERE status = 'open'
              AND due_date IS NOT NULL
              AND TRIM(due_date) != ''
              AND date(due_date) < date('now')
        ''')
        open_maintenance = scalar_int(db, "SELECT COUNT(*) FROM maintenance_tasks WHERE status = 'open'")
        signals.append({
            "key": "maintenance",
            "label": "Wartung",
            "value": overdue_maintenance or open_maintenance,
            "severity": "critical" if overdue_maintenance else ("warning" if open_maintenance else "good"),
            "icon": "tool",
            "description": "Offene Wartungen sollten im Gerätekontext sichtbar abgearbeitet werden.",
            "action_label": "Geräte öffnen",
            "target_url": "/?view=devices#device-inventory",
        })

    if user_can('procurement.view') or user_can('procurement.manage'):
        expiring_contracts = scalar_int(db, '''
            SELECT COUNT(*)
            FROM contracts
            WHERE LOWER(COALESCE(status, 'active')) = 'active'
              AND end_date IS NOT NULL
              AND TRIM(end_date) != ''
              AND date(end_date) BETWEEN date('now') AND date('now', '+90 days')
        ''')
        overdue_orders = scalar_int(db, '''
            SELECT COUNT(*)
            FROM purchase_orders
            WHERE LOWER(COALESCE(status, '')) NOT IN ('received', 'closed', 'cancelled')
              AND expected_date IS NOT NULL
              AND TRIM(expected_date) != ''
              AND date(expected_date) < date('now')
        ''')
        signals.append({
            "key": "procurement",
            "label": "Beschaffung & Verträge",
            "value": expiring_contracts + overdue_orders,
            "severity": "critical" if overdue_orders else ("warning" if expiring_contracts else "good"),
            "icon": "shopping-cart",
            "description": "Ablaufende Verträge und verspätete Bestellungen gehören in denselben operativen Blick wie die betroffenen Assets.",
            "action_label": "Procurement öffnen",
            "target_url": "/procurement",
        })
        workflows.append({
            "key": "renewal_readiness",
            "title": "Renewals vorziehen",
            "description": "Verträge, Bestellungen und Asset-Lifecycle gemeinsam prüfen.",
            "count": expiring_contracts + overdue_orders,
            "target_url": "/procurement",
            "action_label": "Renewals prüfen",
            "icon": "repeat",
        })

    next_actions = sorted(workflows, key=lambda item: item["count"], reverse=True)[:4]
    status_label = "Stabil" if quality_score >= 85 and integration_score >= 70 else "Aufbau nötig"
    if quality_score < 65 or integration_score < 35:
        status_label = "Fokus erforderlich"

    return {
        "score": quality_score,
        "integration_score": integration_score,
        "status_label": status_label,
        "signals": signals,
        "next_actions": next_actions,
        "summary": {
            "devices": total_devices,
            "assets": total_assets,
            "linked_assets": linked_assets,
            "issues": issues_total,
        },
    }

@app.route('/api/enterprise/workflow-hub', methods=['GET'])
@login_required
@require_permissions('categories.view', 'categories.manage')
def enterprise_workflow_hub():
    return jsonify(build_enterprise_workflow_hub(get_db()))

@app.route('/api/users', methods=['GET', 'POST'])
@login_required
@require_permission('users.manage')
def manage_users():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        email = normalize_email(data.get('email') or '')
        role_ids = data.get('role_ids') or []
        if not username or not password:
            return jsonify({"error": "Benutzername und Passwort sind erforderlich"}), 400
        if email and not is_valid_email(email):
            return jsonify({"error": "Ungültige E-Mail-Adresse"}), 400
        if email:
            existing_email = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if existing_email:
                return jsonify({"error": "E-Mail bereits vergeben"}), 400
        min_length = get_password_min_length(db)
        if len(password) < min_length:
            return jsonify({"error": f"Passwort muss mindestens {min_length} Zeichen lang sein"}), 400
        if role_ids and not user_can('roles.assign'):
            return jsonify({"error": "Keine Berechtigung für Rollen"}), 403
        password_hash = generate_password_hash(password)
        try:
            cursor = db.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (username, email or None, password_hash))
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

    users = db.execute('SELECT id, username, email, otp_secret FROM users ORDER BY username').fetchall()
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

@app.route('/api/users/<int:user_id>', methods=['PUT', 'DELETE'])
@login_required
@require_permission('users.manage')
def remove_user(user_id):
    db = get_db()
    if request.method == 'PUT':
        data = request.get_json() or {}
        email = normalize_email(data.get('email') or '')
        if email and not is_valid_email(email):
            return jsonify({"error": "Ungültige E-Mail-Adresse"}), 400
        if email:
            existing_email = db.execute(
                'SELECT id FROM users WHERE email = ? AND id != ?',
                (email, user_id)
            ).fetchone()
            if existing_email:
                return jsonify({"error": "E-Mail bereits vergeben"}), 400
        result = db.execute(
            '''
            UPDATE users
            SET email = ?
            WHERE id = ?
            ''',
            (email or None, user_id)
        )
        if result.rowcount == 0:
            return jsonify({"error": "Benutzer nicht gefunden"}), 404
        log_activity(db, "update", "user_email", user_id, {"email": email or None})
        db.commit()
        return jsonify({"status": "updated", "email": email or None}), 200
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
    min_length = get_password_min_length(db)
    if len(password) < min_length:
        return jsonify({"error": f"Passwort muss mindestens {min_length} Zeichen lang sein"}), 400
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
        "email": access["user"].get("email"),
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

@app.route('/api/server-settings', methods=['GET', 'POST'])
@login_required
@require_permission('server_settings.manage')
def server_settings():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json() or {}
        current_settings, _ = serialize_server_settings(get_server_settings(db))
        payload = {
            "server": {
                "host": data.get("host"),
                "port": data.get("port"),
                "debug": data.get("debug")
            },
            "proFeaturesEnabled": data.get("pro_enabled"),
            "backup": {
                "enabled": data.get("backup_enabled"),
                "compress": data.get("backup_compress"),
                "schedule": data.get("backup_schedule"),
                "time": data.get("backup_time"),
                "retentionDays": data.get("backup_retention_days"),
                "directory": data.get("backup_location"),
                "notifyEmail": data.get("backup_notify_email"),
                "encrypt": data.get("backup_encrypt")
            },
            "updates": current_settings["updates"],
            "importExport": {
                "exportAllowed": data.get("allow_db_export"),
                "importAllowed": data.get("allow_db_import"),
                "exportFormat": data.get("export_format"),
                "importMode": data.get("import_mode"),
                "includeUploads": data.get("include_uploads")
            },
            "security": {
                "forceHttps": data.get("require_https"),
                "requireMfa": data.get("enforce_mfa"),
                "sessionTimeoutMinutes": data.get("session_timeout_minutes"),
                "maxFailedAttempts": data.get("max_failed_logins"),
                "lockoutMinutes": data.get("lockout_minutes"),
                "ipWhitelist": data.get("allowed_ip_ranges"),
                "minPasswordLength": data.get("password_min_length")
            }
        }
        settings_payload, errors = validate_settings_payload(payload)
        if errors:
            return jsonify({"error": "Ungültige Server-Einstellungen.", "details": errors}), 400
        try:
            persist_server_settings(db, settings_payload, session.get("username", "system"))
            schedule_backup_jobs(settings_payload)
            log_activity(db, "update", "server_settings", details={"source": "legacy_api"})
            db.commit()
            store_update_policy(settings_payload["updates"])
        except sqlite3.Error:
            db.rollback()
            raise
    settings = get_server_settings(db)
    return jsonify(serialize_server_settings_flat(settings))

@app.route('/api/settings/server', methods=['GET', 'PUT', 'PATCH'])
@login_required
@require_permission('server_settings.manage')
def server_settings_v2():
    db = get_db()
    settings_row = get_server_settings(db)
    current_settings, meta = serialize_server_settings(settings_row)
    if request.method == 'GET':
        return jsonify({"settings": current_settings, "meta": meta})

    payload = request.get_json() or {}
    if request.method == 'PATCH':
        merged_payload = merge_settings(current_settings, payload)
    else:
        merged_payload = payload
    settings_payload, errors = validate_settings_payload(merged_payload)
    if errors:
        return jsonify({"error": "Ungültige Server-Einstellungen.", "details": errors}), 400
    try:
        persist_server_settings(db, settings_payload, session.get("username", "system"))
        schedule_backup_jobs(settings_payload)
        log_activity(db, "update", "server_settings", details={"schema_version": SETTINGS_SCHEMA_VERSION})
        db.commit()
        store_update_policy(settings_payload["updates"])
    except sqlite3.Error:
        db.rollback()
        raise
    updated_settings, updated_meta = serialize_server_settings(get_server_settings(db))
    return jsonify({"settings": updated_settings, "meta": updated_meta})

@app.route('/api/settings/server/reload', methods=['POST'])
@login_required
@require_permission('server_settings.manage')
def server_settings_reload():
    settings_row = get_server_settings(get_db())
    settings, meta = serialize_server_settings(settings_row)
    return jsonify({
        "status": "pending_restart" if meta["pendingRestart"] else "ok",
        "pendingRestart": meta["pendingRestart"],
        "requiresRestartFields": meta["requiresRestartFields"]
    })

@app.route('/api/settings/server/health', methods=['GET'])
@login_required
@require_permission('server_settings.manage')
def server_settings_health():
    settings_row = get_server_settings(get_db())
    settings, meta = serialize_server_settings(settings_row)
    runtime = load_runtime_settings()
    return jsonify({
        "runtime": runtime,
        "settings": settings,
        "pendingRestart": meta["pendingRestart"]
    })

@app.route('/api/settings/server/history', methods=['GET'])
@login_required
@require_permission('server_settings.manage')
def server_settings_history():
    db = get_db()
    rows = db.execute(
        '''
        SELECT id, settings_json, created_at, created_by
        FROM server_settings_revisions
        ORDER BY id DESC
        LIMIT 20
        '''
    ).fetchall()
    revisions = []
    for row in rows:
        revisions.append({
            "id": row["id"],
            "createdAt": row["created_at"],
            "createdBy": row["created_by"],
            "settings": json.loads(row["settings_json"]) if row["settings_json"] else {}
        })
    return jsonify({"revisions": revisions})

@app.route('/api/inventory-links', methods=['GET', 'POST'])
@login_required
def inventory_links_api():
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401

    if request.method == 'GET':
        return jsonify(list_inventory_links(db, user["id"]))

    data = request.get_json() or {}
    display_name = (data.get("displayName") or "").strip()
    base_url = (data.get("baseUrl") or "").strip()
    auth_mode = data.get("authMode") or "apiKey"
    verify_tls = bool(data.get("verifyTls", True))
    allow_private_network = bool(data.get("allowPrivateNetwork", INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS_DEFAULT))
    connection_scope = data.get("connectionScope") or "internet"
    secret = data.get("secret") or ""

    if not display_name:
        return jsonify({"error": "Display-Name ist erforderlich."}), 400
    if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
        return jsonify({"error": "Ungültiger Auth-Modus."}), 400
    if auth_mode not in {"none", "login"} and not secret:
        return jsonify({"error": "Secret ist erforderlich."}), 400
    if auth_mode == "login" and secret:
        try:
            parse_inventory_link_login_secret(secret)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    try:
        normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
            base_url, connection_scope, verify_tls, allow_private_network
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    scope_error = enforce_inventory_link_scope_access(access, connection_scope)
    if scope_error:
        return jsonify({"error": scope_error}), 403

    try:
        secret_encrypted = encrypt_inventory_link_secret(secret) if secret else ""
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    link_id = str(uuid.uuid4())
    db.execute(
        '''
        INSERT INTO inventory_links (
            id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
            allow_private_network, connection_scope, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''',
        (
            link_id, user["id"], display_name, normalized, 1 if verify_tls else 0,
            auth_mode, secret_encrypted, 1 if allow_private_network else 0, connection_scope
        )
    )
    log_activity(db, "create", "inventory_link", details={"link_id": link_id, "display_name": display_name})
    db.commit()
    link_row = get_inventory_link(db, user["id"], link_id)
    return jsonify(serialize_inventory_link(link_row)), 201

@app.route('/api/inventory-links/test', methods=['POST'])
@login_required
def inventory_links_test_draft():
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    data = request.get_json() or {}
    base_url = (data.get("baseUrl") or "").strip()
    auth_mode = data.get("authMode") or "apiKey"
    verify_tls = bool(data.get("verifyTls", True))
    allow_private_network = bool(data.get("allowPrivateNetwork", INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS_DEFAULT))
    connection_scope = data.get("connectionScope") or "internet"
    secret = data.get("secret") or ""
    if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
        return jsonify({"error": "Ungültiger Auth-Modus."}), 400
    try:
        normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
            base_url, connection_scope, verify_tls, allow_private_network
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    scope_error = enforce_inventory_link_scope_access(access, connection_scope)
    if scope_error:
        return jsonify({"error": scope_error}), 403
    result = perform_inventory_link_test({
        "base_url": normalized,
        "verify_tls": verify_tls,
        "auth_mode": auth_mode,
        "secret": secret,
        "allow_private_network": allow_private_network,
        "connection_scope": connection_scope,
    })
    return jsonify(result), 200

@app.route('/api/inventory-links/<link_id>', methods=['PATCH', 'DELETE'])
@login_required
def inventory_link_detail_api(link_id):
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return jsonify({"error": "Link nicht gefunden."}), 404

    if request.method == 'DELETE':
        db.execute('DELETE FROM inventory_links WHERE id = ? AND user_id = ?', (link_id, user["id"]))
        log_activity(db, "delete", "inventory_link", details={"link_id": link_id})
        db.commit()
        return jsonify({"status": "deleted"}), 200

    data = request.get_json() or {}
    display_name = (data.get("displayName") or link["display_name"]).strip()
    base_url = (data.get("baseUrl") or link["base_url"]).strip()
    auth_mode = data.get("authMode") or link["auth_mode"]
    verify_tls = bool(data.get("verifyTls", bool(link["verify_tls"])))
    allow_private_network = bool(data.get("allowPrivateNetwork", bool(link["allow_private_network"])))
    connection_scope = data.get("connectionScope") or (link["connection_scope"] or "internet")
    secret = data.get("secret")

    if not display_name:
        return jsonify({"error": "Display-Name ist erforderlich."}), 400
    if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
        return jsonify({"error": "Ungültiger Auth-Modus."}), 400
    if auth_mode == "login" and secret is None and link["secret_encrypted"]:
        try:
            existing_secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
            parse_inventory_link_login_secret(existing_secret)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    elif auth_mode == "login" and secret:
        try:
            parse_inventory_link_login_secret(secret)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    try:
        normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
            base_url, connection_scope, verify_tls, allow_private_network
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    scope_error = enforce_inventory_link_scope_access(access, connection_scope)
    if scope_error:
        return jsonify({"error": scope_error}), 403

    secret_encrypted = link["secret_encrypted"]
    if secret is not None:
        if auth_mode not in {"none", "login"} and not secret and not secret_encrypted:
            return jsonify({"error": "Secret ist erforderlich."}), 400
        if secret:
            try:
                secret_encrypted = encrypt_inventory_link_secret(secret)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        elif auth_mode == "none":
            secret_encrypted = ""

    db.execute(
        '''
        UPDATE inventory_links
        SET display_name = ?, base_url = ?, verify_tls = ?, auth_mode = ?, secret_encrypted = ?,
            allow_private_network = ?, connection_scope = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        ''',
        (
            display_name, normalized, 1 if verify_tls else 0, auth_mode, secret_encrypted,
            1 if allow_private_network else 0, connection_scope, link_id, user["id"]
        )
    )
    log_activity(db, "update", "inventory_link", details={"link_id": link_id})
    db.commit()
    updated = get_inventory_link(db, user["id"], link_id)
    return jsonify(serialize_inventory_link(updated)), 200

@app.route('/api/inventory-links/<link_id>/test', methods=['POST'])
@login_required
def inventory_link_test_api(link_id):
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return jsonify({"error": "Link nicht gefunden."}), 404
    secret = ""
    if link["auth_mode"] != "none":
        try:
            secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    result = perform_inventory_link_test({
        "base_url": link["base_url"],
        "verify_tls": bool(link["verify_tls"]),
        "auth_mode": link["auth_mode"],
        "secret": secret,
        "allow_private_network": bool(link["allow_private_network"]),
        "connection_scope": link["connection_scope"] or "internet",
    })
    status_label = result.get("status")
    update_inventory_link_health(db, link_id, status_label)
    db.commit()
    return jsonify(result), 200

@app.route('/api/inventory-links/<link_id>/auth/status', methods=['GET'])
@login_required
def inventory_link_auth_status(link_id):
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return jsonify({"error": "Link nicht gefunden."}), 404
    if link["auth_mode"] != "login":
        return jsonify({"authenticated": True}), 200
    cached_cookie = get_cached_inventory_link_cookie(link, user["id"])
    return jsonify({"authenticated": bool(cached_cookie)}), 200

@app.route('/api/inventory-links/<link_id>/auth/login', methods=['POST'])
@login_required
def inventory_link_auth_login(link_id):
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return jsonify({"error": "Link nicht gefunden."}), 404
    if link["auth_mode"] != "login":
        return jsonify({"error": "Dieser Link benötigt keine Login-Authentifizierung."}), 400
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Benutzername und Passwort erforderlich."}), 400
    try:
        validate_inventory_link_configuration(
            link["base_url"], link["connection_scope"] or "internet",
            bool(link["verify_tls"]), bool(link["allow_private_network"])
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    scope_error = enforce_inventory_link_scope_access(access, link["connection_scope"] or "internet")
    if scope_error:
        return jsonify({"error": scope_error}), 403
    secret = f"{username}:{password}"
    try:
        cookie_header, expires_at = login_inventory_link_session(
            link["base_url"],
            bool(link["verify_tls"]),
            secret
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401
    except InventoryLinkConnectionError as exc:
        return jsonify({"error": str(exc)}), 502
    if not cookie_header:
        return jsonify({"error": "Login fehlgeschlagen. Prüfe Benutzername/Passwort."}), 401
    cache_key = f"{user['id']}:{link['id']}"
    INVENTORY_LINK_LOGIN_SESSION_CACHE.set(cache_key, {
        "cookie": cookie_header,
        "expires_at": expires_at or (time.time() + INVENTORY_LINK_LOGIN_TTL_SECONDS)
    }, INVENTORY_LINK_LOGIN_TTL_SECONDS)
    update_inventory_link_health(db, link_id, "ok")
    db.commit()
    return jsonify({"authenticated": True}), 200

class InventoryLinkNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

@app.route('/api/inventory-links/<link_id>/proxy/', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
@app.route('/api/inventory-links/<link_id>/proxy/<path:subpath>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
@login_required
def inventory_link_proxy(link_id, subpath):
    db = get_db()
    access = get_user_access(db)
    user = access.get("user")
    if not user:
        return jsonify({"error": "Nicht angemeldet"}), 401
    if should_rate_limit_inventory_proxy(user["id"]):
        return jsonify({"error": "Rate limit erreicht."}), 429
    link = get_inventory_link(db, user["id"], link_id)
    if not link:
        return jsonify({"error": "Link nicht gefunden."}), 404

    try:
        validate_inventory_link_configuration(
            link["base_url"], link["connection_scope"] or "internet",
            bool(link["verify_tls"]), bool(link["allow_private_network"])
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    scope_error = enforce_inventory_link_scope_access(access, link["connection_scope"] or "internet")
    if scope_error:
        return jsonify({"error": scope_error}), 403

    if link["auth_mode"] != "none":
        try:
            secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        secret = ""

    target_url = build_inventory_link_target_url(link["base_url"], subpath, request.query_string)
    try:
        headers = build_inventory_link_request_headers(link["auth_mode"], secret, link=link, user_id=user["id"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401
    except InventoryLinkConnectionError as exc:
        return jsonify({"error": str(exc)}), 502
    data = None
    if request.method not in {"GET", "HEAD"}:
        data = request.get_data()
    req = urllib.request.Request(target_url, data=data if data else None, headers=headers, method=request.method)

    context = None
    if link["base_url"].startswith("https://"):
        context = build_inventory_link_ssl_context(bool(link["verify_tls"]))

    handlers = [urllib.request.ProxyHandler({}), InventoryLinkNoRedirect()]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    def perform_proxy_request(request_obj):
        try:
            return opener.open(request_obj, timeout=INVENTORY_LINK_PROXY_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            return exc

    try:
        resp = perform_proxy_request(req)
        if link["auth_mode"] == "login" and resp.getcode() in {401, 403}:
            INVENTORY_LINK_LOGIN_SESSION_CACHE.pop(f"{user['id']}:{link['id']}", None)
            try:
                headers = build_inventory_link_request_headers(link["auth_mode"], secret, link=link, user_id=user["id"])
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 401
            except InventoryLinkConnectionError as exc:
                return jsonify({"error": str(exc)}), 502
            req = urllib.request.Request(target_url, data=data if data else None, headers=headers, method=request.method)
            resp = perform_proxy_request(req)
    except urllib.error.URLError as exc:
        return jsonify({"error": f"Proxy-Fehler: {exc.reason}"}), 502
    except ssl.SSLError as exc:
        return jsonify({"error": f"TLS-Fehler: {str(exc)}"}), 502

    status_code = resp.getcode()
    response_headers = filter_inventory_link_response_headers(resp.headers, link_id, link["base_url"])
    log_activity(db, "proxy", "inventory_link", details={"link_id": link_id, "method": request.method, "path": subpath})
    db.commit()
    content_type = resp.headers.get("Content-Type", "")
    if request.method != "HEAD" and should_rewrite_inventory_link_response(content_type):
        body = resp.read()
        rewritten = rewrite_inventory_link_text_content(body, content_type, link_id, link["base_url"])
        return Response(
            rewritten,
            status=status_code,
            headers=response_headers
        )
    return Response(
        stream_inventory_link_response(resp),
        status=status_code,
        headers=response_headers
    )

@app.route('/api/export', methods=['GET'])
@login_required
@require_permission('server_settings.manage')
def export_data():
    db = get_db()
    settings, _ = serialize_server_settings(get_server_settings(db))
    if not settings["importExport"]["exportAllowed"]:
        return jsonify({"error": "Export ist deaktiviert."}), 403
    export_format = settings["importExport"]["exportFormat"]
    include_uploads = settings["importExport"]["includeUploads"]
    tables = [
        "categories",
        "asset_categories",
        "locations",
        "devices",
        "asset_categories",
        "assets",
        "asset_devices",
        "maintenance_tasks",
        "asset_assignment_history",
        "vendors",
        "contracts",
        "purchase_orders",
        "purchase_order_items",
        "attachments",
    ]
    temp_dir = Path(tempfile.mkdtemp(prefix="inventory_export_"))
    archive_path = None
    try:
        if export_format == "sqlite":
            db_path = temp_dir / "inventory.db"
            run_sqlite_backup(db_path)
            if include_uploads and UPLOADS_DIR.exists():
                archive_path = temp_dir / "inventory_export.zip"
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(db_path, arcname="inventory.db")
                    for path in UPLOADS_DIR.rglob("*"):
                        if path.is_file():
                            archive.write(path, arcname=str(Path("uploads") / path.relative_to(UPLOADS_DIR)))
            else:
                archive_path = db_path
        elif export_format == "json":
            payload = export_tables(db, tables)
            data_path = temp_dir / "inventory_export.json"
            data_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if include_uploads and UPLOADS_DIR.exists():
                archive_path = temp_dir / "inventory_export.zip"
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(data_path, arcname="inventory_export.json")
                    for path in UPLOADS_DIR.rglob("*"):
                        if path.is_file():
                            archive.write(path, arcname=str(Path("uploads") / path.relative_to(UPLOADS_DIR)))
            else:
                archive_path = data_path
        else:
            archive_path = temp_dir / "inventory_export.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for table in tables:
                    rows = db.execute(f"SELECT * FROM {table}").fetchall()
                    csv_path = temp_dir / f"{table}.csv"
                    if rows:
                        fieldnames = rows[0].keys()
                        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                            writer = csv.DictWriter(handle, fieldnames=fieldnames)
                            writer.writeheader()
                            for row in rows:
                                writer.writerow(dict(row))
                    else:
                        csv_path.write_text("", encoding="utf-8")
                    archive.write(csv_path, arcname=f"{table}.csv")
                if include_uploads and UPLOADS_DIR.exists():
                    for path in UPLOADS_DIR.rglob("*"):
                        if path.is_file():
                            archive.write(path, arcname=str(Path("uploads") / path.relative_to(UPLOADS_DIR)))
        if (export_format in {"sqlite", "json"} and include_uploads) or export_format == "csv":
            filename = "inventory_export.zip"
            mimetype = "application/zip"
        else:
            filename = f"inventory_export.{archive_path.suffix.lstrip('.')}"
            mimetype = "application/octet-stream"
        return Response(
            archive_path.read_bytes(),
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/import', methods=['POST'])
@login_required
@require_permission('server_settings.manage')
def import_data():
    db = get_db()
    settings, _ = serialize_server_settings(get_server_settings(db))
    if not settings["importExport"]["importAllowed"]:
        return jsonify({"error": "Import ist deaktiviert."}), 403
    if should_rate_limit(f"import:{session.get('username')}"):
        return jsonify({"error": "Zu viele Import-Anfragen."}), 429
    import_mode = settings["importExport"]["importMode"]
    file_storage = request.files.get("file")
    file_path, error = load_import_file(file_storage)
    if error:
        return jsonify({"error": error}), 400
    antivirus_error = validate_import_file(file_path)
    if antivirus_error:
        shutil.rmtree(file_path.parent, ignore_errors=True)
        return jsonify({"error": antivirus_error}), 400
    tables = [
        "categories",
        "asset_categories",
        "locations",
        "devices",
        "assets",
        "maintenance_tasks",
        "asset_assignment_history",
        "vendors",
        "contracts",
        "purchase_orders",
        "purchase_order_items",
        "attachments",
    ]
    try:
        if import_mode == "replace":
            run_backup_job(db, settings, force=True)
        if file_path.suffix == ".json":
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            with db:
                import_data_payload(db, payload, import_mode, tables)
        elif file_path.suffix == ".zip":
            with zipfile.ZipFile(file_path, "r") as archive:
                try:
                    upload_members = validate_import_archive(archive)
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
                members = archive.namelist()
                data_files = [name for name in members if name.endswith(".csv")]
                if data_files:
                    with db:
                        if import_mode == "replace":
                            for table in tables:
                                db.execute(f"DELETE FROM {table}")
                        for data_file in data_files:
                            table_name = Path(data_file).stem
                            if table_name not in tables:
                                continue
                            with archive.open(data_file) as handle:
                                content = handle.read().decode("utf-8")
                                reader = csv.DictReader(StringIO(content))
                                import_table_rows(db, table_name, list(reader), import_mode if import_mode != "replace" else "append")
                db.commit()
                if settings["importExport"]["includeUploads"] and upload_members:
                    uploads_root = UPLOADS_DIR.resolve()
                    for member_info, relative_path in upload_members:
                        target_path = (uploads_root / relative_path).resolve()
                        if not target_path.is_relative_to(uploads_root):
                            return jsonify({"error": "ZIP-Archiv enthält einen unsicheren Upload-Pfad."}), 400
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member_info) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
        elif file_path.suffix in {".db", ".sqlite"}:
            with db:
                import_from_sqlite(db, file_path, import_mode, tables)
        else:
            return jsonify({"error": "Unbekanntes Import-Format."}), 400
        log_activity(db, "import", "server_settings", details={"mode": import_mode})
        db.commit()
        return jsonify({"status": "success"})
    finally:
        shutil.rmtree(file_path.parent, ignore_errors=True)

@app.route('/api/customize', methods=['GET', 'PUT', 'PATCH'])
@login_required
def customize_settings():
    db = get_db()
    user_id = get_current_user_id(db)
    if not user_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 401

    record = get_customization_record(db, user_id)
    existing = None
    if record:
        existing = json.loads(record["customization_json"])

    if request.method == 'GET':
        customization = migrate_customization(existing or DEFAULT_CUSTOMIZATION)
        latest_revision = None
        if record:
            latest_revision = db.execute(
                """
                SELECT id FROM ui_customization_revisions
                WHERE customization_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (record["id"],),
            ).fetchone()
        return jsonify({
            "customization": customization,
            "updated_at": record["updated_at"] if record else None,
            "revision_id": latest_revision["id"] if latest_revision else None,
        })

    payload = request.get_json() or {}
    if request.method == 'PATCH':
        merged = deep_merge(existing or DEFAULT_CUSTOMIZATION, payload)
    else:
        merged = payload

    customization = migrate_customization(merged)
    valid, errors = validate_customization(customization)
    if not valid:
        return jsonify({"error": "Ungültige Customize-Daten.", "details": errors}), 400

    customization_id = save_customization(db, user_id, customization, session.get("username", "system"))
    latest_revision = db.execute(
        """
        SELECT id FROM ui_customization_revisions
        WHERE customization_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (customization_id,),
    ).fetchone()
    updated_at = db.execute("SELECT updated_at FROM ui_customization WHERE id = ?", (customization_id,)).fetchone()
    log_activity(db, "update", "ui_customization", entity_id=customization_id)
    return jsonify({
        "customization": customization,
        "updated_at": updated_at["updated_at"] if updated_at else None,
        "revision_id": latest_revision["id"] if latest_revision else None,
    })

@app.route('/api/customize/history', methods=['GET'])
@login_required
def customize_history():
    db = get_db()
    user_id = get_current_user_id(db)
    if not user_id:
        return jsonify({"revisions": []})
    record = get_customization_record(db, user_id)
    if not record:
        return jsonify({"revisions": []})
    rows = db.execute(
        """
        SELECT id, created_at, created_by, diff_json
        FROM ui_customization_revisions
        WHERE customization_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (record["id"],),
    ).fetchall()
    revisions = []
    for row in rows:
        revisions.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
            "diff": json.loads(row["diff_json"]) if row["diff_json"] else [],
        })
    return jsonify({"revisions": revisions})

@app.route('/api/customize/rollback/<int:revision_id>', methods=['POST'])
@login_required
def customize_rollback(revision_id):
    db = get_db()
    user_id = get_current_user_id(db)
    if not user_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 401

    record = get_customization_record(db, user_id)
    if not record:
        return jsonify({"error": "Keine Customize-Konfiguration vorhanden."}), 404

    revision = db.execute(
        """
        SELECT revision_json FROM ui_customization_revisions
        WHERE id = ? AND customization_id = ?
        """,
        (revision_id, record["id"]),
    ).fetchone()
    if not revision:
        return jsonify({"error": "Revision nicht gefunden."}), 404

    customization = migrate_customization(json.loads(revision["revision_json"]))
    customization_id = save_customization(db, user_id, customization, session.get("username", "system"))
    latest_revision = db.execute(
        """
        SELECT id FROM ui_customization_revisions
        WHERE customization_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (customization_id,),
    ).fetchone()
    updated_at = db.execute("SELECT updated_at FROM ui_customization WHERE id = ?", (customization_id,)).fetchone()
    log_activity(db, "rollback", "ui_customization", entity_id=customization_id)
    return jsonify({
        "customization": customization,
        "updated_at": updated_at["updated_at"] if updated_at else None,
        "revision_id": latest_revision["id"] if latest_revision else None,
    })

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
    settings, _ = serialize_server_settings(get_server_settings(db))
    if not settings["proFeaturesEnabled"]:
        return jsonify({"pro_locked": True, "open": 0, "overdue": 0})
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
    settings, _ = serialize_server_settings(get_server_settings(db))
    if not settings["importExport"]["exportAllowed"]:
        return jsonify({"error": "Export ist deaktiviert."}), 403
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

    # 5. Asset-, Ticket- und Nutzeranalysen (proaktive Phase 1-3)
    total_assets = db.execute('SELECT COUNT(*) FROM assets').fetchone()[0] or 0
    retired_assets = db.execute('''
        SELECT COUNT(*) FROM assets
        WHERE retirement_date IS NOT NULL AND retirement_date != ''
    ''').fetchone()[0] or 0
    active_assets = total_assets - retired_assets

    ticket_total = db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0] or 0
    ticket_closed = db.execute('''
        SELECT COUNT(*) FROM tickets
        WHERE status IN ('closed', 'resolved', 'done')
    ''').fetchone()[0] or 0
    ticket_open = ticket_total - ticket_closed

    ticket_type_rows = db.execute('''
        SELECT COALESCE(tc.name, 'Unkategorisiert') as name, COUNT(*) as total
        FROM tickets t
        LEFT JOIN ticket_categories tc ON t.category_id = tc.id
        GROUP BY tc.name
        ORDER BY total DESC
    ''').fetchall()
    ticket_type_breakdown = [dict(row) for row in ticket_type_rows] if ticket_type_rows else []

    escalation_rows = db.execute('''
        SELECT escalation_level as level, COUNT(*) as total
        FROM tickets
        GROUP BY escalation_level
        ORDER BY escalation_level
    ''').fetchall()
    escalation_breakdown = [dict(row) for row in escalation_rows] if escalation_rows else []

    closed_ticket_rows = db.execute('''
        SELECT created_at, COALESCE(resolved_at, updated_at) as resolved_at
        FROM tickets
        WHERE status IN ('closed', 'resolved', 'done')
    ''').fetchall()
    total_resolution_hours = 0
    resolved_count = 0
    for row in closed_ticket_rows:
        created_at = parse_datetime(row['created_at'])
        resolved_at = parse_datetime(row['resolved_at'])
        if created_at and resolved_at:
            total_resolution_hours += max(0, (resolved_at - created_at).total_seconds() / 3600)
            resolved_count += 1
    avg_resolution_hours = round(total_resolution_hours / resolved_count, 1) if resolved_count else 0

    action_rows = db.execute('''
        SELECT resolution_action,
               SUM(CASE WHEN resolution_outcome = 'success' THEN 1 ELSE 0 END) as success_count,
               COUNT(*) as total
        FROM tickets
        WHERE resolution_action IS NOT NULL AND resolution_action != ''
        GROUP BY resolution_action
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    action_success_rates = []
    for row in action_rows:
        total = row['total'] or 0
        success = row['success_count'] or 0
        rate = round((success / total) * 100) if total else 0
        action_success_rates.append({
            "action": row['resolution_action'],
            "total": total,
            "success": success,
            "rate": rate
        })

    asset_ticket_rows = db.execute('''
        SELECT a.id, a.name, a.acquisition_date, a.commissioning_date, a.warranty_end,
               COUNT(ta.ticket_id) as ticket_count,
               (
                   SELECT aa.user_identifier
                   FROM asset_assignments aa
                   WHERE aa.asset_id = a.id AND (aa.released_at IS NULL OR aa.released_at = '')
                   ORDER BY aa.assigned_at DESC, aa.created_at DESC
                   LIMIT 1
               ) as assigned_user
        FROM assets a
        LEFT JOIN ticket_assets ta ON ta.asset_id = a.id
        GROUP BY a.id
        ORDER BY ticket_count DESC, a.name
        LIMIT 8
    ''').fetchall()
    asset_ticket_stats = []
    today = datetime.utcnow().date()
    ticket_counts = []
    for row in asset_ticket_rows:
        commissioning_date = parse_date(row['commissioning_date']) or parse_date(row['acquisition_date'])
        age_months = None
        if commissioning_date:
            age_months = round((today - commissioning_date).days / 30.4, 1)
        ticket_counts.append(row['ticket_count'] or 0)
        asset_ticket_stats.append({
            "id": row["id"],
            "name": row["name"],
            "ticket_count": row["ticket_count"] or 0,
            "assigned_user": row["assigned_user"] or "—",
            "age_months": age_months,
            "warranty_status": warranty_status(row["warranty_end"])
        })

    reporter_rows = db.execute('''
        SELECT t.id,
               COALESCE(t.created_by, t.requester_name, 'Unbekannt') as reporter,
               t.priority,
               COUNT(tc.id) as comment_count
        FROM tickets t
        LEFT JOIN ticket_comments tc ON tc.ticket_id = t.id
        GROUP BY t.id
    ''').fetchall()
    reporter_stats = {}
    priority_weights = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
    for row in reporter_rows:
        reporter = row["reporter"] or "Unbekannt"
        stats = reporter_stats.setdefault(reporter, {"tickets": 0, "comments": 0, "priority_score": 0})
        stats["tickets"] += 1
        stats["comments"] += row["comment_count"] or 0
        stats["priority_score"] += priority_weights.get((row["priority"] or "normal").lower(), 2)
    user_behavior_stats = []
    for reporter, stats in reporter_stats.items():
        avg_comments = round(stats["comments"] / stats["tickets"], 1) if stats["tickets"] else 0
        avg_priority = round(stats["priority_score"] / stats["tickets"], 1) if stats["tickets"] else 0
        user_behavior_stats.append({
            "reporter": reporter,
            "tickets": stats["tickets"],
            "avg_comments": avg_comments,
            "avg_priority": avg_priority
        })
    user_behavior_stats.sort(key=lambda item: item["tickets"], reverse=True)
    user_behavior_stats = user_behavior_stats[:6]

    proactive_insights = []
    if ticket_counts:
        avg_tickets = sum(ticket_counts) / len(ticket_counts)
        variance = sum((count - avg_tickets) ** 2 for count in ticket_counts) / len(ticket_counts)
        threshold = max(3, avg_tickets + variance ** 0.5)
        noisy_assets = [a for a in asset_ticket_stats if a["ticket_count"] >= threshold]
        if noisy_assets:
            top_asset = noisy_assets[0]
            proactive_insights.append({
                "title": f"Hohe Ticketlast bei {top_asset['name']}",
                "severity": "warning",
                "description": f"{top_asset['ticket_count']} Tickets (Ø {avg_tickets:.1f}) – Empfehlung: Austausch prüfen oder Ursachenanalyse starten.",
                "evidence": f"Aktuell zugewiesen an {top_asset['assigned_user']}."
            })

    warranty_rows = db.execute('SELECT id, name, warranty_end, retirement_date FROM assets').fetchall()
    expiring_assets = []
    for row in warranty_rows:
        if row["retirement_date"]:
            continue
        warranty_end = parse_date(row["warranty_end"])
        if not warranty_end:
            continue
        days_left = (warranty_end - today).days
        if 0 <= days_left <= 45:
            expiring_assets.append((row["name"], days_left))
    if expiring_assets:
        expiring_assets.sort(key=lambda item: item[1])
        name, days_left = expiring_assets[0]
        proactive_insights.append({
            "title": "Garantie läuft aus",
            "severity": "info",
            "description": f"{len(expiring_assets)} Assets haben eine auslaufende Garantie in den nächsten 45 Tagen.",
            "evidence": f"Nächstes Asset: {name} (in {days_left} Tagen)."
        })

    sla_risk_rows = db.execute('''
        SELECT t.id, t.title, t.created_at, t.status, tc.sla_hours, tc.name as category_name
        FROM tickets t
        LEFT JOIN ticket_categories tc ON t.category_id = tc.id
        WHERE t.status NOT IN ('closed', 'resolved', 'done')
    ''').fetchall()
    sla_risks = []
    for row in sla_risk_rows:
        created_at = parse_datetime(row["created_at"])
        if not created_at:
            continue
        sla_hours = row["sla_hours"] or 72
        age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
        if age_hours > sla_hours:
            sla_risks.append(row)
    if sla_risks:
        sample = sla_risks[0]
        proactive_insights.append({
            "title": "SLA-Risiko bei offenen Tickets",
            "severity": "critical",
            "description": f"{len(sla_risks)} offene Tickets überschreiten aktuell die SLA-Zeit.",
            "evidence": f"Beispiel: #{sample['id']} ({sample['category_name'] or 'Unkategorisiert'})."
        })

    if user_behavior_stats:
        avg_reporter_tickets = sum(item["tickets"] for item in user_behavior_stats) / len(user_behavior_stats)
        top_reporter = user_behavior_stats[0]
        if top_reporter["tickets"] >= max(3, avg_reporter_tickets * 1.5):
            proactive_insights.append({
                "title": "Auffälliges Nutzerverhalten",
                "severity": "warning",
                "description": f"{top_reporter['reporter']} meldet überdurchschnittlich viele Tickets.",
                "evidence": f"{top_reporter['tickets']} Tickets vs. Ø {avg_reporter_tickets:.1f}."
            })
    
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
        'total_assets': total_assets,
        'active_assets': active_assets,
        'retired_assets': retired_assets,
        'ticket_total': ticket_total,
        'ticket_open': ticket_open,
        'ticket_closed': ticket_closed,
        'avg_resolution_hours': avg_resolution_hours,
        'ticket_type_breakdown': ticket_type_breakdown,
        'escalation_breakdown': escalation_breakdown,
        'action_success_rates': action_success_rates,
        'asset_ticket_stats': asset_ticket_stats,
        'user_behavior_stats': user_behavior_stats,
        'proactive_insights': proactive_insights,
        'username': session.get('username', ''),
        'permissions': sorted(access["permissions"]),
        'is_superuser': access["is_superuser"]
    }
    
    return render_template('stats.html', **context)

@app.route('/api/terminal/session/start', methods=['POST'])
@login_required
@require_permission('terminal.use')
def terminal_session_start():
    db = get_db()
    access = get_user_access(db)
    settings_row = get_server_settings(db)
    settings, _ = serialize_server_settings(settings_row)
    terminal_settings = settings["terminal"]
    if not terminal_settings["enabled"]:
        return jsonify({"error": "Terminal ist deaktiviert."}), 403
    remote_ip = get_remote_ip()
    if not is_ip_allowed(remote_ip, terminal_settings["ipAllowlist"]):
        return jsonify({"error": "IP nicht erlaubt."}), 403
    user_id = access["user"]["id"]
    if should_rate_limit_terminal(user_id):
        return jsonify({"error": "Rate-Limit erreicht."}), 429

    payload = request.get_json(silent=True) or {}
    if terminal_settings["requireReauth"]:
        password = payload.get("password") or ""
        otp_code = payload.get("otp") or ""
        user_row = db.execute(
            "SELECT id, password_hash, otp_secret FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not password or not user_row or not check_password_hash(user_row["password_hash"], password):
            log_terminal_audit(db, user_id, None, "session_start", {"reason": "password_failed"}, "error", 0)
            return jsonify({"error": "Re-Auth fehlgeschlagen."}), 403
        if user_row["otp_secret"]:
            if not otp_code or not pyotp.TOTP(user_row["otp_secret"]).verify(str(otp_code).strip()):
                log_terminal_audit(db, user_id, None, "session_start", {"reason": "otp_failed"}, "error", 0)
                return jsonify({"error": "OTP erforderlich."}), 403
        session["terminal_reauth_at"] = time.time()

    session_id, expires_at = create_terminal_session(
        db,
        user_id,
        "maintenance",
        remote_ip,
        request.headers.get("User-Agent", "")
    )
    log_terminal_audit(db, user_id, session_id, "session_start", {"ip": remote_ip}, "ok", 0)
    return jsonify({
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
        "limits": {
            "rate_limit_per_minute": TERMINAL_RATE_LIMIT_MAX_REQUESTS,
            "max_output_bytes": TERMINAL_MAX_OUTPUT_BYTES,
            "session_ttl_seconds": TERMINAL_SESSION_TTL_SECONDS
        },
        "allowlists": {
            "services": TERMINAL_SERVICE_ALLOWLIST,
            "logs": list(TERMINAL_LOG_SOURCES.keys())
        }
    })

@app.route('/api/terminal/session/stop', methods=['POST'])
@login_required
@require_permission('terminal.use')
def terminal_session_stop():
    db = get_db()
    access = get_user_access(db)
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    user_id = access["user"]["id"]
    session_row = get_terminal_session(db, session_id, user_id)
    if not session_row:
        return jsonify({"error": "Session nicht gefunden."}), 404
    terminate_terminal_session(db, session_id)
    log_terminal_audit(db, user_id, session_id, "session_stop", {}, "ok", 0)
    return jsonify({"status": "stopped"})

@app.route('/api/terminal/run', methods=['POST'])
@login_required
@require_permission('terminal.use')
def terminal_run_recipe():
    db = get_db()
    access = get_user_access(db)
    settings_row = get_server_settings(db)
    settings, _ = serialize_server_settings(settings_row)
    terminal_settings = settings["terminal"]
    if not terminal_settings["enabled"]:
        return jsonify({"error": "Terminal ist deaktiviert."}), 403
    remote_ip = get_remote_ip()
    if not is_ip_allowed(remote_ip, terminal_settings["ipAllowlist"]):
        return jsonify({"error": "IP nicht erlaubt."}), 403
    user_id = access["user"]["id"]
    if should_rate_limit_terminal(user_id):
        return jsonify({"error": "Rate-Limit erreicht."}), 429
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    recipe_id = (payload.get("recipe_id") or "").strip()
    params = payload.get("params") or {}
    session_row = get_terminal_session(db, session_id, user_id)
    if not session_row:
        return jsonify({"error": "Session ungültig oder abgelaufen."}), 403
    recipe = TERMINAL_RECIPES.get(recipe_id)
    if not recipe:
        return jsonify({"error": "Recipe nicht erlaubt."}), 400

    start_time = time.time()
    try:
        if recipe_id == "service_restart":
            result = recipe["handler"](params, settings)
        else:
            result = recipe["handler"](params)
    except Exception as exc:
        result = {"status": "error", "output": f"Fehler: {exc}"}
    duration_ms = int((time.time() - start_time) * 1000)
    output = truncate_output(redact_text(result.get("output", "")))
    status = result.get("status", "error")
    touch_terminal_session(db, session_id)
    log_terminal_audit(db, user_id, session_id, recipe_id, params, status, duration_ms, output)
    response = {
        "status": status,
        "output": output,
        "duration_ms": duration_ms
    }
    if result.get("meta"):
        response["meta"] = redact_data(result["meta"])
    return jsonify(response)

@app.route('/api/terminal/audit', methods=['GET'])
@login_required
@require_permission('terminal.view')
def terminal_audit():
    db = get_db()
    access = get_user_access(db)
    user_id = access["user"]["id"]
    start = request.args.get("from")
    end = request.args.get("to")
    params = [user_id]
    query = '''
        SELECT id, action_type, params_json, status, duration_ms, output_preview, created_at
        FROM terminal_audit_logs
        WHERE user_id = ?
    '''
    if start:
        query += " AND created_at >= ?"
        params.append(start)
    if end:
        query += " AND created_at <= ?"
        params.append(end)
    query += " ORDER BY created_at DESC LIMIT 200"
    rows = db.execute(query, tuple(params)).fetchall()
    entries = []
    for row in rows:
        try:
            params_json = json.loads(row["params_json"]) if row["params_json"] else {}
        except json.JSONDecodeError:
            params_json = {}
        entries.append({
            "id": row["id"],
            "action": row["action_type"],
            "params": params_json,
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "preview": row["output_preview"],
            "created_at": row["created_at"]
        })
    return jsonify({"entries": entries})

@app.route('/api/terminal/db/query', methods=['POST'])
@login_required
@require_permission('terminal.use')
def terminal_db_query():
    db = get_db()
    access = get_user_access(db)
    settings_row = get_server_settings(db)
    settings, _ = serialize_server_settings(settings_row)
    terminal_settings = settings["terminal"]
    if not terminal_settings["enabled"]:
        return jsonify({"error": "Terminal ist deaktiviert."}), 403
    remote_ip = get_remote_ip()
    if not is_ip_allowed(remote_ip, terminal_settings["ipAllowlist"]):
        return jsonify({"error": "IP nicht erlaubt."}), 403
    user_id = access["user"]["id"]
    if should_rate_limit_terminal(user_id):
        return jsonify({"error": "Rate-Limit erreicht."}), 429
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    query = payload.get("query") or ""
    session_row = get_terminal_session(db, session_id, user_id)
    if not session_row:
        return jsonify({"error": "Session ungültig oder abgelaufen."}), 403
    if not is_safe_readonly_query(query):
        return jsonify({"error": "Nur SELECT/EXPLAIN erlaubt."}), 400
    if db_is_postgres():
        return jsonify({"error": "DB-Console nur für SQLite verfügbar."}), 400

    start_time = time.time()
    normalized = normalize_sql_query(query)
    result_rows = []
    columns = []
    status = "ok"
    try:
        with sqlite3.connect(DATABASE) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(normalized)
            columns = [col[0] for col in (cursor.description or [])]
            fetched = cursor.fetchmany(TERMINAL_DB_MAX_ROWS + 1)
            truncated = len(fetched) > TERMINAL_DB_MAX_ROWS
            if truncated:
                fetched = fetched[:TERMINAL_DB_MAX_ROWS]
            for row in fetched:
                result_rows.append([redact_data(value) for value in row])
    except Exception as exc:
        status = "error"
        columns = []
        result_rows = []
        output = f"Fehler: {exc}"
    duration_ms = int((time.time() - start_time) * 1000)
    if status == "ok":
        output = f"{len(result_rows)} Zeilen zurückgegeben."
    output = truncate_output(redact_text(output), max_bytes=TERMINAL_DB_MAX_BYTES)
    touch_terminal_session(db, session_id)
    log_terminal_audit(db, user_id, session_id, "db_query", {"query": query}, status, duration_ms, output)
    return jsonify({
        "status": status,
        "columns": columns,
        "rows": result_rows,
        "duration_ms": duration_ms,
        "output": output
    })

@app.route('/api/terminal/db/execute', methods=['POST'])
@login_required
@require_permission('terminal.db_write')
def terminal_db_execute():
    db = get_db()
    access = get_user_access(db)
    settings_row = get_server_settings(db)
    settings, _ = serialize_server_settings(settings_row)
    terminal_settings = settings["terminal"]
    if not terminal_settings["enabled"] or not terminal_settings["allowDbWrite"]:
        return jsonify({"error": "DB-Write ist deaktiviert."}), 403
    remote_ip = get_remote_ip()
    if not is_ip_allowed(remote_ip, terminal_settings["ipAllowlist"]):
        return jsonify({"error": "IP nicht erlaubt."}), 403
    user_id = access["user"]["id"]
    if should_rate_limit_terminal(user_id):
        return jsonify({"error": "Rate-Limit erreicht."}), 429
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    query = payload.get("query") or ""
    confirm = (payload.get("confirm") or "").strip().upper()
    session_row = get_terminal_session(db, session_id, user_id)
    if not session_row:
        return jsonify({"error": "Session ungültig oder abgelaufen."}), 403
    if confirm != "EXECUTE":
        return jsonify({"error": "Bestätigung EXECUTE erforderlich."}), 400
    if not normalize_sql_query(query):
        return jsonify({"error": "Ungültiges SQL."}), 400
    if is_safe_readonly_query(query):
        return jsonify({"error": "Read-only Query bitte über /db/query ausführen."}), 400
    if not terminal_settings["breakGlassMode"] and is_dangerous_query(query):
        return jsonify({"error": "Query ist blockiert (Break-Glass deaktiviert)."}), 403
    if db_is_postgres():
        return jsonify({"error": "DB-Console nur für SQLite verfügbar."}), 400

    start_time = time.time()
    status = "ok"
    rows_affected = 0
    try:
        with sqlite3.connect(DATABASE) as connection:
            cursor = connection.execute(normalize_sql_query(query))
            rows_affected = cursor.rowcount if cursor.rowcount is not None else 0
            connection.commit()
        output = f"{rows_affected} Zeilen geändert."
    except Exception as exc:
        status = "error"
        output = f"Fehler: {exc}"
    duration_ms = int((time.time() - start_time) * 1000)
    output = truncate_output(redact_text(output), max_bytes=TERMINAL_DB_MAX_BYTES)
    touch_terminal_session(db, session_id)
    log_terminal_audit(db, user_id, session_id, "db_execute", {"query": query}, status, duration_ms, output)
    return jsonify({
        "status": status,
        "rows_affected": rows_affected,
        "duration_ms": duration_ms,
        "output": output
    })

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

def generate_recovery_codes():
    return [secrets.token_hex(4) for _ in range(8)]

@app.route('/api/otp/recovery', methods=['POST'])
@login_required
def create_recovery_codes():
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE username = ?', (session.get('username'),)).fetchone()
    if not user:
        return jsonify({"error": "Benutzer nicht gefunden"}), 404
    codes = generate_recovery_codes()
    db.execute('DELETE FROM mfa_recovery_codes WHERE user_id = ?', (user["id"],))
    for code in codes:
        db.execute(
            'INSERT INTO mfa_recovery_codes (user_id, code_hash) VALUES (?, ?)',
            (user["id"], generate_password_hash(code))
        )
    log_activity(db, "mfa_recovery_generated", "user", user["id"])
    db.commit()
    return jsonify({"codes": codes})

def verify_recovery_code(db, user_id, code):
    rows = db.execute(
        'SELECT id, code_hash FROM mfa_recovery_codes WHERE user_id = ? AND used_at IS NULL',
        (user_id,)
    ).fetchall()
    for row in rows:
        if check_password_hash(row["code_hash"], code):
            db.execute('UPDATE mfa_recovery_codes SET used_at = CURRENT_TIMESTAMP WHERE id = ?', (row["id"],))
            return True
    return False

@app.route('/verify')
@login_required
def verify():
    return render_template('verify_otp.html')

@app.route('/api/otp/verify', methods=['POST'])
@login_required
def verify_otp():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get('code') or "").strip()
    username = session.get('username') or ""
    rate_limit_key = f"otp-verify:{get_remote_ip()}:{username.lower()}"
    if should_rate_limit(rate_limit_key):
        return jsonify({
            "verified": False,
            "error": "Zu viele Prüfversuche. Bitte kurz warten.",
        }), 429

    db = get_db()
    user = db.execute('SELECT id, otp_secret FROM users WHERE username = ?', (username,)).fetchone()

    if user and user['otp_secret'] and code and pyotp.TOTP(user['otp_secret']).verify(code):
        log_activity(db, "otp_verify", "user", details={"username": username})
        db.commit()
        RATE_LIMIT_CACHE.pop(rate_limit_key, None)
        session['mfa_verified'] = True
        return jsonify({"verified": True}), 200
    if user and code and verify_recovery_code(db, user["id"], code):
        log_activity(db, "otp_recovery_used", "user", details={"username": username})
        db.commit()
        RATE_LIMIT_CACHE.pop(rate_limit_key, None)
        session['mfa_verified'] = True
        return jsonify({"verified": True, "recovery": True}), 200
    else:
        log_activity(db, "otp_failed", "user", details={"username": username})
        db.commit()
        return jsonify({"verified": False}), 401

@app.route('/reset', methods=['GET'])
def reset_page():
    return render_template('reset_password.html')

@app.route('/reset', methods=['POST'])
def reset_password():
    username = (request.form.get('username') or "").strip()
    otp_code = (request.form.get('otp') or "").strip()
    new_password = request.form.get('new_password') or ""
    neutral_error = "Zurücksetzen nicht möglich. Angaben prüfen oder Administrator kontaktieren."
    rate_limit_key = f"password-reset:{get_remote_ip()}:{username.lower()}"

    if not all([username, otp_code, new_password]):
        return render_template('reset_password.html', error="Alle Felder ausfüllen!")
    if should_rate_limit(rate_limit_key):
        return render_template(
            'reset_password.html',
            error="Zu viele Versuche. Bitte kurz warten.",
        ), 429

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    verification_secret = (
        user["otp_secret"]
        if user and user["otp_secret"]
        else "JBSWY3DPEHPK3PXP"
    )
    otp_valid = pyotp.TOTP(verification_secret).verify(otp_code)
    if not user or not user["otp_secret"] or not otp_valid:
        return render_template('reset_password.html', error=neutral_error), 400

    min_length = get_password_min_length(db)
    if len(new_password) < min_length:
        return render_template('reset_password.html', error=f"Passwort muss mindestens {min_length} Zeichen lang sein.")

    # Neues Passwort setzen
    new_hash = generate_password_hash(new_password)
    db.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, username))
    log_activity(db, "password_reset", "user", details={"username": username})
    db.commit()
    RATE_LIMIT_CACHE.pop(rate_limit_key, None)

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


app.register_blueprint(
    build_backups_blueprint(
        get_db=get_db,
        load_settings=load_backup_settings,
        login_required=login_required,
        require_permission=require_permission,
        run_backup_job=run_backup_job,
    ),
)
app.register_blueprint(
    build_ticket_pages_blueprint(
        ensure_ticket_access=ensure_ticket_access,
        fetch_ticket=fetch_ticket,
        get_db=get_db,
        get_user_access=get_user_access,
        login_required=login_required,
        require_permissions=require_permissions,
    ),
)
app.register_blueprint(
    build_locations_blueprint(
        get_db=get_db,
        get_user_access=get_user_access,
        log_activity=log_activity,
        login_required=login_required,
        require_permissions=require_permissions,
        user_can=user_can,
    ),
)


if __name__ == '__main__':
    init_db()
    with app.app_context():
        settings_row = get_server_settings(get_db())
        settings, _ = serialize_server_settings(settings_row)
        runtime = load_runtime_settings()
        if not runtime or runtime == DEFAULT_SERVER_SETTINGS["server"]:
            runtime = settings["server"]
            store_runtime_settings(runtime)
        store_update_policy(settings["updates"])
        RUNTIME_SETTINGS_CACHE = runtime
        schedule_backup_jobs(settings)
        schedule_health_jobs()
    app.run(host=runtime["host"], port=runtime["port"], debug=runtime["debug"])
