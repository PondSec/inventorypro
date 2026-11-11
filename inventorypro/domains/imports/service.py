"""Validation and preview-proof services for inventory data migrations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from .repository import ImportProfileRepository


class ImportProfileValidationError(ValueError):
    """Raised when an import profile or proof is invalid for user input."""


_ENTITIES = {"devices", "assets"}
_MATCHING_KEYS = {
    "devices": {"serial_number", "name"},
    "assets": {"invoice_number", "name"},
}


def parse_mapping(value: Any) -> dict[str, str | None] | None:
    """Read a mapping from JSON/form input without trusting its shape."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ImportProfileValidationError("Die Feldzuordnung ist kein gültiges JSON-Objekt.") from error
    if not isinstance(value, Mapping):
        raise ImportProfileValidationError("Die Feldzuordnung muss ein Objekt sein.")
    mapping: dict[str, str | None] = {}
    for target, source in value.items():
        if not isinstance(target, str) or not target.strip():
            raise ImportProfileValidationError("Die Feldzuordnung enthält ein ungültiges Zielfeld.")
        if source is not None and (not isinstance(source, str) or not source.strip()):
            raise ImportProfileValidationError("Eine Quellspalte muss Text oder leer sein.")
        mapping[target.strip()] = source.strip() if isinstance(source, str) else None
    return mapping


def parse_profile_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        profile_id = int(value)
    except (TypeError, ValueError) as error:
        raise ImportProfileValidationError("Die Importprofil-ID ist ungültig.") from error
    if profile_id < 1:
        raise ImportProfileValidationError("Die Importprofil-ID ist ungültig.")
    return profile_id


class ImportProfileService:
    """Provide validated profile CRUD and profile resolution."""

    def __init__(self, repository: ImportProfileRepository | None = None):
        self.repository = repository or ImportProfileRepository()

    def _serialize(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "entity": row["entity"],
            "mapping": parse_mapping(row["mapping_json"]) or {},
            "matchingKey": row["matching_key"],
            "sheetName": row["sheet_name"],
            "createdBy": row["created_by"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _validate_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        entity = str(payload.get("entity") or "").strip().lower()
        matching_key = payload.get("matchingKey") or None
        sheet_name = payload.get("sheetName") or None
        if not 1 <= len(name) <= 100:
            raise ImportProfileValidationError("Der Profilname muss zwischen 1 und 100 Zeichen lang sein.")
        if entity not in _ENTITIES:
            raise ImportProfileValidationError("Das Importprofil benötigt Geräte oder Assets als Datentyp.")
        if matching_key is not None and matching_key not in _MATCHING_KEYS[entity]:
            raise ImportProfileValidationError("Der Abgleichschlüssel ist für diesen Datentyp nicht zulässig.")
        if sheet_name is not None and (not isinstance(sheet_name, str) or len(sheet_name.strip()) > 100):
            raise ImportProfileValidationError("Der Tabellenblattname ist ungültig.")
        mapping = parse_mapping(payload.get("mapping")) or {}
        return {
            "name": name,
            "entity": entity,
            "mappingJson": json.dumps(mapping, ensure_ascii=False, sort_keys=True),
            "matchingKey": matching_key,
            "sheetName": sheet_name.strip() if isinstance(sheet_name, str) else None,
        }

    def list(self, connection: Any, entity: str | None = None) -> list[dict[str, Any]]:
        if entity and entity not in _ENTITIES:
            raise ImportProfileValidationError("Der Datentyp ist ungültig.")
        return [self._serialize(row) for row in self.repository.list(connection, entity)]

    def get(self, connection: Any, profile_id: int) -> dict[str, Any] | None:
        row = self.repository.get(connection, profile_id)
        return self._serialize(row) if row else None

    def create(self, connection: Any, payload: Mapping[str, Any], actor: str) -> dict[str, Any]:
        profile = self._validate_payload(payload)
        try:
            with connection:
                row = self.repository.create(connection, profile, actor)
        except Exception as error:
            if "UNIQUE constraint failed: import_profiles.name" in str(error):
                raise ImportProfileValidationError("Ein Importprofil mit diesem Namen existiert bereits.") from error
            raise
        return self._serialize(row)

    def update(self, connection: Any, profile_id: int, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        profile = self._validate_payload(payload)
        try:
            with connection:
                row = self.repository.update(connection, profile_id, profile)
        except Exception as error:
            if "UNIQUE constraint failed: import_profiles.name" in str(error):
                raise ImportProfileValidationError("Ein Importprofil mit diesem Namen existiert bereits.") from error
            raise
        return self._serialize(row) if row else None

    def delete(self, connection: Any, profile_id: int) -> bool:
        with connection:
            return self.repository.delete(connection, profile_id)

    def resolve(self, connection: Any, profile_id: int | None, entity: str) -> dict[str, Any]:
        if profile_id is None:
            return {"mapping": None, "matchingKey": None, "sheetName": None, "profileId": None}
        profile = self.get(connection, profile_id)
        if not profile or profile["entity"] != entity:
            raise ImportProfileValidationError("Das Importprofil ist für diesen Datentyp nicht verfügbar.")
        return {
            "mapping": profile["mapping"] or None,
            "matchingKey": profile["matchingKey"],
            "sheetName": profile["sheetName"],
            "profileId": profile["id"],
        }


def resolve_tabular_import_options(
    connection: Any,
    form: Mapping[str, Any],
    entity: str,
    profile_service: ImportProfileService,
) -> dict[str, Any]:
    """Combine explicit form values with an optional reusable import profile."""
    profile_id = parse_profile_id(form.get("profileId"))
    profile_options = profile_service.resolve(connection, profile_id, entity)
    mapping = parse_mapping(form.get("mapping")) if form.get("mapping") is not None else profile_options["mapping"]
    return {
        "mapping": mapping,
        "matchingKey": form.get("matchingKey") or profile_options["matchingKey"] or None,
        "sheetName": form.get("sheetName") or profile_options["sheetName"] or None,
        "profileId": profile_options["profileId"],
    }


def build_preview_proof_arguments(
    content: bytes,
    filename: str,
    entity: str,
    options: Mapping[str, Any],
    actor: str,
) -> dict[str, Any]:
    """Build the exact option set that must match a later import request."""
    return {
        "content": content,
        "filename": filename,
        "entity": entity,
        "mapping": options["mapping"],
        "matching_key": options["matchingKey"],
        "sheet_name": options["sheetName"],
        "actor": actor,
    }


class ImportPreviewProofService:
    """Bind a tabular import to its validated preview and initiating user."""

    _SALT = "inventorypro.import-preview-proof"
    _MAX_AGE_SECONDS = 15 * 60

    def __init__(self, secret_key: str):
        self.serializer = URLSafeTimedSerializer(secret_key, salt=self._SALT)

    @staticmethod
    def _payload(
        *,
        content: bytes,
        filename: str,
        entity: str,
        mapping: Mapping[str, str | None] | None,
        matching_key: str | None,
        sheet_name: str | None,
        actor: str,
    ) -> dict[str, Any]:
        return {
            "contentSha256": hashlib.sha256(content).hexdigest(),
            "filename": filename,
            "entity": entity,
            "mapping": mapping or {},
            "matchingKey": matching_key,
            "sheetName": sheet_name,
            "actor": actor,
        }

    def issue(self, **kwargs: Any) -> str:
        return self.serializer.dumps(self._payload(**kwargs))

    def verify(self, token: str | None, **kwargs: Any) -> None:
        if not token:
            raise ImportProfileValidationError("Vor dem Import muss eine aktuelle Vorschau erstellt werden.")
        try:
            expected = self._payload(**kwargs)
            actual = self.serializer.loads(token, max_age=self._MAX_AGE_SECONDS)
        except SignatureExpired as error:
            raise ImportProfileValidationError("Die Importvorschau ist abgelaufen. Bitte erneut prüfen.") from error
        except BadData as error:
            raise ImportProfileValidationError("Der Vorschau-Nachweis ist ungültig.") from error
        if actual != expected:
            raise ImportProfileValidationError("Datei oder Importoptionen weichen von der geprüften Vorschau ab.")
