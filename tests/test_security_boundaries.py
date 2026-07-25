import contextlib
import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import app as inventory_app


class SecurityBoundaryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        inventory_app.DATABASE = str(self.temp_path / "test_inventory.db")
        inventory_app.UPLOADS_DIR = self.temp_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = self.temp_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = self.temp_path / "runtime_config.json"
        inventory_app.INITIAL_ADMIN_CREDENTIALS_PATH = None
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "127.0.0.1",
            "port": 0,
            "debug": False,
        }
        inventory_app.RATE_LIMIT_CACHE.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            inventory_app.init_db()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.RATE_LIMIT_CACHE.clear()
        self.temp_dir.cleanup()

    def test_security_headers_and_same_origin_write_boundary(self):
        response = self.client.get("/login")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

        rejected = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(rejected.status_code, 403)

        allowed = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"Origin": "http://localhost"},
            base_url="http://localhost",
        )
        self.assertNotEqual(allowed.status_code, 403)

        opaque_same_origin = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertNotEqual(opaque_same_origin.status_code, 403)

        opaque_cross_site = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"Origin": "null", "Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(opaque_cross_site.status_code, 403)

    def test_import_archive_rejects_traversal_and_symlinks(self):
        traversal_buffer = io.BytesIO()
        with zipfile.ZipFile(traversal_buffer, "w") as archive:
            archive.writestr("uploads/../../outside.txt", "blocked")
        traversal_buffer.seek(0)
        with zipfile.ZipFile(traversal_buffer) as archive:
            with self.assertRaises(ValueError):
                inventory_app.validate_import_archive(archive)

        symlink_buffer = io.BytesIO()
        with zipfile.ZipFile(symlink_buffer, "w") as archive:
            info = zipfile.ZipInfo("uploads/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "../../outside.txt")
        symlink_buffer.seek(0)
        with zipfile.ZipFile(symlink_buffer) as archive:
            with self.assertRaises(ValueError):
                inventory_app.validate_import_archive(archive)

        valid_buffer = io.BytesIO()
        with zipfile.ZipFile(valid_buffer, "w") as archive:
            archive.writestr("uploads/attachments/report.txt", "ok")
        valid_buffer.seek(0)
        with zipfile.ZipFile(valid_buffer) as archive:
            members = inventory_app.validate_import_archive(archive)
        self.assertEqual(members[0][1], Path("attachments/report.txt"))

    def test_bootstrap_secret_is_written_to_owner_only_file(self):
        isolated_dir = Path(tempfile.mkdtemp(dir=self.temp_path))
        inventory_app.DATABASE = str(isolated_dir / "bootstrap.db")
        inventory_app.APP_INSTANCE_PATH = isolated_dir / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = isolated_dir / "runtime_config.json"
        output = io.StringIO()
        with mock.patch.object(
            inventory_app.secrets,
            "token_urlsafe",
            return_value="Protected-Initial-Secret",
        ):
            with contextlib.redirect_stdout(output):
                inventory_app.init_db()

        credentials_path = inventory_app.APP_INSTANCE_PATH / "initial_admin_credentials.txt"
        self.assertTrue(credentials_path.exists())
        self.assertEqual(stat.S_IMODE(credentials_path.stat().st_mode), 0o600)
        self.assertIn("Protected-Initial-Secret", credentials_path.read_text(encoding="utf-8"))
        self.assertNotIn("Protected-Initial-Secret", output.getvalue())

        rotated_path = inventory_app.store_initial_admin_credentials(
            "replacement-admin",
            "Replacement-Secret",
        )
        self.assertNotEqual(rotated_path, credentials_path)
        self.assertTrue(credentials_path.exists())
        self.assertEqual(stat.S_IMODE(rotated_path.stat().st_mode), 0o600)
        self.assertIn("Replacement-Secret", rotated_path.read_text(encoding="utf-8"))

    def test_password_reset_errors_do_not_enumerate_accounts(self):
        unknown = self.client.post(
            "/reset",
            data={
                "username": "unknown-user",
                "otp": "123456",
                "new_password": "LongEnoughPassword!",
            },
        )
        existing = self.client.post(
            "/reset",
            data={
                "username": "admin",
                "otp": "123456",
                "new_password": "LongEnoughPassword!",
            },
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(existing.status_code, 400)
        neutral_message = "Zurücksetzen nicht möglich. Angaben prüfen oder Administrator kontaktieren."
        self.assertIn(neutral_message, unknown.get_data(as_text=True))
        self.assertIn(neutral_message, existing.get_data(as_text=True))

    def test_otp_verification_is_rate_limited(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE users SET otp_secret = ?, must_change_password = 0 WHERE username = 'admin'",
                ("JBSWY3DPEHPK3PXP",),
            )
            db.commit()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["mfa_verified"] = False

        original_limit = inventory_app.RATE_LIMIT_MAX_REQUESTS
        inventory_app.RATE_LIMIT_MAX_REQUESTS = 2
        try:
            self.assertEqual(
                self.client.post("/api/otp/verify", json={"code": "000000"}).status_code,
                401,
            )
            self.assertEqual(
                self.client.post("/api/otp/verify", json={"code": "000000"}).status_code,
                401,
            )
            self.assertEqual(
                self.client.post("/api/otp/verify", json={"code": "000000"}).status_code,
                429,
            )
        finally:
            inventory_app.RATE_LIMIT_MAX_REQUESTS = original_limit


if __name__ == "__main__":
    unittest.main()
