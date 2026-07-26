import base64
import json
import os
import sqlite3
import subprocess
import tempfile
import urllib.error
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import updater


class InventoryUpdaterTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.original_policy_path = updater.POLICY_PATH
        self.original_state_path = updater.STATE_PATH
        self.original_lock_path = updater.LOCK_PATH
        self.original_data_path = updater.DATA_PATH
        self.original_public_key_file = updater.PUBLIC_KEY_FILE
        self.original_public_key_value = updater.PUBLIC_KEY_VALUE
        self.root = root
        updater.POLICY_PATH = root / "update_policy.json"
        updater.STATE_PATH = root / "update_state.json"
        updater.LOCK_PATH = root / "update.lock"
        updater.DATA_PATH = root / "data"
        self.private_key = Ed25519PrivateKey.generate()
        public_key = self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.public_key_pem = public_key
        updater.PUBLIC_KEY_FILE = str(root / "release-public-key.pem")
        updater.PUBLIC_KEY_VALUE = base64.b64encode(public_key).decode("ascii")

    def tearDown(self):
        updater.POLICY_PATH = self.original_policy_path
        updater.STATE_PATH = self.original_state_path
        updater.LOCK_PATH = self.original_lock_path
        updater.DATA_PATH = self.original_data_path
        updater.PUBLIC_KEY_FILE = self.original_public_key_file
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

    def policy_payload(self, **overrides):
        policy = {
            "schemaVersion": 1,
            "autoUpdateEnabled": True,
            "channel": "stable",
            "checkIntervalMinutes": 30,
            "maintenanceWindow": "03:30",
        }
        policy.update(overrides)
        return policy

    def test_json_helpers_and_policy_validation_fail_closed(self):
        missing_path = Path(self.temp_dir.name) / "missing.json"
        self.assertEqual(updater.load_json(missing_path, {"schemaVersion": 1}), {"schemaVersion": 1})
        invalid_path = Path(self.temp_dir.name) / "invalid.json"
        invalid_path.write_text("not-json", encoding="utf-8")
        with self.assertRaises(updater.UpdateError):
            updater.load_json(invalid_path)
        invalid_path.write_text("[]", encoding="utf-8")
        with self.assertRaises(updater.UpdateError):
            updater.load_json(invalid_path)

        for overrides in (
            {"schemaVersion": 2},
            {"checkIntervalMinutes": "invalid"},
            {"checkIntervalMinutes": 10},
            {"maintenanceWindow": "03:30:15"},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(updater.UpdateError):
                    updater.normalize_policy(self.policy_payload(**overrides))

    def test_environment_and_command_helpers(self):
        self.assertEqual(
            updater.env_path("UNSET_UPDATER_PATH", "/tmp/updater-path"),
            Path("/tmp/updater-path").resolve(),
        )
        updater.atomic_write_json(updater.STATE_PATH, {"status": "ok"})
        self.assertEqual(updater.load_json(updater.STATE_PATH), {"status": "ok"})
        self.assertEqual(updater.STATE_PATH.stat().st_mode & 0o777, 0o600)

        completed = Mock(stdout="complete\n")
        with patch.object(updater.subprocess, "run", return_value=completed) as run:
            self.assertEqual(updater.command(["docker", "version"]), "complete")
        self.assertEqual(run.call_args.args[0], ["docker", "version"])
        with patch.object(
            updater.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["docker"], stderr="failed"),
        ):
            with self.assertRaises(updater.UpdateError):
                updater.command(["docker", "version"])

        arguments = updater.compose_args("ps", "--quiet", "app")
        self.assertEqual(arguments[:2], ["docker", "compose"])
        self.assertEqual(arguments[-3:], ["ps", "--quiet", "app"])

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
        disabled_policy = updater.normalize_policy({
            "schemaVersion": 1,
            "autoUpdateEnabled": False,
            "channel": "preview",
            "checkIntervalMinutes": "invalid",
            "maintenanceWindow": "",
        })
        self.assertFalse(disabled_policy["enabled"])
        self.assertEqual(disabled_policy["interval"], 360)
        self.assertEqual(disabled_policy["maintenance_window"], "03:30")
        with self.assertRaises(updater.UpdateError):
            updater.normalize_policy({
                "schemaVersion": 1,
                "autoUpdateEnabled": True,
                "channel": "preview",
                "checkIntervalMinutes": 30,
                "maintenanceWindow": "03:30",
            })

    def test_policy_normalizes_supported_maintenance_window_formats(self):
        for raw_window, normalized_window in (
            ("09:00", "09:00"),
            ("9:00", "09:00"),
            ("09:00:00", "09:00"),
            ("23:30", "23:30"),
            ("00:00", "00:00"),
        ):
            with self.subTest(raw_window=raw_window):
                policy = updater.normalize_policy(
                    self.policy_payload(maintenanceWindow=raw_window)
                )
                self.assertEqual(policy["maintenance_window"], normalized_window)

    def test_maintenance_schedule_stays_anchored_to_configured_time(self):
        policy = updater.normalize_policy({
            "schemaVersion": 1,
            "autoUpdateEnabled": True,
            "channel": "stable",
            "checkIntervalMinutes": 30,
            "maintenanceWindow": "03:30",
        })

        self.assertEqual(
            updater.seconds_until_next_maintenance_window(policy, datetime(2026, 7, 25, 3, 29, 55)),
            5,
        )
        self.assertEqual(
            updater.seconds_until_next_maintenance_window(policy, datetime(2026, 7, 25, 3, 30)),
            24 * 60 * 60,
        )
        self.assertEqual(
            updater.seconds_until_next_maintenance_window(policy, datetime(2026, 7, 25, 4, 0)),
            23 * 60 * 60 + 30 * 60,
        )

    def test_main_waits_for_the_maintenance_anchor_after_each_check(self):
        updater.atomic_write_json(updater.POLICY_PATH, {
            "schemaVersion": 1,
            "autoUpdateEnabled": True,
            "channel": "stable",
            "checkIntervalMinutes": 30,
            "maintenanceWindow": "03:30",
        })

        with patch.object(updater, "run_once", return_value="outside_maintenance_window"):
            with patch.object(updater, "seconds_until_next_maintenance_window", return_value=5):
                with patch.object(updater.time, "sleep", side_effect=KeyboardInterrupt) as sleep:
                    with self.assertRaises(KeyboardInterrupt):
                        updater.main()

        self.assertEqual(sleep.call_args.args, (5,))

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

    def test_manifest_fetch_rejects_untrusted_or_invalid_responses(self):
        class Response:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exception_type, exception, traceback):
                return False

            def read(self, _limit):
                return self.payload

        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest("http://github.com/manifest.json")
        with self.assertRaises(updater.UpdateError):
            updater.fetch_manifest("https://untrusted.example/manifest.json")

        opener = Mock()
        opener.open.return_value = Response(200, b'{"schemaVersion": 1}')
        with patch.object(updater.urllib.request, "build_opener", return_value=opener):
            manifest = updater.fetch_manifest("https://github.com/manifest.json")
        self.assertEqual(manifest["schemaVersion"], 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://github.com/manifest.json")

        for response in (
            Response(500, b"{}"),
            Response(200, b"x" * (updater.MANIFEST_MAX_BYTES + 1)),
            Response(200, b"not-json"),
            Response(200, b"[]"),
        ):
            with self.subTest(status=response.status, size=len(response.payload)):
                opener.open.return_value = response
                with patch.object(updater.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(updater.UpdateError):
                        updater.fetch_manifest("https://github.com/manifest.json")
        opener.open.side_effect = urllib.error.URLError("offline")
        with patch.object(updater.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(updater.UpdateError):
                updater.fetch_manifest("https://github.com/manifest.json")

    def test_public_key_and_manifest_validation_reject_invalid_inputs(self):
        updater.PUBLIC_KEY_VALUE = "invalid-base64"
        with self.assertRaises(updater.UpdateError):
            updater.load_public_key()

        updater.PUBLIC_KEY_VALUE = ""
        with self.assertRaises(updater.UpdateError):
            updater.load_public_key()
        Path(updater.PUBLIC_KEY_FILE).write_bytes(self.public_key_pem)
        public_key = updater.load_public_key()
        self.assertIsInstance(public_key, updater.Ed25519PublicKey)

        invalid_manifests = [
            {},
            {**self.signed_manifest(), "schemaVersion": 2},
            {**self.signed_manifest(), "version": "latest"},
            {**self.signed_manifest(), "image": "ghcr.io/other/image@sha256:" + "a" * 64},
            {**self.signed_manifest(), "signatureAlgorithm": "rsa"},
            {**self.signed_manifest(), "signature": "not-base64"},
        ]
        updater.PUBLIC_KEY_VALUE = base64.b64encode(self.public_key_pem).decode("ascii")
        for manifest in invalid_manifests:
            with self.subTest(manifest=manifest):
                with self.assertRaises(updater.UpdateError):
                    updater.validate_manifest(manifest)
        with self.assertRaises(updater.UpdateError):
            updater.version_tuple("not-a-version")

    def test_redirect_and_active_image_checks_fail_closed(self):
        redirect_handler = updater.SafeHttpsRedirect({"github.com"})
        with self.assertRaises(updater.UpdateError):
            redirect_handler.redirect_request(None, None, 302, "Found", {}, "http://github.com/file")
        with self.assertRaises(updater.UpdateError):
            redirect_handler.redirect_request(None, None, 302, "Found", {}, "https://attacker.example/file")

        with patch.object(updater, "command", return_value=""):
            with self.assertRaises(updater.UpdateError):
                updater.active_container_id()
        with patch.object(
            updater,
            "command",
            side_effect=["container-id\n", "image-id", "ghcr.io/other/image@sha256:" + "a" * 64],
        ):
            with self.assertRaises(updater.UpdateError):
                updater.active_image_reference()
        expected_image = "ghcr.io/pondsec/inventorypro@sha256:" + "b" * 64
        with patch.object(
            updater,
            "command",
            side_effect=["container-id\n", "image-id", f"other\n{expected_image}\n"],
        ):
            self.assertEqual(updater.active_image_reference(), expected_image)

    def test_database_backup_is_private_and_restorable(self):
        database_path = updater.DATA_PATH / "inventory.db"
        database_path.parent.mkdir(parents=True)
        source = sqlite3.connect(database_path)
        source.execute("CREATE TABLE sample (value TEXT)")
        source.execute("INSERT INTO sample (value) VALUES ('preserved')")
        source.commit()
        source.close()

        backup_directory = updater.backup_database("1.2.3")

        backup = sqlite3.connect(backup_directory / "inventory.db")
        value = backup.execute("SELECT value FROM sample").fetchone()[0]
        backup.close()
        metadata = updater.load_json(backup_directory / "metadata.json")
        self.assertEqual(value, "preserved")
        self.assertEqual(metadata["targetVersion"], "1.2.3")
        self.assertEqual(backup_directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((backup_directory / "metadata.json").stat().st_mode & 0o777, 0o600)

        updater.DATA_PATH = self.root / "missing-data"
        with self.assertRaises(updater.UpdateError):
            updater.backup_database("1.2.4")

    def test_health_and_deployment_helpers(self):
        class HealthyResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, exception_type, exception, traceback):
                return False

        with patch.object(updater.urllib.request, "urlopen", return_value=HealthyResponse()):
            self.assertTrue(updater.wait_for_health())
        with patch.object(updater.time, "monotonic", side_effect=[0, 0, 2]):
            with patch.object(updater.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")):
                with patch.object(updater.time, "sleep"):
                    original_timeout = updater.HEALTH_TIMEOUT_SECONDS
                    updater.HEALTH_TIMEOUT_SECONDS = 1
                    try:
                        self.assertFalse(updater.wait_for_health())
                    finally:
                        updater.HEALTH_TIMEOUT_SECONDS = original_timeout

        image = "ghcr.io/pondsec/inventorypro@sha256:" + "c" * 64
        environment = updater.update_environment(image)
        self.assertEqual(environment["INVENTORY_IMAGE"], image)
        with patch.object(updater, "command") as command:
            updater.deploy_image(image)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(command.call_args_list[0].args[0][-2:], ["pull", updater.APP_SERVICE])

    def test_perform_update_records_success_up_to_date_and_rollback(self):
        policy = updater.normalize_policy(self.policy_payload())
        manifest = {
            "version": "1.2.3",
            "image": "ghcr.io/pondsec/inventorypro@sha256:" + "d" * 64,
        }
        previous_image = "ghcr.io/pondsec/inventorypro@sha256:" + "e" * 64
        backup_directory = self.root / "backup"

        updater.atomic_write_json(updater.STATE_PATH, {"schemaVersion": 1, "currentVersion": "1.2.3"})
        with patch.object(updater, "fetch_manifest", return_value={}):
            with patch.object(updater, "validate_manifest", return_value=manifest):
                self.assertEqual(updater.perform_update(policy), "up_to_date")
        self.assertEqual(updater.load_json(updater.STATE_PATH)["lastCheckStatus"], "up_to_date")

        updater.atomic_write_json(updater.STATE_PATH, {"schemaVersion": 1, "currentVersion": "1.2.2"})
        with patch.object(updater, "fetch_manifest", return_value={}):
            with patch.object(updater, "validate_manifest", return_value=manifest):
                with patch.object(updater, "active_image_reference", return_value=previous_image):
                    with patch.object(updater, "backup_database", return_value=backup_directory):
                        with patch.object(updater, "deploy_image") as deploy:
                            with patch.object(updater, "wait_for_health", return_value=True):
                                self.assertEqual(updater.perform_update(policy), "updated")
        state = updater.load_json(updater.STATE_PATH)
        self.assertEqual(state["currentVersion"], "1.2.3")
        self.assertEqual(deploy.call_args.args, (manifest["image"],))

        updater.atomic_write_json(updater.STATE_PATH, {"schemaVersion": 1, "currentVersion": "1.2.2"})
        with patch.object(updater, "fetch_manifest", return_value={}):
            with patch.object(updater, "validate_manifest", return_value=manifest):
                with patch.object(updater, "active_image_reference", return_value=previous_image):
                    with patch.object(updater, "backup_database", return_value=backup_directory):
                        with patch.object(updater, "deploy_image") as deploy:
                            with patch.object(updater, "wait_for_health", side_effect=[False, True]):
                                self.assertEqual(updater.perform_update(policy), "rolled_back")
        self.assertEqual(deploy.call_args_list[0].args, (manifest["image"],))
        self.assertEqual(deploy.call_args_list[1].args, (previous_image,))
        self.assertEqual(updater.load_json(updater.STATE_PATH)["lastCheckStatus"], "rolled_back")

    def test_failed_rollback_and_run_once_are_fail_closed(self):
        policy = updater.normalize_policy(self.policy_payload())
        manifest = {
            "version": "1.2.3",
            "image": "ghcr.io/pondsec/inventorypro@sha256:" + "f" * 64,
        }
        previous_image = "ghcr.io/pondsec/inventorypro@sha256:" + "1" * 64
        with patch.object(updater, "fetch_manifest", return_value={}):
            with patch.object(updater, "validate_manifest", return_value=manifest):
                with patch.object(updater, "active_image_reference", return_value=previous_image):
                    with patch.object(updater, "backup_database", return_value=self.root / "backup"):
                        with patch.object(updater, "deploy_image"):
                            with patch.object(updater, "wait_for_health", side_effect=[False, False]):
                                with self.assertRaises(updater.UpdateError):
                                    updater.perform_update(policy)
        self.assertEqual(updater.load_json(updater.STATE_PATH)["lastCheckStatus"], "rollback_failed")

        updater.atomic_write_json(updater.POLICY_PATH, self.policy_payload())
        with patch.object(updater, "perform_update", return_value="updated") as perform:
            self.assertEqual(updater.run_once(datetime(2026, 7, 25, 3, 30)), "updated")
        perform.assert_called_once()
        with patch.object(updater, "perform_update") as perform:
            self.assertEqual(updater.run_once(datetime(2026, 7, 25, 4, 30)), "outside_maintenance_window")
        perform.assert_not_called()


if __name__ == "__main__":
    unittest.main()
