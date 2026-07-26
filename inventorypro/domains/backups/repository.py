"""Persistence queries for backup execution history."""

from __future__ import annotations

import sqlite3
from typing import Any


class BackupRunRepository:
    """Read backup run history without leaking SQL into HTTP handlers."""

    def list_recent(self, connection: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT id, status, backup_path, backup_size_bytes, message, created_at
            FROM backup_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "status": row["status"],
                "path": row["backup_path"],
                "sizeBytes": row["backup_size_bytes"],
                "message": row["message"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
