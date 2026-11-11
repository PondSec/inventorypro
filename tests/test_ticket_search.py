import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class TicketSearchTestCase(unittest.TestCase):
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
            user = db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("search_admin", "requester@example.test", password_hash),
            )
            inventory_app.assign_user_role(db, user.lastrowid, "Admin")
            device_category = db.execute(
                "INSERT INTO categories (name) VALUES (?)",
                ("Search Devices",),
            )
            location = db.execute(
                "INSERT INTO locations (name) VALUES (?)",
                ("Datacenter Nord",),
            )
            device = db.execute(
                """
                INSERT INTO devices (name, category_id, serial_number, location_id)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "Firewall Cluster",
                    device_category.lastrowid,
                    "SERIAL-ENTERPRISE-42",
                    location.lastrowid,
                ),
            )
            asset_category = db.execute(
                "INSERT INTO asset_categories (name) VALUES (?)",
                ("Netzwerkkomponenten",),
            )
            asset = db.execute(
                "INSERT INTO assets (name, category_id, notes) VALUES (?, ?, ?)",
                ("Perimeter Firewall", asset_category.lastrowid, "Kritische Infrastruktur"),
            )
            db.execute(
                "INSERT INTO asset_devices (asset_id, device_id) VALUES (?, ?)",
                (asset.lastrowid, device.lastrowid),
            )
            self.asset_id = asset.lastrowid
            db.commit()

        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "search_admin"
            session["mfa_verified"] = True

        response = self.client.post(
            "/api/tickets",
            json={
                "title": "Netzwerkzugang gestört",
                "description": "Verbindung zum Standort prüfen.",
                "priority": "high",
                "asset_ids": [self.asset_id],
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.ticket_id = response.get_json()["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def assert_search_finds_ticket(self, term):
        response = self.client.get(
            "/api/tickets",
            query_string={
                "page": 1,
                "per_page": 25,
                "queue": "all-open",
                "search": term,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertIn(self.ticket_id, [item["id"] for item in response.get_json()["items"]])

    def test_searches_business_identifiers_and_asset_relations(self):
        for search_term in (
            f"#{self.ticket_id}",
            "requester@example.test",
            "Perimeter Firewall",
            "SERIAL-ENTERPRISE-42",
            "Datacenter Nord",
            "Netzwerkkomponenten",
        ):
            with self.subTest(search_term=search_term):
                self.assert_search_finds_ticket(search_term)


if __name__ == "__main__":
    unittest.main()
