import os
import tempfile
import unittest

import app as inventory_app


class ServerSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(prefix="inventorypro-test-", suffix=".db")
        inventory_app.DATABASE = self.db_path
        inventory_app.app.config['TESTING'] = True
        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin_tester", inventory_app.generate_password_hash("secretpass")),
            )
            user_id = db.execute("SELECT id FROM users WHERE username = ?", ("admin_tester",)).fetchone()["id"]
            inventory_app.assign_user_role(db, user_id, "Admin")
            db.commit()
        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session['logged_in'] = True
            session['username'] = 'admin_tester'

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_get_and_update_settings(self):
        response = self.client.get('/api/settings/server')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("settings", data)
        payload = data["settings"]
        payload["server"]["port"] = 5055
        payload["backup"]["retentionDays"] = 30
        response = self.client.put('/api/settings/server', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["settings"]["server"]["port"], 5055)
        self.assertEqual(data["settings"]["backup"]["retentionDays"], 30)

    def test_settings_validation(self):
        response = self.client.get('/api/settings/server')
        payload = response.get_json()["settings"]
        payload["server"]["port"] = 99999
        response = self.client.put('/api/settings/server', json=payload)
        self.assertEqual(response.status_code, 400)
        details = response.get_json().get("details", {})
        self.assertIn("server.port", details)

    def test_ip_whitelist_blocks(self):
        response = self.client.get('/api/settings/server')
        payload = response.get_json()["settings"]
        payload["security"]["ipWhitelist"] = "10.0.0.0/24"
        response = self.client.put(
            '/api/settings/server',
            json=payload,
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        )
        self.assertEqual(response.status_code, 200)
        blocked = self.client.get('/api/settings/server', environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(blocked.status_code, 403)

    def test_login_lockout(self):
        response = self.client.get('/api/settings/server')
        payload = response.get_json()["settings"]
        payload["security"]["maxFailedAttempts"] = 1
        payload["security"]["lockoutMinutes"] = 1
        response = self.client.put('/api/settings/server', json=payload)
        self.assertEqual(response.status_code, 200)

        anon_client = inventory_app.app.test_client()
        anon_client.post('/login', data={"username": "admin_tester", "password": "badpass"})
        locked = anon_client.post('/login', data={"username": "admin_tester", "password": "badpass"})
        self.assertIn("gesperrt", locked.get_data(as_text=True).lower())


if __name__ == '__main__':
    unittest.main()
