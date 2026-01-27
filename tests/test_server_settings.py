import json
import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class ServerSettingsTestCase(unittest.TestCase):
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

    def test_get_and_update_settings(self):
        self.login()
        response = self.client.get("/api/settings/server")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        settings = payload["settings"]
        settings["server"]["host"] = "127.0.0.1"
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()
        self.assertTrue(updated["meta"]["pendingRestart"])

    def test_invalid_port_rejected(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["server"]["port"] = 70000
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 400)

    def test_backup_run(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["backup"]["enabled"] = True
        settings["backup"]["directory"] = str(Path(self.temp_dir.name) / "backups")
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 200)
        run_response = self.client.post("/api/backups/run", json={"force": True})
        self.assertEqual(run_response.status_code, 200)
        result = run_response.get_json()
        self.assertIn(result["status"], {"success", "failed"})

    def test_login_lockout(self):
        for _ in range(5):
            self.client.post("/login", data={"username": "tester", "password": "wrong"})
        response = self.client.post("/login", data={"username": "tester", "password": "secret1234"})
        self.assertIn("gesperrt", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
