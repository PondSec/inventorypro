from io import BytesIO
import os
import shutil
from unittest import TestCase
from unittest.mock import patch
import zipfile

from werkzeug.datastructures import FileStorage

from inventorypro.domains.imports.storage import (
    save_import_file,
    validate_import_archive,
    validate_import_file,
)


class ImportStorageTestCase(TestCase):
    def test_save_import_file_rejects_missing_large_and_unsafe_names(self):
        self.assertEqual(save_import_file(None, content_length=None, max_import_bytes=10), (None, "Keine Datei hochgeladen."))
        large = FileStorage(BytesIO(b"1234"), filename="devices.csv")
        self.assertEqual(save_import_file(large, content_length=11, max_import_bytes=10), (None, "Datei ist zu groß."))
        unsafe = FileStorage(BytesIO(b"test"), filename="../..")
        self.assertEqual(save_import_file(unsafe, content_length=4, max_import_bytes=10), (None, "Ungültiger Dateiname."))

    def test_save_import_file_uses_a_private_temporary_path(self):
        upload = FileStorage(BytesIO(b"name,serial\nedge,S-1\n"), filename="../devices.csv")

        path, error = save_import_file(upload, content_length=20, max_import_bytes=100)

        self.assertIsNone(error)
        self.assertEqual(path.name, "devices.csv")
        self.assertEqual(path.read_bytes(), b"name,serial\nedge,S-1\n")
        shutil.rmtree(path.parent, ignore_errors=True)

    def test_save_import_file_removes_temporary_directory_after_write_error(self):
        class BrokenUpload:
            filename = "devices.csv"

            def save(self, _path):
                raise OSError("storage unavailable")

        with self.assertRaisesRegex(OSError, "storage unavailable"):
            save_import_file(BrokenUpload(), content_length=1, max_import_bytes=10)

    def test_antivirus_and_archive_rejections_are_enforced(self):
        with patch.dict(os.environ, {"INVENTORY_ANTIVIRUS_COMMAND": "scanner"}), patch(
            "inventorypro.domains.imports.storage.subprocess.run"
        ) as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "malware detected"
            self.assertEqual(validate_import_file(__file__), "malware detected")
            run.return_value.stderr = ""
            self.assertEqual(validate_import_file(__file__), "Datei konnte nicht geprüft werden.")
            run.return_value.returncode = 0
            self.assertIsNone(validate_import_file(__file__))
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(validate_import_file(__file__))

        archive_data = BytesIO()
        with zipfile.ZipFile(archive_data, "w") as archive:
            archive.writestr("uploads/devices.csv", "name\nedge\n")
        with zipfile.ZipFile(BytesIO(archive_data.getvalue())) as archive:
            members = validate_import_archive(archive, max_expanded_bytes=100)
        self.assertEqual(members[0][1].as_posix(), "devices.csv")

        for filename, expected in (("../escape.csv", "unsicheren"), ("bad\\path.csv", "ungültigen")):
            unsafe_data = BytesIO()
            with zipfile.ZipFile(unsafe_data, "w") as archive:
                archive.writestr(filename, "x")
            with zipfile.ZipFile(BytesIO(unsafe_data.getvalue())) as archive, self.assertRaisesRegex(ValueError, expected):
                validate_import_archive(archive, max_expanded_bytes=100)

        oversized_data = BytesIO()
        with zipfile.ZipFile(oversized_data, "w") as archive:
            archive.writestr("records.csv", "x" * 101)
        with zipfile.ZipFile(BytesIO(oversized_data.getvalue())) as archive, self.assertRaisesRegex(ValueError, "Größe"):
            validate_import_archive(archive, max_expanded_bytes=100)
