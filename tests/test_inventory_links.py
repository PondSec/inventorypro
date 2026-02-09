import json
import socket
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import unittest

from cryptography.fernet import Fernet

import app as inventory_app


class InventoryLinkHandler(BaseHTTPRequestHandler):
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

    def test_inventory_link_validation(self):
        with self.assertRaises(ValueError):
            inventory_app.validate_inventory_link_target("http://127.0.0.1:5001", True)
        inventory_app.validate_inventory_link_target("http://192.168.1.10:5001", True)
        with self.assertRaises(ValueError):
            inventory_app.validate_inventory_link_target("http://192.168.1.10:5001", False)

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
                        allow_private_network
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (link_id, user["id"], "Test", base_url, 1, "apiKey", secret_encrypted, 1)
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


if __name__ == "__main__":
    unittest.main()
