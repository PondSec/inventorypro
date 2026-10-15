"""SQLite persistence operations for locations."""

from __future__ import annotations

import sqlite3
from inventorypro.domains.inventory.assets import unified

from .validators import LocationInput


class LocationRepository:
    """Keep location SQL isolated from HTTP and business decisions."""

    def list_all(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute("SELECT * FROM locations ORDER BY name").fetchall()

    def create(self, connection: sqlite3.Connection, location: LocationInput) -> None:
        connection.execute(
            "INSERT INTO locations (name, description) VALUES (?, ?)",
            (location.name, location.description),
        )

    def update(
        self,
        connection: sqlite3.Connection,
        location_id: int,
        location: LocationInput,
    ) -> bool:
        result = connection.execute(
            "UPDATE locations SET name = ?, description = ? WHERE id = ?",
            (location.name, location.description, location_id),
        )
        return result.rowcount > 0

    def find(self, connection: sqlite3.Connection, location_id: int) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT id, name FROM locations WHERE id = ?", (location_id,)
        ).fetchone()

    def reference_counts(
        self,
        connection: sqlite3.Connection,
        location_id: int,
    ) -> tuple[int, int]:
        # Converted devices are already represented in assets. Count each
        # physical record once, including newly created canonical assets.
        table = 'assets' if unified(connection) else 'devices'
        device_count = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE location_id = ?", (location_id,)
        ).fetchone()[0]
        assignment_count = connection.execute(
            "SELECT COUNT(*) FROM asset_assignments WHERE location_id = ?",
            (location_id,),
        ).fetchone()[0]
        return device_count, assignment_count

    def delete(self, connection: sqlite3.Connection, location_id: int) -> bool:
        return connection.execute(
            "DELETE FROM locations WHERE id = ?", (location_id,)
        ).rowcount > 0
