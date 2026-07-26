"""Safe, schema-aware migration of tabular device and asset inventories."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from typing import Any


class TabularImportError(ValueError):
    """Raised for a recoverable, user-facing tabular import problem."""


_ALIASES = {
    "devices": {
        "name": {"name", "device", "device name", "hostname", "host", "gerät", "geraet"},
        "serial_number": {"serial", "serial number", "serialnumber", "seriennummer", "sn"},
        "category": {"category", "device category", "kategorie", "gerätekategorie", "geraetekategorie"},
        "location": {"location", "site", "standort", "office"},
    },
    "assets": {
        "name": {"name", "asset", "asset name", "bezeichnung", "gerät", "geraet"},
        "category": {"category", "asset category", "kategorie", "assetkategorie"},
        "notes": {"notes", "note", "beschreibung", "description", "notizen"},
        "acquisition_date": {"acquisition date", "purchase date", "kaufdatum", "anschaffungsdatum"},
        "commissioning_date": {"commissioning date", "inbetriebnahme", "inbetriebnahmedatum"},
        "warranty_end": {"warranty end", "warranty expiry", "garantieende", "garantie bis"},
        "purchase_cost": {"purchase cost", "cost", "price", "preis", "anschaffungskosten"},
        "currency": {"currency", "währung", "waehrung"},
        "cost_center": {"cost center", "kostenstelle"},
        "invoice_number": {"invoice", "invoice number", "rechnungsnummer"},
    },
}


def _key(value: str) -> str:
    normalized = value.casefold()
    normalized = normalized.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def parse_tabular_csv(content: bytes, entity: str) -> dict[str, Any]:
    """Parse a CSV/TSV export and infer a conservative Inventory Pro mapping."""
    if entity not in _ALIASES:
        raise TabularImportError("Nur Geräte und Assets können tabellarisch importiert werden.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise TabularImportError("Die Importdatei muss UTF-8-kodiert sein.") from error
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise TabularImportError("Die Datei enthält keine Kopfzeile.")
    mapping = {}
    for target, aliases in _ALIASES[entity].items():
        normalized_aliases = {_key(alias) for alias in aliases}
        mapping[target] = next(
            (header for header in reader.fieldnames if _key(header) in normalized_aliases),
            None,
        )
    if not mapping["name"]:
        raise TabularImportError("Keine Spalte für Name/Gerät/Asset erkannt.")
    rows, errors = [], []
    for line_number, source in enumerate(reader, start=2):
        normalized = {
            target: (source.get(header) or "").strip()
            for target, header in mapping.items()
            if header
        }
        if not normalized.get("name"):
            errors.append({"line": line_number, "error": "Name ist erforderlich."})
            continue
        extras = {
            header: value
            for header, value in source.items()
            if header not in mapping.values() and value
        }
        normalized["specs"] = extras
        rows.append(normalized)
    return {"entity": entity, "mapping": mapping, "rows": rows, "errors": errors, "delimiter": dialect.delimiter}


def preview_tabular_csv(content: bytes, entity: str) -> dict[str, Any]:
    parsed = parse_tabular_csv(content, entity)
    return {
        "entity": entity,
        "mapping": parsed["mapping"],
        "validRows": len(parsed["rows"]),
        "invalidRows": len(parsed["errors"]),
        "errors": parsed["errors"][:100],
        "sample": parsed["rows"][:20],
    }


def import_tabular_csv(connection: sqlite3.Connection, content: bytes, entity: str, mode: str) -> dict[str, Any]:
    """Import validated rows atomically; unknown source columns remain in specs."""
    if mode not in {"append", "merge"}:
        raise TabularImportError("Importmodus muss append oder merge sein.")
    parsed = parse_tabular_csv(content, entity)
    if parsed["errors"]:
        raise TabularImportError("Die Vorschau enthält ungültige Zeilen; bitte zuerst korrigieren.")
    created = updated = skipped = 0
    with connection:
        for row in parsed["rows"]:
            if entity == "devices":
                category_id = _category_id(connection, "categories", row.get("category") or "Importiert")
                location_id = _location_id(connection, row.get("location"))
                existing = _find_device_by_serial(connection, row.get("serial_number"))
                if existing and mode == "append":
                    skipped += 1
                    continue
                values = (
                    row["name"], category_id, row.get("serial_number") or None,
                    location_id, json.dumps(row["specs"], ensure_ascii=False),
                )
                if existing:
                    connection.execute(
                        "UPDATE devices SET name=?, category_id=?, serial_number=?, location_id=?, specs=? WHERE id=?",
                        (*values, existing["id"]),
                    )
                    updated += 1
                else:
                    connection.execute(
                        "INSERT INTO devices (name, category_id, serial_number, location_id, specs) VALUES (?, ?, ?, ?, ?)",
                        values,
                    )
                    created += 1
            else:
                category_id = _category_id(connection, "asset_categories", row.get("category") or "Importiert")
                existing = _find_asset_by_invoice(connection, row.get("invoice_number"))
                if existing and mode == "append":
                    skipped += 1
                    continue
                values = (
                    row["name"], category_id, row.get("notes") or None,
                    json.dumps(row["specs"], ensure_ascii=False), row.get("acquisition_date") or None,
                    row.get("commissioning_date") or None, row.get("warranty_end") or None,
                    _cost(row.get("purchase_cost")), row.get("currency") or None,
                    row.get("cost_center") or None, row.get("invoice_number") or None,
                )
                if existing:
                    connection.execute(
                        "UPDATE assets SET name=?, category_id=?, notes=?, specs=?, acquisition_date=?, commissioning_date=?, warranty_end=?, purchase_cost=?, currency=?, cost_center=?, invoice_number=? WHERE id=?",
                        (*values, existing["id"]),
                    )
                    updated += 1
                else:
                    connection.execute(
                        "INSERT INTO assets (name, category_id, notes, specs, acquisition_date, commissioning_date, warranty_end, purchase_cost, currency, cost_center, invoice_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values,
                    )
                    created += 1
    return {"created": created, "updated": updated, "skipped": skipped, "errors": parsed["errors"]}


def _category_id(connection: sqlite3.Connection, table: str, name: str) -> int:
    row = connection.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return connection.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,)).lastrowid


def _location_id(connection: sqlite3.Connection, name: str | None) -> int | None:
    if not name:
        return None
    row = connection.execute("SELECT id FROM locations WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return connection.execute("INSERT INTO locations (name) VALUES (?)", (name,)).lastrowid


def _cost(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace(" ", "")
    if "," in normalized and "." in normalized:
        decimal_separator = "," if normalized.rfind(",") > normalized.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        normalized = normalized.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError as error:
        raise TabularImportError("Anschaffungskosten sind keine gültige Zahl.") from error


def _find_device_by_serial(connection: sqlite3.Connection, serial_number: str | None):
    if not serial_number:
        return None
    return connection.execute("SELECT id FROM devices WHERE serial_number = ?", (serial_number,)).fetchone()


def _find_asset_by_invoice(connection: sqlite3.Connection, invoice_number: str | None):
    if not invoice_number:
        return None
    return connection.execute("SELECT id FROM assets WHERE invoice_number = ?", (invoice_number,)).fetchone()
