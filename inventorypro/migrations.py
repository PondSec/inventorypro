"""Small, dependency-free SQLite migration runner for incremental adoption."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3


class MigrationError(RuntimeError):
    """Raised when migration state is invalid or a migration cannot be applied."""


@dataclass(frozen=True)
class Migration:
    identifier: str
    path: Path
    checksum: str


def discover_migrations(directory: Path) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        content = path.read_bytes()
        migrations.append(Migration(path.stem, path, hashlib.sha256(content).hexdigest()))
    return migrations


def ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def apply_migrations(connection: sqlite3.Connection, directory: Path) -> list[str]:
    ensure_migration_table(connection)
    applied = {
        row["id"] if isinstance(row, sqlite3.Row) else row[0]: row["checksum"] if isinstance(row, sqlite3.Row) else row[1]
        for row in connection.execute("SELECT id, checksum FROM schema_migrations")
    }
    newly_applied = []
    for migration in discover_migrations(directory):
        existing_checksum = applied.get(migration.identifier)
        if existing_checksum:
            if existing_checksum != migration.checksum:
                raise MigrationError(
                    f"Migration {migration.identifier} wurde nach der Anwendung verändert."
                )
            continue
        try:
            connection.executescript(migration.path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (id, checksum) VALUES (?, ?)",
                (migration.identifier, migration.checksum),
            )
            connection.commit()
            newly_applied.append(migration.identifier)
        except sqlite3.Error as error:
            connection.rollback()
            raise MigrationError(f"Migration {migration.identifier} fehlgeschlagen.") from error
    return newly_applied
