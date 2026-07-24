import json
import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class DeviceValidationTestCase(unittest.TestCase):
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

        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            admin_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("test_admin", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, admin_id, "Admin")
            self.category_id = db.execute(
                "INSERT INTO categories (name, icon, fields) VALUES (?, ?, ?)",
                (
                    "Notebook",
                    "cpu",
                    json.dumps({
                        "RAM": {"type": "number", "unit": "GB"},
                        "Wartung": {"type": "date"},
                        "Status": {"type": "select", "options": ["Lager", "Verwendet"]},
                        "Aktiv": {"type": "checkbox"},
                    }),
                ),
            ).lastrowid
            self.location_id = db.execute(
                "INSERT INTO locations (name) VALUES (?)",
                ("Berlin",),
            ).lastrowid
            db.commit()

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "test_admin", "password": "secret1234"})

    def test_create_device_returns_structured_field_errors(self):
        self.login()
        response = self.client.post(
            "/api/devices",
            json={
                "name": "",
                "category_id": self.category_id,
                "location_id": "abc",
                "specs": {
                    "RAM": "viel",
                    "Wartung": "08.05.2026",
                    "Status": "Defekt",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "Bitte die markierten Felder prüfen")
        self.assertIn("name", payload["field_errors"])
        self.assertIn("location_id", payload["field_errors"])
        self.assertIn("specs.RAM", payload["field_errors"])
        self.assertIn("specs.Wartung", payload["field_errors"])
        self.assertIn("specs.Status", payload["field_errors"])

    def test_create_device_normalizes_specs_by_field_type(self):
        self.login()
        response = self.client.post(
            "/api/devices",
            json={
                "name": "NB-001",
                "category_id": self.category_id,
                "serial_number": "NB-001",
                "location_id": self.location_id,
                "specs": {
                    "RAM": "16,5",
                    "Wartung": "2026-05-08",
                    "Status": "Lager",
                    "Aktiv": "on",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        device_id = response.get_json()["id"]

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            device = db.execute(
                "SELECT name, serial_number, location_id, specs FROM devices WHERE id = ?",
                (device_id,),
            ).fetchone()

        self.assertEqual(device["name"], "NB-001")
        self.assertEqual(device["serial_number"], "NB-001")
        self.assertEqual(device["location_id"], self.location_id)
        specs = json.loads(device["specs"])
        self.assertEqual(specs["RAM"], 16.5)
        self.assertEqual(specs["Wartung"], "2026-05-08")
        self.assertEqual(specs["Status"], "Lager")
        self.assertTrue(specs["Aktiv"])


if __name__ == "__main__":
    unittest.main()
