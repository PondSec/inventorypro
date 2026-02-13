import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class CloudIntegrationTestCase(unittest.TestCase):
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
            "debug": False,
        }
        self.shared_secret = "cloud-integration-secret-123"

        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            admin_pw = inventory_app.generate_password_hash("secret1234")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("cloud-admin", admin_pw),
            )
            inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")

            db.execute(
                """
                UPDATE cloud_integration_settings
                SET enabled = 1,
                    cloud_base_url = ?,
                    shared_secret_hash = ?,
                    sync_enabled = 1,
                    sso_enabled = 1,
                    auto_provision_users = 1,
                    default_role_name = ?
                WHERE id = 1
                """,
                (
                    "http://127.0.0.1:5173",
                    inventory_app.generate_password_hash(self.shared_secret),
                    inventory_app.DEFAULT_ROLE_NAME,
                ),
            )

            category_id = db.execute(
                "INSERT INTO asset_categories (name) VALUES (?)",
                ("Laptops",),
            ).lastrowid
            db.execute(
                "INSERT INTO assets (name, category_id, notes) VALUES (?, ?, ?)",
                ("Lenovo T14", category_id, "Cloud Pilot Asset"),
            )
            db.execute(
                "INSERT INTO tickets (title, description, status, created_by) VALUES (?, ?, ?, ?)",
                ("Cloud Sync Ticket", "Need cloud integration", "open", "cloud-admin"),
            )
            db.commit()

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _headers(self):
        return {"X-InventoryPro-Secret": self.shared_secret}

    def test_cloud_user_sync_and_sso_login(self):
        sync = self.client.post(
            "/api/integration/cloud/users/sync",
            headers=self._headers(),
            json={
                "subject": "cloud-u-101",
                "username": "cloud-agent",
                "email": "cloud-agent@example.com",
                "role_names": ["Mitarbeiter"],
            },
        )
        self.assertEqual(sync.status_code, 200)
        payload = sync.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["status"], "created")

        ticket_res = self.client.post(
            "/api/integration/cloud/sso/ticket",
            headers=self._headers(),
            json={
                "subject": "cloud-u-101",
                "username": "cloud-agent",
                "email": "cloud-agent@example.com",
            },
        )
        self.assertEqual(ticket_res.status_code, 200)
        ticket = ticket_res.get_json()["ticket"]
        self.assertTrue(ticket)

        login = self.client.get(
            f"/integration/cloud/sso/login?ticket={ticket}&next=/tickets",
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.headers.get("Location"), "/tickets")

        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["username"], "cloud-agent")

    def test_cloud_summary_search_recents(self):
        summary = self.client.get("/api/integration/cloud/summary", headers=self._headers())
        self.assertEqual(summary.status_code, 200)
        summary_payload = summary.get_json()
        self.assertGreaterEqual(summary_payload["counts"]["assets"], 1)
        self.assertGreaterEqual(summary_payload["counts"]["tickets_total"], 1)

        recents = self.client.get("/api/integration/cloud/recents?limit=5", headers=self._headers())
        self.assertEqual(recents.status_code, 200)
        recents_payload = recents.get_json()
        self.assertGreaterEqual(recents_payload["count"], 1)

        search = self.client.get("/api/integration/cloud/search?q=lenovo&limit=10", headers=self._headers())
        self.assertEqual(search.status_code, 200)
        search_payload = search.get_json()
        self.assertTrue(any(item["type"] == "asset" for item in search_payload["items"]))

    def test_integration_secret_required(self):
        response = self.client.get("/api/integration/cloud/summary")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
