import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class LocationDeletionTestCase(unittest.TestCase):
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
                ("location_admin", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, admin_id, "Admin")
            used_location_id = db.execute(
                "INSERT INTO locations (name) VALUES (?)",
                ("Verwendeter Standort",),
            ).lastrowid
            unused_location_id = db.execute(
                "INSERT INTO locations (name) VALUES (?)",
                ("Leerer Standort",),
            ).lastrowid
            category_id = db.execute(
                "INSERT INTO categories (name) VALUES (?)",
                ("Standorttest",),
            ).lastrowid
            db.execute(
                "INSERT INTO devices (name, category_id, location_id) VALUES (?, ?, ?)",
                ("Standortgerät", category_id, used_location_id),
            )
            asset_id = db.execute(
                "INSERT INTO assets (name, specs) VALUES (?, ?)",
                ("Standortasset", "{}"),
            ).lastrowid
            db.execute(
                """
                INSERT INTO asset_assignments (asset_id, user_identifier, location_id)
                VALUES (?, ?, ?)
                """,
                (asset_id, "location_admin", used_location_id),
            )
            db.commit()
            self.used_location_id = used_location_id
            self.unused_location_id = unused_location_id
        self.client = inventory_app.app.test_client()
        self.client.post(
            "/login",
            data={"username": "location_admin", "password": "secret1234"},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_used_location_returns_conflict_without_data_loss(self):
        response = self.client.delete(f"/api/locations/{self.used_location_id}")

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "location_in_use")
        self.assertEqual(payload["references"]["devices"], 1)
        self.assertEqual(payload["references"]["asset_assignments"], 1)
        with inventory_app.app.app_context():
            location = inventory_app.get_db().execute(
                "SELECT id FROM locations WHERE id = ?",
                (self.used_location_id,),
            ).fetchone()
        self.assertIsNotNone(location)

    def test_unused_location_can_be_deleted(self):
        response = self.client.delete(f"/api/locations/{self.unused_location_id}")

        self.assertEqual(response.status_code, 200)
        with inventory_app.app.app_context():
            location = inventory_app.get_db().execute(
                "SELECT id FROM locations WHERE id = ?",
                (self.unused_location_id,),
            ).fetchone()
        self.assertIsNone(location)


if __name__ == "__main__":
    unittest.main()
