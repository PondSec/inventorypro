import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app as inventory_app
from inventorypro.domains.audit.service import normalize_activity_outcome
from inventorypro.migrations import apply_migrations, rollback_migrations


class ActivityAuditTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.previous_testing = inventory_app.app.config["TESTING"]
        inventory_app.app.config["TESTING"] = True
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
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.app.config["TESTING"] = self.previous_testing
        self.temp_dir.cleanup()

    def activity_rows(self):
        with inventory_app.app.app_context():
            return [
                dict(row)
                for row in inventory_app.get_db().execute(
                    "SELECT username, action, entity_type, entity_id, details FROM activity_log ORDER BY id"
                ).fetchall()
            ]

    def test_activity_log_preserves_session_actor_and_structured_details(self):
        with inventory_app.app.test_request_context("/"):
            inventory_app.session["username"] = "audit-user"
            inventory_app.log_activity(
                inventory_app.get_db(),
                "update",
                "device",
                42,
                {"name": "Router", "changes": ["location"]},
            )
            inventory_app.get_db().commit()

        self.assertEqual(
            self.activity_rows(),
            [{
                "username": "audit-user",
                "action": "update",
                "entity_type": "device",
                "entity_id": 42,
                "details": '{"name": "Router", "changes": ["location"]}',
            }],
        )

    def test_activity_log_falls_back_to_system_actor_and_empty_details(self):
        with inventory_app.app.test_request_context("/"):
            inventory_app.log_activity(
                inventory_app.get_db(),
                "scheduled",
                "backup",
            )
            inventory_app.get_db().commit()

        self.assertEqual(
            self.activity_rows(),
            [{
                "username": "system",
                "action": "scheduled",
                "entity_type": "backup",
                "entity_id": None,
                "details": "{}",
            }],
        )

    def test_activity_migration_is_reversible_and_installs_integrity_guards(self):
        migration_directory = Path(inventory_app.__file__).with_name("migrations")
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            column_names = {
                row["name"] for row in db.execute("PRAGMA table_info(activity_log)").fetchall()
            }
            self.assertTrue({"request_id", "outcome"}.issubset(column_names))
            trigger_names = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'activity_log'"
                ).fetchall()
            }
            self.assertEqual(
                trigger_names,
                {"activity_log_prevent_delete", "activity_log_prevent_update"},
            )
            self.assertEqual(
                rollback_migrations(db, migration_directory),
                ["003_activity_log_integrity"],
            )
            rolled_back_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(activity_log)").fetchall()
            }
            self.assertNotIn("request_id", rolled_back_columns)
            self.assertNotIn("outcome", rolled_back_columns)
            self.assertEqual(
                apply_migrations(db, migration_directory),
                ["003_activity_log_integrity"],
            )

    def test_activity_entries_are_immutable_inside_the_application_database(self):
        with inventory_app.app.test_request_context("/"):
            db = inventory_app.get_db()
            inventory_app.log_activity(db, "create", "device", 42, {"name": "Router"})
            db.commit()
            activity_id = db.execute("SELECT id FROM activity_log ORDER BY id DESC").fetchone()["id"]
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE activity_log SET action = ? WHERE id = ?", ("update", activity_id))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM activity_log WHERE id = ?", (activity_id,))

    def test_audit_entries_carry_server_request_id_and_failure_outcome(self):
        response = self.client.post(
            "/login",
            data={"username": "unknown-user", "password": "invalid"},
        )

        self.assertEqual(response.status_code, 200)
        request_id = response.headers["X-Request-ID"]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        with inventory_app.app.app_context():
            row = inventory_app.get_db().execute(
                """
                SELECT request_id, outcome
                FROM activity_log
                WHERE action = 'login_failed'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        self.assertEqual(dict(row), {"request_id": request_id, "outcome": "failure"})

    def test_audit_outcome_normalization_rejects_unsupported_statuses(self):
        self.assertEqual(normalize_activity_outcome("login_failed"), "failure")
        self.assertEqual(normalize_activity_outcome("login_locked", "DENIED"), "denied")
        with self.assertRaisesRegex(ValueError, "Ergebnisstatus"):
            normalize_activity_outcome("login", "unknown")


if __name__ == "__main__":
    unittest.main()
