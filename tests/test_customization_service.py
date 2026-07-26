import unittest

import app as inventory_app
from inventorypro.domains.customization.service import deep_merge, migrate_customization


class CustomizationServiceTestCase(unittest.TestCase):
    def test_migration_uses_a_copy_of_defaults_for_non_object_payloads(self):
        migrated = migrate_customization(
            None,
            default_customization=inventory_app.DEFAULT_CUSTOMIZATION,
        )
        migrated["branding"]["name"] = "Lokale Marke"

        self.assertNotEqual(
            inventory_app.DEFAULT_CUSTOMIZATION["branding"]["name"],
            "Lokale Marke",
        )

    def test_deep_merge_preserves_unrelated_nested_defaults(self):
        merged = deep_merge(
            {"branding": {"name": "Inventory Pro", "tagline": "Inventar"}},
            {"branding": {"name": "Eigene Marke"}},
        )

        self.assertEqual(
            merged,
            {"branding": {"name": "Eigene Marke", "tagline": "Inventar"}},
        )


if __name__ == "__main__":
    unittest.main()
