import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from cryptography.fernet import Fernet

import app as inventory_app
from inventorypro.config import ConfigurationError, resolve_application_secret
from inventorypro.migrations import MigrationError, apply_migrations
from inventorypro.factory import create_app
from inventorypro.secrets import (
    EncryptionKeyring,
    SecretConfigurationError,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
)


class ApplicationSecretTestCase(TestCase):
    def test_production_requires_persistent_application_secret(self):
        with self.assertRaises(ConfigurationError):
            resolve_application_secret({"INVENTORY_ENV": "production"})

    def test_configured_application_secret_is_preserved(self):
        secret = resolve_application_secret(
            {"INVENTORY_ENV": "production", "APP_SECRET_KEY": "persistent-value"}
        )
        self.assertEqual(secret.value, "persistent-value")
        self.assertFalse(secret.generated_for_development)

    def test_development_secret_is_explicitly_ephemeral(self):
        secret = resolve_application_secret({"INVENTORY_ENV": "development"})
        self.assertTrue(secret.generated_for_development)
        self.assertGreater(len(secret.value), 32)

    def test_compatibility_factory_returns_configured_application(self):
        application = create_app({"TESTING": True})
        self.assertIs(application, inventory_app.app)
        self.assertTrue(application.testing)


class InventoryLinkSecretTestCase(TestCase):
    def test_missing_or_invalid_key_blocks_secret_storage(self):
        with self.assertRaises(SecretConfigurationError):
            encrypt_secret("do-not-store", {})
        with self.assertRaises(SecretConfigurationError):
            encrypt_secret("do-not-store", {"INVENTORY_LINKS_ENCRYPTION_KEY": "invalid"})

    def test_valid_key_encrypts_without_exposing_plaintext(self):
        key = Fernet.generate_key().decode("utf-8")
        value = encrypt_secret("secret-value", {"INVENTORY_LINKS_ENCRYPTION_KEY": key})
        self.assertTrue(value.startswith("fernet:v1:"))
        self.assertNotIn("secret-value", value)
        self.assertEqual(decrypt_secret(value, {"INVENTORY_LINKS_ENCRYPTION_KEY": key}), "secret-value")

    def test_existing_plaintext_is_blocked_until_migration(self):
        key = Fernet.generate_key().decode("utf-8")
        with self.assertRaises(SecretConfigurationError):
            decrypt_secret("plain:legacy-value", {"INVENTORY_LINKS_ENCRYPTION_KEY": key})

    def test_key_rotation_decrypts_old_and_encrypts_with_primary_key(self):
        old_key = Fernet.generate_key().decode("utf-8")
        new_key = Fernet.generate_key().decode("utf-8")
        legacy = encrypt_secret("rotate-me", {"INVENTORY_LINKS_ENCRYPTION_KEY": old_key})
        rotation_environment = {"INVENTORY_LINKS_ENCRYPTION_KEYS": f"{new_key},{old_key}"}
        self.assertEqual(decrypt_secret(legacy, rotation_environment), "rotate-me")
        rotated = encrypt_secret("rotate-me", rotation_environment)
        self.assertIn(EncryptionKeyring.from_environ(rotation_environment).primary_identifier, rotated)
        self.assertEqual(decrypt_secret(rotated, rotation_environment), "rotate-me")

    def test_wrong_key_cannot_decrypt_value(self):
        encryption_key = Fernet.generate_key().decode("utf-8")
        wrong_key = Fernet.generate_key().decode("utf-8")
        encrypted = encrypt_secret("secret-value", {"INVENTORY_LINKS_ENCRYPTION_KEY": encryption_key})
        with self.assertRaises(SecretDecryptionError):
            decrypt_secret(encrypted, {"INVENTORY_LINKS_ENCRYPTION_KEY": wrong_key})

    def test_application_migrates_legacy_values_without_returning_them(self):
        previous_environment = dict(os.environ)
        old_key = Fernet.generate_key().decode("utf-8")
        new_key = Fernet.generate_key().decode("utf-8")
        try:
            os.environ["INVENTORY_LINKS_ENCRYPTION_KEYS"] = f"{new_key},{old_key}"
            os.environ.pop("INVENTORY_LINKS_ENCRYPTION_KEY", None)
            with tempfile.TemporaryDirectory() as directory:
                database_path = Path(directory) / "links.db"
                connection = sqlite3.connect(database_path)
                connection.row_factory = sqlite3.Row
                connection.execute(
                    "CREATE TABLE inventory_links (id TEXT PRIMARY KEY, secret_encrypted TEXT, updated_at TEXT)"
                )
                legacy_ciphertext = Fernet(old_key.encode("utf-8")).encrypt(b"old-secret").decode("utf-8")
                connection.executemany(
                    "INSERT INTO inventory_links (id, secret_encrypted) VALUES (?, ?)",
                    [("legacy", legacy_ciphertext), ("plain", "plain:plain-secret")],
                )
                connection.commit()
                result = inventory_app.migrate_inventory_link_secrets(connection, reencrypt_all=True)
                rows = connection.execute("SELECT secret_encrypted FROM inventory_links ORDER BY id").fetchall()
                connection.close()
            self.assertEqual(result, {"migrated": 2, "skipped": 0})
            self.assertTrue(all(row["secret_encrypted"].startswith("fernet:v1:") for row in rows))
            self.assertNotIn("old-secret", "".join(row["secret_encrypted"] for row in rows))
        finally:
            os.environ.clear()
            os.environ.update(previous_environment)


class CsrfProtectionTestCase(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)
        inventory_app.DATABASE = str(temporary_path / "inventory.db")
        inventory_app.UPLOADS_DIR = temporary_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temporary_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temporary_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {"host": "127.0.0.1", "port": 0, "debug": False}
        inventory_app.init_db()
        inventory_app.app.config["TESTING"] = False
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.app.config["TESTING"] = True
        self.temporary_directory.cleanup()

    def test_write_requires_a_session_bound_token(self):
        self.client.get("/login")
        rejected = self.client.post("/login", data={"username": "admin", "password": "invalid"})
        self.assertEqual(rejected.status_code, 403)
        with self.client.session_transaction() as session:
            token = session["_csrf_token"]
        accepted = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid", "csrf_token": token},
        )
        self.assertNotEqual(accepted.status_code, 403)

    def test_invalid_or_cross_origin_write_is_rejected(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            token = session["_csrf_token"]
        invalid = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"X-CSRF-Token": "wrong"},
        )
        self.assertEqual(invalid.status_code, 403)
        cross_origin = self.client.post(
            "/login",
            data={"username": "admin", "password": "invalid"},
            headers={"X-CSRF-Token": token, "Origin": "https://attacker.example"},
        )
        self.assertEqual(cross_origin.status_code, 403)

    def test_untrusted_forwarded_headers_are_not_used_for_client_identity(self):
        previous_networks = inventory_app.TRUSTED_PROXY_NETWORKS
        try:
            inventory_app.TRUSTED_PROXY_NETWORKS = ()
            with inventory_app.app.test_request_context(
                "/",
                headers={"X-Forwarded-For": "203.0.113.10", "X-Forwarded-Proto": "https"},
                environ_base={"REMOTE_ADDR": "198.51.100.7"},
            ):
                self.assertEqual(inventory_app.get_client_ip(), "198.51.100.7")
                self.assertNotIn("https://", inventory_app.expected_request_origins())
        finally:
            inventory_app.TRUSTED_PROXY_NETWORKS = previous_networks

    def test_local_inventory_links_require_administrator_access(self):
        self.assertEqual(
            inventory_app.enforce_inventory_link_scope_access(
                {"is_superuser": False, "permissions": set()}, "local"
            ),
            "Lokale Inventory-Link-Verbindungen benötigen Administratorrechte.",
        )
        self.assertIsNone(
            inventory_app.enforce_inventory_link_scope_access(
                {"is_superuser": True, "permissions": set()}, "local"
            )
        )


class MigrationRunnerTestCase(TestCase):
    def test_migrations_are_recorded_and_checksum_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_directory = root / "migrations"
            migration_directory.mkdir()
            migration = migration_directory / "001_create_example.sql"
            migration.write_text("CREATE TABLE example (id INTEGER PRIMARY KEY);", encoding="utf-8")
            connection = sqlite3.connect(root / "database.db")
            self.assertEqual(apply_migrations(connection, migration_directory), ["001_create_example"])
            self.assertEqual(apply_migrations(connection, migration_directory), [])
            migration.write_text("CREATE TABLE changed_example (id INTEGER PRIMARY KEY);", encoding="utf-8")
            with self.assertRaises(MigrationError):
                apply_migrations(connection, migration_directory)
            connection.close()

    def test_failed_migration_rolls_back_schema_and_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_directory = root / "migrations"
            migration_directory.mkdir()
            (migration_directory / "001_broken.sql").write_text(
                "CREATE TABLE should_not_exist (id INTEGER PRIMARY KEY);\n"
                "THIS IS NOT VALID SQL;",
                encoding="utf-8",
            )
            connection = sqlite3.connect(root / "database.db")
            with self.assertRaises(MigrationError):
                apply_migrations(connection, migration_directory)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertNotIn("should_not_exist", tables)
            self.assertNotIn("schema_migrations", tables)
            connection.close()

    def test_missing_applied_migration_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_directory = root / "migrations"
            migration_directory.mkdir()
            migration = migration_directory / "001_create_example.sql"
            migration.write_text("CREATE TABLE example (id INTEGER PRIMARY KEY);", encoding="utf-8")
            connection = sqlite3.connect(root / "database.db")
            apply_migrations(connection, migration_directory)
            migration.unlink()
            with self.assertRaisesRegex(MigrationError, "fehlt"):
                apply_migrations(connection, migration_directory)
            connection.close()

    def test_migrations_respect_an_existing_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_directory = root / "migrations"
            migration_directory.mkdir()
            (migration_directory / "001_create_example.sql").write_text(
                "CREATE TABLE example (id INTEGER PRIMARY KEY);",
                encoding="utf-8",
            )
            connection = sqlite3.connect(root / "database.db")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE outer_change (id INTEGER PRIMARY KEY)")
            self.assertEqual(apply_migrations(connection, migration_directory), ["001_create_example"])
            self.assertTrue(connection.in_transaction)
            connection.rollback()
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertNotIn("outer_change", tables)
            self.assertNotIn("example", tables)
            self.assertNotIn("schema_migrations", tables)
            connection.close()

    def test_migration_cannot_control_its_own_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_directory = root / "migrations"
            migration_directory.mkdir()
            (migration_directory / "001_transaction_control.sql").write_text(
                "-- The runner owns the transaction.\nBEGIN;\nCREATE TABLE example (id INTEGER);",
                encoding="utf-8",
            )
            connection = sqlite3.connect(root / "database.db")
            with self.assertRaisesRegex(MigrationError, "Transaktionsbefehle"):
                apply_migrations(connection, migration_directory)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertNotIn("example", tables)
            connection.close()


class BackupRestoreTestCase(TestCase):
    def test_restore_validates_manifest_and_keeps_rollback_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.db"
            target_path = root / "target.db"
            source_connection = sqlite3.connect(source_path)
            source_connection.execute("CREATE TABLE example (value TEXT)")
            source_connection.execute("INSERT INTO example (value) VALUES ('restored')")
            source_connection.commit()
            source_connection.close()
            target_connection = sqlite3.connect(target_path)
            target_connection.execute("CREATE TABLE example (value TEXT)")
            target_connection.execute("INSERT INTO example (value) VALUES ('previous')")
            target_connection.commit()
            target_connection.close()

            inventory_app.write_backup_manifest(source_path)
            result = inventory_app.restore_sqlite_backup(source_path, target_path)

            restored_connection = sqlite3.connect(target_path)
            restored_value = restored_connection.execute("SELECT value FROM example").fetchone()[0]
            restored_connection.close()
            rollback_connection = sqlite3.connect(result["rollback"])
            rollback_value = rollback_connection.execute("SELECT value FROM example").fetchone()[0]
            rollback_connection.close()
            self.assertEqual(restored_value, "restored")
            self.assertEqual(rollback_value, "previous")

    def test_restore_refuses_a_tampered_manifested_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_path = root / "backup.db"
            connection = sqlite3.connect(backup_path)
            connection.execute("CREATE TABLE example (value TEXT)")
            connection.commit()
            connection.close()
            inventory_app.write_backup_manifest(backup_path)
            with backup_path.open("ab") as handle:
                handle.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "Prüfsumme"):
                inventory_app.restore_sqlite_backup(backup_path, root / "target.db")
