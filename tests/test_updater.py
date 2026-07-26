import base64
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import updater


class InventoryUpdaterTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.original_policy_path = updater.POLICY_PATH
        self.original_state_path = updater.STATE_PATH
        self.original_public_key_value = updater.PUBLIC_KEY_VALUE
        updater.POLICY_PATH = root / "update_policy.json"
        updater.STATE_PATH = root / "update_state.json"
        self.private_key = Ed25519PrivateKey.generate()
        public_key = self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        updater.PUBLIC_KEY_VALUE = base64.b64encode(public_key).decode("ascii")

    def tearDown(self):
        updater.POLICY_PATH = self.original_policy_path
        updater.STATE_PATH = self.original_state_path
        updater.PUBLIC_KEY_VALUE = self.original_public_key_value
        self.temp_dir.cleanup()

    def signed_manifest(self):
        manifest = {
            "schemaVersion": 1,
            "version": "0.0.42",
            "image": "ghcr.io/pondsec/inventorypro@sha256:" + "a" * 64,
            "signatureAlgorithm": "ed25519",
        }
        signature = self.private_key.sign(updater.canonical_manifest(manifest))
        manifest["signature"] = base64.b64encode(signature).decode("ascii")
        return manifest

    def test_signed_immutable_manifest_is_accepted(self):
        manifest = self.signed_manifest()

        validated = updater.validate_manifest(manifest)

        self.assertEqual(validated["version"], "0.0.42")
        self.assertTrue(validated["image"].endswith("a" * 64))

    def test_manifest_with_changed_content_is_rejected(self):
        manifest = self.signed_manifest()
        manifest["version"] = "0.0.43"

        with self.assertRaises(updater.UpdateError):
            updater.validate_manifest(manifest)

    def test_policy_requires_stable_channel_and_maintenance_window(self):
        policy = updater.normalize_policy({
            "schemaVersion": 1,
            "autoUpdateEnabled": True,
            "channel": "stable",
            "checkIntervalMinutes": 30,
            "maintenanceWindow": "03:30",
        })

        self.assertTrue(updater.is_due(policy, datetime(2026, 7, 25, 3, 45)))
        self.assertFalse(updater.is_due(policy, datetime(2026, 7, 25, 4, 1)))
        with self.assertRaises(updater.UpdateError):
            updater.normalize_policy({
                "schemaVersion": 1,
                "autoUpdateEnabled": True,
                "channel": "preview",
                "checkIntervalMinutes": 30,
                "maintenanceWindow": "03:30",
            })

    def test_disabled_policy_never_contacts_release_service(self):
        updater.atomic_write_json(updater.POLICY_PATH, {
            "schemaVersion": 1,
            "autoUpdateEnabled": False,
            "channel": "stable",
            "checkIntervalMinutes": 30,
            "maintenanceWindow": "03:30",
        })

        result = updater.run_once(datetime(2026, 7, 25, 3, 30))

        self.assertEqual(result, "disabled")

    def test_state_file_is_private_and_contains_no_release_signature(self):
        updater.atomic_write_json(updater.STATE_PATH, {"lastCheckStatus": "updated"})

        state = json.loads(updater.STATE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(state["lastCheckStatus"], "updated")
        self.assertNotIn("signature", state)
        self.assertEqual(updater.STATE_PATH.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
