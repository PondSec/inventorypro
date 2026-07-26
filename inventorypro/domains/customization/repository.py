"""Persistence helpers for instance-wide customization revisions."""

from __future__ import annotations

import json
from typing import Any

from .service import compute_customization_diff


INSTANCE_CUSTOMIZATION_WORKSPACE_ID = 0


def get_customization_record(database: Any, user_id: int, workspace_id: int | None = None) -> Any:
    if workspace_id is None:
        record = database.execute(
            "SELECT * FROM ui_customization WHERE workspace_id = ? ORDER BY id LIMIT 1",
            (INSTANCE_CUSTOMIZATION_WORKSPACE_ID,),
        ).fetchone()
        if record:
            return record
        return database.execute(
            "SELECT * FROM ui_customization WHERE workspace_id IS NULL ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()
    return database.execute(
        "SELECT * FROM ui_customization WHERE user_id = ? AND workspace_id = ?",
        (user_id, workspace_id),
    ).fetchone()


def save_customization(
    database: Any,
    user_id: int,
    customization: dict[str, Any],
    updated_by: str,
    workspace_id: int | None = None,
) -> int:
    existing = get_customization_record(database, user_id, workspace_id)
    serialized = json.dumps(customization)
    if existing:
        database.execute(
            """
            UPDATE ui_customization
            SET workspace_id = ?, customization_json = ?, schema_version = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = ?
            """,
            (INSTANCE_CUSTOMIZATION_WORKSPACE_ID, serialized, customization["schemaVersion"], updated_by, existing["id"]),
        )
        customization_id = existing["id"]
    else:
        database.execute(
            """
            INSERT INTO ui_customization (user_id, workspace_id, schema_version, customization_json, updated_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, INSTANCE_CUSTOMIZATION_WORKSPACE_ID, customization["schemaVersion"], serialized, updated_by),
        )
        customization_id = database.execute("SELECT last_insert_rowid()").fetchone()[0]
    diff = compute_customization_diff(json.loads(existing["customization_json"]), customization) if existing else []
    database.execute(
        """
        INSERT INTO ui_customization_revisions (customization_id, revision_json, diff_json, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (customization_id, serialized, json.dumps(diff), updated_by),
    )
    database.commit()
    return customization_id
