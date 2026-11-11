import io
from pathlib import Path
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import Mock
import zipfile

from flask import Flask

from inventorypro.domains.exports.routes import build_exports_blueprint


class ExportRoutesTestCase(TestCase):
    table_names = (
        "categories",
        "asset_categories",
        "locations",
        "devices",
        "assets",
        "asset_devices",
        "maintenance_tasks",
        "asset_assignment_history",
        "vendors",
        "contracts",
        "purchase_orders",
        "purchase_order_items",
        "attachments",
    )

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.uploads_dir = self.root / "uploads"
        self.uploads_dir.mkdir()
        (self.uploads_dir / "report.txt").write_text("export attachment", encoding="utf-8")
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        for table_name in self.table_names:
            self.connection.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, name TEXT)")
        self.connection.execute("DROP TABLE categories")
        self.connection.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        self.connection.execute(
            "DROP TABLE devices"
        )
        self.connection.execute(
            "CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT, serial_number TEXT, specs TEXT, created_at TEXT, category_id INTEGER)"
        )
        self.connection.execute("INSERT INTO categories (id, name) VALUES (1, 'Hardware')")
        self.connection.execute(
            "INSERT INTO devices (name, serial_number, specs, created_at, category_id) VALUES (?, ?, ?, ?, ?)",
            ("Router", "SER-1", "{}", "2026-01-01", 1),
        )
        self.connection.commit()
        self.settings = {"importExport": {"exportAllowed": True, "exportFormat": "csv", "includeUploads": False}}
        self.permissions = {"devices.view": True, "devices.manage": False}
        self.log_activity = Mock()
        self.application = Flask(__name__)
        self.application.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.application.register_blueprint(
            build_exports_blueprint(
                get_db=lambda: self.connection,
                get_export_settings=lambda database: self.settings,
                uploads_dir=self.uploads_dir,
                export_tables=lambda database, tables: {"devices": [{"name": "Router"}]},
                run_sqlite_backup=self.run_sqlite_backup,
                log_activity=self.log_activity,
                user_can=lambda permission: self.permissions.get(permission, False),
                login_required=lambda view: view,
                require_permission=lambda permission: lambda view: view,
            ),
        )
        self.client = self.application.test_client()

    def tearDown(self):
        self.connection.close()
        self.temporary_directory.cleanup()

    @staticmethod
    def run_sqlite_backup(path):
        path.write_bytes(b"sqlite-backup")

    def test_export_archives_include_requested_uploads_for_all_portable_formats(self):
        for export_format, archive_member in (("sqlite", "inventory.db"), ("json", "inventory_export.json"), ("xlsx", "inventory_export.xlsx")):
            with self.subTest(export_format=export_format):
                self.settings["importExport"].update({"exportFormat": export_format, "includeUploads": True})
                response = self.client.get("/api/export")

                self.assertEqual(response.status_code, 200)
                with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                    self.assertIn(archive_member, archive.namelist())
                    self.assertIn("uploads/report.txt", archive.namelist())

    def test_export_guards_and_device_export_preserve_permissions(self):
        self.settings["importExport"]["exportAllowed"] = False
        self.assertEqual(self.client.get("/api/export").status_code, 403)

        self.permissions["devices.view"] = False
        self.assertEqual(self.client.get("/api/export/devices").status_code, 403)

        self.permissions["devices.view"] = True
        self.assertEqual(self.client.get("/api/export/devices").status_code, 403)

        self.settings["importExport"]["exportAllowed"] = True
        device_export = self.client.get("/api/export/devices")
        self.assertEqual(device_export.status_code, 200)
        self.assertIn("Router", device_export.get_data(as_text=True))
