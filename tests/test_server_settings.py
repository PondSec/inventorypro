import os
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

import app as inventory_app


class ServerSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(prefix="inventorypro-test-", suffix=".db")
        inventory_app.DATABASE = self.db_path
        inventory_app.app.config['TESTING'] = True
        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            password_hash = generate_password_hash("secret")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("tester-admin", password_hash),
            )
            role = db.execute("SELECT id FROM roles WHERE is_superuser = 1").fetchone()
            if role:
                db.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (cursor.lastrowid, role["id"]))
            db.commit()
        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session['logged_in'] = True
            session['username'] = 'tester-admin'

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_settings_get_put(self):
        response = self.client.get('/api/settings/server')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["schemaVersion"], 1)
        self.assertIn("settings", data)

        payload = data["settings"]
        payload.update({
            "host": "127.0.0.1",
            "port": 5050,
            "debug": False,
            "backup_enabled": False
        })
        response = self.client.put('/api/settings/server', json=payload)
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()
        self.assertTrue(updated["pendingRestart"])

    def test_settings_validation(self):
        response = self.client.put('/api/settings/server', json={"host": "x", "port": 70000})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("fields", data)
        self.assertIn("port", data["fields"])

    def test_backup_run(self):
        backup_dir = tempfile.mkdtemp(prefix="inventorypro-backup-")
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            settings = inventory_app.normalize_server_settings(inventory_app.get_server_settings(db))
            settings.update({
                "backup_enabled": True,
                "backup_schedule": "daily",
                "backup_location": backup_dir,
            })
            inventory_app.save_server_settings(db, settings, "tester-admin")
            db.commit()

        response = self.client.post('/api/backups/run', json={})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(Path(data["file"]).exists())

    def test_export_gating(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            settings = inventory_app.normalize_server_settings(inventory_app.get_server_settings(db))
            settings["allow_db_export"] = False
            inventory_app.save_server_settings(db, settings, "tester-admin")
            db.commit()
        response = self.client.get('/api/export')
        self.assertEqual(response.status_code, 403)

    def test_login_lockout(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            settings = inventory_app.normalize_server_settings(inventory_app.get_server_settings(db))
            settings["max_failed_logins"] = 2
            inventory_app.save_server_settings(db, settings, "tester-admin")
            db.commit()
        client = inventory_app.app.test_client()
        for _ in range(2):
            client.post('/login', data={"username": "tester-admin", "password": "wrong"})
        response = client.post('/login', data={"username": "tester-admin", "password": "wrong"})
        self.assertIn("gesperrt", response.get_data(as_text=True))

    def test_ip_whitelist_block(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            settings = inventory_app.normalize_server_settings(inventory_app.get_server_settings(db))
            settings["allowed_ip_ranges"] = "10.0.0.0/24"
            inventory_app.save_server_settings(db, settings, "tester-admin")
            db.commit()
        response = self.client.get('/api/me')
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
