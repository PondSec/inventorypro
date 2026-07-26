import json
from datetime import date
from io import BytesIO
import sqlite3
from unittest import TestCase

from openpyxl import Workbook

from inventorypro.data_migration import (
    TabularImportError,
    import_tabular_csv,
    import_tabular_file,
    preview_tabular_file,
    preview_tabular_csv,
)


class DataMigrationTestCase(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
            CREATE TABLE asset_categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
            CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
            CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, serial_number TEXT, location_id INTEGER, specs TEXT);
            CREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, notes TEXT, specs TEXT, acquisition_date TEXT, commissioning_date TEXT, warranty_end TEXT, purchase_cost REAL, currency TEXT, cost_center TEXT, invoice_number TEXT);
            """
        )

    def tearDown(self):
        self.connection.close()

    def test_preview_recognizes_german_headers_and_keeps_extra_columns(self):
        preview = preview_tabular_csv(
            "Gerät;Seriennummer;Standort;Hersteller\nSwitch-01;S-1;Berlin;Pond\n".encode(),
            "devices",
        )
        self.assertEqual(preview["validRows"], 1)
        self.assertEqual(preview["mapping"]["name"], "Gerät")
        self.assertEqual(preview["sample"][0]["specs"], {"Hersteller": "Pond"})

    def test_import_creates_and_merges_devices_without_losing_extra_fields(self):
        source = "hostname,serial,location,model\ncore-1,S-1,HQ,X100\n".encode()
        created = import_tabular_csv(self.connection, source, "devices", "append")
        self.assertEqual(created, {"created": 1, "updated": 0, "skipped": 0, "errors": []})
        row = self.connection.execute("SELECT * FROM devices").fetchone()
        self.assertEqual(json.loads(row["specs"]), {"model": "X100"})
        merged = import_tabular_csv(
            self.connection, "hostname,serial,location\ncore-renamed,S-1,West\n".encode(), "devices", "merge"
        )
        self.assertEqual((merged["created"], merged["updated"]), (0, 1))
        self.assertEqual(self.connection.execute("SELECT name FROM devices").fetchone()[0], "core-renamed")

    def test_asset_import_parses_localized_cost_and_rejects_invalid_rows(self):
        source = "Asset;Rechnungsnummer;Anschaffungskosten;Währung\nLaptop;INV-1;1.234,50;EUR\n".encode()
        result = import_tabular_csv(self.connection, source, "assets", "append")
        self.assertEqual(result["created"], 1)
        self.assertEqual(self.connection.execute("SELECT purchase_cost FROM assets").fetchone()[0], 1234.5)
        with self.assertRaisesRegex(TabularImportError, "Name/Gerät/Asset"):
            preview_tabular_csv(b"foo\nbar\n", "assets")
        with self.assertRaisesRegex(TabularImportError, "Importmodus"):
            import_tabular_csv(self.connection, source, "assets", "replace")

    def test_import_handles_invalid_encodings_empty_rows_and_duplicates(self):
        with self.assertRaisesRegex(TabularImportError, "UTF-8"):
            preview_tabular_csv(b"\xff", "devices")
        with self.assertRaisesRegex(TabularImportError, "Kopfzeile"):
            preview_tabular_csv(b"", "devices")
        preview = preview_tabular_csv(b"name,serial\n,missing\nvalid,S-2\n", "devices")
        self.assertEqual((preview["validRows"], preview["invalidRows"]), (1, 1))
        with self.assertRaisesRegex(TabularImportError, "ungültige Zeilen"):
            import_tabular_csv(self.connection, b"name\n \n", "devices", "append")

        source = b"name,serial\nfirst,S-2\n"
        import_tabular_csv(self.connection, source, "devices", "append")
        self.assertEqual(import_tabular_csv(self.connection, source, "devices", "append")["skipped"], 1)

    def test_asset_merge_and_cost_validation_are_transactional(self):
        source = b"asset,invoice,price\nLaptop,INV-2,1000\n"
        import_tabular_csv(self.connection, source, "assets", "append")
        merged = import_tabular_csv(
            self.connection, b"asset,invoice,price\nLaptop Pro,INV-2,\"1,200.50\"\n", "assets", "merge"
        )
        self.assertEqual(merged["updated"], 1)
        self.assertEqual(self.connection.execute("SELECT name FROM assets").fetchone()[0], "Laptop Pro")
        with self.assertRaisesRegex(TabularImportError, "keine gültige Zahl"):
            import_tabular_csv(self.connection, b"asset,price\nBroken,nope\n", "assets", "append")

    def test_xlsx_import_uses_the_same_alias_mapping_and_preserves_extras(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Hostname", "Seriennummer", "Standort", "Hersteller", "Aktiv", "Prüfdatum"])
        worksheet.append(["core-xlsx", "S-XLSX", "Berlin", "Beispiel GmbH", True, date(2026, 1, 2)])
        buffer = BytesIO()
        workbook.save(buffer)

        preview = preview_tabular_file(buffer.getvalue(), "devices", "device-export.xlsx")
        self.assertEqual(preview["format"], "xlsx")
        self.assertEqual(preview["mapping"]["name"], "Hostname")
        self.assertEqual(
            preview["sample"][0]["specs"],
            {"Hersteller": "Beispiel GmbH", "Aktiv": "true", "Prüfdatum": "2026-01-02"},
        )

        result = import_tabular_file(self.connection, buffer.getvalue(), "devices", "append", "device-export.xlsx")
        self.assertEqual(result["created"], 1)
        self.assertEqual(self.connection.execute("SELECT name FROM devices").fetchone()[0], "core-xlsx")

    def test_json_preview_and_import_accept_named_arrays(self):
        content = json.dumps({
            "assets": [{
                "Bezeichnung": "Notebook",
                "Rechnungsnummer": "INV-JSON",
                "Preis": 1999.95,
                "Währung": "EUR",
                "Hersteller": "Beispiel GmbH",
            }],
        }).encode()

        preview = preview_tabular_file(content, "assets", "assets.json")
        self.assertEqual(preview["format"], "json")
        self.assertEqual(preview["validRows"], 1)
        self.assertEqual(preview["sample"][0]["specs"], {"Hersteller": "Beispiel GmbH"})

        result = import_tabular_file(self.connection, content, "assets", "append", "assets.json")
        self.assertEqual(result["created"], 1)
        self.assertEqual(self.connection.execute("SELECT purchase_cost FROM assets").fetchone()[0], 1999.95)

    def test_rejects_malformed_xlsx(self):
        with self.assertRaisesRegex(TabularImportError, "beschädigt"):
            preview_tabular_file(b"not an xlsx", "devices", "devices.xlsx")

    def test_rejects_ambiguous_or_invalid_source_shapes(self):
        with self.assertRaisesRegex(TabularImportError, "doppelte Spaltenüberschriften"):
            preview_tabular_csv(b"name,Name\nfirst,duplicate\n", "devices")
        with self.assertRaisesRegex(TabularImportError, "Nur Geräte und Assets"):
            preview_tabular_file(b"name\nentry\n", "vendors", "vendors.csv")
        with self.assertRaisesRegex(TabularImportError, "gültig"):
            preview_tabular_file(b"{", "devices", "devices.json")
        with self.assertRaisesRegex(TabularImportError, "Array"):
            preview_tabular_file(b"{}", "devices", "devices.json")
        with self.assertRaisesRegex(TabularImportError, "muss ein Objekt"):
            preview_tabular_file(b'["not-an-object"]', "devices", "devices.json")
        with self.assertRaisesRegex(TabularImportError, "keine Kopfzeile"):
            preview_tabular_file(b"[]", "devices", "devices.json")

    def test_custom_mapping_sheet_selection_and_matching_key_are_enforced(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Nicht verwenden"
        worksheet.append(["Name", "Seriennummer"])
        worksheet.append(["falsches Gerät", "WRONG"])
        hardware = workbook.create_sheet("Hardware")
        hardware.append(["Computer", "Asset Tag", "Lieferant"])
        hardware.append(["edge-1", "EDGE-1", "Pond"])
        buffer = BytesIO()
        workbook.save(buffer)

        mapping = {"name": "Computer", "serial_number": "Asset Tag"}
        preview = preview_tabular_file(
            buffer.getvalue(),
            "devices",
            "legacy.xlsx",
            mapping_override=mapping,
            sheet_name="Hardware",
        )
        self.assertEqual(preview["sheetName"], "Hardware")
        self.assertEqual(preview["availableSheets"], ["Nicht verwenden", "Hardware"])
        self.assertEqual(preview["sample"][0]["specs"], {"Lieferant": "Pond"})

        imported = import_tabular_file(
            self.connection,
            buffer.getvalue(),
            "devices",
            "append",
            "legacy.xlsx",
            mapping_override=mapping,
            matching_key="serial_number",
            sheet_name="Hardware",
        )
        self.assertEqual(imported["created"], 1)
        with self.assertRaisesRegex(TabularImportError, "abgebrochen"):
            import_tabular_file(
                self.connection,
                buffer.getvalue(),
                "devices",
                "abort",
                "legacy.xlsx",
                mapping_override=mapping,
                matching_key="serial_number",
                sheet_name="Hardware",
            )
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0], 1)

    def test_mapping_and_matching_validation_rejects_unsafe_or_missing_choices(self):
        source = b"Computer,Asset Tag\nedge-1,EDGE-1\n"
        with self.assertRaisesRegex(TabularImportError, "Objekt"):
            preview_tabular_file(source, "devices", "devices.csv", mapping_override=["not-a-mapping"])
        with self.assertRaisesRegex(TabularImportError, "unbekannte Zielfelder"):
            preview_tabular_file(source, "devices", "devices.csv", mapping_override={"owner": "Computer"})
        with self.assertRaisesRegex(TabularImportError, "nicht vorhanden"):
            preview_tabular_file(source, "devices", "devices.csv", mapping_override={"name": "Nicht da"})
        with self.assertRaisesRegex(TabularImportError, "nur einem Zielfeld"):
            preview_tabular_file(
                source,
                "devices",
                "devices.csv",
                mapping_override={"name": "Computer", "serial_number": "Computer"},
            )
        with self.assertRaisesRegex(TabularImportError, "Abgleichschlüssel"):
            import_tabular_file(
                self.connection,
                source,
                "devices",
                "append",
                "devices.csv",
                mapping_override={"name": "Computer", "serial_number": "Asset Tag"},
                matching_key="invoice_number",
            )
        with self.assertRaisesRegex(TabularImportError, "zugeordnet"):
            import_tabular_file(
                self.connection,
                source,
                "devices",
                "append",
                "devices.csv",
                mapping_override={"name": "Computer", "serial_number": None},
                matching_key="serial_number",
            )
        with self.assertRaisesRegex(TabularImportError, "Tabellenblatt"):
            workbook = Workbook()
            workbook.active.append(["Name"])
            buffer = BytesIO()
            workbook.save(buffer)
            preview_tabular_file(buffer.getvalue(), "devices", "devices.xlsx", sheet_name="Fehlt")

    def test_asset_conflicts_skip_and_reuse_existing_location(self):
        self.connection.execute("INSERT INTO locations (name) VALUES ('Berlin')")
        import_tabular_csv(self.connection, b"name,serial,location\nedge-1,S-1,Berlin\n", "devices", "append")
        import_tabular_csv(self.connection, b"name,serial,location\nedge-2,S-2,Berlin\n", "devices", "append")
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM locations").fetchone()[0], 1)
        source = b"asset,invoice,price\nNotebook,INV-1,\n"
        self.assertEqual(import_tabular_csv(self.connection, source, "assets", "append")["created"], 1)
        self.assertEqual(import_tabular_csv(self.connection, source, "assets", "append")["skipped"], 1)
        self.assertIsNone(self.connection.execute("SELECT purchase_cost FROM assets").fetchone()[0])
        with self.assertRaisesRegex(TabularImportError, "CSV, TSV, XLSX und JSON"):
            preview_tabular_file(source, "assets", "assets.xml")
