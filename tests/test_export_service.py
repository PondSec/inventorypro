from unittest import TestCase

from inventorypro.domains.exports.service import (
    build_export_metadata,
    protect_spreadsheet_record,
    protect_spreadsheet_row,
    protect_spreadsheet_value,
)


class ExportServiceTestCase(TestCase):
    def test_formula_like_cells_are_exported_as_text(self):
        self.assertEqual(protect_spreadsheet_value("=SUM(A1:A2)"), "'=SUM(A1:A2)")
        self.assertEqual(protect_spreadsheet_value(" \t@HYPERLINK(\"https://example.test\")"), "' \t@HYPERLINK(\"https://example.test\")")
        self.assertEqual(protect_spreadsheet_value(-42), -42)
        self.assertEqual(protect_spreadsheet_value("ordinary text"), "ordinary text")
        self.assertEqual(
            protect_spreadsheet_record({"name": "+payload", "count": 2}),
            {"name": "'+payload", "count": 2},
        )
        self.assertEqual(protect_spreadsheet_row(["-payload", "safe"]), ["'-payload", "safe"])

    def test_metadata_is_utc_and_contains_export_scope(self):
        metadata = build_export_metadata("xlsx", ("devices", "assets"))

        self.assertEqual(metadata["format"], "xlsx")
        self.assertEqual(metadata["tables"], ["devices", "assets"])
        self.assertTrue(metadata["exportedAt"].endswith("Z"))
