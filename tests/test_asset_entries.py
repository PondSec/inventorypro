import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class AssetEntryTestCase(unittest.TestCase):
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
            category_id = db.execute(
                "INSERT INTO categories (name, icon) VALUES (?, ?)",
                ("Hardware", "cpu"),
            ).lastrowid
            self.device_id = db.execute(
                "INSERT INTO devices (name, category_id) VALUES (?, ?)",
                ("Monitor", category_id),
            ).lastrowid
            db.commit()

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "test_admin", "password": "secret1234"})

    def test_create_category_entry_and_assign_device(self):
        self.login()
        category_response = self.client.post(
            "/api/asset-categories",
            json={"name": "Arbeitsplätze"},
        )
        self.assertEqual(category_response.status_code, 201)
        category_id = category_response.get_json()["id"]

        entry_response = self.client.post(
            "/api/asset-entries",
            json={"name": "Arbeitsplatz 1", "category_id": category_id},
        )
        self.assertEqual(entry_response.status_code, 201)
        entry_id = entry_response.get_json()["id"]

        assign_response = self.client.post(
            f"/api/asset-entries/{entry_id}/devices",
            json={"items": [{"device_id": self.device_id, "quantity": 1}]},
        )
        self.assertEqual(assign_response.status_code, 201)

        list_response = self.client.get(f"/api/asset-entries?category_id={category_id}")
        self.assertEqual(list_response.status_code, 200)
        entries = list_response.get_json()
        self.assertEqual(entries[0]["name"], "Arbeitsplatz 1")

    def test_duplicate_device_assignment_is_blocked(self):
        self.login()
        category_response = self.client.post(
            "/api/asset-categories",
            json={"name": "Computer"},
        )
        category_id = category_response.get_json()["id"]

        first_entry = self.client.post(
            "/api/asset-entries",
            json={"name": "PC-01", "category_id": category_id},
        ).get_json()["id"]
        second_entry = self.client.post(
            "/api/asset-entries",
            json={"name": "PC-02", "category_id": category_id},
        ).get_json()["id"]

        self.client.post(
            f"/api/asset-entries/{first_entry}/devices",
            json={"items": [{"device_id": self.device_id, "quantity": 1}]},
        )
        duplicate_response = self.client.post(
            f"/api/asset-entries/{second_entry}/devices",
            json={"items": [{"device_id": self.device_id, "quantity": 1}]},
        )
        self.assertEqual(duplicate_response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
