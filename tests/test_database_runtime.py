import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class DatabaseRuntimeTestCase(unittest.TestCase):
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

    def test_connections_enable_integrity_and_concurrency_pragmas(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA busy_timeout").fetchone()[0], 10000)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0], 1)

    def test_asset_summaries_load_device_metadata_in_one_query(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            category = db.execute(
                "INSERT INTO asset_categories (name) VALUES (?)",
                ("Bulk Summary",),
            )
            device_category = db.execute(
                "INSERT INTO categories (name) VALUES (?)",
                ("Bulk Devices",),
            )
            location = db.execute(
                "INSERT INTO locations (name) VALUES (?)",
                ("Lager Nord",),
            )
            asset_ids = []
            for index in range(2):
                asset = db.execute(
                    "INSERT INTO assets (name, category_id) VALUES (?, ?)",
                    (f"Asset {index}", category.lastrowid),
                )
                device = db.execute(
                    """
                    INSERT INTO devices (name, category_id, serial_number, location_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        f"Device {index}",
                        device_category.lastrowid,
                        f"SERIAL-{index}",
                        location.lastrowid,
                    ),
                )
                db.execute(
                    "INSERT INTO asset_devices (asset_id, device_id) VALUES (?, ?)",
                    (asset.lastrowid, device.lastrowid),
                )
                asset_ids.append(asset.lastrowid)
            db.commit()

            placeholders = ",".join("?" for _ in asset_ids)
            rows = db.execute(
                f"""
                SELECT a.*, ac.name AS category_name,
                       ac.binpacking_config AS category_binpacking_config
                FROM assets a
                LEFT JOIN asset_categories ac ON ac.id = a.category_id
                WHERE a.id IN ({placeholders})
                ORDER BY a.id
                """,
                asset_ids,
            ).fetchall()
            statements = []
            db.set_trace_callback(statements.append)
            summaries = inventory_app.build_asset_summaries(db, rows)
            db.set_trace_callback(None)

            relation_queries = [
                statement
                for statement in statements
                if "FROM asset_devices" in statement
            ]
            self.assertEqual(len(relation_queries), 1)
            self.assertEqual(summaries[0]["serial_numbers"], ["SERIAL-0"])
            self.assertEqual(summaries[1]["locations"], ["Lager Nord"])


if __name__ == "__main__":
    unittest.main()
