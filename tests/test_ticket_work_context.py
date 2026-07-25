import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class TicketWorkContextTestCase(unittest.TestCase):
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
            user = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("context_admin", inventory_app.generate_password_hash("secret1234")),
            )
            inventory_app.assign_user_role(db, user.lastrowid, "Admin")
            self.knowledge_category_id = db.execute(
                "SELECT id FROM knowledge_categories ORDER BY id LIMIT 1"
            ).fetchone()["id"]
            db.commit()
        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "context_admin"
            session["mfa_verified"] = True

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_ticket(self, title, description):
        response = self.client.post(
            "/api/tickets",
            json={"title": title, "description": description, "priority": "high"},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["id"]

    def close_ticket(self, ticket_id, resolution):
        detail = self.client.get(f"/api/tickets/{ticket_id}").get_json()
        response = self.client.put(
            f"/api/tickets/{ticket_id}",
            json={
                "title": detail["title"],
                "description": detail["description"],
                "category_id": detail["category_id"],
                "priority": detail["priority"],
                "status": "resolved",
                "resolution_outcome": resolution,
                "updated_at": detail["updated_at"],
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_ticket_shows_visible_knowledge_and_resolved_context(self):
        previous_ticket_id = self.create_ticket(
            "VPN Einwahl schlägt fehl",
            "Mitarbeitende können sich nicht per VPN verbinden.",
        )
        self.close_ticket(previous_ticket_id, "Das abgelaufene VPN-Zertifikat wurde erneuert.")
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                """
                INSERT INTO knowledge_entries (title, summary, content, category_id, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "VPN-Zertifikat erneuern",
                    "Vorgehen bei einer fehlgeschlagenen VPN-Einwahl.",
                    "Zertifikat prüfen, erneuern und die Einwahl erneut testen.",
                    self.knowledge_category_id,
                    "context_admin",
                ),
            )
            db.commit()
        current_ticket_id = self.create_ticket(
            "VPN Einwahl für neue Mitarbeitende fehlgeschlagen",
            "Der Zugriff über VPN funktioniert nicht.",
        )

        response = self.client.get(f"/api/tickets/{current_ticket_id}")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        context = response.get_json()["work_context"]
        self.assertIn(
            previous_ticket_id,
            [item["id"] for item in context["similar_resolved_tickets"]],
        )
        self.assertIn(
            "VPN-Zertifikat erneuern",
            [item["title"] for item in context["knowledge_entries"]],
        )
        previous = next(
            item for item in context["similar_resolved_tickets"] if item["id"] == previous_ticket_id
        )
        self.assertIn("Zertifikat", previous["resolution"])


if __name__ == "__main__":
    unittest.main()
