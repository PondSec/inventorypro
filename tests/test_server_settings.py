import json
import io
import tempfile
from pathlib import Path
import unittest

from openpyxl import Workbook, load_workbook

import app as inventory_app


class ServerSettingsTestCase(unittest.TestCase):
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
            admin_role = db.execute("SELECT id FROM roles WHERE name = 'Admin'").fetchone()
            if admin_role:
                inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")
            category_id = db.execute(
                "INSERT INTO categories (name) VALUES (?)",
                ("Testkategorie",),
            ).lastrowid
            self.device_id = db.execute(
                "INSERT INTO devices (name, category_id, serial_number, specs) VALUES (?, ?, ?, ?)",
                ("Testgerät", category_id, "SER-001", "{}"),
            ).lastrowid
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username="tester", password="secret1234"):
        return self.client.post("/login", data={"username": username, "password": password})

    def test_get_and_update_settings(self):
        self.login()
        response = self.client.get("/api/settings/server")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        settings = payload["settings"]
        settings["server"]["host"] = "127.0.0.1"
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()
        self.assertTrue(updated["meta"]["pendingRestart"])

    def test_invalid_port_rejected(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["server"]["port"] = 70000
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 400)

    def test_signed_update_policy_is_validated_and_published(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["updates"] = {
            "autoUpdateEnabled": True,
            "channel": "stable",
            "checkIntervalMinutes": 120,
            "maintenanceWindow": "02:45",
        }

        update_response = self.client.put("/api/settings/server", json=settings)

        self.assertEqual(update_response.status_code, 200)
        policy_path = inventory_app.APP_INSTANCE_PATH / "update_policy.json"
        self.assertTrue(policy_path.exists())
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertTrue(policy["autoUpdateEnabled"])
        self.assertEqual(policy["channel"], "stable")
        self.assertEqual(policy["checkIntervalMinutes"], 120)
        self.assertEqual(policy["maintenanceWindow"], "02:45")
        self.assertFalse(any("password" in key.lower() for key in policy))

    def test_unsigned_update_channel_is_rejected(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["updates"]["channel"] = "preview"

        update_response = self.client.put("/api/settings/server", json=settings)

        self.assertEqual(update_response.status_code, 400)
        self.assertIn("updates.channel", update_response.get_json()["details"])

    def test_backup_run(self):
        self.login()
        response = self.client.get("/api/settings/server")
        settings = response.get_json()["settings"]
        settings["backup"]["enabled"] = True
        settings["backup"]["directory"] = str(Path(self.temp_dir.name) / "backups")
        update_response = self.client.put("/api/settings/server", json=settings)
        self.assertEqual(update_response.status_code, 200)
        run_response = self.client.post("/api/backups/run", json={"force": True})
        self.assertEqual(run_response.status_code, 200)
        result = run_response.get_json()
        self.assertIn(result["status"], {"success", "failed"})

    def test_backup_history_keeps_the_existing_response_shape(self):
        self.login()
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            db.execute(
                """
                INSERT INTO backup_runs (status, backup_path, backup_size_bytes, message)
                VALUES (?, ?, ?, ?)
                """,
                ("success", "/backups/example.db", 123, "completed"),
            )
            db.commit()

        response = self.client.get("/api/backups/list")
        self.assertEqual(response.status_code, 200)
        backup = response.get_json()["backups"][0]
        self.assertEqual(
            set(backup),
            {"id", "status", "path", "sizeBytes", "message", "createdAt"},
        )
        self.assertEqual(backup["path"], "/backups/example.db")
        self.assertEqual(backup["sizeBytes"], 123)

    def test_tabular_import_preview_and_device_import(self):
        self.login()
        settings = self.client.get("/api/settings/server").get_json()["settings"]
        settings["importExport"]["importAllowed"] = True
        self.assertEqual(self.client.put("/api/settings/server", json=settings).status_code, 200)
        csv_content = b"Hostname;Seriennummer;Standort;Hersteller\ncore-1;SER-1;Berlin;Pond\n"
        preview = self.client.post(
            "/api/import/preview",
            data={"entity": "devices", "file": (io.BytesIO(csv_content), "devices.csv")},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["validRows"], 1)
        imported = self.client.post(
            "/api/import",
            data={
                "entity": "devices",
                "mode": "append",
                "file": (io.BytesIO(csv_content), "devices.csv"),
            },
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.get_json()["summary"]["created"], 1)

    def test_tabular_xlsx_and_json_previews_are_available(self):
        self.login()
        settings = self.client.get("/api/settings/server").get_json()["settings"]
        settings["importExport"]["importAllowed"] = True
        self.assertEqual(self.client.put("/api/settings/server", json=settings).status_code, 200)

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Hostname", "Seriennummer", "Standort"])
        worksheet.append(["xlsx-device", "XLSX-1", "Hamburg"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        xlsx_content = buffer.getvalue()

        preview = self.client.post(
            "/api/import/preview",
            data={"entity": "devices", "file": (io.BytesIO(xlsx_content), "devices.xlsx")},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["format"], "xlsx")
        imported = self.client.post(
            "/api/import",
            data={"entity": "devices", "mode": "append", "file": (io.BytesIO(xlsx_content), "devices.xlsx")},
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.get_json()["summary"]["created"], 1)

        json_content = b'{"assets": [{"Bezeichnung": "JSON Asset", "Rechnungsnummer": "JSON-1"}]}'
        json_preview = self.client.post(
            "/api/import/preview",
            data={"entity": "assets", "file": (io.BytesIO(json_content), "assets.json")},
        )
        self.assertEqual(json_preview.status_code, 200)
        self.assertEqual(json_preview.get_json()["format"], "json")

    def test_xlsx_export_contains_inventory_sheets(self):
        self.login()
        settings = self.client.get("/api/settings/server").get_json()["settings"]
        settings["importExport"]["exportFormat"] = "xlsx"
        settings["importExport"]["includeUploads"] = False
        self.assertEqual(self.client.put("/api/settings/server", json=settings).status_code, 200)

        response = self.client.get("/api/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(io.BytesIO(response.data), read_only=True, data_only=True)
        self.assertIn("devices", workbook.sheetnames)
        sheet = workbook["devices"]
        self.assertEqual(next(sheet.values)[0], "id")
        self.assertIn("Testgerät", [row[1] for row in sheet.iter_rows(values_only=True)])
        workbook.close()

    def test_all_built_in_features_are_available_without_license_flags(self):
        self.login()

        catalog = self.client.get("/api/features")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(
            set(catalog.get_json()),
            {"features"},
        )
        self.assertIn("maintenance_schedule", catalog.get_json()["features"])
        self.assertIn("csv_export", catalog.get_json()["features"])

        created = self.client.post(
            "/api/maintenance",
            json={"device_id": self.device_id, "title": "Sicherheitsprüfung", "due_date": "2026-08-01"},
        )
        self.assertEqual(created.status_code, 201)
        summary = self.client.get("/api/maintenance/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.get_json()["open"], 1)
        self.assertEqual(set(summary.get_json()), {"open", "overdue"})

        export = self.client.get("/api/export/devices")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.mimetype, "text/csv")
        self.assertIn("Testgerät", export.get_data(as_text=True))

    def test_login_lockout(self):
        for _ in range(5):
            self.client.post("/login", data={"username": "tester", "password": "wrong"})
        response = self.client.post("/login", data={"username": "tester", "password": "secret1234"})
        self.assertIn("gesperrt", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
