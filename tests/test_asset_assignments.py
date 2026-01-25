import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class AssetAssignmentTestCase(unittest.TestCase):
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
            assignee_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("assignee", password_hash),
            ).lastrowid
            viewer_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("viewer", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, viewer_id, "Kunde")
            team_id = db.execute(
                "INSERT INTO teams (name) VALUES (?)",
                ("IT Team",),
            ).lastrowid
            asset_id = db.execute(
                "INSERT INTO assets (name, notes, specs) VALUES (?, ?, ?)",
                ("Laptop", "Test", "{}"),
            ).lastrowid
            db.commit()
            self.asset_id = asset_id
            self.assignee_id = assignee_id
            self.team_id = team_id

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username="test_admin", password="secret1234"):
        return self.client.post("/login", data={"username": username, "password": password})

    def test_assignment_checkout_checkin_flow(self):
        self.login()
        assign_response = self.client.post(
            f"/assets/{self.asset_id}/assign",
            json={"assigned_to_user_id": self.assignee_id, "note": "Start"},
        )
        self.assertEqual(assign_response.status_code, 200)
        payload = assign_response.get_json()
        self.assertEqual(payload["assignment"]["status"], "assigned")

        checkout_response = self.client.post(
            f"/assets/{self.asset_id}/checkout",
            json={
                "assigned_to_user_id": self.assignee_id,
                "due_at": "2024-12-31",
                "note": "Ausgabe",
            },
        )
        self.assertEqual(checkout_response.status_code, 200)
        payload = checkout_response.get_json()
        self.assertEqual(payload["assignment"]["status"], "checked_out")

        checkin_response = self.client.post(
            f"/assets/{self.asset_id}/checkin",
            json={"note": "Zurück"},
        )
        self.assertEqual(checkin_response.status_code, 200)
        payload = checkin_response.get_json()
        self.assertEqual(payload["assignment"]["status"], "checked_in")

    def test_checkin_requires_checkout(self):
        self.login()
        response = self.client.post(
            f"/assets/{self.asset_id}/checkin",
            json={"note": "Ohne Checkout"},
        )
        self.assertEqual(response.status_code, 400)

    def test_rbac_blocks_assignment(self):
        self.login(username="viewer", password="secret1234")
        response = self.client.post(
            f"/assets/{self.asset_id}/assign",
            json={"assigned_to_team_id": self.team_id},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
