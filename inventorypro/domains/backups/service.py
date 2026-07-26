"""Application service for manual backup operations."""

from __future__ import annotations

from collections.abc import Callable
import sqlite3
from typing import Any, Mapping

from .repository import BackupRunRepository


class BackupService:
    """Coordinates settings lookup, backup execution, and run history."""

    def __init__(
        self,
        repository: BackupRunRepository,
        load_settings: Callable[[sqlite3.Connection], Mapping[str, Any]],
        run_backup_job: Callable[[sqlite3.Connection, Mapping[str, Any], bool], dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._load_settings = load_settings
        self._run_backup_job = run_backup_job

    def run(self, connection: sqlite3.Connection, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        force = bool((payload or {}).get("force"))
        return self._run_backup_job(connection, self._load_settings(connection), force)

    def list_recent(self, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        return self._repository.list_recent(connection)
