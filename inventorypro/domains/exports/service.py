"""Safe serialization helpers for spreadsheet-oriented inventory exports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any


_FORMULA_PREFIXES = ("=", "+", "-", "@")


def protect_spreadsheet_value(value: Any) -> Any:
    """Prefix formula-like text so spreadsheet applications keep it as text."""
    if not isinstance(value, str):
        return value
    if value.lstrip(" \t\r\n")[:1] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


def protect_spreadsheet_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy suitable for CSV and XLSX writers."""
    return {key: protect_spreadsheet_value(value) for key, value in record.items()}


def protect_spreadsheet_row(values: Iterable[Any]) -> list[Any]:
    """Return a row suitable for CSV and XLSX writers."""
    return [protect_spreadsheet_value(value) for value in values]


def build_export_metadata(export_format: str, tables: Iterable[str]) -> dict[str, Any]:
    """Create portable, non-sensitive export provenance metadata."""
    exported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "exportedAt": exported_at,
        "format": export_format,
        "tables": list(tables),
    }
