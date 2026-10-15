"""Validation for location commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class LocationValidationError(ValueError):
    """Raised when a location command is incomplete or malformed."""


@dataclass(frozen=True)
class LocationInput:
    """Normalized, storage-ready location attributes."""

    name: str
    description: str


def validate_location_input(payload: Mapping[str, Any] | None) -> LocationInput:
    """Normalize a location command while preserving the legacy error text."""
    payload = payload or {}
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not name:
        raise LocationValidationError("Name ist erforderlich")
    return LocationInput(name=name, description=description)
