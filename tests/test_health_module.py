import json
import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class HealthModuleTestCase(unittest.TestCase):
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
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("tester", password_hash)
            )
            inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "tester", "password": "secret1234"})

    def test_health_summary_endpoint(self):
        self.login()
        response = self.client.get("/api/health/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("overall_status", payload)

    def test_check_config_redaction(self):
        self.login()
        payload = {
            "name": "Secret Check",
            "check_type": "http",
            "category": "Custom",
            "interval_seconds": 60,
            "timeout_seconds": 5,
            "enabled": True,
            "config": {
                "url": "https://example.com",
                "api_key": "super-secret"
            }
        }
        response = self.client.post("/api/health/checks", json=payload)
        self.assertEqual(response.status_code, 201)
        check = response.get_json()["check"]
        self.assertEqual(check["config"]["api_key"], "***")

    def test_incident_open_and_close(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            cursor = db.execute(
                """
                INSERT INTO health_check_definitions (name, slug, category, check_type, config_json, interval_seconds, timeout_seconds, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CPU",
                    "cpu-test",
                    "System",
                    "cpu_load",
                    json.dumps({"incident_open_after_minutes": 0, "incident_close_after_minutes": 0}),
                    60,
                    5,
                    1
                )
            )
            check_id = cursor.lastrowid
            run_id = db.execute(
                "INSERT INTO health_check_runs (started_at, status, triggered_by, initiated_by) VALUES (?, 'running', 'test', 'tester')",
                (inventory_app.health_now(),)
            ).lastrowid
            check_def = db.execute("SELECT * FROM health_check_definitions WHERE id = ?", (check_id,)).fetchone()
            inventory_app.record_health_result(
                db,
                run_id,
                check_def,
                {
                    "status": "CRIT",
                    "severity": "CRIT",
                    "reason": "fail",
                    "metrics": {},
                    "details": {}
                }
            )
            db.commit()
            incident = db.execute(
                "SELECT * FROM health_incidents WHERE check_id = ? AND status = 'open'",
                (check_id,)
            ).fetchone()
            self.assertIsNotNone(incident)
            self.assertIsNotNone(incident["ticket_id"])
            ticket = db.execute(
                '''
                SELECT t.priority, t.due_date, t.tags, c.name AS category_name, c.sla_hours
                FROM tickets t
                JOIN ticket_categories c ON c.id = t.category_id
                WHERE t.id = ?
                ''',
                (incident["ticket_id"],),
            ).fetchone()
            self.assertEqual(ticket["priority"], "high")
            self.assertEqual(ticket["category_name"], "Incident")
            self.assertGreaterEqual(ticket["sla_hours"], 1)
            self.assertTrue(ticket["due_date"])
            self.assertIn("automatic", json.loads(ticket["tags"]))
            inventory_app.record_health_result(
                db,
                run_id,
                check_def,
                {
                    "status": "CRIT",
                    "severity": "CRIT",
                    "reason": "still failing",
                    "metrics": {},
                    "details": {}
                }
            )
            duplicate_count = db.execute(
                "SELECT COUNT(*) AS count FROM tickets WHERE id = ?",
                (incident["ticket_id"],),
            ).fetchone()["count"]
            self.assertEqual(duplicate_count, 1)
            inventory_app.record_health_result(
                db,
                run_id,
                check_def,
                {
                    "status": "OK",
                    "severity": "OK",
                    "reason": "recovered",
                    "metrics": {},
                    "details": {}
                }
            )
            db.commit()
            closed = db.execute(
                "SELECT * FROM health_incidents WHERE check_id = ? AND status = 'closed'",
                (check_id,)
            ).fetchone()
            self.assertIsNotNone(closed)

    def test_warn_status_automatically_creates_a_high_priority_incident_ticket(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            check_id = db.execute(
                '''
                INSERT INTO health_check_definitions (
                    name, slug, category, check_type, config_json, interval_seconds, timeout_seconds, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    "Memory",
                    "memory-test",
                    "System",
                    "memory",
                    json.dumps({"incident_open_after_minutes": 0}),
                    60,
                    5,
                    1,
                ),
            ).lastrowid
            run_id = db.execute(
                "INSERT INTO health_check_runs (started_at, status, triggered_by) VALUES (?, 'running', 'test')",
                (inventory_app.health_now(),),
            ).lastrowid
            check_def = db.execute("SELECT * FROM health_check_definitions WHERE id = ?", (check_id,)).fetchone()

            inventory_app.record_health_result(
                db,
                run_id,
                check_def,
                {
                    "status": "WARN",
                    "severity": "WARN",
                    "reason": "memory threshold",
                    "metrics": {},
                    "details": {},
                },
            )
            incident = db.execute(
                "SELECT ticket_id FROM health_incidents WHERE check_id = ? AND status = 'open'",
                (check_id,),
            ).fetchone()
            ticket = db.execute(
                "SELECT priority FROM tickets WHERE id = ?",
                (incident["ticket_id"],),
            ).fetchone()

        self.assertIsNotNone(incident["ticket_id"])
        self.assertEqual(ticket["priority"], "high")


if __name__ == "__main__":
    unittest.main()
