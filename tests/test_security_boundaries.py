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

    def test_user_totp_requires_verification_after_password_login(self):
        otp_secret = "JBSWY3DPEHPK3PXP"
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE users SET password_hash = ?, otp_secret = ?, must_change_password = 0 WHERE username = 'admin'",
                (inventory_app.generate_password_hash("SecurePassword123!"), otp_secret),
            )
            db.commit()

        login_response = self.client.post(
            "/login",
            data={"username": "admin", "password": "SecurePassword123!"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.headers["Location"].endswith("/verify"))
        with self.client.session_transaction() as session:
            self.assertTrue(session["mfa_required"])
            self.assertFalse(session["mfa_verified"])
        self.assertTrue(self.client.get("/settings", follow_redirects=False).headers["Location"].endswith("/verify"))

        verification_response = self.client.post(
            "/verify",
            data={"otp": inventory_app.pyotp.TOTP(otp_secret).now()},
            follow_redirects=False,
        )

        self.assertEqual(verification_response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertTrue(session["mfa_verified"])

    def test_totp_password_reset_uses_matching_new_passwords(self):
        otp_secret = "JBSWY3DPEHPK3PXP"
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE users SET password_hash = ?, otp_secret = ? WHERE username = 'admin'",
                (inventory_app.generate_password_hash("OldPassword123!"), otp_secret),
            )
            db.commit()

        reset_page = self.client.get("/reset")
        self.assertIn("TOTP-Code", reset_page.get_data(as_text=True))
        self.assertNotIn("E-Mail-Adresse", reset_page.get_data(as_text=True))
        code = inventory_app.pyotp.TOTP(otp_secret).now()
        missing_confirmation = self.client.post(
            "/reset",
            data={
                "username": "admin",
                "otp": code,
                "new_password": "NewPassword123!",
            },
        )
        self.assertEqual(missing_confirmation.status_code, 400)
        self.assertIn(
            "Zurücksetzen nicht möglich. Angaben prüfen oder Administrator kontaktieren.",
            missing_confirmation.get_data(as_text=True),
        )
        rejected = self.client.post(
            "/reset",
            data={
                "username": "admin",
                "otp": code,
                "new_password": "NewPassword123!",
                "password_confirmation": "DifferentPassword123!",
            },
        )
        self.assertIn("Die Passwörter stimmen nicht überein.", rejected.get_data(as_text=True))

        reset_response = self.client.post(
            "/reset",
            data={
                "username": "admin",
                "otp": inventory_app.pyotp.TOTP(otp_secret).now(),
                "new_password": "NewPassword123!",
                "password_confirmation": "NewPassword123!",
            },
            follow_redirects=False,
        )
        self.assertEqual(reset_response.status_code, 302)
        with inventory_app.app.app_context():
            user = inventory_app.get_db().execute(
                "SELECT password_hash FROM users WHERE username = 'admin'"
            ).fetchone()
        self.assertTrue(inventory_app.check_password_hash(user["password_hash"], "NewPassword123!"))

    def test_global_mfa_policy_prevents_totp_deactivation(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute("UPDATE users SET must_change_password = 0 WHERE username = 'admin'")
            db.execute("UPDATE server_settings SET enforce_mfa = 1 WHERE id = 1")
            db.commit()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["mfa_required"] = True
            session["mfa_verified"] = True

        response = self.client.post("/api/otp/disable")

        self.assertEqual(response.status_code, 409)

    def test_totp_setup_requires_confirmation_before_activation(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute("UPDATE users SET otp_secret = NULL, must_change_password = 0 WHERE username = 'admin'")
            db.commit()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["mfa_verified"] = True

        setup_response = self.client.post("/api/otp/setup")

        self.assertEqual(setup_response.status_code, 200)
        setup_payload = setup_response.get_json()
        self.assertTrue(setup_payload["pending"])
        self.assertFalse(setup_payload["enabled"])
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            user = db.execute("SELECT id, otp_secret FROM users WHERE username = 'admin'").fetchone()
            pending = db.execute(
                "SELECT secret FROM mfa_pending_enrollments WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
        self.assertIsNone(user["otp_secret"])
        self.assertEqual(pending["secret"], setup_payload["secret"])

        invalid_response = self.client.post("/api/otp/confirm", json={"code": "000000"})

        self.assertEqual(invalid_response.status_code, 401)
        with inventory_app.app.app_context():
            user = inventory_app.get_db().execute(
                "SELECT otp_secret FROM users WHERE username = 'admin'"
            ).fetchone()
        self.assertIsNone(user["otp_secret"])

        confirmation_response = self.client.post(
            "/api/otp/confirm",
            json={"code": inventory_app.pyotp.TOTP(setup_payload["secret"]).now()},
        )

        self.assertEqual(confirmation_response.status_code, 200)
        self.assertTrue(confirmation_response.get_json()["enabled"])
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            user = db.execute("SELECT id, otp_secret FROM users WHERE username = 'admin'").fetchone()
            pending = db.execute(
                "SELECT 1 FROM mfa_pending_enrollments WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
        self.assertEqual(user["otp_secret"], setup_payload["secret"])
        self.assertIsNone(pending)
        with self.client.session_transaction() as session:
            self.assertTrue(session["mfa_verified"])
            self.assertFalse(session["mfa_enrollment_required"])

    def test_global_mfa_redirects_to_confirmed_enrollment(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE users SET password_hash = ?, otp_secret = NULL, must_change_password = 0 WHERE username = 'admin'",
                (inventory_app.generate_password_hash("SecurePassword123!"),),
            )
            db.execute("UPDATE server_settings SET enforce_mfa = 1 WHERE id = 1")
            db.commit()

        login_response = self.client.post(
            "/login",
            data={"username": "admin", "password": "SecurePassword123!"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.headers["Location"].endswith("/mfa-enroll"))
        enrollment_page = self.client.get("/mfa-enroll")
        self.assertEqual(enrollment_page.status_code, 200)
        self.assertIn("MFA einrichten", enrollment_page.get_data(as_text=True))
        with self.client.session_transaction() as session:
            self.assertTrue(session["mfa_required"])
            self.assertFalse(session["mfa_verified"])
            self.assertTrue(session["mfa_enrollment_required"])

    def test_totp_deactivation_requires_current_code(self):
        otp_secret = "JBSWY3DPEHPK3PXP"
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                "UPDATE users SET otp_secret = ?, must_change_password = 0 WHERE username = 'admin'",
                (otp_secret,),
            )
            db.commit()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["mfa_required"] = True
            session["mfa_verified"] = True

        missing_code = self.client.post("/api/otp/disable", json={})
        disabled = self.client.post(
            "/api/otp/disable",
            json={"code": inventory_app.pyotp.TOTP(otp_secret).now()},
        )

        self.assertEqual(missing_code.status_code, 401)
        self.assertEqual(disabled.status_code, 200)
        with inventory_app.app.app_context():
            user = inventory_app.get_db().execute(
                "SELECT otp_secret FROM users WHERE username = 'admin'"
            ).fetchone()
        self.assertIsNone(user["otp_secret"])


if __name__ == "__main__":
    unittest.main()
