import sqlite3
from unittest import TestCase
from unittest.mock import Mock

from itsdangerous import SignatureExpired

from inventorypro.domains.imports.service import (
    ImportPreviewProofService,
    ImportProfileService,
    ImportProfileValidationError,
    parse_mapping,
    parse_profile_id,
)


class ImportProfileServiceTestCase(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE import_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                entity TEXT NOT NULL,
                mapping_json TEXT NOT NULL DEFAULT '{}',
                matching_key TEXT,
                sheet_name TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.service = ImportProfileService()

    def tearDown(self):
        self.connection.close()

    def test_profile_lifecycle_and_resolution(self):
        created = self.service.create(
            self.connection,
            {
                "name": "Altes Inventar",
                "entity": "devices",
                "mapping": {"name": "Computer", "serial_number": "Asset Tag"},
                "matchingKey": "serial_number",
                "sheetName": "Hardware",
            },
            "admin",
        )
        self.assertEqual(created["createdBy"], "admin")
        self.assertEqual(self.service.list(self.connection, "devices"), [created])
        self.assertEqual(
            self.service.resolve(self.connection, created["id"], "devices"),
            {
                "mapping": {"name": "Computer", "serial_number": "Asset Tag"},
                "matchingKey": "serial_number",
                "sheetName": "Hardware",
                "profileId": created["id"],
            },
        )

        updated = self.service.update(
            self.connection,
            created["id"],
            {
                "name": "Altes Inventar v2",
                "entity": "devices",
                "mapping": {"name": "Hostname"},
                "matchingKey": "name",
            },
        )
        self.assertEqual(updated["name"], "Altes Inventar v2")
        self.assertEqual(updated["sheetName"], None)
        self.assertTrue(self.service.delete(self.connection, created["id"]))
        self.assertFalse(self.service.delete(self.connection, created["id"]))

    def test_profile_validation_rejects_duplicate_invalid_and_foreign_profiles(self):
        created = self.service.create(
            self.connection,
            {"name": "Profil", "entity": "assets", "mapping": {}},
            "admin",
        )
        with self.assertRaisesRegex(ImportProfileValidationError, "existiert bereits"):
            self.service.create(self.connection, {"name": "Profil", "entity": "assets", "mapping": {}}, "admin")
        with self.assertRaisesRegex(ImportProfileValidationError, "nicht zulässig"):
            self.service.create(
                self.connection,
                {"name": "Ungültig", "entity": "assets", "mapping": {}, "matchingKey": "serial_number"},
                "admin",
            )
        with self.assertRaisesRegex(ImportProfileValidationError, "nicht verfügbar"):
            self.service.resolve(self.connection, created["id"], "devices")
        self.assertIsNone(self.service.update(self.connection, 999, {"name": "Neu", "entity": "assets", "mapping": {}}))
        with self.assertRaisesRegex(ImportProfileValidationError, "Datentyp"):
            self.service.list(self.connection, "vendors")

    def test_mapping_profile_id_and_preview_proof_validation(self):
        self.assertEqual(parse_mapping('{"name": "Computer", "serial_number": null}'), {"name": "Computer", "serial_number": None})
        self.assertIsNone(parse_mapping(None))
        self.assertEqual(parse_profile_id("42"), 42)
        with self.assertRaisesRegex(ImportProfileValidationError, "gültiges JSON"):
            parse_mapping("{")
        with self.assertRaisesRegex(ImportProfileValidationError, "Objekt"):
            parse_mapping(["not-a-mapping"])
        with self.assertRaisesRegex(ImportProfileValidationError, "Zielfeld"):
            parse_mapping({"": "Computer"})
        with self.assertRaisesRegex(ImportProfileValidationError, "Quellspalte"):
            parse_mapping({"name": 123})
        with self.assertRaisesRegex(ImportProfileValidationError, "Importprofil-ID"):
            parse_profile_id("0")

        proof = ImportPreviewProofService("test-secret")
        arguments = {
            "content": b"Hostname,Serial\nedge-1,S-1\n",
            "filename": "devices.csv",
            "entity": "devices",
            "mapping": {"name": "Hostname", "serial_number": "Serial"},
            "matching_key": "serial_number",
            "sheet_name": None,
            "actor": "admin",
        }
        token = proof.issue(**arguments)
        self.assertIsNone(proof.verify(token, **arguments))
        with self.assertRaisesRegex(ImportProfileValidationError, "weichen"):
            proof.verify(token, **{**arguments, "content": b"Hostname,Serial\nother,S-1\n"})
        with self.assertRaisesRegex(ImportProfileValidationError, "ungültig"):
            proof.verify("not-a-proof", **arguments)
        with self.assertRaisesRegex(ImportProfileValidationError, "aktuelle Vorschau"):
            proof.verify(None, **arguments)
        expired_proof = ImportPreviewProofService("test-secret")
        expired_proof.serializer = Mock()
        expired_proof.serializer.loads.side_effect = SignatureExpired("expired")
        with self.assertRaisesRegex(ImportProfileValidationError, "abgelaufen"):
            expired_proof.verify("signed-proof", **arguments)

    def test_profile_payload_validation_and_duplicate_update(self):
        with self.assertRaisesRegex(ImportProfileValidationError, "Profilname"):
            self.service.create(self.connection, {"name": "", "entity": "assets", "mapping": {}}, "admin")
        with self.assertRaisesRegex(ImportProfileValidationError, "Datentyp"):
            self.service.create(self.connection, {"name": "Unbekannt", "entity": "vendors", "mapping": {}}, "admin")
        with self.assertRaisesRegex(ImportProfileValidationError, "Tabellenblattname"):
            self.service.create(
                self.connection,
                {"name": "Lang", "entity": "assets", "mapping": {}, "sheetName": "x" * 101},
                "admin",
            )
        first = self.service.create(self.connection, {"name": "Erstes", "entity": "assets", "mapping": {}}, "admin")
        second = self.service.create(self.connection, {"name": "Zweites", "entity": "assets", "mapping": {}}, "admin")
        with self.assertRaisesRegex(ImportProfileValidationError, "existiert bereits"):
            self.service.update(
                self.connection,
                second["id"],
                {"name": first["name"], "entity": "assets", "mapping": {}},
            )
