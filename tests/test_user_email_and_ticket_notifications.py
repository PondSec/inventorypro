import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import app as inventory_app


class UserEmailAndTicketNotificationsTestCase(unittest.TestCase):
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
            "debug": False
        }
        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                ("tester", password_hash, "tester@example.com")
            )
            inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username="tester", password="secret1234"):
        return self.client.post("/login", data={"username": username, "password": password})

    def test_user_email_validation_and_uniqueness(self):
        self.login()
        response = self.client.post(
            "/api/users",
            json={"username": "user1", "password": "strongpass1", "email": "invalid"}
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/users",
            json={"username": "user2", "password": "strongpass1", "email": "user2@example.com"}
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            "/api/users",
            json={"username": "user3", "password": "strongpass1", "email": "user2@example.com"}
        )
        self.assertEqual(response.status_code, 400)

    def test_ticket_author_is_immutable(self):
        self.login()
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            creator = db.execute(
                "SELECT id FROM users WHERE username = ?",
                ("tester",)
            ).fetchone()
            ticket_cursor = db.execute(
                """
                INSERT INTO tickets (title, description, priority, status, created_by_user_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Test", "Beschreibung", "normal", "open", creator["id"], "tester")
            )
            db.commit()
            ticket_id = ticket_cursor.lastrowid

        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"created_by": "hacker"}
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={"created_by_user_id": 999}
        )
        self.assertEqual(response.status_code, 400)

    def test_ticket_notification_targets_creator(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE notification_settings SET enabled = 1, smtp_host = ?, smtp_port = ?, "
                "smtp_username = ?, smtp_password = ?, smtp_from = ? WHERE id = 1",
                ("smtp.example.com", 587, "noreply@example.com", "secret", "noreply@example.com")
            )
            creator_cursor = db.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                ("creator", "hash", "creator@example.com")
            )
            ticket_cursor = db.execute(
                """
                INSERT INTO tickets (title, description, priority, status, created_by_user_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Mail Test", "Ticket Beschreibung", "normal", "open", creator_cursor.lastrowid, "creator")
            )
            db.commit()
            ticket = inventory_app.fetch_ticket(db, ticket_cursor.lastrowid)
            changes = [
                {"key": "status", "label": "Status", "before": "Offen", "after": "In Bearbeitung"}
            ]
            with patch("app.send_notification_email") as mock_send:
                inventory_app.trigger_ticket_notifications(
                    db,
                    "updated",
                    ticket,
                    changes=changes,
                    actor="Admin"
                )
                mock_send.assert_called_once()
                args, kwargs = mock_send.call_args
                recipients = args[1]
                text_body = args[3]
                self.assertEqual(recipients, ["creator@example.com"])
                self.assertIn("Status: Offen → In Bearbeitung", text_body)


if __name__ == "__main__":
    unittest.main()
