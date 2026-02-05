import tempfile
from pathlib import Path
import unittest

import app as inventory_app


class CategoryAssetEnhancementsTestCase(unittest.TestCase):
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
            db.commit()

        self.client = inventory_app.app.test_client()
        self.client.post("/login", data={"username": "test_admin", "password": "secret1234"})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_is_idempotent(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            first_categories = db.execute("SELECT COUNT(*) AS c FROM categories WHERE seed_key IS NOT NULL").fetchone()["c"]
            first_assets = db.execute("SELECT COUNT(*) AS c FROM assets WHERE seed_key IS NOT NULL").fetchone()["c"]
            inventory_app.seed_default_inventory(db)
            db.commit()
            second_categories = db.execute("SELECT COUNT(*) AS c FROM categories WHERE seed_key IS NOT NULL").fetchone()["c"]
            second_assets = db.execute("SELECT COUNT(*) AS c FROM assets WHERE seed_key IS NOT NULL").fetchone()["c"]
            self.assertEqual(first_categories, second_categories)
            self.assertEqual(first_assets, second_assets)

    def test_category_merge_reassigns_assets(self):
        create_a = self.client.post("/api/categories", json={"name": "Source", "slug": "source", "fields": {}})
        create_b = self.client.post("/api/categories", json={"name": "Target", "slug": "target", "fields": {}})
        self.assertEqual(create_a.status_code, 201)
        self.assertEqual(create_b.status_code, 201)
        categories = self.client.get("/api/categories").get_json()
        source_id = next(c["id"] for c in categories if c["slug"] == "source")
        target_id = next(c["id"] for c in categories if c["slug"] == "target")

        asset_resp = self.client.post("/api/assets", json={"name": "Merge Asset", "category_id": source_id, "tags": ["alpha"]})
        self.assertEqual(asset_resp.status_code, 201)

        merge_resp = self.client.post(f"/api/categories/{source_id}/merge", json={"target_category_id": target_id})
        self.assertEqual(merge_resp.status_code, 200)

        assets = self.client.get(f"/api/assets?category_id={target_id}").get_json()
        self.assertTrue(any(asset["name"] == "Merge Asset" for asset in assets))

    def test_bulk_actions_archive(self):
        categories = self.client.get("/api/categories").get_json()
        category_id = categories[0]["id"]
        a1 = self.client.post("/api/assets", json={"name": "Bulk 1", "category_id": category_id}).get_json()["id"]
        a2 = self.client.post("/api/assets", json={"name": "Bulk 2", "category_id": category_id}).get_json()["id"]

        response = self.client.post("/api/assets/bulk", json={"action": "archive", "asset_ids": [a1, a2]})
        self.assertEqual(response.status_code, 200)

        archived = self.client.get("/api/assets?status=archived").get_json()
        archived_ids = {item["id"] for item in archived}
        self.assertIn(a1, archived_ids)
        self.assertIn(a2, archived_ids)

    def test_unique_slug_validation(self):
        first = self.client.post("/api/categories", json={"name": "Slug One", "slug": "slug-one", "fields": {}})
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/categories", json={"name": "Slug One Copy", "slug": "slug-one", "fields": {}})
        self.assertEqual(second.status_code, 201)
        rows = self.client.get("/api/categories?search=slug-one").get_json()
        slugs = [row["slug"] for row in rows]
        self.assertIn("slug-one", slugs)
        self.assertTrue(any(slug.startswith("slug-one-") for slug in slugs))


if __name__ == "__main__":
    unittest.main()
