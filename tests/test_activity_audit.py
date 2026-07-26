import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class ActivityAuditTestCase(unittest.TestCase):
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

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
