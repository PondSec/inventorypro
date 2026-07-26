import json
import os
import tempfile
import unittest

import app as inventory_app


class CustomizationTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(prefix="inventorypro-test-", suffix=".db")
        inventory_app.DATABASE = self.db_path
        inventory_app.app.config['TESTING'] = True
        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            user_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("tester", "hash"),
            ).lastrowid
            inventory_app.assign_user_role(db, user_id, "Admin")
            second_user_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("viewer", "hash"),
            ).lastrowid
            inventory_app.assign_user_role(db, second_user_id, "Mitarbeiter")
            db.commit()
        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session['logged_in'] = True
            session['username'] = 'tester'

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_migrate_legacy_customization(self):
        legacy = {
            "branding": {
                "name": "Legacy",
                "primary": "#111111",
                "accent": "#222222",
                "background": "#333333",
                "radius": 20,
                "density": 1.1,
            },
            "formStyle": {
                "buttonColor": "#444444",
                "buttonText": "#ffffff",
                "inputBackground": "#555555",
                "inputBorder": "#666666",
                "spacing": 18,
            },
        }
        migrated = inventory_app.migrate_customization(legacy)
        self.assertEqual(migrated["branding"]["name"], "Legacy")
        self.assertEqual(migrated["baseTokens"]["colors"]["primary"], "#111111")
        self.assertEqual(migrated["componentOverrides"]["button"]["primary"]["background"], "#444444")
        self.assertEqual(migrated["layoutPrefs"]["formSpacing"], 18)
        self.assertEqual(migrated["navigation"]["items"]["dashboard"]["label"], "Dashboard")

    def test_validate_customization(self):
        valid, errors = inventory_app.validate_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_rejects_invalid_branding_images(self):
        payload = inventory_app.clone_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        payload["branding"]["logoLightDataUrl"] = "data:image/svg+xml;base64,PHN2Zz4="

        valid, errors = inventory_app.validate_customization(payload)

        self.assertFalse(valid)
        self.assertIn(
            "branding.logoLightDataUrl muss ein PNG-, JPEG-, WebP- oder GIF-Data-URL sein.",
            errors,
        )

    def test_customize_api_rejects_invalid_branding_image(self):
        payload = inventory_app.clone_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        payload["branding"]["faviconDataUrl"] = "https://example.invalid/favicon.png"

        response = self.client.put('/api/customize', json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("branding.faviconDataUrl", response.get_json()["details"][0])

    def test_customize_navigation_is_persisted_and_validated(self):
        payload = inventory_app.clone_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        payload["navigation"]["items"]["locations"] = {
            "label": "Niederlassungen",
            "visible": False,
            "order": 25,
        }
        payload["navigation"]["groups"]["legacyPrimary"] = "Mein Inventar"

        response = self.client.put('/api/customize', json=payload)

        self.assertEqual(response.status_code, 200)
        saved = response.get_json()["customization"]["navigation"]
        self.assertEqual(saved["items"]["locations"]["label"], "Niederlassungen")
        self.assertFalse(saved["items"]["locations"]["visible"])
        self.assertEqual(saved["items"]["locations"]["order"], 25)
        self.assertEqual(saved["groups"]["legacyPrimary"], "Mein Inventar")

        payload["navigation"]["items"]["locations"]["order"] = 1000
        invalid = self.client.put('/api/customize', json=payload)
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("navigation.items.locations.order", invalid.get_json()["details"][0])

    def test_customize_persistence(self):
        payload = inventory_app.clone_customization(inventory_app.DEFAULT_CUSTOMIZATION)
        payload["branding"]["name"] = "Persisted"
        payload["branding"]["logoLightDataUrl"] = "data:image/png;base64,bGlnaHQ="
        payload["branding"]["logoDarkDataUrl"] = "data:image/png;base64,ZGFyaw=="
        payload["branding"]["faviconDataUrl"] = "data:image/png;base64,aWNvbg=="
        payload["branding"]["authBackgroundDataUrl"] = "data:image/png;base64,YXV0aA=="

        response = self.client.put('/api/customize', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["customization"]["branding"]["name"], "Persisted")
        self.assertEqual(data["customization"]["branding"]["logoLightDataUrl"], payload["branding"]["logoLightDataUrl"])
        self.assertEqual(data["customization"]["branding"]["logoDarkDataUrl"], payload["branding"]["logoDarkDataUrl"])
        self.assertEqual(data["customization"]["branding"]["faviconDataUrl"], payload["branding"]["faviconDataUrl"])
        self.assertEqual(
            data["customization"]["branding"]["authBackgroundDataUrl"],
            payload["branding"]["authBackgroundDataUrl"],
        )

        response = self.client.get('/api/customize')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["customization"]["branding"]["name"], "Persisted")

        history = self.client.get('/api/customize/history')
        self.assertEqual(history.status_code, 200)
        history_data = history.get_json()
        self.assertTrue(len(history_data["revisions"]) >= 1)

        second_client = inventory_app.app.test_client()
        with second_client.session_transaction() as session:
            session['logged_in'] = True
            session['username'] = 'viewer'
        shared = second_client.get('/api/customize')
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.get_json()["customization"]["branding"]["name"], "Persisted")
        denied = second_client.put('/api/customize', json=payload)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(second_client.get('/api/customize/history').status_code, 403)
        self.assertEqual(second_client.post(f"/api/customize/rollback/{history_data['revisions'][0]['id']}").status_code, 403)


if __name__ == '__main__':
    unittest.main()
