import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class EnterpriseWorkflowHubTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        inventory_app.DATABASE = str(temp_path / "test_inventory.db")
        inventory_app.UPLOADS_DIR = temp_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temp_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temp_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "127.0.0.1",
            "port": 0,
            "debug": False,
        }

        with contextlib.redirect_stdout(io.StringIO()):
            inventory_app.init_db()

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            admin_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("enterprise_admin", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, admin_id, "Admin")
            category_id = db.execute(
                "INSERT INTO categories (name, icon) VALUES (?, ?)",
                ("Notebook", "monitor"),
            ).lastrowid
            asset_category_id = db.execute(
                "INSERT INTO asset_categories (name, icon) VALUES (?, ?)",
                ("Audit-Arbeitsplatz", "package"),
            ).lastrowid
            device_id = db.execute(
                "INSERT INTO devices (name, category_id, serial_number) VALUES (?, ?, ?)",
                ("Notebook ohne Standort", category_id, ""),
            ).lastrowid
            asset_id = db.execute(
                "INSERT INTO assets (name, category_id) VALUES (?, ?)",
                ("Arbeitsplatz Hamburg", asset_category_id),
            ).lastrowid
            db.execute(
                "INSERT INTO asset_devices (asset_id, device_id) VALUES (?, ?)",
                (asset_id, device_id),
            )
            ticket_category_id = db.execute(
                "SELECT id FROM ticket_categories WHERE is_default = 1 LIMIT 1"
            ).fetchone()["id"]
            db.execute(
                """
                INSERT INTO tickets (title, description, category_id, status, priority, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Ticket ohne Asset-Kontext",
                    "Soll im Enterprise-Cockpit als Lücke erscheinen.",
                    ticket_category_id,
                    "open",
                    "normal",
                    "System",
                ),
            )
            db.commit()

        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "enterprise_admin"
            session["mfa_verified"] = True

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_workflow_hub_returns_aggregated_enterprise_signals(self):
        response = self.client.get("/api/enterprise/workflow-hub")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIn("score", payload)
        self.assertIn("integration_score", payload)
        self.assertGreaterEqual(payload["score"], 0)
        self.assertLessEqual(payload["score"], 100)

        signal_keys = {signal["key"] for signal in payload["signals"]}
        self.assertIn("device_identity", signal_keys)
        self.assertIn("service_context", signal_keys)
        self.assertIn("integration_depth", signal_keys)

        service_context = next(signal for signal in payload["signals"] if signal["key"] == "service_context")
        self.assertEqual(service_context["value"], 1)
        self.assertEqual(service_context["target_url"], "/tickets?queue=all-open")

    def test_workflow_hub_requires_login(self):
        anonymous_client = inventory_app.app.test_client()
        response = anonymous_client.get("/api/enterprise/workflow-hub")

        self.assertEqual(response.status_code, 302)

    def set_restricted_role(self, permissions):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            user_id = db.execute("INSERT INTO users (username,password_hash) VALUES ('restricted','unused')").lastrowid
            role_id = db.execute("INSERT INTO roles (name) VALUES ('Restricted workflow')").lastrowid
            db.execute("INSERT INTO user_roles (user_id,role_id) VALUES (?,?)", (user_id,role_id))
            for permission in permissions:
                permission_id = db.execute("SELECT id FROM permissions WHERE key=?", (permission,)).fetchone()[0]
                db.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (?,?)", (role_id,permission_id))
            db.commit()
        with self.client.session_transaction() as session:
            session['username'] = 'restricted'
        return user_id

    def test_category_permission_does_not_disclose_inventory_counts(self):
        self.set_restricted_role(['categories.view'])
        self.assertEqual(self.client.get('/api/enterprise/workflow-hub').status_code, 403)

    def test_own_ticket_signals_exclude_other_users(self):
        user_id = self.set_restricted_role(['categories.view', 'devices.view', 'assets.view', 'tickets.view_own'])
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute("INSERT INTO tickets (title,description,status,created_by,created_by_user_id,due_date) VALUES ('Own','Synthetic test','open','restricted',?,'2000-01-01')", (user_id,))
            db.commit()
        response = self.client.get('/api/enterprise/workflow-hub')
        self.assertEqual(response.status_code, 200)
        signals = {item['key']: item['value'] for item in response.json['signals']}
        self.assertEqual(signals['service_context'], 1)
        self.assertEqual(signals['service_risk'], 1)


if __name__ == "__main__":
    unittest.main()
