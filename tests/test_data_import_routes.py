import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

from flask import Flask

from inventorypro.data_migration import TabularImportError
from inventorypro.domains.imports.data_routes import build_data_import_blueprint


class DataImportRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Mock()
        self.database.__enter__ = Mock(return_value=self.database)
        self.database.__exit__ = Mock(return_value=False)
        self.settings = {
            "importExport": {
                "importAllowed": True,
                "importMode": "append",
                "includeUploads": False,
            },
        }
        self.rate_limited = False
        self.save_error = None
        self.antivirus_error = None
        self.run_backup_job = Mock()
        self.import_tabular_file = Mock(return_value={"created": 1, "updated": 0, "skipped": 0, "errors": []})
        self.import_data_payload = Mock()
        self.validate_import_archive = Mock(return_value=[])
        self.import_table_rows = Mock()
        self.import_from_sqlite = Mock()
        self.log_activity = Mock()
        self.preview_proof_service = Mock()
        self.preview_proof_service.issue.return_value = "preview-proof"
        self.parse_tabular_file = Mock(return_value={"mapping": {"name": "Name"}, "sheetName": None})
        self.preview_tabular_file = Mock(
            return_value={
                "format": "csv",
                "validRows": 1,
                "invalidRows": 0,
                "mapping": {"name": "Name"},
            },
        )
        self.inspect_tabular_conflicts = Mock(return_value={"matchingKey": "name", "conflictCount": 0, "conflicts": []})
        self.application = Flask(__name__)
        self.application.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.application.register_blueprint(
            build_data_import_blueprint(
                get_db=lambda: self.database,
                get_import_settings=lambda database: self.settings,
                should_rate_limit=lambda key: self.rate_limited,
                current_actor=lambda: "tester",
                max_import_bytes=1024 * 1024,
                max_import_expanded_bytes=1024 * 1024,
                uploads_dir=self.root / "uploads",
                import_tables=("devices", "attachments"),
                run_backup_job=self.run_backup_job,
                save_import_file=self.save_import_file,
                validate_import_file=lambda path: self.antivirus_error,
                resolve_tabular_import_options=lambda *args: {
                    "mapping": {"name": "Name"},
                    "matchingKey": "name",
                    "sheetName": None,
                    "profileId": None,
                },
                import_profile_service=Mock(),
                preview_proof_service=self.preview_proof_service,
                build_preview_proof_arguments=lambda *args: {"proof": "valid"},
                import_tabular_file=self.import_tabular_file,
                import_data_payload=self.import_data_payload,
                validate_import_archive=self.validate_import_archive,
                import_table_rows=self.import_table_rows,
                import_from_sqlite=self.import_from_sqlite,
                parse_tabular_file=self.parse_tabular_file,
                preview_tabular_file=self.preview_tabular_file,
                inspect_tabular_conflicts=self.inspect_tabular_conflicts,
                log_activity=self.log_activity,
                login_required=lambda view: view,
                require_permission=lambda permission: lambda view: view,
            ),
        )
        self.client = self.application.test_client()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def save_import_file(self, file_storage, *, content_length, max_import_bytes):
        if self.save_error:
            return None, self.save_error
        directory = Path(tempfile.mkdtemp(dir=self.root))
        path = directory / file_storage.filename
        file_storage.save(path)
        return path, None

    @staticmethod
    def upload(content=b"name\nentry\n", filename="devices.csv"):
        return {"file": (io.BytesIO(content), filename)}

    def test_import_access_and_upload_guards_return_existing_errors(self):
        self.settings["importExport"]["importAllowed"] = False
        self.assertEqual(self.client.post("/api/import", data=self.upload()).status_code, 403)
        self.assertEqual(self.client.post("/api/import/preview", data=self.upload()).status_code, 403)

        self.settings["importExport"]["importAllowed"] = True
        self.rate_limited = True
        self.assertEqual(self.client.post("/api/import", data=self.upload()).status_code, 429)

        self.rate_limited = False
        self.save_error = "Datei fehlt"
        self.assertEqual(self.client.post("/api/import", data=self.upload()).status_code, 400)
        self.assertEqual(self.client.post("/api/import/preview", data=self.upload()).status_code, 400)

        self.save_error = None
        self.antivirus_error = "Datei wurde abgewiesen"
        response = self.client.post("/api/import", data=self.upload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Datei wurde abgewiesen")

    def test_imports_tabular_and_legacy_json_with_the_existing_contract(self):
        self.settings["importExport"]["importMode"] = "replace"
        tabular_response = self.client.post(
            "/api/import",
            data={"entity": "devices", "mode": "append", "previewToken": "preview-proof", **self.upload(b"[]", "devices.json")},
        )

        self.assertEqual(tabular_response.status_code, 200)
        self.assertEqual(tabular_response.get_json()["summary"]["created"], 1)
        self.run_backup_job.assert_called_with(self.database, self.settings, force=True)
        self.preview_proof_service.verify.assert_called_once()
        self.import_tabular_file.assert_called_once()

        legacy_response = self.client.post("/api/import", data=self.upload(b'{"devices": []}', "backup.json"))

        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(legacy_response.get_json(), {"status": "success"})
        self.import_data_payload.assert_called_once()

    def test_imports_zip_uploads_database_and_reports_format_errors(self):
        archive_content = io.BytesIO()
        with zipfile.ZipFile(archive_content, "w") as archive:
            archive.writestr("devices.csv", "name\nrouter\n")
            archive.writestr("uploads/attachments/proof.txt", "verified")
        archive_content.seek(0)

        def valid_archive(archive, *, max_expanded_bytes):
            return [(archive.getinfo("uploads/attachments/proof.txt"), Path("attachments/proof.txt"))]

        self.settings["importExport"]["includeUploads"] = True
        self.validate_import_archive.side_effect = valid_archive
        zip_response = self.client.post("/api/import", data=self.upload(archive_content.getvalue(), "backup.zip"))

        self.assertEqual(zip_response.status_code, 200)
        self.import_table_rows.assert_called_once()
        self.assertEqual((self.root / "uploads" / "attachments" / "proof.txt").read_text(), "verified")

        sqlite_response = self.client.post("/api/import", data=self.upload(b"sqlite", "backup.sqlite"))
        self.assertEqual(sqlite_response.status_code, 200)
        self.import_from_sqlite.assert_called_once()

        unsupported_response = self.client.post("/api/import", data=self.upload(b"unsupported", "backup.xml"))
        self.assertEqual(unsupported_response.status_code, 400)
        self.assertEqual(unsupported_response.get_json()["error"], "Unbekanntes Import-Format.")

        self.validate_import_archive.side_effect = ValueError("Unsicheres Archiv")
        rejected_archive = self.client.post("/api/import", data=self.upload(archive_content.getvalue(), "unsafe.zip"))
        self.assertEqual(rejected_archive.status_code, 400)
        self.assertEqual(rejected_archive.get_json()["error"], "Unsicheres Archiv")

    def test_import_rejection_and_preview_keep_audited_response_shapes(self):
        self.import_tabular_file.side_effect = TabularImportError("Ungültige Zeile")
        rejected = self.client.post(
            "/api/import",
            data={"entity": "devices", "previewToken": "preview-proof", **self.upload()},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["error"], "Ungültige Zeile")
        self.assertTrue(any(call.args[1] == "import_rejected" for call in self.log_activity.call_args_list))

        self.import_tabular_file.side_effect = None
        preview = self.client.post("/api/import/preview", data={"entity": "devices", **self.upload()})

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["previewToken"], "preview-proof")
        self.assertTrue(any(call.args[1] == "import_previewed" for call in self.log_activity.call_args_list))
