"""Transactional, checksummed SQLite schema migrations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3


class MigrationError(RuntimeError):
    """Raised when migration state is invalid or a migration cannot be applied."""


@dataclass(frozen=True)
class Migration:
    """An immutable migration file and its content checksum."""

    identifier: str
    path: Path
    checksum: str
    rollback_path: Path | None


_TRANSACTION_CONTROL_PATTERN = re.compile(
    r"^\s*(?:BEGIN(?:\s+\w+)?|COMMIT|END|ROLLBACK(?:\s+TO(?:\s+SAVEPOINT)?\s+\w+)?)\s*;?\s*$",
    re.IGNORECASE,
)
_SQL_COMMENT_PATTERN = re.compile(r"--[^\n]*(?:\n|$)|/\*.*?\*/", re.DOTALL)


def discover_migrations(directory: Path) -> list[Migration]:
    """Return migrations in their canonical, numeric filename order."""
    if not directory.is_dir():
        raise MigrationError(f"Migrationsverzeichnis fehlt: {directory}")
    migrations = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        if path.name.endswith(".down.sql"):
            continue
        content = path.read_bytes()
        rollback_path = path.with_suffix(".down.sql")
        migrations.append(
            Migration(
                path.stem,
                path,
                hashlib.sha256(content).hexdigest(),
                rollback_path if rollback_path.is_file() else None,
            )
        )
    return migrations


def ensure_migration_table(connection: sqlite3.Connection) -> None:
    """Create the migration ledger inside the caller's transaction."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_id TEXT NOT NULL,
            checksum TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('applied', 'rolled_back')),
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def execute_migration_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute complete SQL statements without breaking the outer transaction.

    ``sqlite3.Connection.executescript`` commits any pending transaction before
    execution.  Splitting on SQLite's own ``complete_statement`` parser keeps a
    migration and its ledger entry in one transaction instead.
    """
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if not sqlite3.complete_statement(statement):
            continue
        statement_without_comments = _SQL_COMMENT_PATTERN.sub("", statement).strip()
        if _TRANSACTION_CONTROL_PATTERN.match(statement_without_comments):
            raise MigrationError(
                "Migrationen dürfen keine eigenen Transaktionsbefehle enthalten."
            )
        connection.execute(statement)
        statement = ""
    if statement.strip():
        raise MigrationError("Migration enthält ein unvollständiges SQL-Statement.")


def _applied_migrations(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        row[0]: row[1]
        for row in connection.execute("SELECT id, checksum FROM schema_migrations")
    }


def _validate_ledger(migrations: list[Migration], applied: dict[str, str]) -> None:
    discovered = {migration.identifier: migration for migration in migrations}
    for identifier, checksum in applied.items():
        migration = discovered.get(identifier)
        if migration is None:
            raise MigrationError(
                f"Angewendete Migration {identifier} fehlt im Migrationsverzeichnis."
            )
        if migration.checksum != checksum:
            raise MigrationError(
                f"Migration {identifier} wurde nach der Anwendung verändert."
            )


def apply_migrations(connection: sqlite3.Connection, directory: Path) -> list[str]:
    """Apply all pending migrations atomically and record their checksums.

    When called from an existing transaction the work is isolated by a
    savepoint.  Otherwise an immediate transaction serializes concurrent
    application starts and protects both schema changes and ledger updates.
    """
    migrations = discover_migrations(directory)
    savepoint_name = "inventorypro_migrations"
    nested_transaction = connection.in_transaction
    savepoint_started = False
    try:
        if nested_transaction:
            connection.execute(f"SAVEPOINT {savepoint_name}")
            savepoint_started = True
        else:
            connection.execute("BEGIN IMMEDIATE")

        ensure_migration_table(connection)
        applied = _applied_migrations(connection)
        _validate_ledger(migrations, applied)

        newly_applied = []
        for migration in migrations:
            if migration.identifier in applied:
                continue
            execute_migration_script(connection, migration.path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (id, checksum) VALUES (?, ?)",
                (migration.identifier, migration.checksum),
            )
            connection.execute(
                "INSERT INTO schema_migration_events (migration_id, checksum, action) VALUES (?, ?, 'applied')",
                (migration.identifier, migration.checksum),
            )
            newly_applied.append(migration.identifier)

        if savepoint_started:
            connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        else:
            connection.commit()
        return newly_applied
    except (OSError, sqlite3.Error, MigrationError) as error:
        if savepoint_started:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        else:
            connection.rollback()
        if isinstance(error, MigrationError):
            raise
        raise MigrationError("Migration konnte nicht atomar angewendet werden.") from error


def rollback_migrations(connection: sqlite3.Connection, directory: Path, *, steps: int = 1) -> list[str]:
    """Roll back the most recently applied migrations using checked down scripts."""
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise MigrationError("Die Anzahl zurückzunehmender Migrationen muss mindestens eins sein.")
    migrations = discover_migrations(directory)
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone():
        return []
    savepoint_name = "inventorypro_migration_rollback"
    nested_transaction = connection.in_transaction
    savepoint_started = False
    try:
        if nested_transaction:
            connection.execute(f"SAVEPOINT {savepoint_name}")
            savepoint_started = True
        else:
            connection.execute("BEGIN IMMEDIATE")

        ensure_migration_table(connection)
        applied = _applied_migrations(connection)
        _validate_ledger(migrations, applied)
        selected = [migration for migration in reversed(migrations) if migration.identifier in applied][:steps]
        if len(selected) < steps:
            raise MigrationError("Es sind nicht genügend angewendete Migrationen für einen Rückwärtslauf vorhanden.")
        missing_rollback = next((migration for migration in selected if migration.rollback_path is None), None)
        if missing_rollback:
            raise MigrationError(
                f"Für Migration {missing_rollback.identifier} fehlt eine Rückwärtsmigration."
            )

        rolled_back = []
        for migration in selected:
            execute_migration_script(connection, migration.rollback_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migration_events (migration_id, checksum, action) VALUES (?, ?, 'rolled_back')",
                (migration.identifier, migration.checksum),
            )
            connection.execute("DELETE FROM schema_migrations WHERE id = ?", (migration.identifier,))
            rolled_back.append(migration.identifier)

        if savepoint_started:
            connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        else:
            connection.commit()
        return rolled_back
    except (OSError, sqlite3.Error, MigrationError) as error:
        if savepoint_started:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        else:
            connection.rollback()
        if isinstance(error, MigrationError):
            raise
        raise MigrationError("Rückwärtsmigration konnte nicht atomar angewendet werden.") from error
