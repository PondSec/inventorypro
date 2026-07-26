"""Persistence helpers for inventory-link records."""

from __future__ import annotations

from typing import Any

from inventorypro.time import utc_now


def serialize_inventory_link(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "displayName": row["display_name"],
        "baseUrl": row["base_url"],
        "verifyTls": bool(row["verify_tls"]),
        "authMode": row["auth_mode"],
        "allowPrivateNetwork": bool(row["allow_private_network"]),
        "connectionScope": row["connection_scope"] or "internet",
        "healthStatus": row["health_status"],
        "lastCheckedAt": row["health_last_checked_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_inventory_links(database: Any, user_id: int) -> list[dict[str, Any]]:
    rows = database.execute(
        """
        SELECT id, display_name, base_url, verify_tls, auth_mode, allow_private_network, connection_scope,
               health_status, health_last_checked_at, created_at, updated_at
        FROM inventory_links
        WHERE user_id = ?
        ORDER BY display_name
        """,
        (user_id,),
    ).fetchall()
    return [serialize_inventory_link(row) for row in rows]


def get_inventory_link(database: Any, user_id: int, link_id: str) -> Any:
    return database.execute(
        """
        SELECT *
        FROM inventory_links
        WHERE id = ? AND user_id = ?
        """,
        (link_id, user_id),
    ).fetchone()


def update_inventory_link_health(database: Any, link_id: str, status: str) -> None:
    database.execute(
        """
        UPDATE inventory_links
        SET health_status = ?, health_last_checked_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, utc_now().isoformat(), link_id),
    )
