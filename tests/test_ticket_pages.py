import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class TicketPagesTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)
        inventory_app.DATABASE = str(temporary_path / "inventory.db")
        inventory_app.UPLOADS_DIR = temporary_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temporary_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temporary_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "127.0.0.1",
            "port": 0,
            "debug": False,
        }
        with contextlib.redirect_stdout(io.StringIO()):
            inventory_app.init_db()
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            administrator_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("ticket_admin", inventory_app.generate_password_hash("secret1234")),
            ).lastrowid
            inventory_app.assign_user_role(db, administrator_id, "Admin")
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_ticket_pages_require_an_authenticated_user(self):
        response = self.client.get("/tickets")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_ticket_pages_keep_existing_success_and_not_found_contracts(self):
        self.client.post(
            "/login",
            data={"username": "ticket_admin", "password": "secret1234"},
        )
        tickets = self.client.get("/tickets")
        self.assertEqual(tickets.status_code, 200)
        self.assertIn(b"Tickets", tickets.data)

        missing_ticket = self.client.get("/tickets/999999")
        self.assertEqual(missing_ticket.status_code, 404)
        self.assertEqual(
            missing_ticket.content_type,
            "text/plain; charset=utf-8",
        )

        administration = self.client.get("/admin/tickets/notifications")
        self.assertEqual(administration.status_code, 200)
        self.assertIn(b"notifications", administration.data)
