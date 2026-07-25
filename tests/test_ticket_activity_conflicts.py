import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class TicketActivityConflictTestCase(unittest.TestCase):
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
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("workflow_admin", password_hash),
            )
            inventory_app.assign_user_role(db, user.lastrowid, "Admin")
            db.commit()

        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "workflow_admin"
            session["mfa_verified"] = True

        created = self.client.post(
            "/api/tickets",
            json={
                "title": "Parallelbearbeitung prüfen",
                "description": "Änderungen müssen mit einer Version geschützt werden.",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        self.ticket_id = created.get_json()["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_stale_update_is_rejected_and_activity_contains_differences(self):
        original = self.client.get(f"/api/tickets/{self.ticket_id}").get_json()
        first_update = self.client.put(
            f"/api/tickets/{self.ticket_id}",
            json={
                "updated_at": original["updated_at"],
                "assignee": "operations",
            },
        )
        self.assertEqual(first_update.status_code, 200, first_update.get_data(as_text=True))
        self.assertNotEqual(first_update.get_json()["updated_at"], original["updated_at"])

        stale_update = self.client.put(
            f"/api/tickets/{self.ticket_id}",
            json={
                "updated_at": original["updated_at"],
                "priority": "urgent",
            },
        )
        self.assertEqual(stale_update.status_code, 409)
        self.assertEqual(stale_update.get_json()["code"], "ticket_update_conflict")

        comment = self.client.post(
            f"/api/tickets/{self.ticket_id}/comments",
            json={"body": "Kontrollhinweis dokumentiert.", "is_internal": True},
        )
        self.assertEqual(comment.status_code, 201, comment.get_data(as_text=True))

        detail = self.client.get(f"/api/tickets/{self.ticket_id}").get_json()
        update_activity = next(item for item in detail["activity"] if item["action"] == "update")
        self.assertTrue(any(change["key"] == "assignee" for change in update_activity["changes"]))
        comment_activity = next(item for item in detail["activity"] if item["action"] == "comment")
        self.assertEqual(comment_activity["details"]["preview"], "Kontrollhinweis dokumentiert.")
        self.assertTrue(comment_activity["details"]["is_internal"])


if __name__ == "__main__":
    unittest.main()
