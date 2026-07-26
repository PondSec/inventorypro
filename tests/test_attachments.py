import io
import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class AttachmentTestCase(unittest.TestCase):
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
            viewer_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("viewer", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, viewer_id, "Kunde")
            asset_id = db.execute(
                "INSERT INTO assets (name, notes, specs) VALUES (?, ?, ?)",
                ("Router", "Test", "{}"),
            ).lastrowid
            ticket_category_id = db.execute("SELECT id FROM ticket_categories LIMIT 1").fetchone()["id"]
            ticket_id = db.execute(
                """
                INSERT INTO tickets (title, description, category_id, priority, status, created_by, requester_name, requester_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Ticket",
                    "Desc",
                    ticket_category_id,
                    "normal",
                    "open",
                    "viewer",
                    "Viewer",
                    "viewer@example.com",
                ),
            ).lastrowid
            db.commit()
            self.asset_id = asset_id
            self.ticket_id = ticket_id

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username="test_admin", password="secret1234"):
        return self.client.post("/login", data={"username": username, "password": password})

    def test_upload_blocks_disallowed_extension(self):
        self.login()
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"alert('x');"), "evil.js"),
        }
        response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_upload_allows_pdf(self):
        self.login()
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "manual.pdf"),
        }
        response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["original_filename"], "manual.pdf")

    def test_upload_rejects_content_mismatching_extension(self):
        self.login()
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"not a PNG"), "image.png"),
        }
        response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Dateiinhalt", response.get_json()["error"])

    def test_upload_size_limit(self):
        self.login()
        original_limit = inventory_app.MAX_UPLOAD_BYTES
        inventory_app.MAX_UPLOAD_BYTES = 10
        try:
            data = {
                "entity_type": "asset",
                "entity_id": str(self.asset_id),
                "file": (io.BytesIO(b"0123456789ABC"), "big.txt"),
            }
            response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
        finally:
            inventory_app.MAX_UPLOAD_BYTES = original_limit

    def test_upload_sanitizes_filename(self):
        self.login()
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"test"), "../notes.txt"),
        }
        response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["original_filename"], "notes.txt")

    def test_attachment_permissions(self):
        self.login(username="viewer", password="secret1234")
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"note"), "note.txt"),
        }
        response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 403)

    def test_ticket_download_requires_permission(self):
        self.login()
        data = {
            "entity_type": "ticket",
            "entity_id": str(self.ticket_id),
            "file": (io.BytesIO(b"test"), "note.txt"),
        }
        upload_response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        attachment_id = upload_response.get_json()["id"]

        self.client = inventory_app.app.test_client()
        self.login(username="viewer", password="secret1234")
        download_response = self.client.get(f"/attachments/{attachment_id}/download")
        self.assertEqual(download_response.status_code, 403)

    def test_admin_can_download_attachment(self):
        self.login()
        data = {
            "entity_type": "asset",
            "entity_id": str(self.asset_id),
            "file": (io.BytesIO(b"manual"), "manual.txt"),
        }
        upload_response = self.client.post("/attachments/upload", data=data, content_type="multipart/form-data")
        attachment_id = upload_response.get_json()["id"]
        download_response = self.client.get(f"/attachments/{attachment_id}/download")
        try:
            self.assertEqual(download_response.status_code, 200)
        finally:
            download_response.close()


if __name__ == "__main__":
    unittest.main()
