import tempfile
from pathlib import Path
import unittest

import app as inventory_app
from pondsec_ai.db import migrate_agent_db


class TicketManagementTestCase(unittest.TestCase):
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
            migrate_agent_db(db)
            password_hash = inventory_app.generate_password_hash("secret1234")
            admin_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("test_admin", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, admin_id, "Admin")
            db.commit()

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "test_admin", "password": "secret1234"})

    def create_ticket(self, title, description):
        response = self.client.post(
            "/api/tickets",
            json={
                "title": title,
                "description": description,
                "priority": "normal",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def test_delete_ticket_removes_related_records(self):
        self.login()
        ticket_id = self.create_ticket("Drucker defekt", "Papierstau")

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            asset_id = db.execute(
                "INSERT INTO assets (name, notes, specs) VALUES (?, ?, ?)",
                ("Drucker A", "", "{}"),
            ).lastrowid
            db.execute(
                "INSERT INTO ticket_comments (ticket_id, author, body, is_internal) VALUES (?, ?, ?, ?)",
                (ticket_id, "test_admin", "Bitte prüfen", 0),
            )
            db.execute(
                "INSERT INTO ticket_watchers (ticket_id, email) VALUES (?, ?)",
                (ticket_id, "watcher@example.com"),
            )
            db.execute(
                "INSERT INTO ticket_assets (ticket_id, asset_id) VALUES (?, ?)",
                (ticket_id, asset_id),
            )
            db.commit()

        delete_response = self.client.delete(f"/api/tickets/{ticket_id}")
        self.assertEqual(delete_response.status_code, 200)

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            ticket = db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            comment_count = db.execute(
                "SELECT COUNT(*) AS count FROM ticket_comments WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()["count"]
            watcher_count = db.execute(
                "SELECT COUNT(*) AS count FROM ticket_watchers WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()["count"]
            asset_count = db.execute(
                "SELECT COUNT(*) AS count FROM ticket_assets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()["count"]

        self.assertIsNone(ticket)
        self.assertEqual(comment_count, 0)
        self.assertEqual(watcher_count, 0)
        self.assertEqual(asset_count, 0)

    def test_merge_tickets_copies_context_and_closes_sources(self):
        self.login()
        target_ticket_id = self.create_ticket("Notebook startet nicht", "Ziel-Ticket")
        source_ticket_id = self.create_ticket("Notebook startet nicht (Duplikat)", "Quelle")

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            source_asset_id = db.execute(
                "INSERT INTO assets (name, notes, specs) VALUES (?, ?, ?)",
                ("Notebook A", "", "{}"),
            ).lastrowid
            db.execute(
                "INSERT INTO ticket_comments (ticket_id, author, body, is_internal) VALUES (?, ?, ?, ?)",
                (source_ticket_id, "reporter", "Zusätzliche Infos", 0),
            )
            db.execute(
                "INSERT INTO ticket_watchers (ticket_id, email) VALUES (?, ?)",
                (source_ticket_id, "watcher@example.com"),
            )
            db.execute(
                "INSERT INTO ticket_assets (ticket_id, asset_id) VALUES (?, ?)",
                (source_ticket_id, source_asset_id),
            )
            db.commit()

        merge_response = self.client.post(
            "/api/tickets/merge",
            json={
                "target_ticket_id": target_ticket_id,
                "source_ticket_ids": [source_ticket_id],
                "note": "Duplikat",
            },
        )
        self.assertEqual(merge_response.status_code, 200)
        self.assertEqual(merge_response.get_json()["status"], "merged")

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            source_ticket = db.execute(
                "SELECT status, resolution_action, resolution_outcome FROM tickets WHERE id = ?",
                (source_ticket_id,),
            ).fetchone()
            target_comments = db.execute(
                "SELECT body FROM ticket_comments WHERE ticket_id = ? ORDER BY id ASC",
                (target_ticket_id,),
            ).fetchall()
            target_watchers = db.execute(
                "SELECT email FROM ticket_watchers WHERE ticket_id = ?",
                (target_ticket_id,),
            ).fetchall()
            target_assets = db.execute(
                "SELECT asset_id FROM ticket_assets WHERE ticket_id = ?",
                (target_ticket_id,),
            ).fetchall()

        self.assertEqual(source_ticket["status"], "closed")
        self.assertEqual(source_ticket["resolution_action"], "merged")
        self.assertIn(str(target_ticket_id), source_ticket["resolution_outcome"])
        self.assertTrue(any("Zusätzliche Infos" in row["body"] for row in target_comments))
        self.assertTrue(any("Ticket #{}".format(source_ticket_id) in row["body"] for row in target_comments))
        self.assertEqual([row["email"] for row in target_watchers], ["watcher@example.com"])
        self.assertEqual(len(target_assets), 1)

    def test_ticket_page_and_api_expose_current_user_context(self):
        self.login()
        ticket_id = self.create_ticket("VPN defekt", "Nutzer kann sich nicht verbinden")

        page_response = self.client.get("/tickets")
        self.assertEqual(page_response.status_code, 200)
        page_html = page_response.get_data(as_text=True)
        self.assertIn('window.inventoryUsername = "test_admin";', page_html)
        self.assertIn('data-current-username="test_admin"', page_html)

        detail_response = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(detail_response.status_code, 200)
        payload = detail_response.get_json()
        self.assertEqual(payload["requester_name"], "test_admin")
        self.assertEqual(payload["created_by"], "test_admin")
        self.assertEqual(payload["creator_display_name"], "test_admin")
        self.assertTrue(payload["access"]["can_update"])
        self.assertTrue(payload["access"]["can_delete"])


if __name__ == "__main__":
    unittest.main()
