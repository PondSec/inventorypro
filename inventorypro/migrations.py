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
        content = path.read_bytes()
        migrations.append(Migration(path.stem, path, hashlib.sha256(content).hexdigest()))
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
