"""Persistence access for reusable inventory import profiles."""

from __future__ import annotations

from typing import Any


class ImportProfileRepository:
    """Keep all import-profile SQL in one narrow repository."""

    def list(self, connection: Any, entity: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM import_profiles"
        parameters: tuple[Any, ...] = ()
        if entity:
            query += " WHERE entity = ?"
            parameters = (entity,)
        query += " ORDER BY name COLLATE NOCASE, id"
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def get(self, connection: Any, profile_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM import_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        return dict(row) if row else None

    def create(self, connection: Any, profile: dict[str, Any], actor: str) -> dict[str, Any]:
        cursor = connection.execute(
            """
            INSERT INTO import_profiles (name, entity, mapping_json, matching_key, sheet_name, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                profile["name"],
                profile["entity"],
                profile["mappingJson"],
                profile["matchingKey"],
                profile["sheetName"],
                actor,
            ),
        )
        return self.get(connection, cursor.lastrowid)  # type: ignore[arg-type]

    def update(self, connection: Any, profile_id: int, profile: dict[str, Any]) -> dict[str, Any] | None:
        connection.execute(
            """
            UPDATE import_profiles
            SET name = ?, entity = ?, mapping_json = ?, matching_key = ?, sheet_name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                profile["name"],
                profile["entity"],
                profile["mappingJson"],
                profile["matchingKey"],
                profile["sheetName"],
                profile_id,
            ),
        )
        return self.get(connection, profile_id)

    def delete(self, connection: Any, profile_id: int) -> bool:
        cursor = connection.execute("DELETE FROM import_profiles WHERE id = ?", (profile_id,))
        return cursor.rowcount == 1
