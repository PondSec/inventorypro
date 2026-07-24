import json
import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class AssetBinpackingTestCase(unittest.TestCase):
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
                ("binpack_admin", password_hash),
            ).lastrowid
            inventory_app.assign_user_role(db, admin_id, "Admin")
            db.commit()

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "binpack_admin", "password": "secret1234"})

    def create_asset_category(self, db, name, fields, binpacking_config=None):
        return db.execute(
            """
            INSERT INTO asset_categories (name, icon, description, fields, binpacking_config)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                "package",
                f"{name} Kategorie",
                json.dumps(fields),
                json.dumps(binpacking_config or {"enabled": False}),
            ),
        ).lastrowid

    def test_asset_category_binpacking_requires_dimension_mapping(self):
        self.login()
        response = self.client.post(
            "/api/asset-categories",
            json={
                "name": "Storage-Racks",
                "fields": {
                    "Breite": {"type": "number", "unit": "cm"},
                    "Höhe": {"type": "number", "unit": "cm"},
                },
                "binpacking_config": {
                    "enabled": True,
                    "content_category_id": 999,
                    "allow_rotation": True,
                    "container_fields": {"width": "Breite", "height": "Höhe", "depth": ""},
                    "item_fields": {"width": "", "height": "", "depth": ""},
                },
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("field_errors", payload)
        self.assertIn("binpacking_config.content_category_id", payload["field_errors"])
        self.assertIn("binpacking_config.container_fields.depth", payload["field_errors"])
        self.assertIn("binpacking_config.item_fields.width", payload["field_errors"])

    def test_asset_detail_returns_binpacking_preview(self):
        self.login()
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            content_category_id = self.create_asset_category(
                db,
                "Brettspiele",
                {
                    "Breite": {"type": "number", "unit": "cm"},
                    "Höhe": {"type": "number", "unit": "cm"},
                    "Tiefe": {"type": "number", "unit": "cm"},
                },
            )
            storage_category_id = self.create_asset_category(
                db,
                "Regale",
                {
                    "Breite": {"type": "number", "unit": "cm"},
                    "Höhe": {"type": "number", "unit": "cm"},
                    "Tiefe": {"type": "number", "unit": "cm"},
                },
                {
                    "enabled": True,
                    "content_category_id": content_category_id,
                    "allow_rotation": True,
                    "clearance": 0,
                    "container_fields": {
                        "width": "Breite",
                        "height": "Höhe",
                        "depth": "Tiefe",
                    },
                    "item_fields": {
                        "width": "Breite",
                        "height": "Höhe",
                        "depth": "Tiefe",
                    },
                    "relation_types": ["enthält"],
                },
            )
            storage_asset_id = db.execute(
                """
                INSERT INTO assets (name, category_id, specs)
                VALUES (?, ?, ?)
                """,
                (
                    "Regal A",
                    storage_category_id,
                    json.dumps({"Breite": 100, "Höhe": 60, "Tiefe": 40}),
                ),
            ).lastrowid
            boardgame_a_id = db.execute(
                """
                INSERT INTO assets (name, category_id, specs)
                VALUES (?, ?, ?)
                """,
                (
                    "Spiel 1",
                    content_category_id,
                    json.dumps({"Breite": 40, "Höhe": 10, "Tiefe": 20}),
                ),
            ).lastrowid
            boardgame_b_id = db.execute(
                """
                INSERT INTO assets (name, category_id, specs)
                VALUES (?, ?, ?)
                """,
                (
                    "Spiel 2",
                    content_category_id,
                    json.dumps({"Breite": 60, "Höhe": 20, "Tiefe": 20}),
                ),
            ).lastrowid
            oversized_item_id = db.execute(
                """
                INSERT INTO assets (name, category_id, specs)
                VALUES (?, ?, ?)
                """,
                (
                    "Spiel 3",
                    content_category_id,
                    json.dumps({"Breite": 120, "Höhe": 20, "Tiefe": 25}),
                ),
            ).lastrowid
            invalid_item_id = db.execute(
                """
                INSERT INTO assets (name, category_id, specs)
                VALUES (?, ?, ?)
                """,
                (
                    "Spiel 4",
                    content_category_id,
                    json.dumps({"Breite": 20, "Höhe": 15}),
                ),
            ).lastrowid
            relation_type_id = db.execute(
                "SELECT id FROM asset_relation_types WHERE name = ?",
                ("enthält",),
            ).fetchone()["id"]
            db.executemany(
                """
                INSERT INTO asset_relations (asset_id, related_asset_id, relation_type_id)
                VALUES (?, ?, ?)
                """,
                [
                    (storage_asset_id, boardgame_a_id, relation_type_id),
                    (storage_asset_id, boardgame_b_id, relation_type_id),
                    (storage_asset_id, oversized_item_id, relation_type_id),
                    (storage_asset_id, invalid_item_id, relation_type_id),
                ],
            )
            db.commit()

        response = self.client.get(f"/api/asset-entries/{storage_asset_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("binpacking", payload)
        preview = payload["binpacking"]
        self.assertTrue(preview["enabled"])
        self.assertEqual(preview["content_category_name"], "Brettspiele")
        self.assertEqual(preview["placed_count"], 2)
        self.assertEqual(preview["unplaced_count"], 1)
        self.assertTrue(preview["packing_strategy_label"])
        self.assertEqual(len(preview["invalid_assets"]), 1)
        self.assertEqual(preview["invalid_assets"][0]["name"], "Spiel 4")
        self.assertGreater(preview["efficiency_percent"], 0)
        self.assertTrue(preview["layers"])
        self.assertTrue(preview["steps"])
        self.assertIn("zone_label", preview["placements"][0])
        self.assertIn("footprint_percent", preview["layers"][0])
        placed_names = {item["asset_name"] for item in preview["placements"]}
        self.assertIn("Spiel 1", placed_names)
        self.assertIn("Spiel 2", placed_names)
        unplaced_names = {item["name"] for item in preview["unplaced_assets"]}
        self.assertIn("Spiel 3", unplaced_names)


if __name__ == "__main__":
    unittest.main()
