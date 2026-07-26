import json
import socket
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from flask import Flask

import app as inventory_app
from inventorypro.domains.inventory_links.routes import build_inventory_links_blueprint


class InventoryLinkHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/login"):
            payload = b"authenticated"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Set-Cookie", "inventory_session=linked; Path=/")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/health/summary"):
            payload = json.dumps({"status": "OK"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/headers"):
            payload = json.dumps({k: v for k, v in self.headers.items()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return
        if self.path.startswith("/final"):
            payload = b"final"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/stream"):
            payload = b"x" * 65536
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/page"):
            payload = b"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'">
    <link rel="stylesheet" href="/static/style.css">
    <script src="/static/app.js"></script>
    <script>fetch('/api/devices'); window.location = '/tickets';</script>
</head>
<body>
    <a href="/tickets">Tickets</a>
    <form action="/login" method="post"></form>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/static/app.js"):
            payload = b"fetch('/api/categories'); const home = '/'; const css = '/static/style.css';"
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/static/style.css"):
            payload = b"body{background:url('/static/bg.png');}"
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/static/bg.png"):
            payload = b"png"
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


class InventoryLinksTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        inventory_app.DATABASE = str(temp_path / "test_inventory.db")
        inventory_app.UPLOADS_DIR = temp_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temp_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temp_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False
        }
        inventory_app.os.environ["INVENTORY_LINKS_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
        inventory_app.os.environ["INVENTORY_LINKS_ALLOW_LOOPBACK"] = "0"
        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("tester", password_hash)
            )
            admin_role = db.execute("SELECT id FROM roles WHERE name = 'Admin'").fetchone()
            if admin_role:
                inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username="tester", password="secret1234"):
        return self.client.post("/login", data={"username": username, "password": password})

    def get_local_ip(self):
        return "127.0.0.1"

    def start_server(self, host_ip):
        server = HTTPServer((host_ip, 0), InventoryLinkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def create_link(self, base_url, *, auth_mode="none", secret=""):
        response = self.client.post(
            "/api/inventory-links",
            json={
                "displayName": "Werkstatt",
                "baseUrl": base_url,
                "authMode": auth_mode,
                "secret": secret,
                "verifyTls": False,
                "allowPrivateNetwork": True,
                "connectionScope": "local",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_inventory_link_validation(self):
        with self.assertRaises(ValueError):
            inventory_app.validate_inventory_link_target("http://127.0.0.1:5001", True)
        inventory_app.validate_inventory_link_target("http://192.168.1.10:5001", True)
        with self.assertRaises(ValueError):
            inventory_app.validate_inventory_link_target("http://192.168.1.10:5001", False)

    def test_connection_scope_enforces_separate_internet_and_lan_policies(self):
        with patch.object(inventory_app, "resolve_inventory_link_ips", return_value=["8.8.8.8"]):
            normalized, scope, verify_tls, allow_private = inventory_app.validate_inventory_link_configuration(
                "https://inventory.example", "internet", True, False
            )
            self.assertEqual(normalized, "https://inventory.example")
            self.assertEqual(scope, "internet")
            self.assertTrue(verify_tls)
            self.assertFalse(allow_private)
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                inventory_app.validate_inventory_link_configuration(
                    "http://inventory.example", "internet", True, False
                )
            with self.assertRaisesRegex(ValueError, "TLS"):
                inventory_app.validate_inventory_link_configuration(
                    "https://inventory.example", "internet", False, False
                )

        with patch.object(inventory_app, "resolve_inventory_link_ips", return_value=["192.168.30.4"]):
            _, scope, _, allow_private = inventory_app.validate_inventory_link_configuration(
                "http://192.168.30.4:5050", "local", False, True
            )
            self.assertEqual(scope, "local")
            self.assertTrue(allow_private)

        with patch.object(inventory_app, "resolve_inventory_link_ips", return_value=["8.8.4.4"]):
            with self.assertRaisesRegex(ValueError, "private LAN"):
                inventory_app.validate_inventory_link_configuration(
                    "https://inventory.example", "local", True, True
                )

    def test_proxy_forwards_headers_and_redirects(self):
        inventory_app.os.environ["INVENTORY_LINKS_ALLOW_LOOPBACK"] = "1"
        host_ip = self.get_local_ip()
        server = self.start_server(host_ip)
        try:
            base_url = f"http://{host_ip}:{server.server_port}"
            with inventory_app.app.app_context():
                db = inventory_app.get_db()
                user = db.execute("SELECT id FROM users WHERE username = ?", ("tester",)).fetchone()
                link_id = "test-link"
                secret_encrypted = inventory_app.encrypt_inventory_link_secret("test-secret")
                db.execute(
                    '''
                    INSERT INTO inventory_links (
                        id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                        allow_private_network, connection_scope
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (link_id, user["id"], "Test", base_url, 1, "apiKey", secret_encrypted, 1, "local")
                )
                db.commit()

            self.login()
            headers_response = self.client.get(f"/api/inventory-links/{link_id}/proxy/headers")
            self.assertEqual(headers_response.status_code, 200)
            headers_payload = headers_response.get_json()
            api_key = None
            for key, value in headers_payload.items():
                if key.lower() == "x-api-key":
                    api_key = value
                    break
            self.assertEqual(api_key, "test-secret")

            redirect_response = self.client.get(f"/api/inventory-links/{link_id}/proxy/redirect")
            self.assertEqual(redirect_response.status_code, 302)
            self.assertEqual(
                redirect_response.headers.get("Location"),
                f"/api/inventory-links/{link_id}/proxy/final"
            )

            stream_response = self.client.get(f"/api/inventory-links/{link_id}/proxy/stream")
            self.assertEqual(stream_response.status_code, 200)
            self.assertEqual(len(stream_response.data), 65536)
        finally:
            server.shutdown()
            server.server_close()

    def test_proxy_rewrites_html_javascript_and_css(self):
        inventory_app.os.environ["INVENTORY_LINKS_ALLOW_LOOPBACK"] = "1"
        host_ip = self.get_local_ip()
        server = self.start_server(host_ip)
        try:
            base_url = f"http://{host_ip}:{server.server_port}"
            with inventory_app.app.app_context():
                db = inventory_app.get_db()
                user = db.execute("SELECT id FROM users WHERE username = ?", ("tester",)).fetchone()
                db.execute(
                    '''
                    INSERT INTO inventory_links (
                        id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                        allow_private_network, connection_scope
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    ("rewrite-link", user["id"], "Rewrite", base_url, 1, "none", "", 1, "local")
                )
                db.commit()

            self.login()
            html_response = self.client.get("/api/inventory-links/rewrite-link/proxy/page")
            self.assertEqual(html_response.status_code, 200)
            html_text = html_response.get_data(as_text=True)
            self.assertIn('<base href="/api/inventory-links/rewrite-link/proxy/">', html_text)
            self.assertIn('href="/api/inventory-links/rewrite-link/proxy/tickets"', html_text)
            self.assertIn('action="/api/inventory-links/rewrite-link/proxy/login"', html_text)
            self.assertIn("fetch('/api/inventory-links/rewrite-link/proxy/api/devices')", html_text)
            self.assertIn("window.location = '/api/inventory-links/rewrite-link/proxy/tickets'", html_text)
            self.assertNotIn("Content-Security-Policy", html_text)
            self.assertEqual(html_response.headers.get("X-Frame-Options"), "SAMEORIGIN")
            self.assertIn(
                "frame-ancestors 'self'",
                html_response.headers.get("Content-Security-Policy", ""),
            )

            js_response = self.client.get("/api/inventory-links/rewrite-link/proxy/static/app.js")
            self.assertEqual(js_response.status_code, 200)
            js_text = js_response.get_data(as_text=True)
            self.assertIn("fetch('/api/inventory-links/rewrite-link/proxy/api/categories')", js_text)
            self.assertIn("const home = '/api/inventory-links/rewrite-link/proxy/'", js_text)
            self.assertIn("const css = '/api/inventory-links/rewrite-link/proxy/static/style.css'", js_text)

            css_response = self.client.get("/api/inventory-links/rewrite-link/proxy/static/style.css")
            self.assertEqual(css_response.status_code, 200)
            css_text = css_response.get_data(as_text=True)
            self.assertIn("url('/api/inventory-links/rewrite-link/proxy/static/bg.png')", css_text)
        finally:
            server.shutdown()
            server.server_close()

    def test_inventory_link_portal_renders_switch_navigation(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            user = db.execute("SELECT id FROM users WHERE username = ?", ("tester",)).fetchone()
            db.execute(
                '''
                INSERT INTO inventory_links (
                    id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                    allow_private_network
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                ("portal-a", user["id"], "Werkstatt", "https://werkstatt.example", 1, "none", "", 0)
            )
            db.execute(
                '''
                INSERT INTO inventory_links (
                    id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                    allow_private_network
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                ("portal-b", user["id"], "Zentrale", "https://hq.example", 1, "none", "", 0)
            )
            db.commit()

        self.login()
        response = self.client.get("/inventory-links/portal-a/portal")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Zurück zu meinem Inventory", body)
        self.assertIn("Werkstatt", body)
        self.assertIn("Zentrale", body)
        self.assertIn('class="sidebar-link active"', body)

    def test_inventory_link_portal_uses_customization_branding_markers(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            user = db.execute("SELECT id FROM users WHERE username = ?", ("tester",)).fetchone()
            db.execute(
                '''
                INSERT INTO inventory_links (
                    id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                    allow_private_network
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                ("portal-branding", user["id"], "Werkstatt", "https://werkstatt.example", 1, "none", "", 0),
            )
            db.commit()

        self.login()
        customization = inventory_app.clone_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        customization["branding"]["name"] = "Beispiel Bestand"
        save_response = self.client.put("/api/customize", json=customization)
        self.assertEqual(save_response.status_code, 200)

        response = self.client.get("/inventory-links/portal-branding/portal")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('data-brand-logo', body)
        self.assertIn('data-brand-logo-icon', body)
        self.assertIn('data-brand-name>Inventory Pro', body)
        self.assertIn('data-brand-tagline>Verknüpfte Instanz', body)

    def test_inventory_link_route_contract(self):
        expected_routes = {
            "/api/inventory-links": ("inventory_links_api", {"GET", "POST"}),
            "/api/inventory-links/test": ("inventory_links_test_draft", {"POST"}),
            "/api/inventory-links/<link_id>": ("inventory_link_detail_api", {"PATCH", "DELETE"}),
            "/api/inventory-links/<link_id>/test": ("inventory_link_test_api", {"POST"}),
            "/api/inventory-links/<link_id>/auth/status": ("inventory_link_auth_status", {"GET"}),
            "/api/inventory-links/<link_id>/auth/login": ("inventory_link_auth_login", {"POST"}),
            "/api/inventory-links/<link_id>/proxy/": (
                "inventory_link_proxy",
                {"GET", "POST", "PUT", "PATCH", "DELETE"},
            ),
            "/api/inventory-links/<link_id>/proxy/<path:subpath>": (
                "inventory_link_proxy",
                {"GET", "POST", "PUT", "PATCH", "DELETE"},
            ),
            "/inventory-links/<link_id>/portal": ("inventory_link_portal", {"GET"}),
        }
        actual_routes = {
            rule.rule: (rule.endpoint, rule.methods - {"HEAD", "OPTIONS"})
            for rule in inventory_app.app.url_map.iter_rules()
            if "inventory-links" in rule.rule
        }
        self.assertEqual(actual_routes, expected_routes)

    def test_inventory_link_crud_and_auth_status(self):
        self.login()
        empty_response = self.client.get("/api/inventory-links")
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.get_json(), [])

        link = self.create_link("http://192.168.30.4:5050")
        self.assertEqual(link["displayName"], "Werkstatt")
        self.assertEqual(link["connectionScope"], "local")

        list_response = self.client.get("/api/inventory-links")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.get_json()], [link["id"]])

        update_response = self.client.patch(
            f"/api/inventory-links/{link['id']}",
            json={"displayName": "Hauptwerkstatt"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["displayName"], "Hauptwerkstatt")

        auth_status = self.client.get(f"/api/inventory-links/{link['id']}/auth/status")
        self.assertEqual(auth_status.status_code, 200)
        self.assertEqual(auth_status.get_json(), {"authenticated": True})

        delete_response = self.client.delete(f"/api/inventory-links/{link['id']}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json(), {"status": "deleted"})

    def test_inventory_link_draft_and_persisted_health_checks(self):
        inventory_app.os.environ["INVENTORY_LINKS_ALLOW_LOOPBACK"] = "1"
        server = self.start_server(self.get_local_ip())
        try:
            self.login()
            base_url = f"http://{self.get_local_ip()}:{server.server_port}"
            draft_response = self.client.post(
                "/api/inventory-links/test",
                json={
                    "baseUrl": base_url,
                    "authMode": "none",
                    "verifyTls": False,
                    "allowPrivateNetwork": True,
                    "connectionScope": "local",
                },
            )
            self.assertEqual(draft_response.status_code, 200)
            self.assertEqual(draft_response.get_json()["status"], "ok")

            link = self.create_link(base_url)
            persisted_response = self.client.post(f"/api/inventory-links/{link['id']}/test")
            self.assertEqual(persisted_response.status_code, 200)
            self.assertEqual(persisted_response.get_json()["status"], "ok")
            with inventory_app.app.app_context():
                row = inventory_app.get_db().execute(
                    "SELECT health_status FROM inventory_links WHERE id = ?",
                    (link["id"],),
                ).fetchone()
            self.assertEqual(row["health_status"], "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_inventory_link_login_and_proxy_post(self):
        inventory_app.os.environ["INVENTORY_LINKS_ALLOW_LOOPBACK"] = "1"
        server = self.start_server(self.get_local_ip())
        try:
            self.login()
            base_url = f"http://{self.get_local_ip()}:{server.server_port}"
            link = self.create_link(base_url, auth_mode="login", secret="stored:secret")

            missing_credentials = self.client.post(f"/api/inventory-links/{link['id']}/auth/login", json={})
            self.assertEqual(missing_credentials.status_code, 400)

            login_response = self.client.post(
                f"/api/inventory-links/{link['id']}/auth/login",
                json={"username": "operator", "password": "secret"},
            )
            self.assertEqual(login_response.status_code, 200)
            self.assertEqual(login_response.get_json(), {"authenticated": True})

            auth_status = self.client.get(f"/api/inventory-links/{link['id']}/auth/status")
            self.assertEqual(auth_status.status_code, 200)
            self.assertEqual(auth_status.get_json(), {"authenticated": True})

            proxy_response = self.client.post(
                f"/api/inventory-links/{link['id']}/proxy/submit",
                data=b"payload",
                headers={"Content-Type": "application/octet-stream"},
            )
            self.assertEqual(proxy_response.status_code, 404)
        finally:
            server.shutdown()
            server.server_close()


class InventoryLinkRouteErrorTestCase(unittest.TestCase):
    link = {
        "id": "link-1",
        "base_url": "https://inventory.example",
        "verify_tls": 1,
        "auth_mode": "none",
        "secret_encrypted": "",
        "allow_private_network": 0,
        "connection_scope": "internet",
        "display_name": "Inventory",
    }

    def build_client(self, **overrides):
        application = Flask(__name__)
        application.secret_key = "route-errors"
        application.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
        database = type(
            "Database",
            (),
            {
                "execute": lambda self, *args, **kwargs: None,
                "commit": lambda self: None,
            },
        )()
        access = {
            "user": {"id": 1},
            "permissions": {"server_settings.manage"},
            "is_superuser": True,
        }
        dependencies = {
            "get_db": lambda: database,
            "get_user_access": lambda database: access,
            "get_inventory_link": lambda database, user_id, link_id: self.link,
            "list_inventory_links": lambda database, user_id: [],
            "serialize_inventory_link": lambda link: {"id": link["id"]},
            "validate_inventory_link_configuration": lambda *args: (
                "https://inventory.example", "internet", True, False
            ),
            "enforce_inventory_link_scope_access": lambda access, scope: None,
            "parse_inventory_link_login_secret": lambda secret: ("operator", "secret"),
            "encrypt_inventory_link_secret": lambda secret: f"encrypted:{secret}",
            "decrypt_inventory_link_secret": lambda encrypted: "operator:secret",
            "perform_inventory_link_test": lambda config: {"status": "ok"},
            "update_inventory_link_health": lambda database, link_id, status: None,
            "get_cached_inventory_link_cookie": lambda link, user_id: None,
            "login_inventory_link_session": lambda base_url, verify_tls, secret: ("cookie=value", None),
            "connection_error": RuntimeError,
            "build_inventory_link_target_url": lambda base_url, subpath, query: base_url,
            "build_inventory_link_request_headers": lambda *args, **kwargs: {},
            "build_inventory_link_ssl_context": lambda verify_tls: None,
            "no_redirect_handler": inventory_app.InventoryLinkNoRedirect,
            "filter_inventory_link_response_headers": lambda headers, link_id, base_url: {},
            "should_rewrite_inventory_link_response": lambda content_type: False,
            "rewrite_inventory_link_text_content": lambda body, content_type, link_id, base_url: body,
            "stream_inventory_link_response": lambda response: (),
            "should_rate_limit_inventory_proxy": lambda user_id: False,
            "login_session_cache": type("Cache", (), {"set": lambda *args: None, "pop": lambda *args: None})(),
            "login_ttl_seconds": 60,
            "proxy_timeout_seconds": 1,
            "allow_private_network_default": False,
            "log_activity": lambda *args, **kwargs: None,
            "login_required": lambda view: view,
        }
        dependencies.update(overrides)
        application.register_blueprint(build_inventory_links_blueprint(**dependencies))
        return application.test_client()

    def test_routes_reject_missing_users_and_links(self):
        no_user = self.build_client(
            get_user_access=lambda database: {"user": None, "permissions": set(), "is_superuser": False}
        )
        self.assertEqual(no_user.get("/inventory-links/link-1/portal").status_code, 302)
        self.assertEqual(no_user.get("/api/inventory-links").status_code, 401)
        self.assertEqual(no_user.post("/api/inventory-links/test", json={}).status_code, 401)
        self.assertEqual(no_user.patch("/api/inventory-links/link-1", json={}).status_code, 401)
        self.assertEqual(no_user.post("/api/inventory-links/link-1/test").status_code, 401)
        self.assertEqual(no_user.get("/api/inventory-links/link-1/auth/status").status_code, 401)
        self.assertEqual(no_user.post("/api/inventory-links/link-1/auth/login", json={}).status_code, 401)
        self.assertEqual(no_user.get("/api/inventory-links/link-1/proxy/").status_code, 401)

        missing_link = self.build_client(get_inventory_link=lambda database, user_id, link_id: None)
        self.assertEqual(missing_link.get("/inventory-links/link-1/portal").status_code, 404)
        self.assertEqual(missing_link.patch("/api/inventory-links/link-1", json={}).status_code, 404)
        self.assertEqual(missing_link.post("/api/inventory-links/link-1/test").status_code, 404)
        self.assertEqual(missing_link.get("/api/inventory-links/link-1/auth/status").status_code, 404)
        self.assertEqual(missing_link.post("/api/inventory-links/link-1/auth/login", json={}).status_code, 404)
        self.assertEqual(missing_link.get("/api/inventory-links/link-1/proxy/").status_code, 404)

    def test_collection_and_draft_validation_errors(self):
        client = self.build_client()
        self.assertEqual(client.post("/api/inventory-links", json={}).status_code, 400)
        self.assertEqual(
            client.post("/api/inventory-links", json={"displayName": "x", "authMode": "invalid"}).status_code,
            400,
        )
        self.assertEqual(
            client.post("/api/inventory-links", json={"displayName": "x", "authMode": "apiKey"}).status_code,
            400,
        )

        invalid_secret = self.build_client(
            parse_inventory_link_login_secret=lambda secret: (_ for _ in ()).throw(ValueError("invalid login secret"))
        )
        self.assertEqual(
            invalid_secret.post(
                "/api/inventory-links",
                json={"displayName": "x", "authMode": "login", "secret": "broken"},
            ).status_code,
            400,
        )

        invalid_target = self.build_client(
            validate_inventory_link_configuration=lambda *args: (_ for _ in ()).throw(ValueError("invalid target"))
        )
        self.assertEqual(
            invalid_target.post("/api/inventory-links", json={"displayName": "x", "authMode": "none"}).status_code,
            400,
        )
        self.assertEqual(
            invalid_target.post("/api/inventory-links/test", json={"authMode": "none"}).status_code,
            400,
        )

        denied_scope = self.build_client(enforce_inventory_link_scope_access=lambda access, scope: "denied")
        self.assertEqual(
            denied_scope.post("/api/inventory-links", json={"displayName": "x", "authMode": "none"}).status_code,
            403,
        )
        self.assertEqual(denied_scope.post("/api/inventory-links/test", json={"authMode": "none"}).status_code, 403)
        self.assertEqual(client.post("/api/inventory-links/test", json={"authMode": "invalid"}).status_code, 400)

        encryption_failure = self.build_client(
            encrypt_inventory_link_secret=lambda secret: (_ for _ in ()).throw(ValueError("key unavailable"))
        )
        self.assertEqual(
            encryption_failure.post(
                "/api/inventory-links",
                json={"displayName": "x", "authMode": "apiKey", "secret": "value"},
            ).status_code,
            400,
        )

    def test_detail_validation_errors(self):
        client = self.build_client()
        self.assertEqual(client.patch("/api/inventory-links/link-1", json={"displayName": " "}).status_code, 400)
        self.assertEqual(client.patch("/api/inventory-links/link-1", json={"authMode": "invalid"}).status_code, 400)

        login_link = dict(self.link, auth_mode="login", secret_encrypted="stored")
        invalid_login = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            parse_inventory_link_login_secret=lambda secret: (_ for _ in ()).throw(ValueError("invalid login secret")),
        )
        self.assertEqual(invalid_login.patch("/api/inventory-links/link-1", json={}).status_code, 400)
        self.assertEqual(
            invalid_login.patch(
                "/api/inventory-links/link-1",
                json={"secret": "broken"},
            ).status_code,
            400,
        )

        invalid_target = self.build_client(
            validate_inventory_link_configuration=lambda *args: (_ for _ in ()).throw(ValueError("invalid target"))
        )
        self.assertEqual(invalid_target.patch("/api/inventory-links/link-1", json={}).status_code, 400)
        denied_scope = self.build_client(enforce_inventory_link_scope_access=lambda access, scope: "denied")
        self.assertEqual(denied_scope.patch("/api/inventory-links/link-1", json={}).status_code, 403)

        missing_secret_link = dict(self.link, auth_mode="apiKey", secret_encrypted="")
        missing_secret = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: missing_secret_link
        )
        self.assertEqual(
            missing_secret.patch("/api/inventory-links/link-1", json={"authMode": "apiKey", "secret": ""}).status_code,
            400,
        )

        encryption_failure = self.build_client(
            encrypt_inventory_link_secret=lambda secret: (_ for _ in ()).throw(ValueError("key unavailable"))
        )
        self.assertEqual(
            encryption_failure.patch(
                "/api/inventory-links/link-1",
                json={"authMode": "apiKey", "secret": "value"},
            ).status_code,
            400,
        )
        self.assertEqual(
            client.patch("/api/inventory-links/link-1", json={"authMode": "none", "secret": ""}).status_code,
            200,
        )

    def test_diagnostic_and_login_error_contracts(self):
        encrypted_link = dict(self.link, auth_mode="apiKey", secret_encrypted="stored")
        decrypt_failure = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: encrypted_link,
            decrypt_inventory_link_secret=lambda encrypted: (_ for _ in ()).throw(ValueError("key unavailable")),
        )
        self.assertEqual(decrypt_failure.post("/api/inventory-links/link-1/test").status_code, 400)

        non_login = self.build_client()
        self.assertEqual(non_login.post("/api/inventory-links/link-1/auth/login", json={}).status_code, 400)

        login_link = dict(self.link, auth_mode="login")
        invalid_target = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            validate_inventory_link_configuration=lambda *args: (_ for _ in ()).throw(ValueError("invalid target")),
        )
        self.assertEqual(
            invalid_target.post(
                "/api/inventory-links/link-1/auth/login",
                json={"username": "operator", "password": "secret"},
            ).status_code,
            400,
        )
        denied_scope = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            enforce_inventory_link_scope_access=lambda access, scope: "denied",
        )
        self.assertEqual(
            denied_scope.post(
                "/api/inventory-links/link-1/auth/login",
                json={"username": "operator", "password": "secret"},
            ).status_code,
            403,
        )
        login_value_error = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            login_inventory_link_session=lambda base_url, verify_tls, secret: (_ for _ in ()).throw(ValueError("invalid")),
        )
        self.assertEqual(
            login_value_error.post(
                "/api/inventory-links/link-1/auth/login",
                json={"username": "operator", "password": "secret"},
            ).status_code,
            401,
        )
        login_connection_error = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            login_inventory_link_session=lambda base_url, verify_tls, secret: (_ for _ in ()).throw(RuntimeError("offline")),
        )
        self.assertEqual(
            login_connection_error.post(
                "/api/inventory-links/link-1/auth/login",
                json={"username": "operator", "password": "secret"},
            ).status_code,
            502,
        )
        no_cookie = self.build_client(
            get_inventory_link=lambda database, user_id, link_id: login_link,
            login_inventory_link_session=lambda base_url, verify_tls, secret: (None, None),
        )
        self.assertEqual(
            no_cookie.post(
                "/api/inventory-links/link-1/auth/login",
                json={"username": "operator", "password": "secret"},
            ).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
