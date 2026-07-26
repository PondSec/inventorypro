"""Append-only activity-log writing helpers."""

from __future__ import annotations

import json
from typing import Any


AUDIT_OUTCOMES = frozenset({"success", "failure", "denied"})


def serialize_activity_details(details: Any) -> str:
    """Serialize structured audit details with the established JSON contract."""
    return json.dumps(details or {})


def normalize_activity_outcome(action: str, outcome: str | None = None) -> str:
    """Return a supported outcome while preserving established failure actions."""
    if outcome is None:
        return "failure" if action.endswith("_failed") else "success"
    normalized = str(outcome).strip().lower()
    if normalized not in AUDIT_OUTCOMES:
        raise ValueError("Ungültiger Audit-Ergebnisstatus.")
    return normalized


def record_activity(
    db: Any,
    username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Any = None,
    request_id: str | None = None,
    outcome: str | None = None,
) -> None:
    """Append one activity event without committing the surrounding transaction."""
    db.execute(
        """
        INSERT INTO activity_log (
            username, action, entity_type, entity_id, details, request_id, outcome
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            action,
            entity_type,
            entity_id,
            serialize_activity_details(details),
            request_id,
            normalize_activity_outcome(action, outcome),
        ),
    )
