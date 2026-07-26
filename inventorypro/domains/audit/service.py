"""Append-only activity-log writing helpers."""

from __future__ import annotations

import json
from typing import Any


def serialize_activity_details(details: Any) -> str:
    """Serialize structured audit details with the established JSON contract."""
    return json.dumps(details or {})


def record_activity(
    db: Any,
    username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Any = None,
) -> None:
    """Append one activity event without committing the surrounding transaction."""
    db.execute(
        """
        INSERT INTO activity_log (username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, action, entity_type, entity_id, serialize_activity_details(details)),
    )
